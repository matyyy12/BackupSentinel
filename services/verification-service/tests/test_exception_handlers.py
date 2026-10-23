import json
from contextlib import nullcontext
import unittest

from fastapi import FastAPI, HTTPException
from sqlalchemy.exc import OperationalError

from verification_app.exception_handlers import register_exception_handlers
from verification_app.exceptions import NotFoundError


async def request_asgi(app, path, *, query=b"", method="GET", body=b""):
    messages = []
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}
    async def send(message):
        messages.append(message)
    scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
             "http_version": "1.1", "method": method, "scheme": "http",
             "path": path, "raw_path": path.encode(), "query_string": query,
             "headers": [(b"content-type", b"application/json")],
             "server": ("test", 80), "client": ("test", 123)}
    try:
        await app(scope, receive, send)
    except Exception:
        # Starlette re-raises unexpected errors after sending the handled 500.
        if not any(m["type"] == "http.response.start" and m["status"] == 500 for m in messages):
            raise
    start = next(m for m in messages if m["type"] == "http.response.start")
    content = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return start["status"], dict(start["headers"]), content


class HandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_expected_unknown_database_and_http_errors(self):
        app = FastAPI()
        register_exception_handlers(app)
        @app.get("/missing")
        async def missing():
            raise NotFoundError("Resource not found")
        @app.get("/unknown")
        async def unknown():
            raise RuntimeError("private path or password")
        @app.get("/database")
        async def database():
            raise OperationalError("SELECT private", {}, Exception("secret"))
        @app.get("/http")
        async def http():
            raise HTTPException(429, "Slow down", headers={"Retry-After": "10"})
        @app.get("/validate")
        async def validate(count: int):
            return count
        for path, expected, detail in [("/missing", 404, "Resource not found"),
                                       ("/unknown", 500, "Internal server error"),
                                       ("/database", 503, "Database temporarily unavailable")]:
            with self.subTest(path=path), self.assertLogs("verification_app.exception_handlers", level="ERROR") if expected != 404 else nullcontext():
                status, _, body = await request_asgi(app, path)
                self.assertEqual(status, expected)
                self.assertEqual(json.loads(body), {"detail": detail})
        status, headers, _ = await request_asgi(app, "/http")
        self.assertEqual(status, 429)
        self.assertEqual(headers[b"retry-after"], b"10")
        self.assertEqual((await request_asgi(app, "/validate", query=b"count=bad"))[0], 422)
        self.assertEqual((await request_asgi(app, "/not-a-route"))[0], 404)


class VerificationHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_transient_errors_have_http_statuses(self):
        from requests.exceptions import ConnectionError, Timeout
        from verification_app.restore import DockerUnavailableError
        for error, code in ((DockerUnavailableError("socket private"), 503),
                            (ConnectionError("private address"), 503),
                            (Timeout("private timeout"), 504),
                            (TimeoutError("private timeout"), 504)):
            app = FastAPI()
            register_exception_handlers(app)
            @app.get("/verify")
            async def verify():
                raise error
            with self.subTest(error=type(error)), self.assertLogs("verification_app.exception_handlers", level="ERROR"):
                status, _, body = await request_asgi(app, "/verify")
                self.assertEqual(status, code)
                self.assertNotIn(b"private", body)

    async def test_real_endpoint_rejects_invalid_storage_key(self):
        import uuid
        from verification_app.router import router
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(router, prefix="/api")
        body = json.dumps(dict(verification_id=str(uuid.uuid4()), backup_id=str(uuid.uuid4()),
                               storage_key="../outside.dump", postgres_version="17")).encode()
        status, _, content = await request_asgi(app, "/api/verification", method="POST", body=body)
        self.assertEqual(status, 422)
        self.assertEqual(json.loads(content)["detail"], "storage_key must be a filename, not a path")
