"""Add market opportunity validation transition history.

Revision ID: 0029
Revises: 0028
Create Date: 2026-03-31 19:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '0029'
down_revision = '0028'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'market_opportunity_validations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('opportunity_id', sa.Integer(), nullable=False),
        sa.Column('from_status', sa.String(length=32), nullable=False, server_default='detected'),
        sa.Column('to_status', sa.String(length=32), nullable=False),
        sa.Column('validator_type', sa.String(length=16), nullable=False, server_default='human'),
        sa.Column('validation_score', sa.Float(), nullable=True),
        sa.Column('rejection_reason', sa.String(length=256), nullable=True),
        sa.Column('validation_notes', sa.Text(), nullable=True),
        sa.Column('validated_by', sa.String(length=128), nullable=False, server_default='system'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['opportunity_id'], ['market_opportunities.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_market_opportunity_validations_opportunity_id', 'market_opportunity_validations', ['opportunity_id'])
    op.create_index('ix_market_opportunity_validations_to_status', 'market_opportunity_validations', ['to_status'])
    op.create_index('ix_market_opportunity_validations_created_at', 'market_opportunity_validations', ['created_at'])


def downgrade() -> None:
    op.drop_table('market_opportunity_validations')
