import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict
from enum import Enum

class Status(Enum):
    RECEIVED = "RECEIVED"
    QUEUED = "QUEUED"
    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"

class VerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verification_id: str
    backup_id: uuid.UUID
    storage_key: str
    postgres_version: Literal["17"]

class VerificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    verification_id: uuid.UUID
    backup_id: uuid.UUID
    status: Status
    started_at: datetime.datetime
    finished_at: datetime.datetime
    error_message: str | None