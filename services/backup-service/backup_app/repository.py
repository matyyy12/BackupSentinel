import uuid

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backup_app.models import Backup
from backup_app.schemas import BackupResponse


class BackupRepository:
    def __init__(self, session: AsyncSession):
        self.session: AsyncSession = session

    async def upload_file(self, backup: Backup) -> None:
        self.session.add(backup)
        await self.session.flush()

    async def get_backups(self) -> list[Backup]:
        result = await self.session.scalars(select(Backup))
        return list(result.unique().all())

    async def get_backup(self, backup_id: uuid.UUID) -> Backup | None:
        return await self.session.scalar(select(Backup).where(Backup.id == backup_id))

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()