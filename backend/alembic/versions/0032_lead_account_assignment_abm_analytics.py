"""Add lead assignment and ABM analytics tables.

Revision ID: 0032
Revises: 0031
Create Date: 2026-04-02 09:35:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '0032'
down_revision = '0031'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'sales_reps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('email', sa.String(length=128), nullable=True),
        sa.Column('team', sa.String(length=64), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sales_reps_email', 'sales_reps', ['email'])

    op.create_table(
        'lead_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('sales_rep_id', sa.Integer(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('assignment_notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id']),
        sa.ForeignKeyConstraint(['sales_rep_id'], ['sales_reps.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_lead_assignments_lead_id', 'lead_assignments', ['lead_id'])
    op.create_index('ix_lead_assignments_sales_rep_id', 'lead_assignments', ['sales_rep_id'])

    op.create_table(
        'abm_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=True),
        sa.Column('region', sa.String(length=64), nullable=False, server_default='GLOBAL'),
        sa.Column('account_segment', sa.String(length=64), nullable=False),
        sa.Column('opportunity_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('expected_value', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['campaign_id'], ['ab_test_campaigns.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_abm_metrics_region', 'abm_metrics', ['region'])
    op.create_index('ix_abm_metrics_account_segment', 'abm_metrics', ['account_segment'])


def downgrade() -> None:
    op.drop_table('abm_metrics')
    op.drop_table('lead_assignments')
    op.drop_table('sales_reps')
