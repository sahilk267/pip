"""b2c cart and checkout tables"""
from alembic import op
import sqlalchemy as sa

revision = "0009_b2c_cart_checkout"
down_revision = "0008_marketing_dispatch_and_b2c_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "b2c_carts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=True),
        sa.Column("cart_token", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="USD"),
        sa.Column("total_amount", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("checked_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_b2c_carts_id", "b2c_carts", ["id"])
    op.create_index("ix_b2c_carts_customer_id", "b2c_carts", ["customer_id"])
    op.create_index("ix_b2c_carts_lead_id", "b2c_carts", ["lead_id"])
    op.create_index("ix_b2c_carts_cart_token", "b2c_carts", ["cart_token"])

    op.create_table(
        "b2c_cart_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cart_id", sa.Integer(), sa.ForeignKey("b2c_carts.id"), nullable=False),
        sa.Column("sku", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("unit_price", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("metadata", sa.JSON(), nullable=True, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_b2c_cart_items_id", "b2c_cart_items", ["id"])
    op.create_index("ix_b2c_cart_items_cart_id", "b2c_cart_items", ["cart_id"])


def downgrade() -> None:
    op.drop_index("ix_b2c_cart_items_cart_id", table_name="b2c_cart_items")
    op.drop_index("ix_b2c_cart_items_id", table_name="b2c_cart_items")
    op.drop_table("b2c_cart_items")

    op.drop_index("ix_b2c_carts_cart_token", table_name="b2c_carts")
    op.drop_index("ix_b2c_carts_lead_id", table_name="b2c_carts")
    op.drop_index("ix_b2c_carts_customer_id", table_name="b2c_carts")
    op.drop_index("ix_b2c_carts_id", table_name="b2c_carts")
    op.drop_table("b2c_carts")
