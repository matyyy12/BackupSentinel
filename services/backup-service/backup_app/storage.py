import os
import shutil
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool
from starlette.responses import FileResponse

from backup_app.exceptions import BackupFileNotFoundError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StagedDeletion:
    original: Path
    staged: Path


def _stage_file_deletion(storage_directory: str, storage_key: str) -> StagedDeletion | None:
    try:
        original = _download_path(storage_directory, storage_key)
    except BackupFileNotFoundError:
        return None
    staged = original.with_name(f".deleting-{uuid.uuid4().hex}-{original.name}")
    original.rename(staged)
    return StagedDeletion(original=original, staged=staged)


async def stage_file_deletion(storage_key: str) -> StagedDeletion | None:
    directory = os.environ.get("BACKUP_STORAGE_PATH")
    if not directory or not directory.strip():
        raise RuntimeError("BACKUP_STORAGE_PATH must specify the backup directory")
    return await run_in_threadpool(_stage_file_deletion, directory, storage_key)


async def restore_staged_file(deletion: StagedDeletion) -> None:
    await run_in_threadpool(deletion.staged.rename, deletion.original)


async def remove_staged_file(deletion: StagedDeletion) -> None:
    await run_in_threadpool(deletion.staged.unlink, missing_ok=True)


def _download_path(storage_directory: str, storage_key: str) -> Path:
    directory = Path(storage_directory).resolve()
    destination = (directory / storage_key).resolve()
    if (
        not storage_key
        or Path(storage_key).name != storage_key
        or "\\" in storage_key
        or "\x00" in storage_key
        or destination.parent != directory
    ):
        raise ValueError("Invalid storage key in backup record")
    if not destination.is_file():
        logger.warning("Backup file missing for storage key %s", storage_key)
        raise BackupFileNotFoundError("Backup file not found")
    return destination


def _save_file(file: UploadFile, destination: Path) -> None:
    with destination.open("xb") as output:
        try:
            shutil.copyfileobj(file.file, output, length=1024 * 1024)
        except BaseException:
            output.close()
            destination.unlink(missing_ok=True)
            raise

def _delete_file(destination: Path) -> None:
    destination.unlink(missing_ok=True)


async def save_file(file: UploadFile, filename: str) -> None:
    storage_directory = os.environ.get("BACKUP_STORAGE_PATH")
    if not storage_directory or not storage_directory.strip():
        raise RuntimeError("BACKUP_STORAGE_PATH must specify the backup directory")

    destination = Path(storage_directory) / filename
    await run_in_threadpool(_save_file, file, destination)

async def download_file(storage_key: str, filename: str) -> FileResponse:
    storage_directory = os.environ.get("BACKUP_STORAGE_PATH")
    if not storage_directory or not storage_directory.strip():
        raise RuntimeError("BACKUP_STORAGE_PATH must specify the backup directory")
    destination = await run_in_threadpool(_download_path, storage_directory, storage_key)
    return FileResponse(path=destination, filename=filename, media_type="application/octet-stream")

async def delete_file(filename: str) -> None:
    storage_directory = os.environ.get("BACKUP_STORAGE_PATH")
    if not storage_directory or not storage_directory.strip():
        raise RuntimeError("BACKUP_STORAGE_PATH must specify the backup directory")
    destination = Path(storage_directory) / filename
    await run_in_threadpool(_delete_file, destination)
