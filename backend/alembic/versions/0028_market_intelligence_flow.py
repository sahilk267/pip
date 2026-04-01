"""Add Phase 3 market intelligence ingestion and scoring tables.

Revision ID: 0028
Revises: 0027
Create Date: 2026-03-31 17:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '0028'
down_revision = '0027'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'market_signal_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_name', sa.String(length=128), nullable=False),
        sa.Column('signal_type', sa.String(length=64), nullable=False),
        sa.Column('product_name', sa.String(length=256), nullable=False),
        sa.Column('region', sa.String(length=64), nullable=False, server_default='GLOBAL'),
        sa.Column('raw_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('sentiment', sa.String(length=16), nullable=False, server_default='neutral'),
        sa.Column('sentiment_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('price_drop_pct', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('demand_spike_pct', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('source_reliability_score', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('normalized_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('ingested_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('ingested_by', sa.String(length=128), nullable=False, server_default='market-intelligence'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_market_signal_events_source_name', 'market_signal_events', ['source_name'])
    op.create_index('ix_market_signal_events_signal_type', 'market_signal_events', ['signal_type'])
    op.create_index('ix_market_signal_events_product_name', 'market_signal_events', ['product_name'])
    op.create_index('ix_market_signal_events_region', 'market_signal_events', ['region'])

    op.create_table(
        'market_data_source_reliability',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_name', sa.String(length=128), nullable=False),
        sa.Column('reliability_score', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('sample_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_signal_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_name'),
    )
    op.create_index('ix_market_data_source_reliability_source_name', 'market_data_source_reliability', ['source_name'])

    op.create_table(
        'market_opportunities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('signal_event_id', sa.Integer(), nullable=False),
        sa.Column('product_name', sa.String(length=256), nullable=False),
        sa.Column('region', sa.String(length=64), nullable=False, server_default='GLOBAL'),
        sa.Column('opportunity_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('confidence_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='detected'),
        sa.Column('summary', sa.String(length=512), nullable=True),
        sa.Column('validation_notes', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['signal_event_id'], ['market_signal_events.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_market_opportunities_signal_event_id', 'market_opportunities', ['signal_event_id'])
    op.create_index('ix_market_opportunities_region', 'market_opportunities', ['region'])
    op.create_index('ix_market_opportunities_opportunity_score', 'market_opportunities', ['opportunity_score'])
    op.create_index('ix_market_opportunities_status', 'market_opportunities', ['status'])
    op.create_index('idx_market_product_region_score', 'market_opportunities', ['product_name', 'region', 'opportunity_score'])


def downgrade() -> None:
    op.drop_table('market_opportunities')
    op.drop_table('market_data_source_reliability')
    op.drop_table('market_signal_events')
