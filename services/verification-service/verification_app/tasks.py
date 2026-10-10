import uuid

from verification_app.celery_app import app
from verification_app.restore import restore
from verification_app.schemas import VerificationRequest, VerificationResponse


@app.task(name="verification_restore")
def verification_restore(backup_id: uuid.UUID,
                         storage_key: str,
                         postgres_version: str) -> None:
    request = VerificationRequest.model_validate({
        "backup_id": backup_id,
        "storage_key": storage_key,
        "postgres_version": postgres_version
    })
    result = restore(request.storage_key)
    result["backup_id"] = request.backup_id
    result = VerificationResponse.model_validate(result)
    app.send_task(
        "backup_results",
        kwargs={"request": result.model_dump(mode="json")},
    )
    return