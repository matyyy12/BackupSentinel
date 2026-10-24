"""Integration tests; TEST_DATABASE_URL must point to a migrated test database."""
import asyncio
import os
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from monitoring_app.models import Alert, AlertType
from monitoring_app.repository import MonitoringRepository
from monitoring_app.monitor import monitor, result_url, backup_url


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

    async def check_terminal_resolution(self, status):
        completed, pending = self.backup_ids
        verification_id = uuid.uuid4()
        await self.add(completed)
        await self.add(pending)
        await self.add(completed, AlertType.VERIFICATION_FAILED, verification_id)

        results_response = Mock()
        results_response.json.return_value = []
        backups_response = Mock()
        backups_response.json.return_value = [
            {"id": str(verification_id), "backup_id": str(completed), "status": status},
            {"id": str(uuid.uuid4()), "backup_id": str(pending), "status": "QUEUED",
             "requested_at": "2020-01-01T00:00:00Z"},
        ]

        async def snapshot():
            async with self.sessions() as session:
                alerts = (await session.scalars(select(Alert).where(
                    Alert.backup_id.in_(self.backup_ids),
                ))).all()
                return {(a.backup_id, a.type): a.resolved_at for a in alerts}

        def get(url, **kwargs):
            return {result_url: results_response, backup_url: backups_response}[url]

        with patch.dict(os.environ, DATABASE_URL=os.environ["TEST_DATABASE_URL"]), \
             patch("monitoring_app.monitor.requests.get", side_effect=get):
            await monitor()
            first = await snapshot()
            self.assertIsNotNone(first[(completed, AlertType.VERIFICATION_TIMEOUT)])
            self.assertIsNone(first[(completed, AlertType.VERIFICATION_FAILED)])
            self.assertIsNone(first[(pending, AlertType.VERIFICATION_TIMEOUT)])
            self.assertEqual(len(first), 3)
            await monitor()
            self.assertEqual(await snapshot(), first)

    async def test_verified_backup_closes_only_its_timeout(self):
        await self.check_terminal_resolution("VERIFIED")

    async def test_failed_backup_closes_timeout_but_preserves_failure_alert(self):
        await self.check_terminal_resolution("FAILED")

    async def test_timeout_uses_request_time_instead_of_backup_age(self):
        fresh_id, stale_id = uuid.uuid4(), uuid.uuid4()
        attempts = [
            {"id": str(fresh_id), "backup_id": str(self.backup_ids[0]), "status": "QUEUED",
             "requested_at": datetime.now(timezone.utc).isoformat(), "upload_date": "2020-01-01T00:00:00Z"},
            {"id": str(stale_id), "backup_id": str(self.backup_ids[1]), "status": "QUEUED",
             "requested_at": "2020-01-01T00:00:00Z"},
        ]
        with patch.dict(os.environ, DATABASE_URL=os.environ["TEST_DATABASE_URL"]), \
             patch("monitoring_app.monitor.requests.get") as get:
            get.return_value.json.side_effect = [[], attempts]
            await monitor()
        async with self.sessions() as session:
            rows = (await session.scalars(select(Alert).where(Alert.backup_id.in_(self.backup_ids)))).all()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].verification_id, stale_id)

    async def test_old_terminal_attempt_does_not_close_new_timeout(self):
        backup_id = self.backup_ids[0]
        active_id = uuid.uuid4()
        await self.add(backup_id, verification_id=active_id)
        attempts = [
            {"id": str(uuid.uuid4()), "backup_id": str(backup_id), "status": "VERIFIED"},
            {"id": str(active_id), "backup_id": str(backup_id), "status": "QUEUED",
             "requested_at": "2020-01-01T00:00:00Z"},
        ]
        with patch.dict(os.environ, DATABASE_URL=os.environ["TEST_DATABASE_URL"]), \
             patch("monitoring_app.monitor.requests.get") as get:
            get.return_value.json.side_effect = [[], attempts]
            await monitor()
        self.assertEqual(await self.count(unresolved=True), 1)


if __name__ == "__main__":
    unittest.main()
