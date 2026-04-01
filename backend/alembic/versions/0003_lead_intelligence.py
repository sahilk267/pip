"""lead segmentation, attribution, and marketing fields"""
from alembic import op
import sqlalchemy as sa

revision = "0003_lead_intelligence"
down_revision = "0002_add_categorization_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "leads",
        sa.Column("segment", sa.String(length=64), nullable=False, server_default="unsegmented"),
    )
    op.add_column(
        "leads",
        sa.Column("attribution_channel", sa.String(length=128), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "leads",
        sa.Column("marketing_consent", sa.String(length=16), nullable=False, server_default="unknown"),
    )
    op.add_column(
        "leads",
        sa.Column("lead_score", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "leads",
        sa.Column("unsubscribed_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_column("leads", "unsubscribed_at")
    op.drop_column("leads", "lead_score")
    op.drop_column("leads", "marketing_consent")
    op.drop_column("leads", "attribution_channel")
    op.drop_column("leads", "segment")
