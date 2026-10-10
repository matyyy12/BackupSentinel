from fastapi import APIRouter
from fastapi.params import Depends
from typing import Annotated
from starlette import status

from verification_app.schemas import VerificationRequest, VerificationResponse
from verification_app.service import VerificationService

router = APIRouter()

@router.post("/verification", status_code=status.HTTP_200_OK, response_model=VerificationResponse)
async def verification(request: VerificationRequest,
                       service: Annotated[VerificationService, Depends(VerificationService)]) -> VerificationResponse:
    return await service.verify(request)