"""Integration tests; TEST_DATABASE_URL must point to a migrated test database."""
import asyncio
import os
import unittest
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from monitoring_app.models import Alert, AlertType
from monitoring_app.repository import MonitoringRepository


@unittest.skipUnless(os.environ.get("TEST_DATABASE_URL"), "Requires a PostgreSQL test database")
class TimeoutAlertTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.backup_ids = [uuid.uuid4(), uuid.uuid4()]

    async def asyncTearDown(self):
        try:
            async with self.sessions.begin() as session:
                await session.execute(delete(Alert).where(Alert.backup_id.in_(self.backup_ids)))
        finally:
            await self.engine.dispose()

    async def add(self, backup_id, alert_type=AlertType.VERIFICATION_TIMEOUT, verification_id=None):
        async with self.sessions.begin() as session:
            return await MonitoringRepository(session).add(Alert(
                backup_id=backup_id,
                verification_id=verification_id,
                type=alert_type,
                message="integration test",
            ))

    async def count(self, *, unresolved=False):
        query = select(func.count()).select_from(Alert).where(Alert.backup_id.in_(self.backup_ids))
        if unresolved:
            query = query.where(Alert.resolved_at.is_(None))
        async with self.sessions() as session:
            return await session.scalar(query)

    async def test_second_open_timeout_is_skipped(self):
        self.assertTrue(await self.add(self.backup_ids[0]))
        self.assertFalse(await self.add(self.backup_ids[0]))
        self.assertEqual(await self.count(), 1)

    async def test_resolved_timeout_allows_new_alert_and_preserves_history(self):
        self.assertTrue(await self.add(self.backup_ids[0]))
        async with self.sessions.begin() as session:
            await session.execute(update(Alert).where(Alert.backup_id == self.backup_ids[0]).values(
                resolved_at=datetime.now(timezone.utc),
            ))
        self.assertTrue(await self.add(self.backup_ids[0]))
        self.assertEqual(await self.count(), 2)
        self.assertEqual(await self.count(unresolved=True), 1)

    async def test_different_backups_can_have_open_timeouts(self):
        for backup_id in self.backup_ids:
            self.assertTrue(await self.add(backup_id))
        self.assertEqual(await self.count(), 2)

    async def test_failed_verifications_keep_separate_deduplication(self):
        backup_id = self.backup_ids[0]
        verification_id = uuid.uuid4()
        self.assertTrue(await self.add(backup_id))
        self.assertTrue(await self.add(backup_id, AlertType.VERIFICATION_FAILED, verification_id))
        self.assertFalse(await self.add(backup_id, AlertType.VERIFICATION_FAILED, verification_id))
        self.assertTrue(await self.add(backup_id, AlertType.VERIFICATION_FAILED, uuid.uuid4()))
        self.assertEqual(await self.count(), 3)

    async def test_concurrent_inserts_create_one_open_timeout(self):
        results = await asyncio.gather(self.add(self.backup_ids[0]), self.add(self.backup_ids[0]))
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(await self.count(), 1)


if __name__ == "__main__":
    unittest.main()
