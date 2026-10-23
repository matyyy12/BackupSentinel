import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from verification_app.models import VerificationResultOutbox
from verification_app.schemas import VerificationResponse


class VerificationResultOutboxRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, verification_id: uuid.UUID) -> VerificationResultOutbox | None:
        return await self.session.get(VerificationResultOutbox, verification_id)

    async def add(self, result: VerificationResponse) -> bool:
        statement = (
            insert(VerificationResultOutbox)
            .values(
                verification_id=result.verification_id,
                backup_id=result.backup_id,
                payload=result.model_dump(mode="json"),
            )
            .on_conflict_do_nothing(index_elements=[VerificationResultOutbox.verification_id])
            .returning(VerificationResultOutbox.verification_id)
        )
        return await self.session.scalar(statement) is not None

    async def get_pending(self, limit: int = 10) -> list[VerificationResultOutbox]:
        statement = (
            select(VerificationResultOutbox)
            .where(VerificationResultOutbox.sent_at.is_(None))
            .order_by(VerificationResultOutbox.created_at, VerificationResultOutbox.verification_id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list((await self.session.scalars(statement)).all())
