"""marketing intent fields for leads"""
from alembic import op
import sqlalchemy as sa

revision = "0007_marketing_intent"
down_revision = "0006_lead_stage_transitions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("marketing_intent_data", sa.JSON(), server_default="{}"))
    op.add_column("leads", sa.Column("marketing_intent_score", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("leads", sa.Column("last_intent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "last_intent_at")
    op.drop_column("leads", "marketing_intent_score")
    op.drop_column("leads", "marketing_intent_data")
