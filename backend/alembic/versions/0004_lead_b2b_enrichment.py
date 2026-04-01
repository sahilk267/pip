"""lead B2B enrichment fields"""
from alembic import op
import sqlalchemy as sa

revision = "0004_lead_b2b_enrichment"
down_revision = "0003_lead_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("revenue_estimate", sa.String(length=64), nullable=True))
    op.add_column("leads", sa.Column("company_size", sa.String(length=64), nullable=True))
    op.add_column("leads", sa.Column("decision_maker", sa.String(length=128), nullable=True))
    op.add_column("leads", sa.Column("b2b_score", sa.String(length=8), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "b2b_score")
    op.drop_column("leads", "decision_maker")
    op.drop_column("leads", "company_size")
    op.drop_column("leads", "revenue_estimate")

