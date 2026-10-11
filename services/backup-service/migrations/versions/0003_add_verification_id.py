"""Add a unique verification identifier to existing and new results.

Revision ID: 0003
Revises: 41b78b17003b
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "41b78b17003b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("backup_results", sa.Column("verification_id", sa.UUID(), nullable=True))
    op.execute("UPDATE backup_results SET verification_id = gen_random_uuid()")
    op.alter_column("backup_results", "verification_id", existing_type=sa.UUID(), nullable=False)
    op.create_unique_constraint(
        "uq_backup_results_verification_id", "backup_results", ["verification_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_backup_results_verification_id", "backup_results", type_="unique")
    op.drop_column("backup_results", "verification_id")
