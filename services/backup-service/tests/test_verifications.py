import asyncio
import io
import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import FastAPI, UploadFile
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from database import get_session
from backup_app.exception_handlers import register_exception_handlers
from backup_app.models import Backup, BackupResult, Outbox, Status, Verification
from backup_app.repository import BackupRepository, BackupResultRepository, OutboxRepository, VerificationRepository
from backup_app.router import router
from backup_app.schemas import VerificationResult
from backup_app.service import BackupService
from test_exception_handlers import request_asgi


@unittest.skipUnless(os.environ.get("TEST_DATABASE_URL"), "Requires a migrated PostgreSQL test database")
class VerificationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.backup_id = uuid.uuid4()
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, BACKUP_STORAGE_PATH=self.temp.name)
        self.env.start()
        async with self.sessions.begin() as session:
            session.add(Backup(id=self.backup_id, filename="old.dump", storage_key=f"{self.backup_id}.dump",
                               size=1, postgres_version="17", status=Status.VERIFIED,
                               upload_date=datetime.now(timezone.utc) - timedelta(days=30)))
        self.app = FastAPI()
        register_exception_handlers(self.app)
        self.app.include_router(router, prefix="/api")
        async def session_dependency():
            async with self.sessions() as session:
                yield session
        self.app.dependency_overrides[get_session] = session_dependency
        self.path = f"/api/backups/{self.backup_id}/verifications"

    async def asyncTearDown(self):
        try:
            async with self.sessions.begin() as session:
                await session.execute(delete(BackupResult).where(BackupResult.backup_id == self.backup_id))
                await session.execute(delete(Outbox).where(Outbox.backup_id == self.backup_id))
                await session.execute(delete(Verification).where(Verification.backup_id == self.backup_id))
                await session.execute(delete(Backup).where(Backup.id == self.backup_id))
        finally:
            await self.engine.dispose()
            self.env.stop()
            self.temp.cleanup()

    def service(self, session):
        return BackupService(BackupRepository(session), BackupResultRepository(session),
                             OutboxRepository(session), VerificationRepository(session))

    async def request(self, path=None):
        status, _, body = await request_asgi(self.app, path or self.path, method="POST")
        return status, json.loads(body)

    async def finish(self, verification_id, status="VERIFIED"):
        now = datetime.now(timezone.utc)
        async with self.sessions() as session:
            return await self.service(session).save_backup_status(VerificationResult(
                verification_id=verification_id, backup_id=self.backup_id, status=status,
                started_at=now, finished_at=now, error_message=None,
            ))

    async def test_request_queues_attempt_and_outbox_atomically(self):
        before = datetime.now(timezone.utc)
        code, attempt = await self.request()
        self.assertEqual(code, 202)
        self.assertEqual(attempt["backup_id"], str(self.backup_id))
        self.assertEqual(attempt["status"], "QUEUED")
        self.assertGreaterEqual(datetime.fromisoformat(attempt["requested_at"]), before)
        async with self.sessions() as session:
            message = await session.scalar(select(Outbox).where(Outbox.backup_id == self.backup_id))
            self.assertEqual(message.payload["verification_id"], attempt["id"])
            self.assertEqual(message.payload["storage_key"], f"{self.backup_id}.dump")
            self.assertEqual((await session.get(Backup, self.backup_id)).status, Status.QUEUED)
        code, _, body = await request_asgi(self.app, self.path)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body), [attempt])

    async def test_duplicate_active_requests_return_409(self):
        outcomes = await asyncio.gather(self.request(), self.request())
        self.assertEqual(sorted(code for code, _ in outcomes), [202, 409])
        async with self.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(Verification).where(
                Verification.backup_id == self.backup_id)), 1)

    async def test_new_attempt_and_old_duplicate_preserve_current_status(self):
        _, first = await self.request()
        await self.finish(first["id"], "FAILED")
        _, second = await self.request()
        self.assertNotEqual(first["id"], second["id"])
        await self.finish(first["id"], "FAILED")
        async with self.sessions() as session:
            self.assertEqual((await session.get(Backup, self.backup_id)).status, Status.QUEUED)
        await self.finish(second["id"])
        async with self.sessions() as session:
            self.assertEqual((await session.get(Backup, self.backup_id)).status, Status.VERIFIED)
            self.assertEqual((await session.get(Verification, uuid.UUID(first["id"]))).status, Status.FAILED)
            self.assertEqual((await session.get(Verification, uuid.UUID(second["id"]))).status, Status.VERIFIED)

    async def test_outbox_failure_rolls_back_attempt_and_status(self):
        with patch.object(OutboxRepository, "add_outbox", side_effect=RuntimeError("test")), \
             self.assertLogs("backup_app.exception_handlers", level="ERROR"):
            self.assertEqual((await self.request())[0], 500)
        async with self.sessions() as session:
            self.assertEqual(await session.scalar(select(func.count()).select_from(Verification).where(
                Verification.backup_id == self.backup_id)), 0)
            self.assertEqual((await session.get(Backup, self.backup_id)).status, Status.VERIFIED)

    async def test_missing_backup_returns_404_and_invalid_id_422(self):
        self.assertEqual((await self.request(f"/api/backups/{uuid.uuid4()}/verifications"))[0], 404)
        self.assertEqual((await self.request("/api/backups/bad/verifications"))[0], 422)

    async def test_upload_uses_same_attempt_outbox_flow(self):
        backup_id = None
        try:
            async with self.sessions() as session:
                file = UploadFile(file=io.BytesIO(b"test dump"), filename="first.dump", size=9)
                response = await self.service(session).upload_file(file, "17")
                backup_id = response.id
                self.assertEqual(response.status, Status.QUEUED)
            async with self.sessions() as session:
                attempt = await session.scalar(select(Verification).where(Verification.backup_id == backup_id))
                message = await session.scalar(select(Outbox).where(Outbox.backup_id == backup_id))
                self.assertEqual(message.payload["verification_id"], str(attempt.id))
        finally:
            if backup_id:
                async with self.sessions.begin() as session:
                    await session.execute(delete(Outbox).where(Outbox.backup_id == backup_id))
                    await session.execute(delete(Verification).where(Verification.backup_id == backup_id))
                    await session.execute(delete(Backup).where(Backup.id == backup_id))

    async def seed_deletion_history(self, attempt_status=Status.VERIFIED):
        verification_id = uuid.uuid4()
        async with self.sessions.begin() as session:
            session.add(Verification(id=verification_id, backup_id=self.backup_id, status=attempt_status))
            await session.flush()
            session.add(Outbox(backup_id=self.backup_id, task_name="verification_restore",
                              payload={"verification_id": str(verification_id)}))
            if attempt_status in (Status.VERIFIED, Status.FAILED):
                now = datetime.now(timezone.utc)
                session.add(BackupResult(backup_id=self.backup_id, verification_id=verification_id,
                                         status=attempt_status, started_at=now, finished_at=now))
        path = Path(self.temp.name, f"{self.backup_id}.dump")
        path.write_bytes(b"original backup")
        return path, verification_id

    async def delete_request(self, backup_id=None):
        return await request_asgi(self.app, f"/api/backups/{backup_id or self.backup_id}", method="DELETE")

    async def test_delete_removes_file_record_history_and_outbox(self):
        path, _ = await self.seed_deletion_history()
        code, _, body = await self.delete_request()
        self.assertEqual(code, 204)
        self.assertEqual(body, b"")
        self.assertFalse(path.exists())
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])
        async with self.sessions() as session:
            self.assertIsNone(await session.get(Backup, self.backup_id))
            for model in (Verification, BackupResult, Outbox):
                self.assertEqual(await session.scalar(select(func.count()).select_from(model).where(
                    model.backup_id == self.backup_id)), 0)
        self.assertEqual((await self.delete_request())[0], 404)

    async def test_delete_active_verification_is_rejected(self):
        path, attempt_id = await self.seed_deletion_history(Status.QUEUED)
        self.assertEqual((await self.delete_request())[0], 409)
        async with self.sessions.begin() as session:
            await session.execute(update(Verification).where(Verification.id == attempt_id).values(status=Status.VERIFYING))
        self.assertEqual((await self.delete_request())[0], 409)
        self.assertEqual(path.read_bytes(), b"original backup")

    async def test_delete_missing_backup_and_invalid_id(self):
        self.assertEqual((await self.delete_request(uuid.uuid4()))[0], 404)
        self.assertEqual((await self.delete_request("invalid"))[0], 422)

    async def test_delete_database_failure_restores_file_and_records(self):
        path, _ = await self.seed_deletion_history()
        with patch.object(BackupRepository, "commit", side_effect=RuntimeError("commit failed")), \
             self.assertLogs("backup_app.exception_handlers", level="ERROR"):
            self.assertEqual((await self.delete_request())[0], 500)
        self.assertEqual(path.read_bytes(), b"original backup")
        self.assertEqual(list(Path(self.temp.name).iterdir()), [path])
        async with self.sessions() as session:
            self.assertIsNotNone(await session.get(Backup, self.backup_id))
            self.assertEqual(await session.scalar(select(func.count()).select_from(BackupResult).where(
                BackupResult.backup_id == self.backup_id)), 1)

    async def test_delete_storage_failure_leaves_record_untouched(self):
        path, _ = await self.seed_deletion_history()
        with patch("backup_app.service.stage_file_deletion", side_effect=PermissionError("cannot rename")), \
             self.assertLogs("backup_app.exception_handlers", level="ERROR"):
            self.assertEqual((await self.delete_request())[0], 500)
        self.assertTrue(path.exists())
        async with self.sessions() as session:
            self.assertIsNotNone(await session.get(Backup, self.backup_id))

    async def test_delete_missing_file_still_removes_metadata(self):
        path, _ = await self.seed_deletion_history()
        path.unlink()
        self.assertEqual((await self.delete_request())[0], 204)
        async with self.sessions() as session:
            self.assertIsNone(await session.get(Backup, self.backup_id))

    async def test_delete_final_cleanup_failure_is_logged_after_metadata_commit(self):
        path, _ = await self.seed_deletion_history()
        with patch("backup_app.service.remove_staged_file", side_effect=PermissionError("cannot unlink")), \
             self.assertLogs("backup_app.service", level="ERROR"):
            self.assertEqual((await self.delete_request())[0], 204)
        self.assertFalse(path.exists())
        self.assertEqual(len(list(Path(self.temp.name).glob(".deleting-*"))), 1)
        async with self.sessions() as session:
            self.assertIsNone(await session.get(Backup, self.backup_id))

    async def test_delete_racing_with_new_verification_has_consistent_outcome(self):
        path, _ = await self.seed_deletion_history()
        requested, removed = await asyncio.gather(self.request(), self.delete_request())
        self.assertIn((requested[0], removed[0]), {(202, 409), (404, 204)})
        self.assertEqual(path.exists(), removed[0] != 204)
