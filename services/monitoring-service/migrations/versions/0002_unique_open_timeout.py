"""Allow only one unresolved timeout alert per backup."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_alerts_open_timeout_backup",
        "alerts",
        ["backup_id"],
        unique=True,
        postgresql_where=sa.text(
            "type = 'VERIFICATION_TIMEOUT' AND resolved_at IS NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_alerts_open_timeout_backup", table_name="alerts")
