"""rfq rate limiting rules"""
from alembic import op
import sqlalchemy as sa

revision = "0012_rfq_rate_limiting"
down_revision = "0011_rfq_vendor_responses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rfq_rate_limit_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_key", sa.String(length=128), nullable=False),
        sa.Column("max_per_window", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("window_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_rfq_rate_limit_rules_id", "rfq_rate_limit_rules", ["id"])
    op.create_index("ix_rfq_rate_limit_rules_entity", "rfq_rate_limit_rules", ["entity_type", "entity_key"])


def downgrade() -> None:
    op.drop_index("ix_rfq_rate_limit_rules_entity", table_name="rfq_rate_limit_rules")
    op.drop_index("ix_rfq_rate_limit_rules_id", table_name="rfq_rate_limit_rules")
    op.drop_table("rfq_rate_limit_rules")
