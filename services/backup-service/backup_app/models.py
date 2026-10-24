import datetime
import uuid
from enum import Enum
from typing import Any

from sqlalchemy import UUID, String, DateTime, func, BigInteger, Enum as SqlEnum, ForeignKey, JSON, Index, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass

class Status(Enum):
    RECEIVED = "RECEIVED"
    QUEUED = "QUEUED"
    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"

class Backup(Base):
    __tablename__ = "backups"
    id : Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    storage_key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[Status] = mapped_column(SqlEnum(Status), nullable=False, default=Status.RECEIVED)
    upload_date: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    postgres_version: Mapped[str] = mapped_column(String, nullable=False)
    results: Mapped[list["BackupResult"]] = relationship(back_populates="backup")


class BackupResult(Base):
    __tablename__ = "backup_results"
    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)

    verification_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("verifications.id"), nullable=False, unique=True)
    backup_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("backups.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[Status] = mapped_column(SqlEnum(Status), nullable=False, default=Status.RECEIVED)
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    backup: Mapped["Backup"] = relationship(back_populates="results")


class Verification(Base):
    __tablename__ = "verifications"
    __table_args__ = (
        Index("uq_verifications_active_backup", "backup_id", unique=True,
              postgresql_where=text("status IN ('QUEUED', 'VERIFYING')")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    backup_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("backups.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    status: Mapped[Status] = mapped_column(SqlEnum(Status), nullable=False, default=Status.QUEUED)

class Outbox(Base):
    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    backup_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("backups.id", ondelete="CASCADE"), index=True, nullable=False)
    task_name: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    sent_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
