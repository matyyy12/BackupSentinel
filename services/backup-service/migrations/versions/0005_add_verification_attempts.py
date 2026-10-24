"""Track each verification request independently of its eventual result."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "verifications",
        sa.Column("id", sa.UUID(), primary_key=True, nullable=False),
        sa.Column("backup_id", sa.UUID(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("status", postgresql.ENUM(
            "RECEIVED", "QUEUED", "VERIFYING", "VERIFIED", "FAILED",
            name="status", create_type=False,
        ), nullable=False),
        sa.ForeignKeyConstraint(["backup_id"], ["backups.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_verifications_backup_id", "verifications", ["backup_id"])
    # Historical results have no request timestamp; started_at is the closest available value.
    op.execute("""
        INSERT INTO verifications (id, backup_id, requested_at, status)
        SELECT verification_id, backup_id, started_at, status FROM backup_results
    """)
    # Preserve the latest outstanding request for each unfinished legacy backup.
    op.execute("""
        INSERT INTO verifications (id, backup_id, requested_at, status)
        SELECT DISTINCT ON (o.backup_id)
            (o.payload->>'verification_id')::uuid, o.backup_id, b.upload_date, 'QUEUED'::status
        FROM outbox o JOIN backups b ON b.id = o.backup_id
        WHERE o.task_name = 'verification_restore'
          AND b.status IN ('RECEIVED', 'QUEUED', 'VERIFYING')
          AND NOT EXISTS (
              SELECT 1 FROM verifications v WHERE v.id = (o.payload->>'verification_id')::uuid
          )
        ORDER BY o.backup_id, o.id DESC
        ON CONFLICT (id) DO NOTHING
    """)
    op.create_index(
        "uq_verifications_active_backup", "verifications", ["backup_id"], unique=True,
        postgresql_where=sa.text("status IN ('QUEUED', 'VERIFYING')"),
    )
    op.create_foreign_key(
        "fk_backup_results_verification", "backup_results", "verifications", ["verification_id"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_backup_results_verification", "backup_results", type_="foreignkey")
    op.drop_index("uq_verifications_active_backup", table_name="verifications")
    op.drop_index("ix_verifications_backup_id", table_name="verifications")
    op.drop_table("verifications")
