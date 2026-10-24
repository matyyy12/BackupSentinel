from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backup_app.repository import BackupRepository, BackupResultRepository, OutboxRepository, VerificationRepository
from database import get_session
from backup_app.service import BackupService


def get_service(
        session: Annotated[AsyncSession,Depends(get_session)]) -> BackupService:
    return BackupService(BackupRepository(session), BackupResultRepository(session), OutboxRepository(session), VerificationRepository(session))
