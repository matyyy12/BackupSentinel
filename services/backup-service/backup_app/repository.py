import uuid

from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backup_app.models import Backup, BackupResult, Outbox, Verification, Status


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

    async def get_backup_for_update(self, backup_id: uuid.UUID) -> Backup | None:
        return await self.session.scalar(select(Backup).where(Backup.id == backup_id).with_for_update())

    async def delete(self, backup_id: uuid.UUID) -> None:
        # Database foreign keys cascade to results, attempts and outbox messages.
        await self.session.execute(delete(Backup).where(Backup.id == backup_id))

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

class BackupResultRepository:
    def __init__(self, session: AsyncSession):
        self.session: AsyncSession = session

    async def add_result(self, result: BackupResult) -> bool:
        statement = (insert(BackupResult)
                     .values(
                            verification_id=result.verification_id,
                            backup_id=result.backup_id,
                            status=result.status,
                            started_at=result.started_at,
                            finished_at=result.finished_at,
                            error_message=result.error_message,
                    )
                    .on_conflict_do_nothing(
                            index_elements=[BackupResult.verification_id]
                    )
                    .returning(BackupResult.id)
        )
        result_id = await self.session.scalar(statement)
        return result_id is not None

    async def get_result(self, backup_id: uuid.UUID) -> BackupResult | None:
        return await self.session.scalar(select(BackupResult)
                                         .where(BackupResult.backup_id == backup_id)
                                         .order_by(BackupResult.finished_at.desc(), BackupResult.id.desc())
                                         .limit(1))

    async def get_results(self) -> list[BackupResult]:
        result = await self.session.scalars(select(BackupResult))
        return list(result.all())

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

class OutboxRepository:
    def __init__(self, session: AsyncSession):
        self.session: AsyncSession = session

    async def get_pending(self, limit: int = 10) -> list[Outbox]:
        statement = (select(Outbox).where(Outbox.sent_at.is_(None)).order_by(Outbox.id.asc()).limit(limit))
        result = await self.session.scalars(statement)
        return list(result.all())

    async def add_outbox(self, outbox: Outbox) -> None:
        self.session.add(outbox)
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()


class VerificationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, verification: Verification) -> None:
        self.session.add(verification)
        await self.session.flush()

    async def get(self, verification_id: uuid.UUID) -> Verification | None:
        return await self.session.get(Verification, verification_id)

    async def get_active(self, backup_id: uuid.UUID) -> Verification | None:
        return await self.session.scalar(select(Verification).where(
            Verification.backup_id == backup_id,
            Verification.status.in_([Status.QUEUED, Status.VERIFYING]),
        ))

    async def get_all(self, backup_id: uuid.UUID | None = None) -> list[Verification]:
        statement = select(Verification)
        if backup_id is not None:
            statement = statement.where(Verification.backup_id == backup_id)
        statement = statement.order_by(Verification.requested_at.desc(), Verification.id.desc())
        return list((await self.session.scalars(statement)).all())
