import asyncio
import os
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from verification_app.models import VerificationResultOutbox
from verification_app.outbox import get_saved_result, save_result
from verification_app.publisher import publish_pending
from verification_app.schemas import VerificationResponse
from verification_app.tasks import verification_restore


@unittest.skipUnless(os.environ.get("TEST_DATABASE_URL"), "Requires a migrated PostgreSQL test database")
class ResultOutboxTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.env = patch.dict(os.environ, DATABASE_URL=os.environ["TEST_DATABASE_URL"])
        self.env.start()
        self.engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        now = datetime.now(timezone.utc)
        self.result = VerificationResponse(
            verification_id=uuid.uuid4(), backup_id=uuid.uuid4(), status="VERIFIED",
            started_at=now, finished_at=now, error_message=None,
        )

    async def asyncTearDown(self):
        try:
            async with self.sessions.begin() as session:
                await session.execute(delete(VerificationResultOutbox).where(
                    VerificationResultOutbox.verification_id == self.result.verification_id,
                ))
        finally:
            await self.engine.dispose()
            self.env.stop()

    async def row(self):
        async with self.sessions() as session:
            return await session.get(VerificationResultOutbox, self.result.verification_id)

    async def test_duplicate_save_preserves_original_payload(self):
        await save_result(self.result)
        await save_result(self.result.model_copy(update={"error_message": "changed"}))
        self.assertEqual((await self.row()).payload, self.result.model_dump(mode="json"))

    async def test_publish_failure_preserves_unsent_result_for_next_attempt(self):
        await save_result(self.result)
        with patch("verification_app.publisher.app.send_task", side_effect=ConnectionError("Redis unavailable")):
            with self.assertRaises(ConnectionError):
                await publish_pending()
        self.assertIsNone((await self.row()).sent_at)
        with patch("verification_app.publisher.app.send_task") as send:
            self.assertEqual(await publish_pending(), 1)
            send.assert_called_once_with("backup_results", kwargs={"request": self.result.model_dump(mode="json")})
            self.assertIsNotNone((await self.row()).sent_at)
            self.assertEqual(await publish_pending(), 0)
            send.assert_called_once()

    async def test_repeated_task_uses_persisted_result_without_restore(self):
        await save_result(self.result)
        with patch("verification_app.tasks.restore") as restore, \
             patch("verification_app.tasks.app.send_task") as send:
            await asyncio.to_thread(
                verification_restore.run,
                verification_id=str(self.result.verification_id), backup_id=str(self.result.backup_id),
                storage_key="test.dump", postgres_version="17",
            )
            restore.assert_not_called()
            send.assert_not_called()
        self.assertEqual((await get_saved_result(self.result.verification_id)), self.result)

    async def test_task_saves_result_without_publishing(self):
        result = self.result.model_dump()
        result.pop("verification_id")
        result.pop("backup_id")
        with patch("verification_app.tasks.restore", return_value=result), \
             patch("verification_app.tasks.app.send_task") as send:
            await asyncio.to_thread(
                verification_restore.run,
                verification_id=str(self.result.verification_id), backup_id=str(self.result.backup_id),
                storage_key="test.dump", postgres_version="17",
            )
            send.assert_not_called()
        self.assertEqual((await self.row()).payload, self.result.model_dump(mode="json"))

    async def test_verification_id_cannot_be_reused_for_another_backup(self):
        await save_result(self.result)
        with self.assertRaises(ValueError):
            await save_result(self.result.model_copy(update={"backup_id": uuid.uuid4()}))
        self.assertEqual((await self.row()).backup_id, self.result.backup_id)


if __name__ == "__main__":
    unittest.main()
