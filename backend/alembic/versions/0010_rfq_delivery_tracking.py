"""rfq delivery and failure tracking"""
from alembic import op
import sqlalchemy as sa

revision = "0010_rfq_delivery_tracking"
down_revision = "0009_b2c_cart_checkout"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rfq_broadcasts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=True),
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="email"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("performed_by", sa.String(length=128), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_rfq_broadcasts_id", "rfq_broadcasts", ["id"])
    op.create_index("ix_rfq_broadcasts_lead_id", "rfq_broadcasts", ["lead_id"])

    op.create_table(
        "rfq_delivery_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("broadcast_id", sa.Integer(), sa.ForeignKey("rfq_broadcasts.id"), nullable=False),
        sa.Column("vendor_id", sa.Integer(), sa.ForeignKey("vendors.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("external_ref", sa.String(length=128), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_rfq_delivery_attempts_id", "rfq_delivery_attempts", ["id"])
    op.create_index("ix_rfq_delivery_attempts_broadcast_id", "rfq_delivery_attempts", ["broadcast_id"])
    op.create_index("ix_rfq_delivery_attempts_vendor_id", "rfq_delivery_attempts", ["vendor_id"])


def downgrade() -> None:
    op.drop_index("ix_rfq_delivery_attempts_vendor_id", table_name="rfq_delivery_attempts")
    op.drop_index("ix_rfq_delivery_attempts_broadcast_id", table_name="rfq_delivery_attempts")
    op.drop_index("ix_rfq_delivery_attempts_id", table_name="rfq_delivery_attempts")
    op.drop_table("rfq_delivery_attempts")

    op.drop_index("ix_rfq_broadcasts_lead_id", table_name="rfq_broadcasts")
    op.drop_index("ix_rfq_broadcasts_id", table_name="rfq_broadcasts")
    op.drop_table("rfq_broadcasts")
