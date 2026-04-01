from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func, JSON, Text, Float, Boolean, Index
from sqlalchemy.orm import relationship

from .database import Base


class Vendor(Base):
    __tablename__ = 'vendors'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(256), nullable=False)
    normalized_name = Column(String(256), nullable=False, index=True)
    source = Column(String(128), default='manual')
    contact_email = Column(String(128))
    phone = Column(String(64))
    industry = Column(String(128))
    vendor_metadata = Column('metadata', JSON, server_default='{}')
    category = Column(String(128), nullable=False, server_default='uncategorized')
    category_confidence = Column(Float, nullable=False, server_default='0.0')
    categorization_source = Column(String(128), default='rule-engine')
    category_notes = Column(Text)
    last_categorized_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class VendorOptOutRule(Base):
    __tablename__ = 'vendor_opt_out_rules'

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False, index=True)
    channel = Column(String(32), nullable=False, server_default='all', index=True)
    is_opted_out = Column(Boolean, nullable=False, server_default='true')
    rule_type = Column(String(16), nullable=False, server_default='opt_out')  # opt_out / blacklist
    reason = Column(String(512))
    created_by = Column(String(128), nullable=False, server_default='compliance')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    vendor = relationship('Vendor')


class Product(Base):
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(256), nullable=False)
    normalized_name = Column(String(256), nullable=False, index=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=True)
    sku = Column(String(128), index=True)
    attributes = Column(JSON, server_default='{}')
    price = Column(String(32))
    category = Column(String(128), nullable=False, server_default='uncategorized')
    category_confidence = Column(Float, nullable=False, server_default='0.0')
    categorization_source = Column(String(128), default='rule-engine')
    category_notes = Column(Text)
    last_categorized_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    vendor = relationship('Vendor')


class Lead(Base):
    __tablename__ = 'leads'

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(256), nullable=False)
    email = Column(String(128))
    phone = Column(String(64))
    company = Column(String(256))
    # B2B lead intelligence enrichment (Phase 1 stub using CSV fixtures / optional API)
    revenue_estimate = Column(String(64))
    company_size = Column(String(64))
    decision_maker = Column(String(128))
    b2b_score = Column(String(8))
    stage = Column(String(64), default='lead')
    consented = Column(String(16), default='unknown')
    source = Column(String(128))
    segment = Column(String(64), nullable=False, server_default='unsegmented')
    attribution_channel = Column(String(128), nullable=False, server_default='unknown')
    marketing_consent = Column(String(16), nullable=False, server_default='unknown')
    marketing_intent_data = Column(JSON, server_default='{}')
    marketing_intent_score = Column(Integer, nullable=False, server_default='0')
    last_intent_at = Column(DateTime(timezone=True))
    lead_score = Column(Integer, nullable=False, server_default='0')
    unsubscribed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DataSource(Base):
    __tablename__ = 'data_sources'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), unique=True, nullable=False)
    description = Column(Text)
    last_synced = Column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = 'audit_logs'

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(Integer)
    action = Column(String(64), nullable=False)
    detail = Column(Text)
    performed_by = Column(String(128), default='system')
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Alert(Base):
    __tablename__ = 'alerts'

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(256), nullable=False)
    severity = Column(String(32), nullable=False, default='warning')
    detail = Column(Text)
    category = Column(String(128), default='monitoring')
    entity_type = Column(String(64))
    entity_id = Column(Integer)
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True))


class CRMCommunication(Base):
    __tablename__ = 'crm_communications'

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey('leads.id'), nullable=True, index=True)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=True, index=True)
    channel = Column(String(32), nullable=False, server_default='email')
    direction = Column(String(16), nullable=False, server_default='outbound')
    subject = Column(String(256))
    message = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, server_default='logged')
    follow_up_at = Column(DateTime(timezone=True))
    reminder_sent_at = Column(DateTime(timezone=True))
    performed_by = Column(String(128), nullable=False, server_default='system')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    lead = relationship('Lead')


class LeadStageTransition(Base):
    __tablename__ = 'lead_stage_transitions'

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey('leads.id'), nullable=False, index=True)
    from_stage = Column(String(64))
    to_stage = Column(String(64), nullable=False)
    reason = Column(String(256))
    performed_by = Column(String(128), nullable=False, server_default='system')
    changed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    lead = relationship('Lead')


class MarketingCampaignDispatch(Base):
    __tablename__ = 'marketing_campaign_dispatches'

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey('leads.id'), nullable=True, index=True)
    provider = Column(String(64), nullable=False, server_default='mailchimp')
    campaign_type = Column(String(32), nullable=False, server_default='nurture')
    channel = Column(String(64), nullable=False, server_default='unknown')
    status = Column(String(32), nullable=False, server_default='queued')
    external_id = Column(String(128))
    payload = Column(JSON, server_default='{}')
    error_detail = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    dispatched_at = Column(DateTime(timezone=True))
    last_synced_at = Column(DateTime(timezone=True))

    lead = relationship('Lead')


