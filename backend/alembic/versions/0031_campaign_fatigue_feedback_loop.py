"""Add campaign fatigue and feedback loop tracking tables.

Revision ID: 0031
Revises: 0030
Create Date: 2026-04-02 09:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '0031'
down_revision = '0030'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'campaign_fatigue_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=True),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('outreach_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_outreach_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['campaign_id'], ['ab_test_campaigns.id']),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_campaign_fatigue_records_campaign_id', 'campaign_fatigue_records', ['campaign_id'])
    op.create_index('ix_campaign_fatigue_records_lead_id', 'campaign_fatigue_records', ['lead_id'])

    op.create_table(
        'feedback_loop_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=True),
        sa.Column('lead_id', sa.Integer(), nullable=True),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('event_value', sa.Float(), nullable=True),
        sa.Column('event_details', sa.Text(), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['campaign_id'], ['ab_test_campaigns.id']),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_feedback_loop_records_campaign_id', 'feedback_loop_records', ['campaign_id'])
    op.create_index('ix_feedback_loop_records_lead_id', 'feedback_loop_records', ['lead_id'])


def downgrade() -> None:
    op.drop_table('feedback_loop_records')
    op.drop_table('campaign_fatigue_records')
