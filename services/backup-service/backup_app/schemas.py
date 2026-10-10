import datetime
import uuid

from pydantic import BaseModel, ConfigDict
from backup_app.models import Status

class BackupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    size: int
    status: Status
    upload_date: datetime.datetime
    postgres_version: str

class VerificationResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    backup_id: uuid.UUID
    status: Status
    started_at: datetime.datetime
    finished_at: datetime.datetime
    error_message: str | None