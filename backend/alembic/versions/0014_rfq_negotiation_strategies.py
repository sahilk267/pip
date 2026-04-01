"""RFQ negotiation strategies and rounds

Revision ID: 0014
Revises: 0013
Create Date: 2026-03-31 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'rfq_negotiation_strategies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vendor_id', sa.Integer(), nullable=False),
        sa.Column('target_unit_price_reduction_pct', sa.Float(), server_default='10.0', nullable=False),
        sa.Column('target_moq_reduction_pct', sa.Float(), server_default='15.0', nullable=False),
        sa.Column('max_acceptable_lead_time_days', sa.Integer(), server_default='30', nullable=False),
        sa.Column('negotiation_rounds_limit', sa.Integer(), server_default='3', nullable=False),
        sa.Column('prior_success_rate', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('strategy_metadata', postgresql.JSON(astext_type=sa.Text()), server_default='{}', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('vendor_id', name='uq_negotiation_strategy_vendor'),
    )
    op.create_index(
        'ix_rfq_negotiation_strategies_vendor_id',
        'rfq_negotiation_strategies',
        ['vendor_id'],
        unique=True,
    )

    op.create_table(
        'rfq_negotiation_rounds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('quote_id', sa.Integer(), nullable=False),
        sa.Column('attempt_id', sa.Integer(), nullable=False),
        sa.Column('vendor_id', sa.Integer(), nullable=False),
        sa.Column('round_number', sa.Integer(), server_default='1', nullable=False),
        sa.Column('counter_offer_unit_price', sa.Float(), nullable=True),
        sa.Column('counter_offer_moq', sa.Integer(), nullable=True),
        sa.Column('counter_offer_lead_time_days', sa.Integer(), nullable=True),
        sa.Column('justification', sa.Text(), nullable=True),
        sa.Column('vendor_response', sa.Text(), nullable=True),
        sa.Column('status', sa.String(32), server_default='pending', nullable=False),
        sa.Column('generated_by', sa.String(128), server_default='system', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['attempt_id'], ['rfq_delivery_attempts.id'], ),
        sa.ForeignKeyConstraint(['quote_id'], ['rfq_parsed_quotes.id'], ),
        sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_rfq_negotiation_rounds_quote_id',
        'rfq_negotiation_rounds',
        ['quote_id'],
    )
    op.create_index(
        'ix_rfq_negotiation_rounds_attempt_id',
        'rfq_negotiation_rounds',
        ['attempt_id'],
    )
    op.create_index(
        'ix_rfq_negotiation_rounds_vendor_id',
        'rfq_negotiation_rounds',
        ['vendor_id'],
    )


def downgrade():
    op.drop_index(
        'ix_rfq_negotiation_rounds_vendor_id',
        table_name='rfq_negotiation_rounds',
    )
    op.drop_index(
        'ix_rfq_negotiation_rounds_attempt_id',
        table_name='rfq_negotiation_rounds',
    )
    op.drop_index(
        'ix_rfq_negotiation_rounds_quote_id',
        table_name='rfq_negotiation_rounds',
    )
    op.drop_table('rfq_negotiation_rounds')
    
    op.drop_index(
        'ix_rfq_negotiation_strategies_vendor_id',
        table_name='rfq_negotiation_strategies',
    )
    op.drop_table('rfq_negotiation_strategies')
