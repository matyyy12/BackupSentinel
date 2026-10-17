"""Create alerts and prevent duplicate verification alerts."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("backup_id", sa.UUID(), nullable=False),
        sa.Column("verification_id", sa.UUID(), nullable=True),
        sa.Column("type", sa.Enum("VERIFICATION_FAILED", "VERIFICATION_TIMEOUT", name="alerttype"), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("verification_id", "type", name="uq_alerts_verification_type"),
    )
    op.create_index("ix_alerts_backup_id", "alerts", ["backup_id"])


def downgrade() -> None:
    op.drop_index("ix_alerts_backup_id", table_name="alerts")
    op.drop_table("alerts")
    postgresql.ENUM(name="alerttype").drop(op.get_bind(), checkfirst=True)
