"""HTTP integration tests using Uvicorn and a migrated PostgreSQL test database."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from monitoring_app.models import Alert, AlertType


@unittest.skipUnless(os.environ.get("TEST_DATABASE_URL"), "Requires a PostgreSQL test database")
class AlertApiTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        cls.base_url = f"http://127.0.0.1:{port}"
        cls.logs = tempfile.TemporaryFile(mode="w+")
        cls.server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)],
            env={**os.environ, "DATABASE_URL": os.environ["TEST_DATABASE_URL"]},
            stdout=cls.logs, stderr=subprocess.STDOUT,
        )
        for _ in range(100):
            try:
                with urllib.request.urlopen(cls.base_url + "/openapi.json", timeout=1):
                    return
            except (OSError, urllib.error.URLError):
                if cls.server.poll() is not None:
                    break
                time.sleep(0.1)
        cls.server.terminate()
        cls.server.wait(timeout=10)
        cls.logs.seek(0)
        output = cls.logs.read()
        cls.logs.close()
        raise RuntimeError(f"API did not start: {output}")

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate()
        cls.server.wait(timeout=10)
        cls.logs.close()

    async def asyncSetUp(self):
        self.engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.backup_id = uuid.uuid4()
        self.verification_id = uuid.uuid4()
        async with self.sessions.begin() as session:
            opened = Alert(backup_id=self.backup_id, verification_id=None,
                           type=AlertType.VERIFICATION_TIMEOUT, message="Waiting for verification")
            resolved = Alert(backup_id=self.backup_id, verification_id=self.verification_id,
                             type=AlertType.VERIFICATION_FAILED, message="Invalid archive",
                             resolved_at=datetime.now(timezone.utc))
            session.add_all([opened, resolved])
            await session.flush()
            self.open_id, self.resolved_id = opened.id, resolved.id

    async def asyncTearDown(self):
        try:
            async with self.sessions.begin() as session:
                await session.execute(delete(Alert).where(Alert.backup_id == self.backup_id))
        finally:
            await self.engine.dispose()

    def request(self, path, *, method="GET", body=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base_url + path, data=data, method=method,
                                         headers={"Content-Type": "application/json"})
        try:
            response = urllib.request.urlopen(request, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    async def test_list_and_resolved_filters(self):
        for query, present, absent in (
            ("", {self.open_id, self.resolved_id}, set()),
            ("?resolved=false", {self.open_id}, {self.resolved_id}),
            ("?resolved=true", {self.resolved_id}, {self.open_id}),
        ):
            with self.subTest(query=query):
                status, rows = self.request("/api/alerts/" + query)
                self.assertEqual(status, 200)
                ids = {row["id"] for row in rows}
                self.assertTrue(present <= ids)
                self.assertTrue(absent.isdisjoint(ids))

    async def test_details_support_nullable_fields(self):
        status, body = self.request(f"/api/alerts/{self.open_id}")
        self.assertEqual(status, 200)
        self.assertEqual(body["backup_id"], str(self.backup_id))
        self.assertEqual(body["type"], "VERIFICATION_TIMEOUT")
        self.assertEqual(body["message"], "Waiting for verification")
        self.assertIsNone(body["verification_id"])
        self.assertIsNone(body["resolved_at"])

    async def test_patch_persists_server_timestamp_and_is_idempotent(self):
        before = datetime.now(timezone.utc)
        path = f"/api/alerts/{self.open_id}"
        status, body = self.request(path, method="PATCH", body={"resolved": True})
        self.assertEqual(status, 200)
        resolved_at = datetime.fromisoformat(body["resolved_at"])
        self.assertLessEqual(before, resolved_at)
        self.assertLessEqual(resolved_at, datetime.now(timezone.utc))
        async with self.sessions() as session:
            saved = await session.scalar(select(Alert).where(Alert.id == self.open_id))
            self.assertEqual(saved.resolved_at, resolved_at)
        self.assertEqual(self.request(path)[1]["resolved_at"], body["resolved_at"])
        self.assertEqual(self.request(path, method="PATCH", body={"resolved": True})[1]["resolved_at"], body["resolved_at"])
        _, rows = self.request("/api/alerts/?resolved=false")
        self.assertNotIn(self.open_id, {row["id"] for row in rows})

    async def test_unknown_alert_returns_404(self):
        for method, body in (("GET", None), ("PATCH", {"resolved": True})):
            status, response = self.request("/api/alerts/-1", method=method, body=body)
            self.assertEqual(status, 404)
            self.assertEqual(response["detail"], "Alert not found")

    async def test_invalid_patch_does_not_resolve_alert(self):
        for body in ({}, {"resolved": False}, {"resolved_at": "2026-10-23T00:00:00Z"},
                     {"resolved": True, "id": self.open_id}):
            with self.subTest(body=body):
                status, _ = self.request(f"/api/alerts/{self.open_id}", method="PATCH", body=body)
                self.assertEqual(status, 422)
        self.assertIsNone(self.request(f"/api/alerts/{self.open_id}")[1]["resolved_at"])

    async def test_invalid_query_and_path_return_422(self):
        for path in ("/api/alerts/?resolved=invalid", "/api/alerts/not-an-integer"):
            self.assertEqual(self.request(path)[0], 422)


if __name__ == "__main__":
    unittest.main()