class B2COrder(Base):
    __tablename__ = 'b2c_orders'

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=True, index=True)
    lead_id = Column(Integer, ForeignKey('leads.id'), nullable=True, index=True)
    status = Column(String(32), nullable=False, server_default='created')
    fulfillment_status = Column(String(32), nullable=False, server_default='pending')
    currency = Column(String(8), nullable=False, server_default='USD')
    total_amount = Column(Float, nullable=False, server_default='0.0')
    order_items = Column(JSON, server_default='[]')
    source_channel = Column(String(32), nullable=False, server_default='web')
    shipping_address = Column(JSON, server_default='{}')
    tracking_number = Column(String(128))
    carrier = Column(String(64))
    external_order_id = Column(String(128))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    shipped_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))

    lead = relationship('Lead')


class OrderFulfillmentEvent(Base):
    __tablename__ = 'order_fulfillment_events'

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey('b2c_orders.id'), nullable=False, index=True)
    status = Column(String(32), nullable=False)
    location = Column(String(128))
    note = Column(String(256))
    tracking_number = Column(String(128))
    carrier = Column(String(64))
    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    order = relationship('B2COrder')


class OrderShippingShipment(Base):
    __tablename__ = 'order_shipping_shipments'

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey('b2c_orders.id'), nullable=False, index=True)
    provider = Column(String(64), nullable=False, server_default='mockship')
    service_level = Column(String(32), nullable=False, server_default='standard')
    external_shipment_id = Column(String(128), nullable=False, unique=True, index=True)
    tracking_number = Column(String(128), nullable=False, index=True)
    status = Column(String(32), nullable=False, server_default='booked')
    current_location = Column(String(128))
    estimated_delivery_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))
    shipping_cost = Column(Float, nullable=False, server_default='0.0')
    shipment_metadata = Column('metadata', JSON, server_default='{}')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    order = relationship('B2COrder')


class OrderDealFeedback(Base):
    __tablename__ = 'order_deal_feedback'

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey('b2c_orders.id'), nullable=False, index=True)
    actor_type = Column(String(32), nullable=False, server_default='customer')  # vendor/client/customer
    actor_id = Column(Integer, nullable=True, index=True)
    sentiment = Column(String(16), nullable=False, server_default='neutral')
    rating = Column(Integer, nullable=True)
    feedback_text = Column(Text)
    feedback_metadata = Column('metadata', JSON, server_default='{}')
    created_by = Column(String(128), nullable=False, server_default='system')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    order = relationship('B2COrder')


class SalesRepNotification(Base):
    __tablename__ = 'sales_rep_notifications'

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey('leads.id'), nullable=True, index=True)
    entity_type = Column(String(32), nullable=False, server_default='rfq', index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    notification_type = Column(String(64), nullable=False, server_default='rfq_update', index=True)
    priority = Column(String(16), nullable=False, server_default='medium')
    channel = Column(String(32), nullable=False, server_default='inbox')
    recipient = Column(String(128), nullable=False, server_default='sales')
    message = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, server_default='pending')
    notification_metadata = Column('metadata', JSON, server_default='{}')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    sent_at = Column(DateTime(timezone=True))

    lead = relationship('Lead')


class PricingApprovalRequest(Base):
    __tablename__ = 'pricing_approval_requests'

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(16), nullable=False, index=True)  # order/quote
    entity_id = Column(Integer, nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey('leads.id'), nullable=True, index=True)
    requested_discount_pct = Column(Float, nullable=True)
    requested_discount_amount = Column(Float, nullable=True)
    currency = Column(String(8), nullable=False, server_default='USD')
    reason = Column(Text)
    status = Column(String(32), nullable=False, server_default='pending', index=True)  # pending/approved/rejected
    request_metadata = Column('metadata', JSON, server_default='{}')
    requested_by = Column(String(128), nullable=False, server_default='sales')
    reviewed_by = Column(String(128))
    review_note = Column(Text)
    approved_discount_pct = Column(Float, nullable=True)
    approved_discount_amount = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    reviewed_at = Column(DateTime(timezone=True))

    lead = relationship('Lead')


class MultiChannelDedupRecord(Base):
    __tablename__ = 'multi_channel_dedup_records'

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(64), nullable=False, index=True)
    dedup_key = Column(String(128), nullable=False, index=True)
    primary_channel = Column(String(64), nullable=False, server_default='unknown')
    channels_seen = Column(JSON, server_default='[]')
    first_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    duplicate_count = Column(Integer, nullable=False, server_default='1')
    status = Column(String(32), nullable=False, server_default='active')


