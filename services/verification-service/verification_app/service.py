from starlette.concurrency import run_in_threadpool

from verification_app.schemas import VerificationRequest, VerificationResponse
from verification_app.restore import restore

class VerificationService:

    async def verify(self, request: VerificationRequest) -> VerificationResponse:
        result = await run_in_threadpool(restore, request.storage_key)
        result["backup_id"] = request.backup_id
        return VerificationResponse.model_validate(result)
