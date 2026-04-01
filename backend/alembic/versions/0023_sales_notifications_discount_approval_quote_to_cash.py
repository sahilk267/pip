"""Sales notifications, pricing approvals, and quote-to-cash records

Revision ID: 0023
Revises: 0022
Create Date: 2026-03-31 02:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0023'
down_revision = '0022'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'sales_rep_notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=True),
        sa.Column('entity_type', sa.String(length=32), nullable=False, server_default='rfq'),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('notification_type', sa.String(length=64), nullable=False, server_default='rfq_update'),
        sa.Column('priority', sa.String(length=16), nullable=False, server_default='medium'),
        sa.Column('channel', sa.String(length=32), nullable=False, server_default='inbox'),
        sa.Column('recipient', sa.String(length=128), nullable=False, server_default='sales'),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('metadata', sa.JSON(), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sales_rep_notifications_id', 'sales_rep_notifications', ['id'])
    op.create_index('ix_sales_rep_notifications_lead_id', 'sales_rep_notifications', ['lead_id'])
    op.create_index('ix_sales_rep_notifications_entity_type', 'sales_rep_notifications', ['entity_type'])
    op.create_index('ix_sales_rep_notifications_entity_id', 'sales_rep_notifications', ['entity_id'])
    op.create_index('ix_sales_rep_notifications_notification_type', 'sales_rep_notifications', ['notification_type'])

    op.create_table(
        'pricing_approval_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=16), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=True),
        sa.Column('requested_discount_pct', sa.Float(), nullable=True),
        sa.Column('requested_discount_amount', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(length=8), nullable=False, server_default='USD'),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('metadata', sa.JSON(), nullable=True, server_default='{}'),
        sa.Column('requested_by', sa.String(length=128), nullable=False, server_default='sales'),
        sa.Column('reviewed_by', sa.String(length=128), nullable=True),
        sa.Column('review_note', sa.Text(), nullable=True),
        sa.Column('approved_discount_pct', sa.Float(), nullable=True),
        sa.Column('approved_discount_amount', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_pricing_approval_requests_id', 'pricing_approval_requests', ['id'])
    op.create_index('ix_pricing_approval_requests_entity_type', 'pricing_approval_requests', ['entity_type'])
    op.create_index('ix_pricing_approval_requests_entity_id', 'pricing_approval_requests', ['entity_id'])
    op.create_index('ix_pricing_approval_requests_lead_id', 'pricing_approval_requests', ['lead_id'])
    op.create_index('ix_pricing_approval_requests_status', 'pricing_approval_requests', ['status'])

    op.create_table(
        'quote_to_cash_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('quote_id', sa.Integer(), nullable=True),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('lead_id', sa.Integer(), nullable=True),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='quoted'),
        sa.Column('payment_status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('invoice_number', sa.String(length=128), nullable=True),
        sa.Column('invoice_amount', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('currency', sa.String(length=8), nullable=False, server_default='USD'),
        sa.Column('external_system', sa.String(length=64), nullable=True),
        sa.Column('external_reference', sa.String(length=128), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True, server_default='{}'),
        sa.Column('created_by', sa.String(length=128), nullable=False, server_default='system'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.Column('invoiced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id']),
        sa.ForeignKeyConstraint(['order_id'], ['b2c_orders.id']),
        sa.ForeignKeyConstraint(['quote_id'], ['rfq_parsed_quotes.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('invoice_number', name='uq_quote_to_cash_records_invoice_number'),
    )
    op.create_index('ix_quote_to_cash_records_id', 'quote_to_cash_records', ['id'])
    op.create_index('ix_quote_to_cash_records_quote_id', 'quote_to_cash_records', ['quote_id'])
    op.create_index('ix_quote_to_cash_records_order_id', 'quote_to_cash_records', ['order_id'])
    op.create_index('ix_quote_to_cash_records_lead_id', 'quote_to_cash_records', ['lead_id'])
    op.create_index('ix_quote_to_cash_records_customer_id', 'quote_to_cash_records', ['customer_id'])
    op.create_index('ix_quote_to_cash_records_status', 'quote_to_cash_records', ['status'])
    op.create_index('ix_quote_to_cash_records_invoice_number', 'quote_to_cash_records', ['invoice_number'])


def downgrade() -> None:
    op.drop_index('ix_quote_to_cash_records_invoice_number', table_name='quote_to_cash_records')
    op.drop_index('ix_quote_to_cash_records_status', table_name='quote_to_cash_records')
    op.drop_index('ix_quote_to_cash_records_customer_id', table_name='quote_to_cash_records')
    op.drop_index('ix_quote_to_cash_records_lead_id', table_name='quote_to_cash_records')
    op.drop_index('ix_quote_to_cash_records_order_id', table_name='quote_to_cash_records')
    op.drop_index('ix_quote_to_cash_records_quote_id', table_name='quote_to_cash_records')
    op.drop_index('ix_quote_to_cash_records_id', table_name='quote_to_cash_records')
    op.drop_table('quote_to_cash_records')

    op.drop_index('ix_pricing_approval_requests_status', table_name='pricing_approval_requests')
    op.drop_index('ix_pricing_approval_requests_lead_id', table_name='pricing_approval_requests')
    op.drop_index('ix_pricing_approval_requests_entity_id', table_name='pricing_approval_requests')
    op.drop_index('ix_pricing_approval_requests_entity_type', table_name='pricing_approval_requests')
    op.drop_index('ix_pricing_approval_requests_id', table_name='pricing_approval_requests')
    op.drop_table('pricing_approval_requests')

    op.drop_index('ix_sales_rep_notifications_notification_type', table_name='sales_rep_notifications')
    op.drop_index('ix_sales_rep_notifications_entity_id', table_name='sales_rep_notifications')
    op.drop_index('ix_sales_rep_notifications_entity_type', table_name='sales_rep_notifications')
    op.drop_index('ix_sales_rep_notifications_lead_id', table_name='sales_rep_notifications')
    op.drop_index('ix_sales_rep_notifications_id', table_name='sales_rep_notifications')
    op.drop_table('sales_rep_notifications')
