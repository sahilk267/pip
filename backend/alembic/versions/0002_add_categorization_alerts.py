"""add categorization metadata and alert tracking"""
from alembic import op
import sqlalchemy as sa

revision = "0002_add_categorization_alerts"
down_revision = "0001_create_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vendors",
        sa.Column("category", sa.String(length=128), nullable=False, server_default="uncategorized"),
    )
    op.add_column(
        "vendors",
        sa.Column("category_confidence", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "vendors",
        sa.Column("categorization_source", sa.String(length=128), server_default="rule-engine"),
    )
    op.add_column(
        "vendors",
        sa.Column("category_notes", sa.Text()),
    )
    op.add_column(
        "vendors",
        sa.Column("last_categorized_at", sa.DateTime(timezone=True)),
    )

    op.add_column(
        "products",
        sa.Column("category", sa.String(length=128), nullable=False, server_default="uncategorized"),
    )
    op.add_column(
        "products",
        sa.Column("category_confidence", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "products",
        sa.Column("categorization_source", sa.String(length=128), server_default="rule-engine"),
    )
    op.add_column(
        "products",
        sa.Column("category_notes", sa.Text()),
    )
    op.add_column(
        "products",
        sa.Column("last_categorized_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False, server_default="warning"),
        sa.Column("detail", sa.Text()),
        sa.Column("category", sa.String(length=128), server_default="monitoring"),
        sa.Column("entity_type", sa.String(length=64)),
        sa.Column("entity_id", sa.Integer()),
        sa.Column("resolved", sa.Boolean(), server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_column("products", "last_categorized_at")
    op.drop_column("products", "category_notes")
    op.drop_column("products", "categorization_source")
    op.drop_column("products", "category_confidence")
    op.drop_column("products", "category")
    op.drop_column("vendors", "last_categorized_at")
    op.drop_column("vendors", "category_notes")
    op.drop_column("vendors", "categorization_source")
    op.drop_column("vendors", "category_confidence")
    op.drop_column("vendors", "category")