class B2CCart(Base):
    __tablename__ = 'b2c_carts'

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=True, index=True)
    lead_id = Column(Integer, ForeignKey('leads.id'), nullable=True, index=True)
    cart_token = Column(String(128), nullable=True, index=True)
    status = Column(String(32), nullable=False, server_default='active')
    currency = Column(String(8), nullable=False, server_default='USD')
    total_amount = Column(Float, nullable=False, server_default='0.0')
    coupon_code = Column(String(64))
    coupon_discount_amount = Column(Float, nullable=False, server_default='0.0')
    loyalty_discount_amount = Column(Float, nullable=False, server_default='0.0')
    checked_out_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class B2CCartItem(Base):
    __tablename__ = 'b2c_cart_items'

    id = Column(Integer, primary_key=True, index=True)
    cart_id = Column(Integer, ForeignKey('b2c_carts.id'), nullable=False, index=True)
    sku = Column(String(128), nullable=False)
    name = Column(String(256), nullable=False)
    unit_price = Column(Float, nullable=False, server_default='0.0')
    quantity = Column(Integer, nullable=False, server_default='1')
    item_metadata = Column('metadata', JSON, server_default='{}')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    cart = relationship('B2CCart')


class RFQBroadcast(Base):
    __tablename__ = 'rfq_broadcasts'

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey('leads.id'), nullable=True, index=True)
    channel = Column(String(32), nullable=False, server_default='email')
    status = Column(String(32), nullable=False, server_default='pending')
    message = Column(Text)
    performed_by = Column(String(128), nullable=False, server_default='system')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    lead = relationship('Lead')


class RFQDeliveryAttempt(Base):
    __tablename__ = 'rfq_delivery_attempts'

    id = Column(Integer, primary_key=True, index=True)
    broadcast_id = Column(Integer, ForeignKey('rfq_broadcasts.id'), nullable=False, index=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False, index=True)
    status = Column(String(32), nullable=False, server_default='queued')
    external_ref = Column(String(128))
    error_detail = Column(Text)
    attempted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    delivered_at = Column(DateTime(timezone=True))
    last_updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    broadcast = relationship('RFQBroadcast')
    vendor = relationship('Vendor')


class RFQVendorResponse(Base):
    __tablename__ = 'rfq_vendor_responses'

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey('rfq_delivery_attempts.id'), nullable=False, index=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False, index=True)
    response_status = Column(String(32), nullable=False, server_default='replied')
    response_text = Column(Text)
    quoted_price = Column(Float, nullable=True)
    responded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    recorded_by = Column(String(128), nullable=False, server_default='system')

    attempt = relationship('RFQDeliveryAttempt')
    vendor = relationship('Vendor')


class RFQRateLimitRule(Base):
    __tablename__ = 'rfq_rate_limit_rules'

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(32), nullable=False)   # 'lead', 'operator', 'global'
    entity_key = Column(String(128), nullable=False)   # lead_id as str, operator name, or 'global'
    max_per_window = Column(Integer, nullable=False, server_default='10')
    window_hours = Column(Integer, nullable=False, server_default='24')
    is_active = Column(Boolean, nullable=False, server_default='1')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RFQParsedQuote(Base):
    __tablename__ = 'rfq_parsed_quotes'

    id = Column(Integer, primary_key=True, index=True)
    response_id = Column(Integer, ForeignKey('rfq_vendor_responses.id'), nullable=False, index=True)
    attempt_id = Column(Integer, ForeignKey('rfq_delivery_attempts.id'), nullable=False, index=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False, index=True)
    currency = Column(String(16), nullable=False, server_default='USD')
    unit_price = Column(Float, nullable=True)
    total_price = Column(Float, nullable=True)
    quantity = Column(Integer, nullable=True)
    lead_time_days = Column(Integer, nullable=True)
    minimum_order_quantity = Column(Integer, nullable=True)
    confidence = Column(Float, nullable=False, server_default='0.0')
    parser_version = Column(String(32), nullable=False, server_default='rule-v1')
    raw_excerpt = Column(Text)
    parse_metadata = Column('metadata', JSON, server_default='{}')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    response = relationship('RFQVendorResponse')
    attempt = relationship('RFQDeliveryAttempt')
    vendor = relationship('Vendor')


class EntityVersionRecord(Base):
    __tablename__ = 'entity_version_records'

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(32), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    snapshot = Column(JSON, server_default='{}')
    change_reason = Column(Text)
    changed_by = Column(String(128), nullable=False, server_default='system')
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RFQNegotiationStrategy(Base):
    __tablename__ = 'rfq_negotiation_strategies'

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False, unique=True, index=True)
    target_unit_price_reduction_pct = Column(Float, nullable=False, server_default='10.0')
    target_moq_reduction_pct = Column(Float, nullable=False, server_default='15.0')
    max_acceptable_lead_time_days = Column(Integer, nullable=False, server_default='30')
    negotiation_rounds_limit = Column(Integer, nullable=False, server_default='3')
    prior_success_rate = Column(Float, nullable=False, server_default='0.0')
    require_human_review_for_high_value = Column(Boolean, nullable=False, server_default='0')
    high_value_threshold = Column(Float, nullable=False, server_default='50000')
    is_active = Column(Boolean, nullable=False, server_default='1')
    strategy_metadata = Column('strategy_metadata', JSON, server_default='{}')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    vendor = relationship('Vendor')


