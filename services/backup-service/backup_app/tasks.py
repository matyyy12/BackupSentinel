import asyncio
import os

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from backup_app.celery_app import app
from backup_app.repository import BackupRepository
from backup_app.schemas import VerificationResult
from backup_app.service import BackupService


@app.task(name="backup_results")
def backup_results(request) -> None:
        asyncio.run(save_verification_result(request))

async def save_verification_result(request):
    engine = create_async_engine(os.environ["DATABASE_URL"])
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with Session() as session:
            service = BackupService(BackupRepository(session))
            request = VerificationResult.model_validate(request)
            await service.update_backup_status(request.backup_id, request.status)
    finally:
        await engine.dispose()