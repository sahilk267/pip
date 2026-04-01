"""RFQ human review for high-value deals

Revision ID: 0015
Revises: 0014
Create Date: 2026-03-31 18:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'rfq_negotiation_strategies',
        sa.Column('require_human_review_for_high_value', sa.Boolean(), nullable=False, server_default='0'),
    )
    op.add_column(
        'rfq_negotiation_strategies',
        sa.Column('high_value_threshold', sa.Float(), nullable=False, server_default='50000'),
    )

    op.create_table(
        'rfq_human_review_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('quote_id', sa.Integer(), nullable=False),
        sa.Column('attempt_id', sa.Integer(), nullable=False),
        sa.Column('vendor_id', sa.Integer(), nullable=False),
        sa.Column('estimated_total_value', sa.Float(), nullable=False),
        sa.Column('high_value_threshold', sa.Float(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('request_reason', sa.Text(), nullable=True),
        sa.Column('requested_by', sa.String(length=128), nullable=False, server_default='system'),
        sa.Column('reviewed_by', sa.String(length=128), nullable=True),
        sa.Column('review_note', sa.Text(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['attempt_id'], ['rfq_delivery_attempts.id']),
        sa.ForeignKeyConstraint(['quote_id'], ['rfq_parsed_quotes.id']),
        sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_rfq_human_review_requests_quote_id', 'rfq_human_review_requests', ['quote_id'])
    op.create_index('ix_rfq_human_review_requests_attempt_id', 'rfq_human_review_requests', ['attempt_id'])
    op.create_index('ix_rfq_human_review_requests_vendor_id', 'rfq_human_review_requests', ['vendor_id'])
    op.create_index('ix_rfq_human_review_requests_status', 'rfq_human_review_requests', ['status'])


def downgrade() -> None:
    op.drop_index('ix_rfq_human_review_requests_status', table_name='rfq_human_review_requests')
    op.drop_index('ix_rfq_human_review_requests_vendor_id', table_name='rfq_human_review_requests')
    op.drop_index('ix_rfq_human_review_requests_attempt_id', table_name='rfq_human_review_requests')
    op.drop_index('ix_rfq_human_review_requests_quote_id', table_name='rfq_human_review_requests')
    op.drop_table('rfq_human_review_requests')

    op.drop_column('rfq_negotiation_strategies', 'high_value_threshold')
    op.drop_column('rfq_negotiation_strategies', 'require_human_review_for_high_value')