class RFQNegotiationRound(Base):
    __tablename__ = 'rfq_negotiation_rounds'

    id = Column(Integer, primary_key=True, index=True)
    quote_id = Column(Integer, ForeignKey('rfq_parsed_quotes.id'), nullable=False, index=True)
    attempt_id = Column(Integer, ForeignKey('rfq_delivery_attempts.id'), nullable=False, index=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False, index=True)
    round_number = Column(Integer, nullable=False, server_default='1')
    counter_offer_unit_price = Column(Float, nullable=True)
    counter_offer_moq = Column(Integer, nullable=True)
    counter_offer_lead_time_days = Column(Integer, nullable=True)
    justification = Column(Text)
    vendor_response = Column(Text)
    status = Column(String(32), nullable=False, server_default='pending')  # pending/accepted/rejected/counter_offered
    generated_by = Column(String(128), nullable=False, server_default='system')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    quote = relationship('RFQParsedQuote')
    attempt = relationship('RFQDeliveryAttempt')
    vendor = relationship('Vendor')


class RFQNegotiationFeedback(Base):
    __tablename__ = 'rfq_negotiation_feedback'

    id = Column(Integer, primary_key=True, index=True)
    round_id = Column(Integer, ForeignKey('rfq_negotiation_rounds.id'), nullable=False, unique=True, index=True)
    quote_id = Column(Integer, ForeignKey('rfq_parsed_quotes.id'), nullable=False, index=True)
    attempt_id = Column(Integer, ForeignKey('rfq_delivery_attempts.id'), nullable=False, index=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False, index=True)
    outcome = Column(String(32), nullable=False, server_default='counter_offered')  # accepted/rejected/counter_offered/expired
    realized_unit_price = Column(Float, nullable=True)
    realized_moq = Column(Integer, nullable=True)
    realized_lead_time_days = Column(Integer, nullable=True)
    feedback_note = Column(Text)
    recorded_by = Column(String(128), nullable=False, server_default='system')
    feedback_metadata = Column('metadata', JSON, server_default='{}')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    round = relationship('RFQNegotiationRound')
    quote = relationship('RFQParsedQuote')
    attempt = relationship('RFQDeliveryAttempt')
    vendor = relationship('Vendor')


class RFQQuoteAuthenticityCheck(Base):
    __tablename__ = 'rfq_quote_authenticity_checks'

    id = Column(Integer, primary_key=True, index=True)
    quote_id = Column(Integer, ForeignKey('rfq_parsed_quotes.id'), nullable=False, index=True)
    attempt_id = Column(Integer, ForeignKey('rfq_delivery_attempts.id'), nullable=False, index=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False, index=True)
    broadcast_id = Column(Integer, ForeignKey('rfq_broadcasts.id'), nullable=False, index=True)
    verdict = Column(String(16), nullable=False, server_default='pending')  # authentic/suspicious/rejected/pending
    flags = Column(JSON, server_default='[]')  # list of triggered flag name strings
    duplicate_of_quote_id = Column(Integer, ForeignKey('rfq_parsed_quotes.id'), nullable=True)
    confidence_score = Column(Float, nullable=False, server_default='0.0')
    performed_by = Column(String(128), nullable=False, server_default='system')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    quote = relationship('RFQParsedQuote', foreign_keys=[quote_id])
    duplicate_of = relationship('RFQParsedQuote', foreign_keys=[duplicate_of_quote_id])
    attempt = relationship('RFQDeliveryAttempt')
    vendor = relationship('Vendor')
    broadcast = relationship('RFQBroadcast')


class RFQEscalationCase(Base):
    __tablename__ = 'rfq_escalation_cases'

    id = Column(Integer, primary_key=True, index=True)
    broadcast_id = Column(Integer, ForeignKey('rfq_broadcasts.id'), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey('leads.id'), nullable=True, index=True)
    escalation_reason = Column(String(128), nullable=False, server_default='no_vendor_response')
    severity = Column(String(32), nullable=False, server_default='warning')
    status = Column(String(32), nullable=False, server_default='open')  # open/acknowledged/resolved
    escalated_by = Column(String(128), nullable=False, server_default='system')
    escalation_metadata = Column('metadata', JSON, server_default='{}')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    broadcast = relationship('RFQBroadcast')
    lead = relationship('Lead')


class QuoteToCashRecord(Base):
    __tablename__ = 'quote_to_cash_records'

    id = Column(Integer, primary_key=True, index=True)
    quote_id = Column(Integer, ForeignKey('rfq_parsed_quotes.id'), nullable=True, index=True)
    order_id = Column(Integer, ForeignKey('b2c_orders.id'), nullable=True, index=True)
    lead_id = Column(Integer, ForeignKey('leads.id'), nullable=True, index=True)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=True, index=True)
    status = Column(String(32), nullable=False, server_default='quoted', index=True)
    payment_status = Column(String(32), nullable=False, server_default='pending')
    invoice_number = Column(String(128), nullable=True, unique=True, index=True)
    invoice_amount = Column(Float, nullable=False, server_default='0.0')
    currency = Column(String(8), nullable=False, server_default='USD')
    external_system = Column(String(64), nullable=True)
    external_reference = Column(String(128), nullable=True)
    qtc_metadata = Column('metadata', JSON, server_default='{}')
    created_by = Column(String(128), nullable=False, server_default='system')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    invoiced_at = Column(DateTime(timezone=True))
    paid_at = Column(DateTime(timezone=True))
    synced_at = Column(DateTime(timezone=True))

    quote = relationship('RFQParsedQuote')
    order = relationship('B2COrder')
    lead = relationship('Lead')
    customer = relationship('Customer')


