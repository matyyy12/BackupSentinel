import datetime
import uuid

from pydantic import BaseModel, ConfigDict
from app.models import Status

class BackupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    size: int
    status: Status
    upload_date: datetime.datetime
    postgres_version: str