import datetime
import uuid
from enum import Enum
from sqlalchemy import UUID, String, DateTime, func, BigInteger, Enum as SqlEnum, ForeignKey
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

    verification_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    backup_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("backups.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[Status] = mapped_column(SqlEnum(Status), nullable=False, default=Status.RECEIVED)
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    backup: Mapped["Backup"] = relationship(back_populates="results")