class RFQHumanReviewRequest(Base):
    __tablename__ = 'rfq_human_review_requests'

    id = Column(Integer, primary_key=True, index=True)
    quote_id = Column(Integer, ForeignKey('rfq_parsed_quotes.id'), nullable=False, index=True)
    attempt_id = Column(Integer, ForeignKey('rfq_delivery_attempts.id'), nullable=False, index=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False, index=True)
    estimated_total_value = Column(Float, nullable=False)
    high_value_threshold = Column(Float, nullable=False)
    status = Column(String(32), nullable=False, server_default='pending')  # pending/approved/rejected
    request_reason = Column(Text)
    requested_by = Column(String(128), nullable=False, server_default='system')
    reviewed_by = Column(String(128), nullable=True)
    review_note = Column(Text)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    quote = relationship('RFQParsedQuote')
    attempt = relationship('RFQDeliveryAttempt')
    vendor = relationship('Vendor')


class CustomerUpdateNotification(Base):
    """Automated status communications dispatched to customers/leads on order events."""
    __tablename__ = 'customer_update_notifications'

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey('b2c_orders.id'), nullable=True, index=True)
    lead_id = Column(Integer, ForeignKey('leads.id'), nullable=True, index=True)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=True, index=True)
    event_type = Column(String(64), nullable=False, server_default='order_status', index=True)
    channel = Column(String(32), nullable=False, server_default='email')
    recipient_address = Column(String(256))
    subject = Column(String(256))
    message = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, server_default='queued', index=True)
    update_metadata = Column('metadata', JSON, server_default='{}')
    dispatched_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    order = relationship('B2COrder')
    lead = relationship('Lead')
    customer = relationship('Customer')


class DealOutcomeRecord(Base):
    """Win/loss/abandoned outcome with reason code for every closed deal."""
    __tablename__ = 'deal_outcome_records'

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(16), nullable=False, index=True)  # order / rfq
    entity_id = Column(Integer, nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey('leads.id'), nullable=True, index=True)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=True, index=True)
    outcome = Column(String(32), nullable=False, index=True)   # won / lost / abandoned / expired
    reason_code = Column(String(64), nullable=False, server_default='unspecified', index=True)
    reason_detail = Column(Text)
    competitor = Column(String(256))
    deal_value = Column(Float, nullable=True)
    currency = Column(String(8), nullable=False, server_default='USD')
    recorded_by = Column(String(128), nullable=False, server_default='system')
    outcome_metadata = Column('metadata', JSON, server_default='{}')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    lead = relationship('Lead')
    customer = relationship('Customer')


class RegionalLegalReview(Base):
    """Structured legal review checklist record per entity, region, and regulation."""
    __tablename__ = 'regional_legal_reviews'

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(32), nullable=False, index=True)  # order / rfq / vendor / campaign
    entity_id = Column(Integer, nullable=False, index=True)
    region = Column(String(64), nullable=False, index=True)       # IN / EU / US / GLOBAL
    regulation = Column(String(32), nullable=False, index=True)   # GDPR / DPDP / CCPA / PCI_DSS
    status = Column(String(32), nullable=False, server_default='pending', index=True)  # pending/approved/flagged/waived
    checklist_items = Column(JSON, server_default='[]')           # [{id, label, status, notes}]
    reviewer = Column(String(128), nullable=False, server_default='legal')
    notes = Column(Text)
    reviewed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class MessageTemplate(Base):
    """Translatable message templates for customer updates, sales notifications, marketing campaigns."""
    __tablename__ = 'message_templates'

    id = Column(Integer, primary_key=True, index=True)
    template_code = Column(String(128), nullable=False, unique=True, index=True)
    template_type = Column(String(32), nullable=False, server_default='notification')  # notification/email/sms/marketing
    default_locale = Column(String(8), nullable=False, server_default='en')
    translations = Column(JSON, server_default='{}')  # { locale: { subject, body, variables[] } }
    usage_metadata = Column('metadata', JSON, server_default='{}')  # context, category, version
    created_by = Column(String(128), nullable=False, server_default='system')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (Index('idx_template_code_type', 'template_code', 'template_type'),)


