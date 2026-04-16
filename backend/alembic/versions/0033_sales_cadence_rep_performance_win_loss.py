"""Add sales cadence, rep performance snapshots, and win/loss records.

Revision ID: 0033
Revises: 0032
Create Date: 2026-04-11 11:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '0033'
down_revision = '0032'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'sales_cadence_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sales_rep_id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('cadence_step', sa.String(length=64), nullable=False, server_default='initial_outreach'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='scheduled'),
        sa.Column('due_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['sales_rep_id'], ['sales_reps.id']),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sales_cadence_records_sales_rep_id', 'sales_cadence_records', ['sales_rep_id'])
    op.create_index('ix_sales_cadence_records_lead_id', 'sales_cadence_records', ['lead_id'])
    op.create_index('ix_sales_cadence_records_status', 'sales_cadence_records', ['status'])

    op.create_table(
        'rep_performance_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sales_rep_id', sa.Integer(), nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('opportunities_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('opportunities_won', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('win_rate', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('quota_target', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('revenue_achieved', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('forecast_revenue', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['sales_rep_id'], ['sales_reps.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_rep_performance_snapshots_sales_rep_id', 'rep_performance_snapshots', ['sales_rep_id'])

    op.create_table(
        'win_loss_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('opportunity_id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=True),
        sa.Column('sales_rep_id', sa.Integer(), nullable=True),
        sa.Column('outcome', sa.String(length=16), nullable=False),
        sa.Column('reason', sa.String(length=512), nullable=False),
        sa.Column('recorded_by', sa.String(length=128), nullable=False, server_default='system'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['opportunity_id'], ['market_opportunities.id']),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id']),
        sa.ForeignKeyConstraint(['sales_rep_id'], ['sales_reps.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_win_loss_records_opportunity_id', 'win_loss_records', ['opportunity_id'])
    op.create_index('ix_win_loss_records_outcome', 'win_loss_records', ['outcome'])


def downgrade() -> None:
    op.drop_table('win_loss_records')
    op.drop_table('rep_performance_snapshots')
    op.drop_table('sales_cadence_records')
