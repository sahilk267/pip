"""Add multi-language templates, external integrations, and escalation rules.

Revision ID: 0025
Revises: 0024
Create Date: 2026-03-31 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0025'
down_revision = '0024'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'message_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_code', sa.String(length=128), nullable=False),
        sa.Column('template_type', sa.String(length=32), nullable=False, server_default='notification'),
        sa.Column('default_locale', sa.String(length=8), nullable=False, server_default='en'),
        sa.Column('translations', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_by', sa.String(length=128), nullable=False, server_default='system'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('template_code'),
        sa.Index('idx_template_code_type', 'template_code', 'template_type'),
    )
    op.create_index('ix_message_templates_template_code', 'message_templates', ['template_code'])

    op.create_table(
        'external_integrations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('provider', sa.String(length=64), nullable=False, server_default='custom'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('entity_sync_types', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('api_endpoint', sa.String(length=512)),
        sa.Column('credentials_encrypted', sa.Text()),
        sa.Column('sync_direction', sa.String(length=32), nullable=False, server_default='bidirectional'),
        sa.Column('field_mappings', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('last_sync_at', sa.DateTime(timezone=True)),
        sa.Column('configured_by', sa.String(length=128), nullable=False, server_default='system'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_external_integrations_name', 'name'),
        sa.Index('ix_external_integrations_status', 'status'),
    )

    op.create_table(
        'integration_sync_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('integration_id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=32), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('sync_direction', sa.String(length=16), nullable=False),
        sa.Column('external_id', sa.String(length=256)),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('sync_payload', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('error_message', sa.Text()),
        sa.Column('synced_at', sa.DateTime(timezone=True)),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['integration_id'], ['external_integrations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_integration_sync_records_integration_id', 'integration_id'),
        sa.Index('ix_integration_sync_records_entity_type', 'entity_type'),
        sa.Index('idx_sync_entity', 'entity_type', 'entity_id', 'integration_id'),
        sa.Index('ix_integration_sync_records_status', 'status'),
    )

    op.create_table(
        'escalation_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rule_code', sa.String(length=128), nullable=False),
        sa.Column('rule_type', sa.String(length=32), nullable=False),
        sa.Column('entity_type', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('conditions', sa.JSON(), nullable=False),
        sa.Column('actions', sa.JSON(), nullable=False),
        sa.Column('notify_roles', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('sla_hours', sa.Integer()),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_by', sa.String(length=128), nullable=False, server_default='system'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('rule_code'),
        sa.Index('ix_escalation_rules_rule_code', 'rule_code'),
        sa.Index('ix_escalation_rules_status', 'status'),
    )

    op.create_table(
        'escalation_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rule_id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=32), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('trigger_reason', sa.String(length=256), nullable=False),
        sa.Column('severity', sa.String(length=16), nullable=False, server_default='warning'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='open'),
        sa.Column('actions_taken', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('resolution_notes', sa.Text()),
        sa.Column('resolved_at', sa.DateTime(timezone=True)),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('triggered_by', sa.String(length=128), nullable=False, server_default='system'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['rule_id'], ['escalation_rules.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_escalation_records_rule_id', 'rule_id'),
        sa.Index('ix_escalation_records_entity_type', 'entity_type'),
        sa.Index('ix_escalation_records_status', 'status'),
    )


def downgrade() -> None:
    op.drop_table('escalation_records')
    op.drop_table('escalation_rules')
    op.drop_table('integration_sync_records')
    op.drop_table('external_integrations')
    op.drop_table('message_templates')
