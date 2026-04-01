"""create initial schema"""
from alembic import op
import sqlalchemy as sa

revision = "0001_create_schema"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "vendors",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("normalized_name", sa.String(length=256), nullable=False, index=True),
        sa.Column("source", sa.String(length=128), server_default="manual"),
        sa.Column("contact_email", sa.String(length=128)),
        sa.Column("phone", sa.String(length=64)),
        sa.Column("industry", sa.String(length=128)),
        sa.Column("metadata", sa.JSON(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("normalized_name", sa.String(length=256), nullable=False, index=True),
        sa.Column("vendor_id", sa.Integer(), sa.ForeignKey("vendors.id"), nullable=True),
        sa.Column("sku", sa.String(length=128), index=True),
        sa.Column("attributes", sa.JSON(), server_default="{}"),
        sa.Column("price", sa.String(length=32)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("full_name", sa.String(length=256), nullable=False),
        sa.Column("email", sa.String(length=128)),
        sa.Column("phone", sa.String(length=64)),
        sa.Column("company", sa.String(length=256)),
        sa.Column("stage", sa.String(length=64), server_default="lead"),
        sa.Column("consented", sa.String(length=16), server_default="unknown"),
        sa.Column("source", sa.String(length=128)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "data_sources",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(length=128), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("last_synced", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Integer()),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("detail", sa.Text()),
        sa.Column("performed_by", sa.String(length=128), server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("email", sa.String(length=128)),
        sa.Column("phone", sa.String(length=64)),
        sa.Column("vendor_id", sa.Integer(), sa.ForeignKey("vendors.id"), nullable=True),
        sa.Column("account_status", sa.String(length=64), server_default="inactive"),
        sa.Column("consent_status", sa.String(length=32), server_default="unknown"),
        sa.Column("engagement_score", sa.Integer(), server_default="0"),
        sa.Column("last_engaged_at", sa.DateTime(timezone=True)),
        sa.Column("metadata", sa.String(), server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

def downgrade() -> None:
    op.drop_table("customers")
    op.drop_table("audit_logs")
    op.drop_table("data_sources")
    op.drop_table("leads")
    op.drop_index("ix_products_normalized_name", table_name="products")
    op.drop_table("products")
    op.drop_index("ix_vendors_normalized_name", table_name="vendors")
    op.drop_table("vendors")
