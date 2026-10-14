import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from celery.exceptions import Retry
from docker.errors import DockerException
from requests.exceptions import ConnectionError, Timeout

from verification_app.restore import DockerUnavailableError, restore
from verification_app.tasks import verification_restore


class RetryTests(unittest.TestCase):
    def setUp(self):
        self.args = dict(verification_id=str(uuid.uuid4()), backup_id=str(uuid.uuid4()),
                         storage_key="test.dump", postgres_version="17")

    def test_initial_connection_failure_is_classified(self):
        error = DockerException("API version request failed")
        error.__cause__ = ConnectionError("socket unavailable")
        with patch("verification_app.restore.docker.from_env", side_effect=error):
            with self.assertRaises(DockerUnavailableError):
                restore("test.dump")

    def test_configuration_error_is_not_classified_as_connection_failure(self):
        error = DockerException("invalid Docker configuration")
        with patch("verification_app.restore.docker.from_env", side_effect=error):
            with self.assertRaises(DockerException) as caught:
                restore("test.dump")
        self.assertIs(caught.exception, error)

    def test_transient_errors_retry_with_backoff_without_publishing(self):
        for kind in (DockerUnavailableError, ConnectionError, Timeout, TimeoutError):
            for retries, delay in enumerate((10, 20, 40)):
                with self.subTest(error=kind, retries=retries):
                    error = kind("unavailable")
                    verification_restore.push_request(retries=retries)
                    try:
                        with patch("verification_app.tasks.restore", side_effect=error), \
                             patch.object(verification_restore, "retry", side_effect=Retry()) as retry, \
                             patch("verification_app.tasks.app.send_task") as send:
                            with self.assertRaises(Retry):
                                verification_restore.run(**self.args)
                            retry.assert_called_once_with(exc=error, countdown=delay)
                            send.assert_not_called()
                    finally:
                        verification_restore.pop_request()

    def test_exhaustion_publishes_failed_with_original_identifiers(self):
        verification_restore.push_request(retries=3)
        try:
            before = datetime.now(timezone.utc)
            with patch("verification_app.tasks.restore", side_effect=TimeoutError("not ready")), \
                 patch("verification_app.tasks.app.send_task") as send:
                verification_restore.run(**self.args)
            result = send.call_args.kwargs["kwargs"]["request"]
            self.assertEqual(send.call_args.args[0], "backup_results")
            self.assertEqual(result["status"], "FAILED")
            self.assertEqual(result["verification_id"], self.args["verification_id"])
            self.assertEqual(result["backup_id"], self.args["backup_id"])
            self.assertEqual(result["error_message"], "not ready")
            self.assertLessEqual(before, datetime.fromisoformat(result["started_at"]))
            self.assertLessEqual(result["started_at"], result["finished_at"])
        finally:
            verification_restore.pop_request()

    def test_invalid_dump_publishes_without_retry(self):
        now = datetime.now(timezone.utc)
        result = dict(status="FAILED", started_at=now, finished_at=now,
                      error_message="invalid archive")
        with patch("verification_app.tasks.restore", return_value=result), \
             patch.object(verification_restore, "retry") as retry, \
             patch("verification_app.tasks.app.send_task") as send:
            verification_restore.run(**self.args)
            retry.assert_not_called()
            send.assert_called_once()

    def test_publish_failure_is_not_retried_as_restore(self):
        now = datetime.now(timezone.utc)
        result = dict(status="VERIFIED", started_at=now, finished_at=now, error_message=None)
        with patch("verification_app.tasks.restore", return_value=result), \
             patch.object(verification_restore, "retry") as retry, \
             patch("verification_app.tasks.app.send_task", side_effect=ConnectionError("broker")):
            with self.assertRaises(ConnectionError):
                verification_restore.run(**self.args)
            retry.assert_not_called()


if __name__ == "__main__":
    unittest.main()
