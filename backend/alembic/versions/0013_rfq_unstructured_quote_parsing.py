"""rfq unstructured quote parsing"""
from alembic import op
import sqlalchemy as sa

revision = "0013_rfq_unstructured_quote_parsing"
down_revision = "0012_rfq_rate_limiting"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rfq_parsed_quotes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("response_id", sa.Integer(), sa.ForeignKey("rfq_vendor_responses.id"), nullable=False),
        sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("rfq_delivery_attempts.id"), nullable=False),
        sa.Column("vendor_id", sa.Integer(), sa.ForeignKey("vendors.id"), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default="USD"),
        sa.Column("unit_price", sa.Float(), nullable=True),
        sa.Column("total_price", sa.Float(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("minimum_order_quantity", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("parser_version", sa.String(length=32), nullable=False, server_default="rule-v1"),
        sa.Column("raw_excerpt", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_rfq_parsed_quotes_id", "rfq_parsed_quotes", ["id"])
    op.create_index("ix_rfq_parsed_quotes_response_id", "rfq_parsed_quotes", ["response_id"])
    op.create_index("ix_rfq_parsed_quotes_attempt_id", "rfq_parsed_quotes", ["attempt_id"])
    op.create_index("ix_rfq_parsed_quotes_vendor_id", "rfq_parsed_quotes", ["vendor_id"])


def downgrade() -> None:
    op.drop_index("ix_rfq_parsed_quotes_vendor_id", table_name="rfq_parsed_quotes")
    op.drop_index("ix_rfq_parsed_quotes_attempt_id", table_name="rfq_parsed_quotes")
    op.drop_index("ix_rfq_parsed_quotes_response_id", table_name="rfq_parsed_quotes")
    op.drop_index("ix_rfq_parsed_quotes_id", table_name="rfq_parsed_quotes")
    op.drop_table("rfq_parsed_quotes")
