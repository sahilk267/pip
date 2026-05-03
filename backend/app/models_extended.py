"""Extended models for analytics, scoring, invoices, and cost optimization."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

# ─── PRICE TREND ANALYTICS ───────────────────────────────────────────────

class PriceHistory(Base):
    """Historical price data for trending and benchmarking."""
    __tablename__ = 'price_history'

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False, index=True)
    product_name = Column(String(256), nullable=False, index=True)
    category = Column(String(128), index=True)
    unit_price = Column(Float, nullable=False)
    quantity = Column(Integer)
    currency = Column(String(8), default='USD')
    source = Column(String(64))  # 'quote', 'invoice', 'historical'
    quote_id = Column(Integer)  # Reference to RFQParsedQuote if applicable
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    vendor = relationship('Vendor')


class PriceBenchmark(Base):
    """Aggregated price benchmarks by category and vendor."""
    __tablename__ = 'price_benchmarks'

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(128), nullable=False, unique=True, index=True)
    avg_price = Column(Float, nullable=False)
    min_price = Column(Float, nullable=False)
    max_price = Column(Float, nullable=False)
    median_price = Column(Float, nullable=False)
    std_dev = Column(Float)
    sample_count = Column(Integer, default=0)
    best_vendor_id = Column(Integer, ForeignKey('vendors.id'))
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    best_vendor = relationship('Vendor')

# ─── SUPPLIER SCORING ────────────────────────────────────────────────────

class SupplierScore(Base):
    """Aggregated supplier performance scorecard."""
    __tablename__ = 'supplier_scores'

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False, unique=True, index=True)
    total_score = Column(Float, nullable=False, server_default='0.0')  # 0-100
    quality_score = Column(Float, server_default='0.0')  # On-time delivery, defect rate
    reliability_score = Column(Float, server_default='0.0')  # Response time, quote accuracy
    price_score = Column(Float, server_default='0.0')  # Competitiveness vs benchmark
    communication_score = Column(Float, server_default='0.0')  # Responsiveness
    compliance_score = Column(Float, server_default='0.0')  # Certifications, audits
    rating_metadata = Column(JSON, server_default='{}')  # {rfq_count, avg_response_hours, defect_rate, etc}
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    vendor = relationship('Vendor')


class SupplierRatingHistory(Base):
    """Historical supplier ratings for trend analysis."""
    __tablename__ = 'supplier_rating_history'

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False, index=True)
    total_score = Column(Float, nullable=False)
    event_type = Column(String(64))  # 'rfq_quote', 'delivery', 'payment', 'feedback'
    event_id = Column(Integer)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    vendor = relationship('Vendor')

# ─── INVOICE MANAGEMENT ──────────────────────────────────────────────────

class Invoice(Base):
    """Invoices generated from Purchase Orders."""
    __tablename__ = 'invoices'

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(64), nullable=False, unique=True, index=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False, index=True)
    po_number = Column(String(64), index=True)
    quote_id = Column(Integer)  # Reference to RFQParsedQuote
    total_amount = Column(Float, nullable=False)
    currency = Column(String(8), default='USD')
    status = Column(String(32), default='draft', index=True)  # draft, sent, paid, overdue, disputed
    invoice_date = Column(DateTime(timezone=True), server_default=func.now())
    due_date = Column(DateTime(timezone=True), nullable=True)
    paid_date = Column(DateTime(timezone=True), nullable=True)
    payment_terms = Column(String(64))  # 'Net 30', 'Net 60', etc
    notes = Column(Text)
    created_by = Column(String(128), default='system')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    vendor = relationship('Vendor')
    items = relationship('InvoiceItem', back_populates='invoice')


class InvoiceItem(Base):
    """Line items on an invoice."""
    __tablename__ = 'invoice_items'

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey('invoices.id'), nullable=False, index=True)
    description = Column(String(256), nullable=False)
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    invoice = relationship('Invoice', back_populates='items')

# ─── BULK RFQ TEMPLATES ──────────────────────────────────────────────────

class RFQTemplate(Base):
    """Reusable RFQ templates for bulk sourcing."""
    __tablename__ = 'rfq_templates'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(256), nullable=False)
    description = Column(Text)
    category = Column(String(128), nullable=False, index=True)
    created_by = Column(String(128), nullable=False, default='system')
    is_public = Column(Boolean, default=False)
    template_metadata = Column(JSON, server_default='{}')  # {industry, complexity, avg_lead_time}
    use_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    items = relationship('RFQTemplateItem', back_populates='template')


class RFQTemplateItem(Base):
    """Products/requirements in an RFQ template."""
    __tablename__ = 'rfq_template_items'

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey('rfq_templates.id'), nullable=False, index=True)
    product_name = Column(String(256), nullable=False)
    quantity = Column(Float, nullable=False)
    target_price = Column(Float, nullable=True)
    lead_time_days = Column(Integer, nullable=True)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    template = relationship('RFQTemplate', back_populates='items')

# ─── SMART VENDOR RECOMMENDATIONS ────────────────────────────────────────

class VendorRanking(Base):
    """Ranked vendors for specific product categories."""
    __tablename__ = 'vendor_rankings'

    id = Column(Integer, primary_key=True, index=True)
    product_category = Column(String(128), nullable=False, index=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False, index=True)
    rank = Column(Integer, nullable=False)  # 1 = best
    score = Column(Float, nullable=False)  # Composite score
    score_breakdown = Column(JSON, server_default='{}')  # {price: 25, quality: 30, reliability: 20, speed: 15, ...}
    recommendation_reason = Column(Text)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    vendor = relationship('Vendor')

# ─── COST OPTIMIZATION ───────────────────────────────────────────────────

class CostOpportunity(Base):
    """Identified cost savings opportunities."""
    __tablename__ = 'cost_opportunities'

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(256), nullable=False)
    category = Column(String(128), nullable=False, index=True)
    opportunity_type = Column(String(64))  # 'bulk_discount', 'alternative_vendor', 'consolidation', 'timing'
    current_cost = Column(Float, nullable=False)
    potential_savings = Column(Float, nullable=False)
    savings_percentage = Column(Float)  # (savings/current) * 100
    recommended_action = Column(Text)
    affected_vendors = Column(JSON, server_default='[]')  # list of vendor IDs
    status = Column(String(32), default='identified', index=True)  # identified, approved, implemented, rejected
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DiscountTier(Base):
    """Volume discount tiers offered by vendors."""
    __tablename__ = 'discount_tiers'

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False, index=True)
    product_category = Column(String(128), nullable=False, index=True)
    min_quantity = Column(Float, nullable=False)
    max_quantity = Column(Float, nullable=True)  # NULL = unlimited
    discount_percentage = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    effective_from = Column(DateTime(timezone=True), nullable=True)
    effective_to = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    vendor = relationship('Vendor')
