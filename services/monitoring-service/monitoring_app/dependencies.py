from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from monitoring_app.database import get_session
from monitoring_app.repository import MonitoringRepository
from monitoring_app.service import AlertService


def get_service(session: Annotated[AsyncSession, Depends(get_session)]) -> AlertService:
    return AlertService(MonitoringRepository(session))
