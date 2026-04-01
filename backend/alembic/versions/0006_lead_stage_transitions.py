"""lead stage transitions for sales funnel analytics"""
from alembic import op
import sqlalchemy as sa

revision = "0006_lead_stage_transitions"
down_revision = "0005_crm_communications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lead_stage_transitions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("from_stage", sa.String(length=64), nullable=True),
        sa.Column("to_stage", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=256), nullable=True),
        sa.Column("performed_by", sa.String(length=128), nullable=False, server_default="system"),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_lead_stage_transitions_lead_id", "lead_stage_transitions", ["lead_id"])


def downgrade() -> None:
    op.drop_index("ix_lead_stage_transitions_lead_id", table_name="lead_stage_transitions")
    op.drop_table("lead_stage_transitions")
