import uuid
from typing import Annotated

from fastapi import APIRouter, File, UploadFile, Depends, Form
from starlette import status

from app.dependencies import get_service
from app.schemas import BackupResponse
from app.service import BackupService


router = APIRouter(prefix="/backup", tags=["backup"])


@router.post("/files", response_model=BackupResponse, status_code=status.HTTP_201_CREATED)
async def post(file: Annotated[UploadFile, File()],
               postgres_version: Annotated[str, Form()],
               service: Annotated[BackupService, Depends(get_service)]) -> BackupResponse:
    return await service.upload_file(file, postgres_version)

@router.get("/backups", response_model=list[BackupResponse], status_code=status.HTTP_200_OK)
async def get_backups(service: Annotated[BackupService, Depends(get_service)]) -> list[BackupResponse]:
    return await service.get_backups()

@router.get('/backups/{backup_id}', response_model=BackupResponse, status_code=status.HTTP_200_OK)
async def get_backup(backup_id: uuid.UUID,
                     service: Annotated[BackupService, Depends(get_service)]) -> BackupResponse:
    return await service.get_backup(backup_id)