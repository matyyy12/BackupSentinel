"""Create the durable verification result outbox."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "verification_result_outbox",
        sa.Column("verification_id", sa.UUID(), nullable=False),
        sa.Column("backup_id", sa.UUID(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("verification_id"),
    )
    op.create_index(
        "ix_verification_result_outbox_backup_id", "verification_result_outbox", ["backup_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_verification_result_outbox_backup_id", table_name="verification_result_outbox")
    op.drop_table("verification_result_outbox")