class ExternalIntegration(Base):
    """Configured external system integration (Salesforce, HubSpot, ERP, etc.)."""
    __tablename__ = 'external_integrations'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False, index=True)  # salesforce, hubspot, sap_erp, etc.
    provider = Column(String(64), nullable=False, server_default='custom')  # salesforce/hubspot/sap/custom
    status = Column(String(32), nullable=False, server_default='active', index=True)  # active/paused/archived
    entity_sync_types = Column(JSON, server_default='[]')  # [order, deal, rfq, lead, customer]
    api_endpoint = Column(String(512))
    credentials_encrypted = Column(Text)  # JSON encrypted with fernet
    sync_direction = Column(String(32), nullable=False, server_default='bidirectional')  # outbound/inbound/bidirectional
    field_mappings = Column(JSON, server_default='{}')  # { local_field: external_field }
    integration_metadata = Column('metadata', JSON, server_default='{}')
    last_sync_at = Column(DateTime(timezone=True))
    configured_by = Column(String(128), nullable=False, server_default='system')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class IntegrationSyncRecord(Base):
    """History of syncs between local systems and external integrations."""
    __tablename__ = 'integration_sync_records'

    id = Column(Integer, primary_key=True, index=True)
    integration_id = Column(Integer, ForeignKey('external_integrations.id'), nullable=False, index=True)
    entity_type = Column(String(32), nullable=False, index=True)  # order / deal / rfq / lead
    entity_id = Column(Integer, nullable=False, index=True)
    sync_direction = Column(String(16), nullable=False)  # outbound / inbound
    external_id = Column(String(256))
    status = Column(String(32), nullable=False, server_default='pending', index=True)  # pending/synced/failed/skipped
    sync_payload = Column(JSON, server_default='{}')
    error_message = Column(Text)
    synced_at = Column(DateTime(timezone=True))
    sync_metadata = Column('metadata', JSON, server_default='{}')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    integration = relationship('ExternalIntegration')

    __table_args__ = (Index('idx_sync_entity', 'entity_type', 'entity_id', 'integration_id'),)


class EscalationRule(Base):
    """Defines conditions and actions for automated escalation of orders, deals, and other entities."""
    __tablename__ = 'escalation_rules'

    id = Column(Integer, primary_key=True, index=True)
    rule_code = Column(String(128), nullable=False, unique=True, index=True)
    rule_type = Column(String(32), nullable=False)  # order_delay / no_response / price_deviation / compliance_risk / etc.
    entity_type = Column(String(32), nullable=False)  # order / rfq / deal / lead
    status = Column(String(32), nullable=False, server_default='active', index=True)
    priority = Column(Integer, nullable=False, server_default='5')  # 1=highest, 10=lowest
    conditions = Column(JSON, nullable=False)  # [{field, operator, value}] - AND/OR logic
    actions = Column(JSON, nullable=False)  # [{action_type, target, message, metadata}]
    notify_roles = Column(JSON, server_default='[]')  # [sales, manager, compliance]
    sla_hours = Column(Integer)
    rule_metadata = Column('metadata', JSON, server_default='{}')
    created_by = Column(String(128), nullable=False, server_default='system')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EscalationRecord(Base):
    """History of escalation rule triggers and outcomes."""
    __tablename__ = 'escalation_records'

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, ForeignKey('escalation_rules.id'), nullable=False, index=True)
    entity_type = Column(String(32), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    trigger_reason = Column(String(256), nullable=False)
    severity = Column(String(16), nullable=False, server_default='warning')  # info/warning/critical
    status = Column(String(32), nullable=False, server_default='open', index=True)  # open/acknowledged/resolved/escalated
    actions_taken = Column(JSON, server_default='[]')  # [{action, timestamp, performed_by}]
    resolution_notes = Column(Text)
    resolved_at = Column(DateTime(timezone=True))
    escalation_metadata = Column('metadata', JSON, server_default='{}')
    triggered_by = Column(String(128), nullable=False, server_default='system')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    rule = relationship('EscalationRule')


class AIModelGovernanceRecord(Base):
    """Versioning, approvals, and rollback records for AI models used in automation flows."""
    __tablename__ = 'ai_model_governance_records'

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(128), nullable=False, index=True)
    model_type = Column(String(64), nullable=False, server_default='negotiation', index=True)
    model_version = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, server_default='draft', index=True)  # draft/approved/rejected/rolled_back
    approval_required = Column(Boolean, nullable=False, server_default='1')
    approved_by = Column(String(128))
    approved_at = Column(DateTime(timezone=True))
    rollback_to_version = Column(String(64))
    rollback_reason = Column(Text)
    evaluation_metrics = Column(JSON, server_default='{}')
    governance_metadata = Column('metadata', JSON, server_default='{}')
    created_by = Column(String(128), nullable=False, server_default='system')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_ai_model_name_version', 'model_name', 'model_version'),
    )


class CurrencyExchangeRate(Base):
    """Exchange rates used for multi-currency order and quote calculations."""
    __tablename__ = 'currency_exchange_rates'

    id = Column(Integer, primary_key=True, index=True)
    base_currency = Column(String(8), nullable=False, index=True)
    quote_currency = Column(String(8), nullable=False, index=True)
    rate = Column(Float, nullable=False)
    source = Column(String(64), nullable=False, server_default='manual')
    as_of = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    rate_metadata = Column('metadata', JSON, server_default='{}')
    created_by = Column(String(128), nullable=False, server_default='system')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_currency_pair_asof', 'base_currency', 'quote_currency', 'as_of'),
    )


