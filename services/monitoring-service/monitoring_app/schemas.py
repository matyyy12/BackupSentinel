import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict

from monitoring_app.models import AlertType


class AlertUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolved: Literal[True]


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: AlertType
    created_at: datetime.datetime
    resolved_at: datetime.datetime | None


class AlertDetailsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    backup_id: uuid.UUID
    verification_id: uuid.UUID | None
    type: AlertType
    message: str
    created_at: datetime.datetime
    resolved_at: datetime.datetime | None
