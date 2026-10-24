import uuid
from typing import Annotated

from fastapi import APIRouter, File, UploadFile, Depends, Form, Response
from starlette import status
from starlette.responses import FileResponse

from backup_app.dependencies import get_service
from backup_app.schemas import BackupResponse, VerificationResult, VerificationResponse
from backup_app.service import BackupService


router = APIRouter(prefix="/backups", tags=["backup"])


@router.post("/files", response_model=BackupResponse, status_code=status.HTTP_201_CREATED)
async def post(file: Annotated[UploadFile, File()],
               postgres_version: Annotated[str, Form()],
               service: Annotated[BackupService, Depends(get_service)]) -> BackupResponse:
    return await service.upload_file(file, postgres_version)

@router.get("/", response_model=list[BackupResponse], status_code=status.HTTP_200_OK)
async def get_backups(service: Annotated[BackupService, Depends(get_service)]) -> list[BackupResponse]:
    return await service.get_backups()


@router.get('/results', response_model=list[VerificationResult], status_code=status.HTTP_200_OK)
async def get_results(service: Annotated[BackupService, Depends(get_service)]) -> list[VerificationResult]:
    return await service.get_results()

@router.get('/verifications', response_model=list[VerificationResponse])
async def get_verifications(service: Annotated[BackupService, Depends(get_service)]) -> list[VerificationResponse]:
    return await service.get_verifications()


@router.post('/{backup_id}/verifications', response_model=VerificationResponse, status_code=status.HTTP_202_ACCEPTED)
async def request_verification(backup_id: uuid.UUID,
                               service: Annotated[BackupService, Depends(get_service)]) -> VerificationResponse:
    return await service.request_verification(backup_id)


@router.get('/{backup_id}/verifications', response_model=list[VerificationResponse])
async def get_backup_verifications(backup_id: uuid.UUID,
                                   service: Annotated[BackupService, Depends(get_service)]) -> list[VerificationResponse]:
    return await service.get_verifications(backup_id)


@router.get('/{backup_id}/download', response_class=FileResponse, status_code=status.HTTP_200_OK)
async def download_backup(backup_id: uuid.UUID,
                          service: Annotated[BackupService, Depends(get_service)]) -> FileResponse:
    return await service.download_backup(backup_id)

@router.get('/{backup_id}', response_model=BackupResponse, status_code=status.HTTP_200_OK)
async def get_backup(backup_id: uuid.UUID,
                     service: Annotated[BackupService, Depends(get_service)]) -> BackupResponse:
    return await service.get_backup(backup_id)


@router.delete('/{backup_id}', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_backup(backup_id: uuid.UUID,
                        service: Annotated[BackupService, Depends(get_service)]) -> Response:
    await service.delete_backup(backup_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get('/status/{backup_id}', response_model=VerificationResult, status_code=status.HTTP_200_OK)
async def get_backup_status(backup_id: uuid.UUID,
                            service: Annotated[BackupService, Depends(get_service)]) -> VerificationResult:
    return await service.get_backup_status(backup_id)