class TaxComplianceRule(Base):
    """Tax compliance rule per region/country and entity type."""
    __tablename__ = 'tax_compliance_rules'

    id = Column(Integer, primary_key=True, index=True)
    region = Column(String(64), nullable=False, index=True)
    country_code = Column(String(8), nullable=False, index=True)
    tax_name = Column(String(64), nullable=False)
    tax_type = Column(String(16), nullable=False, server_default='exclusive')  # inclusive/exclusive
    tax_rate = Column(Float, nullable=False)
    applies_to = Column(String(32), nullable=False, server_default='order')  # order/quote/cart
    status = Column(String(32), nullable=False, server_default='active', index=True)
    effective_from = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    effective_to = Column(DateTime(timezone=True))
    rule_metadata = Column('metadata', JSON, server_default='{}')
    created_by = Column(String(128), nullable=False, server_default='system')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_tax_rule_scope', 'country_code', 'applies_to', 'status'),
    )


class NurtureReengagementTrigger(Base):
    """Recorded trigger events for nurture or re-engagement campaigns."""
    __tablename__ = 'nurture_reengagement_triggers'

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey('leads.id'), nullable=True, index=True)
    source_type = Column(String(32), nullable=False, index=True)  # abandoned_cart/deal_outcome/manual
    source_id = Column(Integer, nullable=False, index=True)
    campaign_type = Column(String(32), nullable=False, server_default='reengagement', index=True)
    reason = Column(String(256), nullable=False)
    status = Column(String(32), nullable=False, server_default='triggered', index=True)
    trigger_metadata = Column('metadata', JSON, server_default='{}')
    triggered_by = Column(String(128), nullable=False, server_default='system')
    triggered_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    lead = relationship('Lead')

    __table_args__ = (
        Index('idx_nurture_source', 'source_type', 'source_id', 'campaign_type'),
    )


class PaymentGatewayConfig(Base):
    """B2C payment gateway configuration (Stripe, Razorpay, etc.)."""
    __tablename__ = 'payment_gateway_configs'

    id = Column(Integer, primary_key=True, index=True)
    gateway_code = Column(String(64), nullable=False, unique=True, index=True)
    display_name = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False, server_default='active', index=True)
    supported_currencies = Column(JSON, server_default='[]')
    config_metadata = Column('metadata', JSON, server_default='{}')
    configured_by = Column(String(128), nullable=False, server_default='system')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PaymentTransaction(Base):
    """Payment transaction lifecycle for B2C orders."""
    __tablename__ = 'payment_transactions'

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey('b2c_orders.id'), nullable=False, index=True)
    gateway_code = Column(String(64), nullable=False, index=True)
    transaction_type = Column(String(32), nullable=False, server_default='payment_intent')
    amount = Column(Float, nullable=False, server_default='0.0')
    currency = Column(String(8), nullable=False, server_default='USD')
    status = Column(String(32), nullable=False, server_default='created', index=True)
    external_payment_id = Column(String(128), index=True)
    external_reference = Column(String(256))
    payment_metadata = Column('metadata', JSON, server_default='{}')
    created_by = Column(String(128), nullable=False, server_default='system')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    paid_at = Column(DateTime(timezone=True))

    order = relationship('B2COrder')


class CouponPromotion(Base):
    """Coupon or promotion definition for checkout discounts."""
    __tablename__ = 'coupon_promotions'

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), nullable=False, unique=True, index=True)
    promotion_type = Column(String(16), nullable=False, server_default='percent')  # percent/fixed
    discount_value = Column(Float, nullable=False, server_default='0.0')
    min_order_amount = Column(Float, nullable=False, server_default='0.0')
    max_discount_amount = Column(Float)
    usage_limit = Column(Integer)
    usage_count = Column(Integer, nullable=False, server_default='0')
    status = Column(String(32), nullable=False, server_default='active', index=True)
    starts_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
    promotion_metadata = Column('metadata', JSON, server_default='{}')
    created_by = Column(String(128), nullable=False, server_default='marketing')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CouponRedemption(Base):
    """Coupon application records per cart/order."""
    __tablename__ = 'coupon_redemptions'

    id = Column(Integer, primary_key=True, index=True)
    coupon_id = Column(Integer, ForeignKey('coupon_promotions.id'), nullable=False, index=True)
    cart_id = Column(Integer, ForeignKey('b2c_carts.id'), nullable=True, index=True)
    order_id = Column(Integer, ForeignKey('b2c_orders.id'), nullable=True, index=True)
    lead_id = Column(Integer, ForeignKey('leads.id'), nullable=True, index=True)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=True, index=True)
    discount_amount = Column(Float, nullable=False, server_default='0.0')
    status = Column(String(32), nullable=False, server_default='applied', index=True)
    redemption_metadata = Column('metadata', JSON, server_default='{}')
    redeemed_at = Column(DateTime(timezone=True), server_default=func.now())

    coupon = relationship('CouponPromotion')
    cart = relationship('B2CCart')
    order = relationship('B2COrder')


