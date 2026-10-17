import uuid

from fastapi import UploadFile, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from backup_app.celery_app import app
from backup_app.models import Backup, BackupResult, Outbox
from backup_app.repository import BackupRepository, BackupResultRepository, OutboxRepository
from backup_app.schemas import BackupResponse, VerificationResult
from backup_app.storage import save_file, delete_file


class BackupService:
    def __init__(self, repository: BackupRepository,
                 results_repository: BackupResultRepository,
                 outbox_repository: OutboxRepository):
        self.repository: BackupRepository = repository
        self.results_repository: BackupResultRepository = results_repository
        self.outbox_repository: OutboxRepository = outbox_repository

    async def upload_file(self, file: UploadFile, postgres_version: str) -> BackupResponse:
        backup_id = uuid.uuid4()
        storage_key = f"{backup_id}.dump"
        backup = Backup(id=backup_id,
                        filename=file.filename,
                        size=file.size,
                        storage_key=storage_key,
                        postgres_version=postgres_version)
        outbox = Outbox(backup_id=backup_id,
                        task_name="verification_restore",
                        payload={
                            "verification_id": str(uuid.uuid4()),
                            "backup_id": str(backup_id),
                            "storage_key": storage_key,
                            "postgres_version": postgres_version,
                        })
        try:
            await save_file(file, storage_key)
            await self.repository.upload_file(backup)
            await self.outbox_repository.add_outbox(outbox)
            await self.repository.commit()
        except SQLAlchemyError:
            try:
                await self.repository.rollback()
            finally:
                await delete_file(storage_key)
            raise
        return BackupResponse.model_validate(backup)

    async def get_backups(self) -> list[BackupResponse]:
        backups = await self.repository.get_backups()
        return [BackupResponse.model_validate(backup) for backup in backups]

    async def get_backup(self, backup_id: uuid.UUID) -> BackupResponse:
        backup = await self.repository.get_backup(backup_id)
        if backup is None:
            raise HTTPException(status_code=404, detail="Backup not found")
        return BackupResponse.model_validate(backup)

    async def save_backup_status(self, request: VerificationResult) -> BackupResponse:
        backup = await self.repository.get_backup_for_update(request.backup_id)
        if backup is None:
            raise ValueError("Backup not found")
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
                backup.status=request.status
            await self.results_repository.commit()
        except SQLAlchemyError:
            await self.results_repository.rollback()
            raise
        return BackupResponse.model_validate(backup)

    async def get_backup_status(self, backup_id: uuid.UUID) -> VerificationResult:
        result = await self.results_repository.get_result(backup_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Result not found")
        return VerificationResult.model_validate(result)

    async def get_results(self) -> list[VerificationResult]:
        statuses = await self.results_repository.get_results()
        return [VerificationResult.model_validate(status) for status in statuses]
