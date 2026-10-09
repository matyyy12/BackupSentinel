import os
import shutil
from pathlib import Path

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool


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


async def delete_file(filename: str) -> None:
    storage_directory = os.environ.get("BACKUP_STORAGE_PATH")
    if not storage_directory or not storage_directory.strip():
        raise RuntimeError("BACKUP_STORAGE_PATH must specify the backup directory")
    destination = Path(storage_directory) / filename
    await run_in_threadpool(_delete_file, destination)
