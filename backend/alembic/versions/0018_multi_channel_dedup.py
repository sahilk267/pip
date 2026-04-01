"""Multi-channel deduplication registry and order source channel

Revision ID: 0018
Revises: 0017
Create Date: 2026-03-31 23:05:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'b2c_orders',
        sa.Column('source_channel', sa.String(length=32), nullable=False, server_default='web'),
    )

    op.create_table(
        'multi_channel_dedup_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=64), nullable=False),
        sa.Column('dedup_key', sa.String(length=128), nullable=False),
        sa.Column('primary_channel', sa.String(length=64), nullable=False, server_default='unknown'),
        sa.Column('channels_seen', postgresql.JSON(astext_type=sa.Text()), nullable=True, server_default='[]'),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('duplicate_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_multi_channel_dedup_records_entity_type', 'multi_channel_dedup_records', ['entity_type'])
    op.create_index('ix_multi_channel_dedup_records_dedup_key', 'multi_channel_dedup_records', ['dedup_key'])


def downgrade() -> None:
    op.drop_index('ix_multi_channel_dedup_records_dedup_key', table_name='multi_channel_dedup_records')
    op.drop_index('ix_multi_channel_dedup_records_entity_type', table_name='multi_channel_dedup_records')
    op.drop_table('multi_channel_dedup_records')
    op.drop_column('b2c_orders', 'source_channel')
