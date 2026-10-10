import uuid

from fastapi import UploadFile, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from backup_app.celery_app import app
from backup_app.models import Backup, Status
from backup_app.repository import BackupRepository
from backup_app.schemas import BackupResponse
from backup_app.storage import save_file, delete_file


class BackupService:
    def __init__(self, repository: BackupRepository):
        self.repository: BackupRepository = repository

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
            await self.repository.commit()
        except SQLAlchemyError:
            try:
                await self.repository.rollback()
            finally:
                await delete_file(storage_key)
            raise
        await run_in_threadpool(
            app.send_task,
            "verification_restore",
            kwargs={"backup_id": str(backup_id),
                    "storage_key": storage_key,
                    "postgres_version": postgres_version},
        )
        return BackupResponse.model_validate(backup)

    async def get_backups(self) -> list[BackupResponse]:
        backups = await self.repository.get_backups()
        return [BackupResponse.model_validate(backup) for backup in backups]

    async def get_backup(self, backup_id: uuid.UUID) -> BackupResponse:
        backup = await self.repository.get_backup(backup_id)
        if backup is None:
            raise HTTPException(status_code=404, detail="Backup not found")
        return BackupResponse.model_validate(backup)

    async def update_backup_status(self, backup_id: uuid.UUID, status: Status) -> BackupResponse:
        backup = await self.repository.get_backup_for_update(backup_id)
        if backup is None:
            raise ValueError("Backup not found")
        backup.status = status
        await self.repository.commit()
        return BackupResponse.model_validate(backup)
