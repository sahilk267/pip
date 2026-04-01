"""Add AI governance records, currency/tax compliance, and nurture trigger tables.

Revision ID: 0026
Revises: 0025
Create Date: 2026-03-31 14:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '0026'
down_revision = '0025'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ai_model_governance_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('model_name', sa.String(length=128), nullable=False),
        sa.Column('model_type', sa.String(length=64), nullable=False, server_default='negotiation'),
        sa.Column('model_version', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='draft'),
        sa.Column('approval_required', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('approved_by', sa.String(length=128), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rollback_to_version', sa.String(length=64), nullable=True),
        sa.Column('rollback_reason', sa.Text(), nullable=True),
        sa.Column('evaluation_metrics', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_by', sa.String(length=128), nullable=False, server_default='system'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_model_governance_records_model_name', 'ai_model_governance_records', ['model_name'])
    op.create_index('ix_ai_model_governance_records_model_type', 'ai_model_governance_records', ['model_type'])
    op.create_index('ix_ai_model_governance_records_model_version', 'ai_model_governance_records', ['model_version'])
    op.create_index('ix_ai_model_governance_records_status', 'ai_model_governance_records', ['status'])
    op.create_index('idx_ai_model_name_version', 'ai_model_governance_records', ['model_name', 'model_version'])

    op.create_table(
        'currency_exchange_rates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('base_currency', sa.String(length=8), nullable=False),
        sa.Column('quote_currency', sa.String(length=8), nullable=False),
        sa.Column('rate', sa.Float(), nullable=False),
        sa.Column('source', sa.String(length=64), nullable=False, server_default='manual'),
        sa.Column('as_of', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_by', sa.String(length=128), nullable=False, server_default='system'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_currency_exchange_rates_base_currency', 'currency_exchange_rates', ['base_currency'])
    op.create_index('ix_currency_exchange_rates_quote_currency', 'currency_exchange_rates', ['quote_currency'])
    op.create_index('ix_currency_exchange_rates_as_of', 'currency_exchange_rates', ['as_of'])
    op.create_index('idx_currency_pair_asof', 'currency_exchange_rates', ['base_currency', 'quote_currency', 'as_of'])

    op.create_table(
        'tax_compliance_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('region', sa.String(length=64), nullable=False),
        sa.Column('country_code', sa.String(length=8), nullable=False),
        sa.Column('tax_name', sa.String(length=64), nullable=False),
        sa.Column('tax_type', sa.String(length=16), nullable=False, server_default='exclusive'),
        sa.Column('tax_rate', sa.Float(), nullable=False),
        sa.Column('applies_to', sa.String(length=32), nullable=False, server_default='order'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('effective_from', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('effective_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_by', sa.String(length=128), nullable=False, server_default='system'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tax_compliance_rules_region', 'tax_compliance_rules', ['region'])
    op.create_index('ix_tax_compliance_rules_country_code', 'tax_compliance_rules', ['country_code'])
    op.create_index('ix_tax_compliance_rules_status', 'tax_compliance_rules', ['status'])
    op.create_index('idx_tax_rule_scope', 'tax_compliance_rules', ['country_code', 'applies_to', 'status'])

    op.create_table(
        'nurture_reengagement_triggers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=True),
        sa.Column('source_type', sa.String(length=32), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('campaign_type', sa.String(length=32), nullable=False, server_default='reengagement'),
        sa.Column('reason', sa.String(length=256), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='triggered'),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('triggered_by', sa.String(length=128), nullable=False, server_default='system'),
        sa.Column('triggered_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_nurture_reengagement_triggers_lead_id', 'nurture_reengagement_triggers', ['lead_id'])
    op.create_index('ix_nurture_reengagement_triggers_source_type', 'nurture_reengagement_triggers', ['source_type'])
    op.create_index('ix_nurture_reengagement_triggers_campaign_type', 'nurture_reengagement_triggers', ['campaign_type'])
    op.create_index('ix_nurture_reengagement_triggers_status', 'nurture_reengagement_triggers', ['status'])
    op.create_index('idx_nurture_source', 'nurture_reengagement_triggers', ['source_type', 'source_id', 'campaign_type'])


def downgrade() -> None:
    op.drop_table('nurture_reengagement_triggers')
    op.drop_table('tax_compliance_rules')
    op.drop_table('currency_exchange_rates')
    op.drop_table('ai_model_governance_records')
