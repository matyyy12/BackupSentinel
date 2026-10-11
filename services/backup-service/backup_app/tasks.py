import asyncio
import os

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from backup_app.celery_app import app
from backup_app.repository import BackupRepository, BackupResultRepository
from backup_app.schemas import VerificationResult
from backup_app.service import BackupService


@app.task(name="backup_results")
def backup_results(request: VerificationResult) -> None:
    asyncio.run(save_verification_result(request))

async def save_verification_result(request: VerificationResult) -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with Session() as session:
            service = BackupService(BackupRepository(session), BackupResultRepository(session))
            request = VerificationResult.model_validate(request)
            await service.save_backup_status(request)
    finally:
        await engine.dispose()
