from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.repository import BackupRepository
from database import get_session
from app.service import BackupService


def get_service(
        session: Annotated[AsyncSession,Depends(get_session)]) -> BackupService:
    return BackupService(BackupRepository(session))
