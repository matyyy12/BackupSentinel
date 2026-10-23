import datetime
import os
import logging
import uuid

import requests
from starlette.concurrency import run_in_threadpool

from monitoring_app.models import Alert, AlertType
from monitoring_app.repository import MonitoringRepository
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


logger = logging.getLogger(__name__)
result_url = "http://backup-service:8000/api/backups/results"
backup_url = "http://backup-service:8000/api/backups/"

async def monitor() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    Session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with Session() as session:
            repository = MonitoringRepository(session)
            response = await run_in_threadpool(requests.get, result_url, timeout=10)
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

            response = await run_in_threadpool(requests.get, backup_url, timeout=10)
            response.raise_for_status()
            results = response.json()
            for result in results:
                if result["status"] in ("FAILED", "VERIFIED"):
                    try:
                        await repository.resolve_timeout(uuid.UUID(result["id"]))
                        await repository.commit()
                    except Exception:
                        await repository.rollback()
                        raise
                    continue
                uploaded_at = datetime.datetime.fromisoformat(result["upload_date"].replace("Z", "+00:00"))
                now = datetime.datetime.now(datetime.timezone.utc)
                if now - uploaded_at <= datetime.timedelta(minutes=15):
                    continue
                alert = Alert(
                    backup_id=uuid.UUID(result["id"]),
                    verification_id=None,
                    message="Timeout",
                    type=AlertType.VERIFICATION_TIMEOUT
                )
                try:
                    await repository.add(alert)
                    await repository.commit()
                except Exception:
                    await repository.rollback()
                    raise
    finally:
        await engine.dispose()
