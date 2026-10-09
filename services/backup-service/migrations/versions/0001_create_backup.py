"""Create backup table and status enum.

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backup",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Enum("RECEIVED", "QUEUED", "VERIFYING", "VERIFIED", "FAILED", name="status"), nullable=False),
        sa.Column("upload_date", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("postgres_version", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )


def downgrade() -> None:
    op.drop_table("backup")
    postgresql.ENUM(name="status").drop(op.get_bind(), checkfirst=True)