class LoyaltyAccount(Base):
    """Loyalty points balance for a customer or lead."""
    __tablename__ = 'loyalty_accounts'

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=True, index=True)
    lead_id = Column(Integer, ForeignKey('leads.id'), nullable=True, index=True)
    points_balance = Column(Integer, nullable=False, server_default='0')
    tier = Column(String(32), nullable=False, server_default='standard')
    status = Column(String(32), nullable=False, server_default='active', index=True)
    loyalty_metadata = Column('metadata', JSON, server_default='{}')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    customer = relationship('Customer')
    lead = relationship('Lead')


class LoyaltyLedgerEntry(Base):
    """Point earn/redeem transactions for auditability."""
    __tablename__ = 'loyalty_ledger_entries'

    id = Column(Integer, primary_key=True, index=True)
    loyalty_account_id = Column(Integer, ForeignKey('loyalty_accounts.id'), nullable=False, index=True)
    entry_type = Column(String(16), nullable=False)  # earn/redeem/adjust
    points = Column(Integer, nullable=False)
    source_type = Column(String(32), nullable=False, server_default='order')
    source_id = Column(Integer, nullable=False, index=True)
    note = Column(String(256))
    created_by = Column(String(128), nullable=False, server_default='system')
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    loyalty_account = relationship('LoyaltyAccount')


class MarketSignalEvent(Base):
    """Raw ingested market signals from external/partner/public data sources."""
    __tablename__ = 'market_signal_events'

    id = Column(Integer, primary_key=True, index=True)
    source_name = Column(String(128), nullable=False, index=True)
    signal_type = Column(String(64), nullable=False, index=True)  # trend/price_drop/bulk_clearance/campaign
    product_name = Column(String(256), nullable=False, index=True)
    region = Column(String(64), nullable=False, server_default='GLOBAL', index=True)
    raw_score = Column(Float, nullable=False, server_default='0.0')
    sentiment = Column(String(16), nullable=False, server_default='neutral')  # positive/neutral/negative
    sentiment_score = Column(Float, nullable=False, server_default='0.0')
    price_drop_pct = Column(Float, nullable=False, server_default='0.0')
    demand_spike_pct = Column(Float, nullable=False, server_default='0.0')
    source_reliability_score = Column(Float, nullable=False, server_default='0.5')
    normalized_score = Column(Float, nullable=False, server_default='0.0')
    signal_metadata = Column('metadata', JSON, server_default='{}')
    observed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ingested_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ingested_by = Column(String(128), nullable=False, server_default='market-intelligence')


class MarketDataSourceReliability(Base):
    """Reliability scoring ledger for each market data source."""
    __tablename__ = 'market_data_source_reliability'

    id = Column(Integer, primary_key=True, index=True)
    source_name = Column(String(128), nullable=False, unique=True, index=True)
    reliability_score = Column(Float, nullable=False, server_default='0.5')
    sample_count = Column(Integer, nullable=False, server_default='0')
    last_signal_at = Column(DateTime(timezone=True))
    reliability_metadata = Column('metadata', JSON, server_default='{}')
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class MarketOpportunity(Base):
    """Scored market opportunity derived from normalized market signals."""
    __tablename__ = 'market_opportunities'

    id = Column(Integer, primary_key=True, index=True)
    signal_event_id = Column(Integer, ForeignKey('market_signal_events.id'), nullable=False, index=True)
    product_name = Column(String(256), nullable=False, index=True)
    region = Column(String(64), nullable=False, server_default='GLOBAL', index=True)
    opportunity_score = Column(Float, nullable=False, server_default='0.0', index=True)
    confidence_score = Column(Float, nullable=False, server_default='0.0')
    status = Column(String(32), nullable=False, server_default='detected', index=True)  # detected/validated/rejected
    summary = Column(String(512))
    validation_notes = Column(Text)
    opportunity_metadata = Column('metadata', JSON, server_default='{}')
    detected_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    signal_event = relationship('MarketSignalEvent')
    validations = relationship('MarketOpportunityValidation', back_populates='opportunity')

    __table_args__ = (
        Index('idx_market_product_region_score', 'product_name', 'region', 'opportunity_score'),
    )


class MarketOpportunityValidation(Base):
    """Immutable validation transition records for detected opportunities."""
    __tablename__ = 'market_opportunity_validations'

    id = Column(Integer, primary_key=True, index=True)
    opportunity_id = Column(Integer, ForeignKey('market_opportunities.id'), nullable=False, index=True)
    from_status = Column(String(32), nullable=False, server_default='detected')
    to_status = Column(String(32), nullable=False, index=True)  # validated/rejected
    validator_type = Column(String(16), nullable=False, server_default='human')  # human/ai
    validation_score = Column(Float, nullable=True)  # optional AI confidence score in [0, 1]
    rejection_reason = Column(String(256), nullable=True)
    validation_notes = Column(Text, nullable=True)
    validated_by = Column(String(128), nullable=False, server_default='system')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    opportunity = relationship('MarketOpportunity', back_populates='validations')
