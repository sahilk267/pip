"""Vendor blacklist and opt-out rules

Revision ID: 0019
Revises: 0018
Create Date: 2026-03-31 23:40:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0019'
down_revision = '0018'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'vendor_opt_out_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vendor_id', sa.Integer(), nullable=False),
        sa.Column('channel', sa.String(length=32), nullable=False, server_default='all'),
        sa.Column('is_opted_out', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('rule_type', sa.String(length=16), nullable=False, server_default='opt_out'),
        sa.Column('reason', sa.String(length=512), nullable=True),
        sa.Column('created_by', sa.String(length=128), nullable=False, server_default='compliance'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('vendor_id', 'channel', 'rule_type', name='uq_vendor_opt_out_scope'),
    )
    op.create_index('ix_vendor_opt_out_rules_vendor_id', 'vendor_opt_out_rules', ['vendor_id'])
    op.create_index('ix_vendor_opt_out_rules_channel', 'vendor_opt_out_rules', ['channel'])


def downgrade() -> None:
    op.drop_index('ix_vendor_opt_out_rules_channel', table_name='vendor_opt_out_rules')
    op.drop_index('ix_vendor_opt_out_rules_vendor_id', table_name='vendor_opt_out_rules')
    op.drop_table('vendor_opt_out_rules')
