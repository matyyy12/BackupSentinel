import uuid

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from monitoring_app.models import Alert


class MonitoringRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, alert: Alert) -> bool:
        statement = (insert(Alert).values(
            backup_id=alert.backup_id,
            verification_id=alert.verification_id,
            type=alert.type,
            message=alert.message,
            resolved_at=alert.resolved_at,
        ).on_conflict_do_nothing(constraint="uq_alerts_verification_type").returning(Alert.id))
        result_id = await self.session.scalar(statement)
        return result_id is not None

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
