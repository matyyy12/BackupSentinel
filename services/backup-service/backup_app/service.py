import uuid
import logging

from fastapi import UploadFile
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import FileResponse

from backup_app.exceptions import NotFoundError, ConflictError
from backup_app.models import Backup, BackupResult, Outbox, Verification, Status
from backup_app.repository import BackupRepository, BackupResultRepository, OutboxRepository, VerificationRepository
from backup_app.schemas import BackupResponse, VerificationResult, VerificationResponse
from backup_app.storage import (
    save_file, delete_file, download_file,
    stage_file_deletion, restore_staged_file, remove_staged_file,
)

logger = logging.getLogger(__name__)


class BackupService:
    def __init__(self, repository: BackupRepository,
                 results_repository: BackupResultRepository,
                 outbox_repository: OutboxRepository,
                 verification_repository: VerificationRepository):
        self.repository: BackupRepository = repository
        self.results_repository: BackupResultRepository = results_repository
        self.outbox_repository: OutboxRepository = outbox_repository
        self.verification_repository = verification_repository

    async def upload_file(self, file: UploadFile, postgres_version: str) -> BackupResponse:
        backup_id = uuid.uuid4()
        storage_key = f"{backup_id}.dump"
        backup = Backup(id=backup_id,
                        filename=file.filename,
                        size=file.size,
                        storage_key=storage_key,
                        postgres_version=postgres_version)
        try:
            await save_file(file, storage_key)
            await self.repository.upload_file(backup)
            await self._queue_verification(backup)
            await self.repository.commit()
        except SQLAlchemyError:
            try:
                await self.repository.rollback()
            finally:
                await delete_file(storage_key)
            raise
        return BackupResponse.model_validate(backup)

    async def _queue_verification(self, backup: Backup) -> Verification:
        verification = Verification(id=uuid.uuid4(), backup_id=backup.id, status=Status.QUEUED)
        await self.verification_repository.add(verification)
        await self.outbox_repository.add_outbox(Outbox(
            backup_id=backup.id, task_name="verification_restore",
            payload={"verification_id": str(verification.id), "backup_id": str(backup.id),
                     "storage_key": backup.storage_key, "postgres_version": backup.postgres_version},
        ))
        backup.status = Status.QUEUED
        return verification

    async def request_verification(self, backup_id: uuid.UUID) -> VerificationResponse:
        try:
            backup = await self.repository.get_backup_for_update(backup_id)
            if backup is None:
                raise NotFoundError("Backup not found")
            if await self.verification_repository.get_active(backup_id) is not None:
                raise ConflictError("Backup already has an active verification")
            verification = await self._queue_verification(backup)
            await self.repository.commit()
        except Exception:
            await self.repository.rollback()
            raise
        return VerificationResponse.model_validate(verification)

    async def get_verifications(self, backup_id: uuid.UUID | None = None) -> list[VerificationResponse]:
        if backup_id is not None and await self.repository.get_backup(backup_id) is None:
            raise NotFoundError("Backup not found")
        attempts = await self.verification_repository.get_all(backup_id)
        return [VerificationResponse.model_validate(attempt) for attempt in attempts]

    async def download_backup(self, backup_id: uuid.UUID) -> FileResponse:
        backup = await self.repository.get_backup(backup_id)
        if backup is None:
            raise NotFoundError("Backup not found")
        file_response = await download_file(backup.storage_key, backup.filename)
        return file_response

    async def delete_backup(self, backup_id: uuid.UUID) -> None:
        deletion = None
        try:
            backup = await self.repository.get_backup_for_update(backup_id)
            if backup is None:
                raise NotFoundError("Backup not found")
            if await self.verification_repository.get_active(backup_id) is not None:
                raise ConflictError("Cannot delete backup with an active verification")
            deletion = await stage_file_deletion(backup.storage_key)
            await self.repository.delete(backup_id)
            await self.repository.commit()
        except BaseException:
            try:
                await self.repository.rollback()
            finally:
                if deletion is not None:
                    await restore_staged_file(deletion)
            raise
        if deletion is not None:
            try:
                await remove_staged_file(deletion)
            except OSError:
                logger.exception("Backup %s deleted; staged file needs cleanup: %s", backup_id, deletion.staged)

    async def get_backups(self) -> list[BackupResponse]:
        backups = await self.repository.get_backups()
        return [BackupResponse.model_validate(backup) for backup in backups]

    async def get_backup(self, backup_id: uuid.UUID) -> BackupResponse:
        backup = await self.repository.get_backup(backup_id)
        if backup is None:
            raise NotFoundError("Backup not found")
        return BackupResponse.model_validate(backup)

    async def save_backup_status(self, request: VerificationResult) -> BackupResponse:
        backup = await self.repository.get_backup_for_update(request.backup_id)
        if backup is None:
            raise NotFoundError("Backup not found")
        verification = await self.verification_repository.get(request.verification_id)
        if verification is None or verification.backup_id != backup.id:
            raise NotFoundError("Verification not found for this backup")
        if request.status not in (Status.VERIFIED, Status.FAILED):
            raise ValueError("A verification result must have a terminal status")
        result = BackupResult(verification_id=request.verification_id,
                              status=request.status,
                              backup_id=backup.id,
                              started_at=request.started_at,
                              finished_at=request.finished_at,
                              error_message=request.error_message,
                              )
        try:
            inserted = await self.results_repository.add_result(result)
            if inserted:
                verification.status = request.status
                attempts = await self.verification_repository.get_all(backup.id)
                if attempts[0].id == verification.id:
                    backup.status = request.status
            await self.results_repository.commit()
        except SQLAlchemyError:
            await self.results_repository.rollback()
            raise
        return BackupResponse.model_validate(backup)

    async def get_backup_status(self, backup_id: uuid.UUID) -> VerificationResult:
        result = await self.results_repository.get_result(backup_id)
        if result is None:
            raise NotFoundError("Result not found")
        return VerificationResult.model_validate(result)

    async def get_results(self) -> list[VerificationResult]:
        statuses = await self.results_repository.get_results()
        return [VerificationResult.model_validate(status) for status in statuses]
