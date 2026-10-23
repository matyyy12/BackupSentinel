import uuid

from sqlalchemy import text, select, update, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from monitoring_app.models import Alert, AlertType


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
        ))
        if alert.type == AlertType.VERIFICATION_TIMEOUT:
            statement = statement.on_conflict_do_nothing(
                index_elements=[Alert.backup_id],
                index_where=text(
                    "type = 'VERIFICATION_TIMEOUT' AND resolved_at IS NULL"
                ),
            )
        else:
            statement = statement.on_conflict_do_nothing(
                constraint="uq_alerts_verification_type",
            )

        statement = statement.returning(Alert.id)
        result_id = await self.session.scalar(statement)
        return result_id is not None

    async def get_alerts(self, resolved: bool | None) -> list[Alert]:
        statement = select(Alert)
        if resolved is True:
            statement = statement.where(Alert.resolved_at.isnot(None))
        elif resolved is False:
            statement = statement.where(Alert.resolved_at.is_(None))
        result = await self.session.scalars(statement)
        return list(result.unique().all())

    async def get_alert_by_id(self, alert_id: int) -> Alert | None:
        return await self.session.scalar(select(Alert).where(Alert.id == alert_id))

    async def get_alert_for_update(self, alert_id: int) -> Alert | None:
        return await self.session.scalar(select(Alert).where(Alert.id == alert_id).with_for_update())

    async def resolve_timeout(self, backup_id: uuid.UUID) -> None:
        statement = (
            update(Alert)
            .where(
                Alert.backup_id == backup_id,
                Alert.type == AlertType.VERIFICATION_TIMEOUT,
                Alert.resolved_at.is_(None),
            )
            .values(resolved_at=func.now())
        )
        await self.session.execute(statement)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
