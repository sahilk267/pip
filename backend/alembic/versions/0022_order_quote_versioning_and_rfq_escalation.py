"""Order/quote versioning and RFQ escalation tables

Revision ID: 0022
Revises: 0021
Create Date: 2026-03-31 01:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0022'
down_revision = '0021'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'entity_version_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=32), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('snapshot', sa.JSON(), nullable=True, server_default='{}'),
        sa.Column('change_reason', sa.Text(), nullable=True),
        sa.Column('changed_by', sa.String(length=128), nullable=False, server_default='system'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entity_type', 'entity_id', 'version_number', name='uq_entity_version_records_key'),
    )
    op.create_index('ix_entity_version_records_id', 'entity_version_records', ['id'])
    op.create_index('ix_entity_version_records_entity_type', 'entity_version_records', ['entity_type'])
    op.create_index('ix_entity_version_records_entity_id', 'entity_version_records', ['entity_id'])

    op.create_table(
        'rfq_escalation_cases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('broadcast_id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=True),
        sa.Column('escalation_reason', sa.String(length=128), nullable=False, server_default='no_vendor_response'),
        sa.Column('severity', sa.String(length=32), nullable=False, server_default='warning'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='open'),
        sa.Column('escalated_by', sa.String(length=128), nullable=False, server_default='system'),
        sa.Column('metadata', sa.JSON(), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['broadcast_id'], ['rfq_broadcasts.id']),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_rfq_escalation_cases_id', 'rfq_escalation_cases', ['id'])
    op.create_index('ix_rfq_escalation_cases_broadcast_id', 'rfq_escalation_cases', ['broadcast_id'])
    op.create_index('ix_rfq_escalation_cases_lead_id', 'rfq_escalation_cases', ['lead_id'])
    op.create_index('ix_rfq_escalation_cases_status', 'rfq_escalation_cases', ['status'])


def downgrade() -> None:
    op.drop_index('ix_rfq_escalation_cases_status', table_name='rfq_escalation_cases')
    op.drop_index('ix_rfq_escalation_cases_lead_id', table_name='rfq_escalation_cases')
    op.drop_index('ix_rfq_escalation_cases_broadcast_id', table_name='rfq_escalation_cases')
    op.drop_index('ix_rfq_escalation_cases_id', table_name='rfq_escalation_cases')
    op.drop_table('rfq_escalation_cases')

    op.drop_index('ix_entity_version_records_entity_id', table_name='entity_version_records')
    op.drop_index('ix_entity_version_records_entity_type', table_name='entity_version_records')
    op.drop_index('ix_entity_version_records_id', table_name='entity_version_records')
    op.drop_table('entity_version_records')
