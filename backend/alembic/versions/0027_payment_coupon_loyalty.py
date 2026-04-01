"""Add payment gateway, coupon/promotion, and loyalty tables for B2C checkout.

Revision ID: 0027
Revises: 0026
Create Date: 2026-03-31 16:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '0027'
down_revision = '0026'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('b2c_carts', sa.Column('coupon_code', sa.String(length=64), nullable=True))
    op.add_column('b2c_carts', sa.Column('coupon_discount_amount', sa.Float(), nullable=False, server_default='0.0'))
    op.add_column('b2c_carts', sa.Column('loyalty_discount_amount', sa.Float(), nullable=False, server_default='0.0'))

    op.create_table(
        'payment_gateway_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gateway_code', sa.String(length=64), nullable=False),
        sa.Column('display_name', sa.String(length=128), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('supported_currencies', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('configured_by', sa.String(length=128), nullable=False, server_default='system'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('gateway_code'),
    )
    op.create_index('ix_payment_gateway_configs_gateway_code', 'payment_gateway_configs', ['gateway_code'])
    op.create_index('ix_payment_gateway_configs_status', 'payment_gateway_configs', ['status'])

    op.create_table(
        'payment_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('gateway_code', sa.String(length=64), nullable=False),
        sa.Column('transaction_type', sa.String(length=32), nullable=False, server_default='payment_intent'),
        sa.Column('amount', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('currency', sa.String(length=8), nullable=False, server_default='USD'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='created'),
        sa.Column('external_payment_id', sa.String(length=128), nullable=True),
        sa.Column('external_reference', sa.String(length=256), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_by', sa.String(length=128), nullable=False, server_default='system'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['order_id'], ['b2c_orders.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_payment_transactions_order_id', 'payment_transactions', ['order_id'])
    op.create_index('ix_payment_transactions_gateway_code', 'payment_transactions', ['gateway_code'])
    op.create_index('ix_payment_transactions_status', 'payment_transactions', ['status'])
    op.create_index('ix_payment_transactions_external_payment_id', 'payment_transactions', ['external_payment_id'])

    op.create_table(
        'coupon_promotions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('promotion_type', sa.String(length=16), nullable=False, server_default='percent'),
        sa.Column('discount_value', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('min_order_amount', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('max_discount_amount', sa.Float(), nullable=True),
        sa.Column('usage_limit', sa.Integer(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_by', sa.String(length=128), nullable=False, server_default='marketing'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_index('ix_coupon_promotions_code', 'coupon_promotions', ['code'])
    op.create_index('ix_coupon_promotions_status', 'coupon_promotions', ['status'])

    op.create_table(
        'coupon_redemptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('coupon_id', sa.Integer(), nullable=False),
        sa.Column('cart_id', sa.Integer(), nullable=True),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('lead_id', sa.Integer(), nullable=True),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('discount_amount', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='applied'),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('redeemed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['coupon_id'], ['coupon_promotions.id']),
        sa.ForeignKeyConstraint(['cart_id'], ['b2c_carts.id']),
        sa.ForeignKeyConstraint(['order_id'], ['b2c_orders.id']),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id']),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_coupon_redemptions_coupon_id', 'coupon_redemptions', ['coupon_id'])
    op.create_index('ix_coupon_redemptions_cart_id', 'coupon_redemptions', ['cart_id'])
    op.create_index('ix_coupon_redemptions_order_id', 'coupon_redemptions', ['order_id'])
    op.create_index('ix_coupon_redemptions_status', 'coupon_redemptions', ['status'])

    op.create_table(
        'loyalty_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('lead_id', sa.Integer(), nullable=True),
        sa.Column('points_balance', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tier', sa.String(length=32), nullable=False, server_default='standard'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_loyalty_accounts_customer_id', 'loyalty_accounts', ['customer_id'])
    op.create_index('ix_loyalty_accounts_lead_id', 'loyalty_accounts', ['lead_id'])
    op.create_index('ix_loyalty_accounts_status', 'loyalty_accounts', ['status'])

    op.create_table(
        'loyalty_ledger_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('loyalty_account_id', sa.Integer(), nullable=False),
        sa.Column('entry_type', sa.String(length=16), nullable=False),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.Column('source_type', sa.String(length=32), nullable=False, server_default='order'),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('note', sa.String(length=256), nullable=True),
        sa.Column('created_by', sa.String(length=128), nullable=False, server_default='system'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['loyalty_account_id'], ['loyalty_accounts.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_loyalty_ledger_entries_loyalty_account_id', 'loyalty_ledger_entries', ['loyalty_account_id'])
    op.create_index('ix_loyalty_ledger_entries_source_id', 'loyalty_ledger_entries', ['source_id'])


def downgrade() -> None:
    op.drop_table('loyalty_ledger_entries')
    op.drop_table('loyalty_accounts')
    op.drop_table('coupon_redemptions')
    op.drop_table('coupon_promotions')
    op.drop_table('payment_transactions')
    op.drop_table('payment_gateway_configs')
    op.drop_column('b2c_carts', 'loyalty_discount_amount')
    op.drop_column('b2c_carts', 'coupon_discount_amount')
    op.drop_column('b2c_carts', 'coupon_code')
