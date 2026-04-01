"""rfq vendor response analytics"""
from alembic import op
import sqlalchemy as sa

revision = "0011_rfq_vendor_responses"
down_revision = "0010_rfq_delivery_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rfq_vendor_responses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("rfq_delivery_attempts.id"), nullable=False),
        sa.Column("vendor_id", sa.Integer(), sa.ForeignKey("vendors.id"), nullable=False),
        sa.Column("response_status", sa.String(length=32), nullable=False, server_default="replied"),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("quoted_price", sa.Float(), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("recorded_by", sa.String(length=128), nullable=False, server_default="system"),
    )
    op.create_index("ix_rfq_vendor_responses_id", "rfq_vendor_responses", ["id"])
    op.create_index("ix_rfq_vendor_responses_attempt_id", "rfq_vendor_responses", ["attempt_id"])
    op.create_index("ix_rfq_vendor_responses_vendor_id", "rfq_vendor_responses", ["vendor_id"])


def downgrade() -> None:
    op.drop_index("ix_rfq_vendor_responses_vendor_id", table_name="rfq_vendor_responses")
    op.drop_index("ix_rfq_vendor_responses_attempt_id", table_name="rfq_vendor_responses")
    op.drop_index("ix_rfq_vendor_responses_id", table_name="rfq_vendor_responses")
    op.drop_table("rfq_vendor_responses")
