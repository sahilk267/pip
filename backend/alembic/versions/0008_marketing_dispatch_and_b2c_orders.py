"""marketing dispatch and b2c order fulfillment"""
from alembic import op
import sqlalchemy as sa

revision = "0008_marketing_dispatch_and_b2c_orders"
down_revision = "0007_marketing_intent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketing_campaign_dispatches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False, server_default="mailchimp"),
        sa.Column("campaign_type", sa.String(length=32), nullable=False, server_default="nurture"),
        sa.Column("channel", sa.String(length=64), nullable=False, server_default="unknown"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True, server_default=sa.text("'{}'")),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_marketing_campaign_dispatches_id", "marketing_campaign_dispatches", ["id"])
    op.create_index("ix_marketing_campaign_dispatches_lead_id", "marketing_campaign_dispatches", ["lead_id"])

    op.create_table(
        "b2c_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("fulfillment_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="USD"),
        sa.Column("total_amount", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("order_items", sa.JSON(), nullable=True, server_default=sa.text("'[]'")),
        sa.Column("shipping_address", sa.JSON(), nullable=True, server_default=sa.text("'{}'")),
        sa.Column("tracking_number", sa.String(length=128), nullable=True),
        sa.Column("carrier", sa.String(length=64), nullable=True),
        sa.Column("external_order_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_b2c_orders_id", "b2c_orders", ["id"])
    op.create_index("ix_b2c_orders_customer_id", "b2c_orders", ["customer_id"])
    op.create_index("ix_b2c_orders_lead_id", "b2c_orders", ["lead_id"])

    op.create_table(
        "order_fulfillment_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("b2c_orders.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("location", sa.String(length=128), nullable=True),
        sa.Column("note", sa.String(length=256), nullable=True),
        sa.Column("tracking_number", sa.String(length=128), nullable=True),
        sa.Column("carrier", sa.String(length=64), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_order_fulfillment_events_id", "order_fulfillment_events", ["id"])
    op.create_index("ix_order_fulfillment_events_order_id", "order_fulfillment_events", ["order_id"])


def downgrade() -> None:
    op.drop_index("ix_order_fulfillment_events_order_id", table_name="order_fulfillment_events")
    op.drop_index("ix_order_fulfillment_events_id", table_name="order_fulfillment_events")
    op.drop_table("order_fulfillment_events")

    op.drop_index("ix_b2c_orders_lead_id", table_name="b2c_orders")
    op.drop_index("ix_b2c_orders_customer_id", table_name="b2c_orders")
    op.drop_index("ix_b2c_orders_id", table_name="b2c_orders")
    op.drop_table("b2c_orders")

    op.drop_index("ix_marketing_campaign_dispatches_lead_id", table_name="marketing_campaign_dispatches")
    op.drop_index("ix_marketing_campaign_dispatches_id", table_name="marketing_campaign_dispatches")
    op.drop_table("marketing_campaign_dispatches")
