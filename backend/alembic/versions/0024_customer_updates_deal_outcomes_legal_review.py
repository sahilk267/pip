"""Alembic migration 0024 – customer updates, deal outcomes, regional legal reviews."""
from alembic import op
import sqlalchemy as sa

revision = '0024'
down_revision = '0023'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'customer_update_notifications',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('order_id', sa.Integer, sa.ForeignKey('b2c_orders.id'), nullable=True),
        sa.Column('lead_id', sa.Integer, sa.ForeignKey('leads.id'), nullable=True),
        sa.Column('customer_id', sa.Integer, sa.ForeignKey('customers.id'), nullable=True),
        sa.Column('event_type', sa.String(64), nullable=False, server_default='order_status'),
        sa.Column('channel', sa.String(32), nullable=False, server_default='email'),
        sa.Column('recipient_address', sa.String(256)),
        sa.Column('subject', sa.String(256)),
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('status', sa.String(32), nullable=False, server_default='queued'),
        sa.Column('metadata', sa.JSON, server_default='{}'),
        sa.Column('dispatched_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_cust_update_order_id', 'customer_update_notifications', ['order_id'])
    op.create_index('ix_cust_update_lead_id', 'customer_update_notifications', ['lead_id'])
    op.create_index('ix_cust_update_event_type', 'customer_update_notifications', ['event_type'])
    op.create_index('ix_cust_update_status', 'customer_update_notifications', ['status'])

    op.create_table(
        'deal_outcome_records',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('entity_type', sa.String(16), nullable=False),
        sa.Column('entity_id', sa.Integer, nullable=False),
        sa.Column('lead_id', sa.Integer, sa.ForeignKey('leads.id'), nullable=True),
        sa.Column('customer_id', sa.Integer, sa.ForeignKey('customers.id'), nullable=True),
        sa.Column('outcome', sa.String(32), nullable=False),
        sa.Column('reason_code', sa.String(64), nullable=False, server_default='unspecified'),
        sa.Column('reason_detail', sa.Text),
        sa.Column('competitor', sa.String(256)),
        sa.Column('deal_value', sa.Float),
        sa.Column('currency', sa.String(8), nullable=False, server_default='USD'),
        sa.Column('recorded_by', sa.String(128), nullable=False, server_default='system'),
        sa.Column('metadata', sa.JSON, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_deal_outcome_entity_type', 'deal_outcome_records', ['entity_type'])
    op.create_index('ix_deal_outcome_entity_id', 'deal_outcome_records', ['entity_id'])
    op.create_index('ix_deal_outcome_outcome', 'deal_outcome_records', ['outcome'])
    op.create_index('ix_deal_outcome_reason_code', 'deal_outcome_records', ['reason_code'])

    op.create_table(
        'regional_legal_reviews',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('entity_type', sa.String(32), nullable=False),
        sa.Column('entity_id', sa.Integer, nullable=False),
        sa.Column('region', sa.String(64), nullable=False),
        sa.Column('regulation', sa.String(32), nullable=False),
        sa.Column('status', sa.String(32), nullable=False, server_default='pending'),
        sa.Column('checklist_items', sa.JSON, server_default='[]'),
        sa.Column('reviewer', sa.String(128), nullable=False, server_default='legal'),
        sa.Column('notes', sa.Text),
        sa.Column('reviewed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_legal_review_entity_type', 'regional_legal_reviews', ['entity_type'])
    op.create_index('ix_legal_review_entity_id', 'regional_legal_reviews', ['entity_id'])
    op.create_index('ix_legal_review_region', 'regional_legal_reviews', ['region'])
    op.create_index('ix_legal_review_regulation', 'regional_legal_reviews', ['regulation'])
    op.create_index('ix_legal_review_status', 'regional_legal_reviews', ['status'])


def downgrade() -> None:
    op.drop_table('regional_legal_reviews')
    op.drop_table('deal_outcome_records')
    op.drop_table('customer_update_notifications')
