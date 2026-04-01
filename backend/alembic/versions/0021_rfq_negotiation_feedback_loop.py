"""Negotiation AI feedback loop records

Revision ID: 0021
Revises: 0020
Create Date: 2026-03-31 00:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0021'
down_revision = '0020'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'rfq_negotiation_feedback',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('round_id', sa.Integer(), nullable=False),
        sa.Column('quote_id', sa.Integer(), nullable=False),
        sa.Column('attempt_id', sa.Integer(), nullable=False),
        sa.Column('vendor_id', sa.Integer(), nullable=False),
        sa.Column('outcome', sa.String(length=32), nullable=False, server_default='counter_offered'),
        sa.Column('realized_unit_price', sa.Float(), nullable=True),
        sa.Column('realized_moq', sa.Integer(), nullable=True),
        sa.Column('realized_lead_time_days', sa.Integer(), nullable=True),
        sa.Column('feedback_note', sa.Text(), nullable=True),
        sa.Column('recorded_by', sa.String(length=128), nullable=False, server_default='system'),
        sa.Column('metadata', sa.JSON(), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['attempt_id'], ['rfq_delivery_attempts.id']),
        sa.ForeignKeyConstraint(['quote_id'], ['rfq_parsed_quotes.id']),
        sa.ForeignKeyConstraint(['round_id'], ['rfq_negotiation_rounds.id']),
        sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('round_id', name='uq_rfq_negotiation_feedback_round_id'),
    )
    op.create_index('ix_rfq_negotiation_feedback_id', 'rfq_negotiation_feedback', ['id'])
    op.create_index('ix_rfq_negotiation_feedback_round_id', 'rfq_negotiation_feedback', ['round_id'])
    op.create_index('ix_rfq_negotiation_feedback_quote_id', 'rfq_negotiation_feedback', ['quote_id'])
    op.create_index('ix_rfq_negotiation_feedback_attempt_id', 'rfq_negotiation_feedback', ['attempt_id'])
    op.create_index('ix_rfq_negotiation_feedback_vendor_id', 'rfq_negotiation_feedback', ['vendor_id'])
    op.create_index('ix_rfq_negotiation_feedback_outcome', 'rfq_negotiation_feedback', ['outcome'])


def downgrade() -> None:
    op.drop_index('ix_rfq_negotiation_feedback_outcome', table_name='rfq_negotiation_feedback')
    op.drop_index('ix_rfq_negotiation_feedback_vendor_id', table_name='rfq_negotiation_feedback')
    op.drop_index('ix_rfq_negotiation_feedback_attempt_id', table_name='rfq_negotiation_feedback')
    op.drop_index('ix_rfq_negotiation_feedback_quote_id', table_name='rfq_negotiation_feedback')
    op.drop_index('ix_rfq_negotiation_feedback_round_id', table_name='rfq_negotiation_feedback')
    op.drop_index('ix_rfq_negotiation_feedback_id', table_name='rfq_negotiation_feedback')
    op.drop_table('rfq_negotiation_feedback')
