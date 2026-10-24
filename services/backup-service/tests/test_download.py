import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from backup_app.dependencies import get_service
from backup_app.exception_handlers import register_exception_handlers
from backup_app.router import router
from backup_app.service import BackupService
from test_exception_handlers import request_asgi


class DownloadTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, BACKUP_STORAGE_PATH=self.temp.name)
        self.env.start()
        self.backup_id = uuid.uuid4()
        self.key = f"{self.backup_id}.dump"
        self.repository = AsyncMock()
        self.repository.get_backup.return_value = SimpleNamespace(storage_key=self.key, filename="original.dump")
        service = BackupService(self.repository, AsyncMock(), AsyncMock(), AsyncMock())
        self.app = FastAPI()
        register_exception_handlers(self.app)
        self.app.include_router(router, prefix="/api")
        self.app.dependency_overrides[get_service] = lambda: service
        self.url = f"/api/backups/{self.backup_id}/download"

    async def asyncTearDown(self):
        self.env.stop()
        self.temp.cleanup()

    async def test_download_sends_bytes_under_original_filename(self):
        data = b"binary\x00backup" * 200000
        Path(self.temp.name, self.key).write_bytes(data)
        status, headers, body = await request_asgi(self.app, self.url)
        self.assertEqual(status, 200)
        self.assertEqual(body, data)
        self.assertEqual(headers[b"content-type"], b"application/octet-stream")
        self.assertIn(b'filename="original.dump"', headers[b"content-disposition"])

    async def test_missing_file_returns_404(self):
        status, _, body = await request_asgi(self.app, self.url)
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body), {"detail": "Backup file not found"})

    async def test_missing_record_returns_404(self):
        self.repository.get_backup.return_value = None
        self.assertEqual((await request_asgi(self.app, self.url))[0], 404)

    async def test_invalid_uuid_returns_422(self):
        self.assertEqual((await request_asgi(self.app, "/api/backups/bad/download"))[0], 422)

    async def test_storage_configuration_error_remains_500(self):
        with patch.dict(os.environ, BACKUP_STORAGE_PATH=""), self.assertLogs("backup_app.exception_handlers", level="ERROR"):
            status, _, body = await request_asgi(self.app, self.url)
        self.assertEqual(status, 500)
        self.assertEqual(json.loads(body), {"detail": "Internal server error"})

    async def test_path_outside_storage_is_not_served(self):
        self.repository.get_backup.return_value.storage_key = "../outside.dump"
        with self.assertLogs("backup_app.exception_handlers", level="ERROR"):
            self.assertEqual((await request_asgi(self.app, self.url))[0], 500)
