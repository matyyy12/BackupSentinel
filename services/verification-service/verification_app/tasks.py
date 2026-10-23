import asyncio
import datetime
import uuid

from verification_app.celery_app import app
from verification_app.restore import DockerUnavailableError, restore
from verification_app.outbox import get_saved_result, save_result
from verification_app.schemas import VerificationRequest, VerificationResponse, Status
from requests.exceptions import ConnectionError, Timeout


@app.task(name="verification_restore", bind=True, max_retries=3)
def verification_restore(self,
                         verification_id: str,
                         backup_id: uuid.UUID,
                         storage_key: str,
                         postgres_version: str) -> None:
    request = VerificationRequest.model_validate({
        "verification_id": verification_id,
        "backup_id": backup_id,
        "storage_key": storage_key,
        "postgres_version": postgres_version
    })
    saved = asyncio.run(get_saved_result(request.verification_id))
    if saved is not None:
        if saved.backup_id != request.backup_id:
            raise ValueError("verification_id already belongs to a different backup")
        return
    started_at = datetime.datetime.now(datetime.timezone.utc)
    try:
        result = restore(request.storage_key)
    except (DockerUnavailableError, ConnectionError, Timeout, TimeoutError) as e:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=10 * (2 ** self.request.retries))
        result = {
            "status": Status.FAILED,
            "started_at": started_at,
            "finished_at": datetime.datetime.now(datetime.timezone.utc),
            "error_message": str(e),
        }
    result["backup_id"] = request.backup_id
    result['verification_id'] = request.verification_id
    result = VerificationResponse.model_validate(result)
    asyncio.run(save_result(result))
    return
