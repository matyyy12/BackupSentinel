"""rename backup table and add verification results

Revision ID: 41b78b17003b
Revises: 0001
Create Date: 2026-10-10 16:05:11.375885

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '41b78b17003b'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table("backup", "backups")
    op.create_table(
        "backup_results",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("backup_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "RECEIVED", "QUEUED", "VERIFYING", "VERIFIED", "FAILED",
                name="status", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["backup_id"], ["backups.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_backup_results_backup_id", "backup_results", ["backup_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_backup_results_backup_id", table_name="backup_results")
    op.drop_table("backup_results")
    op.rename_table("backups", "backup")
