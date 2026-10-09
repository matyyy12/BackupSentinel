import datetime
import uuid
from enum import Enum
from sqlalchemy import UUID, String, DateTime, func, BigInteger, Enum as SqlEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Status(Enum):
    RECEIVED = "RECEIVED"
    QUEUED = "QUEUED"
    VERIFYING = "VERIFYING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"

class Backup(Base):
    __tablename__ = "backup"
    id : Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, nullable=False, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    storage_key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[Status] = mapped_column(SqlEnum(Status), nullable=False, default=Status.RECEIVED)
    upload_date: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    postgres_version: Mapped[str] = mapped_column(String, nullable=False)
