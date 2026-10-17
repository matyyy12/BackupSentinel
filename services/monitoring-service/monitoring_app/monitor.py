import os
import logging
import uuid

import requests
from starlette.concurrency import run_in_threadpool

from monitoring_app.models import Alert, AlertType
from monitoring_app.repository import MonitoringRepository
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


logger = logging.getLogger(__name__)
url = "http://backup-service:8000/api/backups/results"

async def monitor() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with Session() as session:
            repository = MonitoringRepository(session)
            response = await run_in_threadpool(requests.get, url, timeout=10)
            response.raise_for_status()
            results = response.json()
            for result in results:
                if result["status"] != "FAILED":
                    continue
                verification_id = uuid.UUID(result["verification_id"])
                alert = Alert(
                            backup_id=uuid.UUID(result["backup_id"]),
                            verification_id=verification_id,
                            message=result["error_message"] or "Verification failed",
                            type=AlertType.VERIFICATION_FAILED)
                try:
                    await repository.add(alert)
                    await repository.commit()
                except Exception:
                    await repository.rollback()
                    raise
    finally:
        await engine.dispose()
