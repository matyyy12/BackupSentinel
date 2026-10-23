import datetime
import uuid
from enum import Enum

from sqlalchemy import UUID, String, DateTime, Enum as SqlEnum, func, UniqueConstraint, Index, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AlertType(Enum):
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    VERIFICATION_TIMEOUT = "VERIFICATION_TIMEOUT"


class Alert(Base):
    __tablename__ = "alerts"

    __table_args__ = (
        UniqueConstraint(
            "verification_id", "type",
            name="uq_alerts_verification_type",
        ),
        Index(
            "uq_alerts_open_timeout_backup",
            "backup_id",
            unique=True,
            postgresql_where=text(
                "type = 'VERIFICATION_TIMEOUT' AND resolved_at IS NULL"
            ),
        ),
    )

    id : Mapped[int] = mapped_column(primary_key=True, nullable=False)
    backup_id : Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    verification_id : Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    type: Mapped[AlertType] = mapped_column(SqlEnum(AlertType), nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    resolved_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
