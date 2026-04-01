"""Order shipping logistics integration

Revision ID: 0016
Revises: 0015
Create Date: 2026-03-31 21:05:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'order_shipping_shipments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=64), nullable=False, server_default='mockship'),
        sa.Column('service_level', sa.String(length=32), nullable=False, server_default='standard'),
        sa.Column('external_shipment_id', sa.String(length=128), nullable=False),
        sa.Column('tracking_number', sa.String(length=128), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='booked'),
        sa.Column('current_location', sa.String(length=128), nullable=True),
        sa.Column('estimated_delivery_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('shipping_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['order_id'], ['b2c_orders.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_order_shipping_shipments_order_id', 'order_shipping_shipments', ['order_id'])
    op.create_index('ix_order_shipping_shipments_tracking_number', 'order_shipping_shipments', ['tracking_number'])
    op.create_index('ix_order_shipping_shipments_external_shipment_id', 'order_shipping_shipments', ['external_shipment_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_order_shipping_shipments_external_shipment_id', table_name='order_shipping_shipments')
    op.drop_index('ix_order_shipping_shipments_tracking_number', table_name='order_shipping_shipments')
    op.drop_index('ix_order_shipping_shipments_order_id', table_name='order_shipping_shipments')
    op.drop_table('order_shipping_shipments')
