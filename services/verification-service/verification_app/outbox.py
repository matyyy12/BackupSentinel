import uuid

from verification_app.database import session_scope
from verification_app.repository import VerificationResultOutboxRepository
from verification_app.schemas import VerificationResponse


async def get_saved_result(verification_id: uuid.UUID) -> VerificationResponse | None:
    async with session_scope() as session:
        row = await VerificationResultOutboxRepository(session).get(verification_id)
        return None if row is None else VerificationResponse.model_validate(row.payload)


async def save_result(result: VerificationResponse) -> None:
    async with session_scope() as session:
        repository = VerificationResultOutboxRepository(session)
        await repository.add(result)
        saved = await repository.get(result.verification_id)
        if saved.backup_id != result.backup_id:
            raise ValueError("verification_id already belongs to a different backup")
