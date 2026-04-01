"""Quote authenticity validation checks

Revision ID: 0020
Revises: 0019
Create Date: 2026-03-31 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0020'
down_revision = '0019'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'rfq_quote_authenticity_checks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('quote_id', sa.Integer(), nullable=False),
        sa.Column('attempt_id', sa.Integer(), nullable=False),
        sa.Column('vendor_id', sa.Integer(), nullable=False),
        sa.Column('broadcast_id', sa.Integer(), nullable=False),
        sa.Column('verdict', sa.String(length=16), nullable=False, server_default='pending'),
        sa.Column('flags', sa.JSON(), nullable=True, server_default='[]'),
        sa.Column('duplicate_of_quote_id', sa.Integer(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('performed_by', sa.String(length=128), nullable=False, server_default='system'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['attempt_id'], ['rfq_delivery_attempts.id']),
        sa.ForeignKeyConstraint(['broadcast_id'], ['rfq_broadcasts.id']),
        sa.ForeignKeyConstraint(['duplicate_of_quote_id'], ['rfq_parsed_quotes.id']),
        sa.ForeignKeyConstraint(['quote_id'], ['rfq_parsed_quotes.id']),
        sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_rfq_quote_authenticity_checks_id', 'rfq_quote_authenticity_checks', ['id'])
    op.create_index('ix_rfq_quote_authenticity_checks_quote_id', 'rfq_quote_authenticity_checks', ['quote_id'])
    op.create_index('ix_rfq_quote_authenticity_checks_attempt_id', 'rfq_quote_authenticity_checks', ['attempt_id'])
    op.create_index('ix_rfq_quote_authenticity_checks_vendor_id', 'rfq_quote_authenticity_checks', ['vendor_id'])
    op.create_index('ix_rfq_quote_authenticity_checks_broadcast_id', 'rfq_quote_authenticity_checks', ['broadcast_id'])


def downgrade() -> None:
    op.drop_index('ix_rfq_quote_authenticity_checks_broadcast_id', table_name='rfq_quote_authenticity_checks')
    op.drop_index('ix_rfq_quote_authenticity_checks_vendor_id', table_name='rfq_quote_authenticity_checks')
    op.drop_index('ix_rfq_quote_authenticity_checks_attempt_id', table_name='rfq_quote_authenticity_checks')
    op.drop_index('ix_rfq_quote_authenticity_checks_quote_id', table_name='rfq_quote_authenticity_checks')
    op.drop_index('ix_rfq_quote_authenticity_checks_id', table_name='rfq_quote_authenticity_checks')
    op.drop_table('rfq_quote_authenticity_checks')
