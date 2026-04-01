"""crm communication tracking and follow-up reminders"""
from alembic import op
import sqlalchemy as sa

revision = "0005_crm_communications"
down_revision = "0004_lead_b2b_enrichment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crm_communications",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="email"),
        sa.Column("direction", sa.String(length=16), nullable=False, server_default="outbound"),
        sa.Column("subject", sa.String(length=256), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="logged"),
        sa.Column("follow_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("performed_by", sa.String(length=128), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_crm_communications_lead_id", "crm_communications", ["lead_id"])
    op.create_index("ix_crm_communications_customer_id", "crm_communications", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_crm_communications_customer_id", table_name="crm_communications")
    op.drop_index("ix_crm_communications_lead_id", table_name="crm_communications")
    op.drop_table("crm_communications")
