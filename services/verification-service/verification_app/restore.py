import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import PurePosixPath

import docker
from docker.errors import DockerException
from requests.exceptions import ConnectionError, Timeout


class DockerUnavailableError(Exception):
    ...


def restore(storage_key: str, *, ready_timeout: float = 60) -> dict:
    if (
        not storage_key
        or PurePosixPath(storage_key).name != storage_key
        or storage_key in {".", ".."}
        or "\\" in storage_key
        or "\x00" in storage_key
    ):
        raise ValueError("storage_key must be a filename, not a path")
    if ready_timeout <= 0:
        raise ValueError("ready_timeout must be positive")

    volume = os.environ.get("BACKUP_VOLUME_NAME", "backupsentinel_backup_files")
    started_at = datetime.now(timezone.utc)
    try:
        client = docker.from_env(timeout=300)
    except DockerException as exc:
        if isinstance(exc.__cause__, (ConnectionError, Timeout)):
            raise DockerUnavailableError(str(exc)) from exc
        raise
    container = None
    try:
        client.volumes.get(volume)
        container = client.containers.run(
            "postgres:17-bookworm",
            detach=True,
            environment={
                "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
                "POSTGRES_DB": "restore_test",
            },
            volumes={volume: {"bind": "/backups", "mode": "ro"}},
            network_mode="none",
            mem_limit="512m",
            nano_cpus=1_000_000_000,
            pids_limit=128,
            labels={"backupsentinel.purpose": "restore-test"},
        )
        deadline = time.monotonic() + ready_timeout
        while True:
            container.reload()
            if container.status != "running":
                raise RuntimeError("Test PostgreSQL stopped before becoming ready")
            result = container.exec_run(
                ["pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "restore_test"],
                user="postgres",
            )
            if result.exit_code == 0:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError("Test PostgreSQL did not become ready in time")
            time.sleep(0.5)

        result = container.exec_run(
            [
                "pg_restore", "-U", "postgres", "-d", "restore_test",
                "--no-owner", "--no-privileges", "--exit-on-error",
                f"/backups/{storage_key}",
            ],
            user="postgres",
        )
        return {
            "status": "VERIFIED" if result.exit_code == 0 else "FAILED",
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc),
            "error_message": (
                None if result.exit_code == 0
                else result.output.decode("utf-8", errors="replace").strip()
            ),
        }
    finally:
        try:
            if container is not None:
                container.remove(force=True, v=True)
        finally:
            client.close()
