"""Add A/B test campaign tables and consent record for GDPR plus lead scoring fields.

Revision ID: 0030
Revises: 0029
Create Date: 2026-03-31 20:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '0030'
down_revision = '0029'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ab_test_campaigns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=256), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('target_segment', sa.String(length=128), nullable=False, server_default='all'),
        sa.Column('variants', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index('ix_ab_test_campaigns_name', 'ab_test_campaigns', ['name'])

    op.create_table(
        'ab_test_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=True),
        sa.Column('variant', sa.String(length=64), nullable=False),
        sa.Column('outcome', sa.String(length=32), nullable=False),
        sa.Column('value', sa.Float(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['campaign_id'], ['ab_test_campaigns.id']),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ab_test_results_campaign_id', 'ab_test_results', ['campaign_id'])
    op.create_index('ix_ab_test_results_lead_id', 'ab_test_results', ['lead_id'])

    op.create_table(
        'consent_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('consent_type', sa.String(length=32), nullable=False, server_default='email'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='granted'),
        sa.Column('granted_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source', sa.String(length=64), nullable=False, server_default='system'),
        sa.Column('region', sa.String(length=32), nullable=False, server_default='GLOBAL'),
        sa.Column('policy_version', sa.String(length=64), nullable=False, server_default='1.0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_consent_records_lead_id', 'consent_records', ['lead_id'])
    op.create_index('ix_consent_records_status', 'consent_records', ['status'])


def downgrade() -> None:
    op.drop_table('consent_records')
    op.drop_table('ab_test_results')
    op.drop_table('ab_test_campaigns')
