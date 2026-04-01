"""Post-deal feedback collection

Revision ID: 0017
Revises: 0016
Create Date: 2026-03-31 22:05:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'order_deal_feedback',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('actor_type', sa.String(length=32), nullable=False, server_default='customer'),
        sa.Column('actor_id', sa.Integer(), nullable=True),
        sa.Column('sentiment', sa.String(length=16), nullable=False, server_default='neutral'),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('feedback_text', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('created_by', sa.String(length=128), nullable=False, server_default='system'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['order_id'], ['b2c_orders.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_order_deal_feedback_order_id', 'order_deal_feedback', ['order_id'])
    op.create_index('ix_order_deal_feedback_actor_id', 'order_deal_feedback', ['actor_id'])


def downgrade() -> None:
    op.drop_index('ix_order_deal_feedback_actor_id', table_name='order_deal_feedback')
    op.drop_index('ix_order_deal_feedback_order_id', table_name='order_deal_feedback')
    op.drop_table('order_deal_feedback')
