from datetime import datetime 
 
from typing import Any, Optional
 
from pydantic import BaseModel, EmailStr, Field, model_validator

class VendorBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=256)
    source: str = Field(default='manual')
    contact_email: Optional[EmailStr] = None
    phone: Optional[str] = None
    industry: Optional[str] = None
    vendor_metadata: Optional[dict] = Field(default_factory=dict)

    model_config = {
        'populate_by_name': True,
        'from_attributes': True,
    }


class VendorCreate(VendorBase):
    @model_validator(mode='before')
    @classmethod
    def _ingest_metadata_key(cls, data):
        """Accept JSON key `metadata` from connectors; avoid clashing with SQLAlchemy's `metadata`."""
        if not isinstance(data, dict):
            return data
        out = dict(data)
        if 'metadata' in out and 'vendor_metadata' not in out:
            out['vendor_metadata'] = out.get('metadata') or {}
        out.pop('metadata', None)
        return out
 
class VendorResponse(VendorBase):
    id: int
    category: str = 'uncategorized'
    category_confidence: float = 0.0
    categorization_source: Optional[str] = None
    category_notes: Optional[str] = None
    last_categorized_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class VendorOptOutRuleCreate(BaseModel):
    channel: str = Field(default='all', min_length=2, max_length=32)
    is_opted_out: bool = True
    rule_type: str = Field(default='opt_out', min_length=6, max_length=16)
    reason: Optional[str] = Field(default=None, max_length=512)
    created_by: str = Field(default='compliance', max_length=128)


class VendorOptOutRuleResponse(BaseModel):
    id: int
    vendor_id: int
    channel: str
    is_opted_out: bool
    rule_type: str
    reason: Optional[str] = None
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class ProductBase(BaseModel): 
    name: str = Field(..., min_length=2, max_length=256) 
    vendor_id: Optional[int] = None 
    sku: Optional[str] = None 
    price: Optional[str] = None 
    attributes: Optional[dict] = Field(default_factory=dict) 
 
class ProductCreate(ProductBase):
    @model_validator(mode='before')
    @classmethod
    def _normalize_catalog_fields(cls, data):
        if not isinstance(data, dict):
            return data
        out = dict(data)
        if out.get('sku') is not None:
            out['sku'] = str(out['sku']).strip().upper()
        if out.get('price') is not None:
            out['price'] = str(out['price']).strip()
        return out
 
class ProductResponse(ProductBase):
    id: int
    category: str = 'uncategorized'
    category_confidence: float = 0.0
    categorization_source: Optional[str] = None
    category_notes: Optional[str] = None
    last_categorized_at: Optional[datetime] = None
    created_at: datetime

    model_config = {
        'from_attributes': True,
    }


class AdminCategoryPatch(BaseModel):
    category: str = Field(..., min_length=1, max_length=128)
    notes: Optional[str] = None
    performed_by: str = Field(default='admin', max_length=128)
 
class LeadCreate(BaseModel): 
    full_name: str 
    email: Optional[EmailStr] = None 
    phone: Optional[str] = None 
    company: Optional[str] = None 
    # B2B enrichment fields (optional at create time; filled by enrichment job)
    revenue_estimate: Optional[str] = None
    company_size: Optional[str] = None
    decision_maker: Optional[str] = None
    b2b_score: Optional[str] = None
    source: Optional[str] = None 
 
class LeadResponse(LeadCreate):
    id: int
    stage: str
    consented: str
    segment: str = 'unsegmented'
    attribution_channel: str = 'unknown'
    marketing_consent: str = 'unknown'
    marketing_intent_data: dict = Field(default_factory=dict)
    marketing_intent_score: int = 0
    last_intent_at: Optional[datetime] = None
    lead_score: int = 0
    unsubscribed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {
        'from_attributes': True,
    }


class LeadUpdate(BaseModel):
    stage: str
    consented: Optional[str] = None


class LeadPreferences(BaseModel):
    marketing_consent: Optional[str] = None
    unsubscribe: bool = False
 
class CustomerBase(BaseModel): 
    name: str = Field(..., min_length=2, max_length=256) 
    email: Optional[EmailStr] = None 
    phone: Optional[str] = None 
    vendor_id: Optional[int] = None 
    account_status: Optional[str] = Field(default='active') 
    consent_status: Optional[str] = Field(default='unknown') 
    engagement_score: Optional[int] = Field(default=0) 
 
class CustomerCreate(CustomerBase): 
    pass 
 
class CustomerResponse(CustomerBase): 
    id: int 
    created_at: datetime 
    updated_at: datetime 
    model_config = { 
        'from_attributes': True, 
    } 
 
class ConsentUpdate(BaseModel):
    consent_status: str


class CustomerEngagementPatch(BaseModel):
    account_status: Optional[str] = None
    engagement_score: Optional[int] = None


class CrmDashboard(BaseModel):
    totals: dict[str, int]
    leads_by_stage: dict[str, int]
    leads_by_segment: dict[str, int]
    customers_by_consent: dict[str, int]


class LeadStageTransitionResponse(BaseModel):
    id: int
    lead_id: int
    from_stage: Optional[str] = None
    to_stage: str
    reason: Optional[str] = None
    performed_by: str
    changed_at: datetime

    model_config = {
        'from_attributes': True,
    }


class FunnelConversionMetric(BaseModel):
    from_stage: str
    to_stage: str
    transitions: int
    base: int
    conversion_rate: float


class SalesFunnelMetrics(BaseModel):
    generated_at: datetime
    window_days: int
    total_leads: int
    stage_counts: dict[str, int]
    conversion_rates: list[FunnelConversionMetric]
    median_time_in_stage_hours: dict[str, float]
    drop_off_reasons: dict[str, dict[str, int]]


class SalesPlaybookStep(BaseModel):
    step: int
    title: str
    action: str
    reason: str


class LeadSalesPlaybook(BaseModel):
    lead_id: int
    full_name: str
    stage: str
    lead_score: int
    priority: str
    recommended_channel: str
    summary: str
    steps: list[SalesPlaybookStep]


class SalesPlaybookQueueResponse(BaseModel):
    generated_at: datetime
    leads: list[LeadSalesPlaybook]


class CRMCommunicationCreate(BaseModel):
    lead_id: Optional[int] = None
    customer_id: Optional[int] = None
    channel: str = Field(default='email', min_length=2, max_length=32)
    direction: str = Field(default='outbound', min_length=2, max_length=16)
    subject: Optional[str] = Field(default=None, max_length=256)
    message: str = Field(..., min_length=1)
    status: str = Field(default='logged', min_length=2, max_length=32)
    follow_up_at: Optional[datetime] = None
    performed_by: str = Field(default='system', max_length=128)

    @model_validator(mode='after')
    def _target_required(self):
        if self.lead_id is None and self.customer_id is None:
            raise ValueError('Either lead_id or customer_id is required')
        return self


class CRMCommunicationResponse(BaseModel):
    id: int
    lead_id: Optional[int] = None
    customer_id: Optional[int] = None
    channel: str
    direction: str
    subject: Optional[str] = None
    message: str
    status: str
    follow_up_at: Optional[datetime] = None
    reminder_sent_at: Optional[datetime] = None
    performed_by: str
    created_at: datetime

    model_config = {
        'from_attributes': True,
    }


class ScrapingComplianceResponse(BaseModel):
    policy: dict
    checklist: list[dict]


class EscalationPlaybookResponse(BaseModel):
    steps: list[dict]


class LocaleStringsResponse(BaseModel):
    locale: str
    strings: dict[str, str]


class ExternalIntegrationEvent(BaseModel):
    provider: str = Field(..., min_length=2, max_length=64)
    event_type: str = Field(..., min_length=2, max_length=128)
    payload: dict = Field(default_factory=dict)
    performed_by: str = Field(default='integration', max_length=128)


class IntegrationAck(BaseModel):
    status: str
    detail: str


class LeadB2BEnrichmentResponse(BaseModel):
    leads_enriched: int
    scanned: int


class MarketingIntentEvent(BaseModel):
    lead_id: int = Field(..., ge=1)
    source: str = Field(..., min_length=2, max_length=64)
    signal_type: str = Field(..., min_length=2, max_length=64)
    strength: int = Field(default=1, ge=1, le=100)
    metadata: dict = Field(default_factory=dict)
    performed_by: str = Field(default='marketing', max_length=128)


class MarketingIntentResponse(BaseModel):
    lead_id: int
    marketing_intent_score: int
    lead_score: int
    attribution_channel: str
    marketing_intent_data: dict


class MarketingChannelConversionMetric(BaseModel):
    channel: str
    leads: int
    converted: int
    conversion_rate: float


class MarketingAnalyticsOverview(BaseModel):
    generated_at: datetime
    window_days: int
    total_automation_events: int
    automation_events_by_provider: dict[str, int]
    automation_events_by_type: dict[str, int]
    intent_signals_by_type: dict[str, int]
    intent_sources: dict[str, int]
    lead_attribution: dict[str, int]
    intent_score_bands: dict[str, int]
    conversion_by_channel: list[MarketingChannelConversionMetric]


class MarketingCampaignTriggerRequest(BaseModel):
    campaign_type: str = Field(default='auto', min_length=4, max_length=16)
    limit: int = Field(default=100, ge=1, le=500)
    performed_by: str = Field(default='marketing', max_length=128)


class MarketingCampaignTarget(BaseModel):
    lead_id: int
    campaign_type: str
    reason: str
    channel: str


class MarketingCampaignTriggerResponse(BaseModel):
    generated_at: datetime
    campaign_type: str
    triggered: int
    total_candidates: int
    targets: list[MarketingCampaignTarget]


class MarketingAutomationDispatchRequest(BaseModel):
    campaign_type: str = Field(default='auto', min_length=4, max_length=16)
    limit: int = Field(default=100, ge=1, le=500)
    provider_override: Optional[str] = Field(default=None, max_length=64)
    performed_by: str = Field(default='marketing', max_length=128)


class MarketingAutomationDispatchResponse(BaseModel):
    generated_at: datetime
    campaign_type: str
    triggered: int
    dispatched: int
    providers: dict[str, int]
    campaign_types: dict[str, int]


class MarketingDispatchStatusResponse(BaseModel):
    id: int
    lead_id: Optional[int] = None
    provider: str
    campaign_type: str
    channel: str
    status: str
    external_id: Optional[str] = None
    error_detail: Optional[str] = None
    created_at: datetime
    dispatched_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None

    model_config = {
        'from_attributes': True,
    }


class MarketingDispatchSyncResponse(BaseModel):
    scanned: int
    sent: int
    failed: int


class MarketingUpsellCrossSellTriggerRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=500)
    provider_override: Optional[str] = Field(default=None, max_length=64)
    performed_by: str = Field(default='marketing', max_length=128)


class MarketingChannelROIMetric(BaseModel):
    channel: str
    automation_events: int
    converted_leads: int
    estimated_spend: float
    estimated_revenue: float
    roi: Optional[float] = None


class MarketingROIOverview(BaseModel):
    generated_at: datetime
    window_days: int
    total_automation_events: int
    total_converted_leads: int
    estimated_spend: float
    estimated_revenue: float
    overall_roi: Optional[float] = None
    spend_by_provider: dict[str, float]
    events_by_provider: dict[str, int]
    roi_by_channel: list[MarketingChannelROIMetric]


class B2COrderCreate(BaseModel):
    customer_id: Optional[int] = Field(default=None, ge=1)
    lead_id: Optional[int] = Field(default=None, ge=1)
    currency: str = Field(default='USD', min_length=3, max_length=8)
    total_amount: float = Field(default=0.0, ge=0.0)
    order_items: list[dict] = Field(default_factory=list)
    source_channel: str = Field(default='web', min_length=2, max_length=32)
    shipping_address: dict = Field(default_factory=dict)


class B2COrderResponse(BaseModel):
    id: int
    customer_id: Optional[int] = None
    lead_id: Optional[int] = None
    status: str
    fulfillment_status: str
    currency: str
    total_amount: float
    order_items: list[dict]
    source_channel: str
    shipping_address: dict
    tracking_number: Optional[str] = None
    carrier: Optional[str] = None
    external_order_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None

    model_config = {
        'from_attributes': True,
    }


class B2COrderFulfillmentPatch(BaseModel):
    fulfillment_status: str = Field(..., min_length=2, max_length=32)
    tracking_number: Optional[str] = Field(default=None, max_length=128)
    carrier: Optional[str] = Field(default=None, max_length=64)
    location: Optional[str] = Field(default=None, max_length=128)
    note: Optional[str] = Field(default=None, max_length=256)
    performed_by: str = Field(default='operations', max_length=128)


class B2COrderTrackingEventResponse(BaseModel):
    id: int
    order_id: int
    status: str
    location: Optional[str] = None
    note: Optional[str] = None
    tracking_number: Optional[str] = None
    carrier: Optional[str] = None
    occurred_at: datetime

    model_config = {
        'from_attributes': True,
    }


class B2COrderTrackingResponse(BaseModel):
    order_id: int
    status: str
    fulfillment_status: str
    tracking_number: Optional[str] = None
    carrier: Optional[str] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    events: list[B2COrderTrackingEventResponse]


class EntityVersionRecordResponse(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    version_number: int
    snapshot: dict[str, Any] = Field(default_factory=dict)
    change_reason: Optional[str] = None
    changed_by: str
    created_at: datetime

    model_config = {
        'from_attributes': True,
    }


class EntityVersionRollbackRequest(BaseModel):
    reason: str = Field(default='manual rollback requested', max_length=2000)
    performed_by: str = Field(default='operations', max_length=128)


class SalesRepNotificationCreate(BaseModel):
    entity_type: str = Field(default='rfq', min_length=2, max_length=32)
    entity_id: int = Field(..., ge=1)
    notification_type: str = Field(default='rfq_update', min_length=2, max_length=64)
    message: str = Field(..., min_length=1, max_length=2000)
    priority: str = Field(default='medium', min_length=2, max_length=16)
    lead_id: Optional[int] = Field(default=None, ge=1)
    recipient: str = Field(default='sales', min_length=2, max_length=128)
    channel: str = Field(default='inbox', min_length=2, max_length=32)
    metadata: dict[str, Any] = Field(default_factory=dict)
    performed_by: str = Field(default='system', max_length=128)


class SalesRepNotificationStatusPatch(BaseModel):
    status: str = Field(..., min_length=2, max_length=32)
    performed_by: str = Field(default='system', max_length=128)


class SalesRepNotificationResponse(BaseModel):
    id: int
    lead_id: Optional[int] = None
    entity_type: str
    entity_id: int
    notification_type: str
    priority: str
    channel: str
    recipient: str
    message: str
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias='notification_metadata')
    created_at: datetime
    sent_at: Optional[datetime] = None

    model_config = {
        'from_attributes': True,
    }


class PricingApprovalRequestCreate(BaseModel):
    entity_type: str = Field(..., min_length=5, max_length=16)
    entity_id: int = Field(..., ge=1)
    requested_discount_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    requested_discount_amount: Optional[float] = Field(default=None, ge=0.0)
    reason: Optional[str] = Field(default=None, max_length=2000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    requested_by: str = Field(default='sales', max_length=128)


class PricingApprovalReviewRequest(BaseModel):
    decision: str = Field(..., min_length=7, max_length=32)
    approved_discount_pct: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    approved_discount_amount: Optional[float] = Field(default=None, ge=0.0)
    review_note: Optional[str] = Field(default=None, max_length=2000)
    reviewed_by: str = Field(default='sales-manager', max_length=128)


class PricingApprovalRequestResponse(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    lead_id: Optional[int] = None
    requested_discount_pct: Optional[float] = None
    requested_discount_amount: Optional[float] = None
    currency: str
    reason: Optional[str] = None
    status: str
    request_metadata: dict[str, Any] = Field(default_factory=dict)
    requested_by: str
    reviewed_by: Optional[str] = None
    review_note: Optional[str] = None
    approved_discount_pct: Optional[float] = None
    approved_discount_amount: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    reviewed_at: Optional[datetime] = None

    model_config = {
        'from_attributes': True,
    }


class QuoteToCashRecordCreate(BaseModel):
    quote_id: Optional[int] = Field(default=None, ge=1)
    order_id: Optional[int] = Field(default=None, ge=1)
    customer_id: Optional[int] = Field(default=None, ge=1)
    external_system: Optional[str] = Field(default=None, max_length=64)
    created_by: str = Field(default='system', max_length=128)

    @model_validator(mode='after')
    def _require_quote_or_order(self):
        if self.quote_id is None and self.order_id is None:
            raise ValueError('quote_id or order_id is required')
        return self


class QuoteToCashRecordAdvanceRequest(BaseModel):
    status: str = Field(..., min_length=4, max_length=32)
    payment_status: Optional[str] = Field(default=None, max_length=32)
    external_reference: Optional[str] = Field(default=None, max_length=128)
    performed_by: str = Field(default='finance', max_length=128)


class QuoteToCashRecordResponse(BaseModel):
    id: int
    quote_id: Optional[int] = None
    order_id: Optional[int] = None
    lead_id: Optional[int] = None
    customer_id: Optional[int] = None
    status: str
    payment_status: str
    invoice_number: Optional[str] = None
    invoice_amount: float
    currency: str
    external_system: Optional[str] = None
    external_reference: Optional[str] = None
    qtc_metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str
    created_at: datetime
    updated_at: datetime
    invoiced_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    synced_at: Optional[datetime] = None

    model_config = {
        'from_attributes': True,
    }


class B2COrderShippingCreate(BaseModel):
    provider: str = Field(default='mockship', min_length=2, max_length=64)
    service_level: str = Field(default='standard', min_length=2, max_length=32)
    shipping_cost: float = Field(default=0.0, ge=0.0)
    estimated_delivery_days: int = Field(default=4, ge=1, le=30)
    shipment_metadata: dict = Field(default_factory=dict)
    performed_by: str = Field(default='operations', max_length=128)


class B2COrderShippingSyncPatch(BaseModel):
    status: str = Field(..., min_length=2, max_length=32)
    current_location: Optional[str] = Field(default=None, max_length=128)
    note: Optional[str] = Field(default=None, max_length=256)
    performed_by: str = Field(default='shipping-sync', max_length=128)


class B2COrderShippingShipmentResponse(BaseModel):
    id: int
    order_id: int
    provider: str
    service_level: str
    external_shipment_id: str
    tracking_number: str
    status: str
    current_location: Optional[str] = None
    estimated_delivery_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    shipping_cost: float
    shipment_metadata: dict
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class OrderDealFeedbackCreate(BaseModel):
    actor_type: str = Field(default='customer', min_length=3, max_length=32)
    actor_id: Optional[int] = Field(default=None, ge=1)
    sentiment: str = Field(default='neutral', min_length=3, max_length=16)
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    feedback_text: Optional[str] = Field(default=None, max_length=3000)
    feedback_metadata: dict = Field(default_factory=dict)
    created_by: str = Field(default='support', max_length=128)


class OrderDealFeedbackResponse(BaseModel):
    id: int
    order_id: int
    actor_type: str
    actor_id: Optional[int] = None
    sentiment: str
    rating: Optional[int] = None
    feedback_text: Optional[str] = None
    feedback_metadata: dict
    created_by: str
    created_at: datetime

    model_config = {
        'from_attributes': True,
    }


class OrderDealFeedbackSummary(BaseModel):
    generated_at: datetime
    window_days: int
    total_feedback: int
    average_rating: float
    sentiment_counts: dict[str, int]
    by_actor_type: dict[str, int]


class SelfLearningFeedbackRequest(BaseModel):
    entity_type: str = Field(default='order', min_length=2, max_length=64)
    entity_id: Optional[int] = Field(default=None, ge=1)
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    outcome: Optional[str] = Field(default=None, max_length=256)
    comments: Optional[str] = Field(default=None, max_length=2000)
    performed_by: str = Field(default='system', max_length=128)


class SelfLearningFeedbackResponse(BaseModel):
    entity_type: str
    entity_id: Optional[int] = None
    rating: Optional[int] = None
    outcome: Optional[str] = None
    comments: Optional[str] = None
    recorded_at: datetime


class ExplainabilityResponse(BaseModel):
    model_name: str
    entity_type: str
    entity_id: int
    explanation: str
    features: dict[str, Any]
    confidence: float
    generated_at: datetime


class ModelDriftStatusResponse(BaseModel):
    model_name: str
    window_days: int
    total_models: int
    recent_models: int
    recent_feedback_events: int
    drift_score: float
    retrain_recommended: bool


class HumanOverrideRequest(BaseModel):
    action: str = Field(..., min_length=4, max_length=8)
    reason: Optional[str] = Field(default=None, max_length=2000)
    performed_by: str = Field(default='ops', max_length=128)


class HumanOverrideStatusResponse(BaseModel):
    override_enabled: bool
    reason: Optional[str] = None
    performed_by: str
    updated_at: Optional[datetime] = None


class FraudRiskResponse(BaseModel):
    order_id: Optional[int] = None
    source_channel: Optional[str] = None
    total_amount: float
    risk_score: float
    risk_level: str
    reasons: list[str]


class InventoryForecastResponse(BaseModel):
    sku: str
    forecast_days: int
    average_daily_demand: float
    forecast_units: int
    recent_units: int
    unit_counts: dict[str, int]


class RecommendationItem(BaseModel):
    product_name: str
    sku: str
    reason: str
    confidence: float


class PersonalizedRecommendationsResponse(BaseModel):
    lead_id: Optional[int] = None
    customer_id: Optional[int] = None
    source: str
    recommendations: list[RecommendationItem]


class EthicsReviewResponse(BaseModel):
    scope: str
    region: Optional[str] = None
    review_status: str
    issues_identified: list[str]
    compliance_score: float
    reviewed_at: datetime


class CompetitorPriceRecord(BaseModel):
    competitor: str
    product: str
    observed_price: float
    outcome_count: int
    last_seen_at: datetime


class CompetitorMonitoringResponse(BaseModel):
    product_name: Optional[str] = None
    records: list[CompetitorPriceRecord]
    monitored_at: datetime


class DynamicPricingResponse(BaseModel):
    sku: Optional[str] = None
    base_price: float
    recommended_price: float
    demand_factor: float
    pricing_strategy: str


class FraudFeedbackRequest(BaseModel):
    order_id: int = Field(..., ge=1)
    feedback: str = Field(..., min_length=5, max_length=2000)
    severity: str = Field(default='medium', min_length=4, max_length=16)
    performed_by: str = Field(default='audit', max_length=128)


class FraudFeedbackResponse(BaseModel):
    order_id: int
    feedback: str
    severity: str
    recorded_at: datetime


class BiasFairnessResponse(BaseModel):
    model_name: str
    fairness_score: float
    bias_issues: list[str]
    remediation_recommendation: str


class SalesProcessEnforcementResponse(BaseModel):
    sales_rep_id: Optional[int] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    compliance_issues: list[str]
    recommended_actions: list[str]
    evaluated_at: datetime


class ChatbotEscalationRequest(BaseModel):
    issue_description: str = Field(..., min_length=5, max_length=2000)
    fallback_channel: str = Field(default='human_agent', min_length=2, max_length=64)
    performed_by: str = Field(default='chatbot', max_length=128)


class ChatbotEscalationResponse(BaseModel):
    alert_id: int
    status: str
    fallback_channel: str
    performed_by: str
    created_at: datetime


class B2CCartItemInput(BaseModel):
    sku: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=256)
    unit_price: float = Field(..., ge=0.0)
    quantity: int = Field(default=1, ge=1, le=100)
    item_metadata: dict = Field(default_factory=dict)


class B2CCartLocator(BaseModel):
    customer_id: Optional[int] = Field(default=None, ge=1)
    lead_id: Optional[int] = Field(default=None, ge=1)
    cart_token: Optional[str] = Field(default=None, min_length=3, max_length=128)

    @model_validator(mode='after')
    def _require_locator(self):
        if self.customer_id is None and self.lead_id is None and not self.cart_token:
            raise ValueError('At least one of customer_id, lead_id, or cart_token is required')
        return self


class B2CCartAddItemRequest(B2CCartLocator):
    currency: str = Field(default='USD', min_length=3, max_length=8)
    item: B2CCartItemInput
    performed_by: str = Field(default='commerce', max_length=128)


class B2CCartRemoveItemRequest(B2CCartLocator):
    sku: str = Field(..., min_length=1, max_length=128)
    performed_by: str = Field(default='commerce', max_length=128)


class B2CCartCheckoutRequest(B2CCartLocator):
    shipping_address: dict = Field(default_factory=dict)
    coupon_code: Optional[str] = Field(default=None, min_length=2, max_length=64)
    loyalty_points_to_redeem: int = Field(default=0, ge=0, le=100000)
    performed_by: str = Field(default='commerce', max_length=128)


class B2CCartItemResponse(BaseModel):
    id: int
    sku: str
    name: str
    unit_price: float
    quantity: int
    item_metadata: dict

    model_config = {
        'from_attributes': True,
    }


class B2CCartResponse(BaseModel):
    cart_id: int
    customer_id: Optional[int] = None
    lead_id: Optional[int] = None
    cart_token: Optional[str] = None
    status: str
    currency: str
    total_amount: float
    coupon_code: Optional[str] = None
    coupon_discount_amount: float = 0.0
    loyalty_discount_amount: float = 0.0
    total_items: int
    items: list[B2CCartItemResponse]
    checked_out_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class B2CCheckoutResponse(BaseModel):
    cart: B2CCartResponse
    order: B2COrderResponse


class PaymentGatewayConfigCreate(BaseModel):
    gateway_code: str = Field(..., min_length=2, max_length=64)
    display_name: str = Field(..., min_length=2, max_length=128)
    supported_currencies: list[str] = Field(default_factory=lambda: ['USD'])
    configured_by: str = Field(default='finance', max_length=128)


class PaymentGatewayConfigResponse(BaseModel):
    id: int
    gateway_code: str
    display_name: str
    status: str
    supported_currencies: list[str]
    config_metadata: dict[str, Any] = Field(default_factory=dict)
    configured_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class PaymentIntentCreateRequest(BaseModel):
    gateway_code: str = Field(..., min_length=2, max_length=64)
    amount: Optional[float] = Field(default=None, ge=0.0)
    created_by: str = Field(default='checkout', max_length=128)


class PaymentConfirmRequest(BaseModel):
    status: str = Field(..., min_length=4, max_length=32)
    external_reference: Optional[str] = Field(default=None, max_length=256)
    performed_by: str = Field(default='payment-webhook', max_length=128)


class PaymentTransactionResponse(BaseModel):
    id: int
    order_id: int
    gateway_code: str
    transaction_type: str
    amount: float
    currency: str
    status: str
    external_payment_id: Optional[str] = None
    external_reference: Optional[str] = None
    payment_metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str
    created_at: datetime
    updated_at: datetime
    paid_at: Optional[datetime] = None

    model_config = {
        'from_attributes': True,
    }


class CouponPromotionCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=64)
    promotion_type: str = Field(default='percent', max_length=16)
    discount_value: float = Field(..., ge=0.0)
    min_order_amount: float = Field(default=0.0, ge=0.0)
    max_discount_amount: Optional[float] = Field(default=None, ge=0.0)
    usage_limit: Optional[int] = Field(default=None, ge=1)
    created_by: str = Field(default='marketing', max_length=128)


class CouponPromotionResponse(BaseModel):
    id: int
    code: str
    promotion_type: str
    discount_value: float
    min_order_amount: float
    max_discount_amount: Optional[float] = None
    usage_limit: Optional[int] = None
    usage_count: int
    status: str
    starts_at: datetime
    expires_at: Optional[datetime] = None
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class LoyaltyAccountCreateOrUpdate(BaseModel):
    customer_id: Optional[int] = Field(default=None, ge=1)
    lead_id: Optional[int] = Field(default=None, ge=1)


class LoyaltyAccountResponse(BaseModel):
    id: int
    customer_id: Optional[int] = None
    lead_id: Optional[int] = None
    points_balance: int
    tier: str
    status: str
    loyalty_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class RFQBroadcastCreate(BaseModel):
    lead_id: Optional[int] = Field(default=None, ge=1)
    vendor_ids: list[int] = Field(default_factory=list)
    channel: str = Field(default='email', min_length=3, max_length=32)
    message: str = Field(default='Please share your quote and delivery timeline.', min_length=4, max_length=2000)
    auto_match_limit: int = Field(default=0, ge=0, le=100)
    performed_by: str = Field(default='sales', max_length=128)


class RFQBroadcastResponse(BaseModel):
    id: int
    lead_id: Optional[int] = None
    channel: str
    status: str
    message: Optional[str] = None
    performed_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class RFQDeliveryAttemptResponse(BaseModel):
    id: int
    broadcast_id: int
    vendor_id: int
    status: str
    external_ref: Optional[str] = None
    error_detail: Optional[str] = None
    attempted_at: datetime
    delivered_at: Optional[datetime] = None
    last_updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class RFQDeliveryAttemptPatch(BaseModel):
    status: str = Field(..., min_length=4, max_length=32)
    external_ref: Optional[str] = Field(default=None, max_length=128)
    error_detail: Optional[str] = Field(default=None, max_length=2000)
    performed_by: str = Field(default='sales-ops', max_length=128)


class RFQDeliverySyncResponse(BaseModel):
    scanned: int
    delivered: int
    failed: int


class RFQEscalationCaseResponse(BaseModel):
    id: int
    broadcast_id: int
    lead_id: Optional[int] = None
    escalation_reason: str
    severity: str
    status: str
    escalated_by: str
    escalation_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = {
        'from_attributes': True,
    }


class RFQEscalationRunResponse(BaseModel):
    scanned: int
    escalated: int
    alerts_created: int
    expansion_attempts: int
    cases: list[RFQEscalationCaseResponse] = Field(default_factory=list)


class RFQDeliverySummary(BaseModel):
    generated_at: datetime
    window_days: int
    total_attempts: int
    delivered: int
    failed: int
    queued: int
    by_channel: dict[str, dict[str, int]]
    by_status: dict[str, int]


class RFQRateLimitRuleCreate(BaseModel):
    entity_type: str = Field(..., min_length=3, max_length=32)
    entity_key: str = Field(..., min_length=1, max_length=128)
    max_per_window: int = Field(default=10, ge=1, le=10000)
    window_hours: int = Field(default=24, ge=1, le=720)
    is_active: bool = Field(default=True)


class RFQRateLimitRuleResponse(BaseModel):
    id: int
    entity_type: str
    entity_key: str
    max_per_window: int
    window_hours: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class RFQRateLimitUsageBucket(BaseModel):
    entity_type: str
    entity_key: str
    broadcasts_in_window: int
    limit: int
    window_hours: int
    remaining: int
    is_limited: bool


class RFQRateLimitUsageSummary(BaseModel):
    generated_at: datetime
    window_hours: int
    buckets: list[RFQRateLimitUsageBucket]


class RFQVendorResponseCreate(BaseModel):
    response_status: str = Field(default='replied', min_length=4, max_length=32)
    response_text: Optional[str] = Field(default=None, max_length=4000)
    quoted_price: Optional[float] = Field(default=None, ge=0)
    recorded_by: str = Field(default='sales', max_length=128)


class RFQVendorResponseResponse(BaseModel):
    id: int
    attempt_id: int
    vendor_id: int
    response_status: str
    response_text: Optional[str] = None
    quoted_price: Optional[float] = None
    responded_at: datetime
    recorded_by: str

    model_config = {
        'from_attributes': True,
    }


class RFQVendorResponseAnalyticsBucket(BaseModel):
    total_deliveries: int
    responses: int
    opens: int
    replies: int
    no_responses: int
    reply_rate: float
    open_rate: float


class RFQVendorResponseAnalytics(BaseModel):
    generated_at: datetime
    window_days: int
    total_deliveries: int
    total_responses: int
    reply_rate: float
    open_rate: float
    by_vendor: dict[str, RFQVendorResponseAnalyticsBucket]
    by_channel: dict[str, RFQVendorResponseAnalyticsBucket]


class RFQQuoteParseRequest(BaseModel):
    parser_version: str = Field(default='rule-v1', min_length=3, max_length=32)
    performed_by: str = Field(default='sales-ops', max_length=128)


class RFQParsedQuoteResponse(BaseModel):
    id: int
    response_id: int
    attempt_id: int
    vendor_id: int
    currency: str
    unit_price: Optional[float] = None
    total_price: Optional[float] = None
    quantity: Optional[int] = None
    lead_time_days: Optional[int] = None
    minimum_order_quantity: Optional[int] = None
    confidence: float
    parser_version: str
    raw_excerpt: Optional[str] = None
    parse_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class RFQQuoteParsingSummary(BaseModel):
    generated_at: datetime
    total_quotes: int
    parsed_with_unit_price: int
    parsed_with_lead_time: int
    parsed_with_quantity: int
    average_confidence: float


class RFQNegotiationStrategyCreate(BaseModel):
    vendor_id: int
    target_unit_price_reduction_pct: float = 10.0
    target_moq_reduction_pct: float = 15.0
    max_acceptable_lead_time_days: int = 30
    negotiation_rounds_limit: int = 3
    prior_success_rate: float = 0.0
    require_human_review_for_high_value: bool = False
    high_value_threshold: float = 50000.0
    is_active: bool = True
    strategy_metadata: dict[str, Any] = Field(default_factory=dict)


class RFQNegotiationStrategyResponse(BaseModel):
    id: int
    vendor_id: int
    target_unit_price_reduction_pct: float
    target_moq_reduction_pct: float
    max_acceptable_lead_time_days: int
    negotiation_rounds_limit: int
    prior_success_rate: float
    require_human_review_for_high_value: bool
    high_value_threshold: float
    is_active: bool
    strategy_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class RFQCounterOfferRequest(BaseModel):
    quote_id: int
    reason: str = "Optimizing terms based on budget and timeline requirements"


class RFQNegotiationRoundResponse(BaseModel):
    id: int
    quote_id: int
    attempt_id: int
    vendor_id: int
    round_number: int
    counter_offer_unit_price: Optional[float] = None
    counter_offer_moq: Optional[int] = None
    counter_offer_lead_time_days: Optional[int] = None
    justification: Optional[str] = None
    vendor_response: Optional[str] = None
    status: str
    generated_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class RFQNegotiationFeedbackCreate(BaseModel):
    outcome: str = Field(default='counter_offered', min_length=7, max_length=32)
    realized_unit_price: Optional[float] = None
    realized_moq: Optional[int] = None
    realized_lead_time_days: Optional[int] = None
    feedback_note: Optional[str] = Field(default=None, max_length=3000)
    feedback_metadata: dict[str, Any] = Field(default_factory=dict)
    recorded_by: str = Field(default='sales-ops', max_length=128)


class RFQNegotiationFeedbackResponse(BaseModel):
    id: int
    round_id: int
    quote_id: int
    attempt_id: int
    vendor_id: int
    outcome: str
    realized_unit_price: Optional[float] = None
    realized_moq: Optional[int] = None
    realized_lead_time_days: Optional[int] = None
    feedback_note: Optional[str] = None
    feedback_metadata: dict[str, Any] = Field(default_factory=dict)
    recorded_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class RFQNegotiationAnalytics(BaseModel):
    generated_at: datetime
    total_negotiation_rounds: int
    rounds_accepted: int
    rounds_rejected: int
    rounds_pending: int
    accepted_rate: float
    average_price_reduction_achieved: float
    average_moq_reduction_achieved: float
    by_vendor: dict[str, dict[str, Any]] = Field(default_factory=dict)


class RFQQuoteAuthenticityRequest(BaseModel):
    performed_by: str = Field(default='sales-ops', max_length=128)


class RFQQuoteAuthenticityCheckResponse(BaseModel):
    id: int
    quote_id: int
    attempt_id: int
    vendor_id: int
    broadcast_id: int
    verdict: str
    flags: list[str] = Field(default_factory=list)
    duplicate_of_quote_id: Optional[int] = None
    confidence_score: float
    performed_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class RFQQuoteAuthenticityCheckSummary(BaseModel):
    generated_at: datetime
    window_days: int
    total_checks: int
    by_verdict: dict[str, int]
    flag_counts: dict[str, int]
    rejection_rate: float
    suspicion_rate: float


class RFQHumanReviewRequestCreate(BaseModel):
    quote_id: int
    request_reason: str = 'High-value deal requires manual approval before negotiation.'
    requested_by: str = 'system'


class RFQHumanReviewDecision(BaseModel):
    status: str  # approved/rejected
    review_note: Optional[str] = None
    reviewed_by: str = 'reviewer'


class RFQHumanReviewRequestResponse(BaseModel):
    id: int
    quote_id: int
    attempt_id: int
    vendor_id: int
    estimated_total_value: float
    high_value_threshold: float
    status: str
    request_reason: Optional[str] = None
    requested_by: str
    reviewed_by: Optional[str] = None
    review_note: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class MarketingOrderAttributionBucket(BaseModel):
    orders: int
    revenue: float


class MarketingOrderAnalyticsOverview(BaseModel):
    generated_at: datetime
    window_days: int
    orders_total: int
    orders_attributed: int
    orders_unattributed: int
    attributed_revenue: float
    unattributed_revenue: float
    attribution_by_provider: dict[str, MarketingOrderAttributionBucket]
    attribution_by_channel: dict[str, MarketingOrderAttributionBucket]
    attribution_by_campaign_type: dict[str, MarketingOrderAttributionBucket]

class ComplianceLogEntry(BaseModel):
    entity_type: str
    action: str
    detail: str
    performed_by: str
    created_at: datetime

    model_config = {
        'from_attributes': True,
    }


class ComplianceReport(BaseModel):
    total_entries: int
    entity_counts: dict[str, int]
    action_counts: dict[str, int]
    recent_entries: list[ComplianceLogEntry]
    window_minutes: int

    model_config = {
        'from_attributes': True,
    }


class CustomerUpdateNotificationResponse(BaseModel):
    id: int
    order_id: Optional[int] = None
    lead_id: Optional[int] = None
    customer_id: Optional[int] = None
    event_type: str
    channel: str
    recipient_address: Optional[str] = None
    subject: Optional[str] = None
    message: str
    status: str
    update_metadata: dict[str, Any] = Field(default_factory=dict)
    dispatched_at: Optional[datetime] = None
    created_at: datetime

    model_config = {
        'from_attributes': True,
    }


class DealOutcomeRecordCreate(BaseModel):
    entity_type: str = Field(..., min_length=3, max_length=16)
    entity_id: int = Field(..., ge=1)
    outcome: str = Field(..., min_length=3, max_length=32)
    reason_code: str = Field(default='unspecified', min_length=2, max_length=64)
    reason_detail: Optional[str] = Field(default=None, max_length=4000)
    competitor: Optional[str] = Field(default=None, max_length=256)
    deal_value: Optional[float] = Field(default=None, ge=0.0)
    currency: str = Field(default='USD', min_length=3, max_length=8)
    lead_id: Optional[int] = Field(default=None, ge=1)
    customer_id: Optional[int] = Field(default=None, ge=1)
    outcome_metadata: dict[str, Any] = Field(default_factory=dict)
    recorded_by: str = Field(default='sales', max_length=128)


class DealOutcomeRecordResponse(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    lead_id: Optional[int] = None
    customer_id: Optional[int] = None
    outcome: str
    reason_code: str
    reason_detail: Optional[str] = None
    competitor: Optional[str] = None
    deal_value: Optional[float] = None
    currency: str
    recorded_by: str
    outcome_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class DealOutcomeReasonBucket(BaseModel):
    reason_code: str
    count: int


class DealOutcomeAnalytics(BaseModel):
    generated_at: datetime
    window_days: int
    total_deals: int
    by_outcome: dict[str, int]
    by_entity_type: dict[str, int]
    by_reason_code: dict[str, int]
    win_rate: float
    total_deal_value: float
    won_deal_value: float
    top_loss_reasons: list[DealOutcomeReasonBucket]


class LegalChecklistItem(BaseModel):
    id: str
    label: str
    category: str
    status: str = 'pending'
    notes: str = ''


class RegionalLegalReviewCreate(BaseModel):
    entity_type: str = Field(..., min_length=2, max_length=32)
    entity_id: int = Field(..., ge=1)
    region: str = Field(..., min_length=2, max_length=64)
    regulation: str = Field(..., min_length=4, max_length=32)
    checklist_items: list[LegalChecklistItem] = Field(default_factory=list)
    reviewer: str = Field(default='legal', max_length=128)
    notes: Optional[str] = Field(default=None, max_length=4000)
    status: str = Field(default='pending', max_length=32)
    performed_by: str = Field(default='legal', max_length=128)


class RegionalLegalReviewUpdateRequest(BaseModel):
    status: str = Field(..., min_length=4, max_length=32)
    checklist_items: Optional[list[LegalChecklistItem]] = None
    notes: Optional[str] = Field(default=None, max_length=4000)
    reviewer: str = Field(default='legal', max_length=128)
    performed_by: str = Field(default='legal', max_length=128)


class RegionalLegalReviewResponse(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    region: str
    regulation: str
    status: str
    checklist_items: list[dict[str, Any]] = Field(default_factory=list)
    reviewer: str
    notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class MessageTemplateCreate(BaseModel):
    template_code: str = Field(..., min_length=2, max_length=128)
    template_type: str = Field(default='notification', max_length=32)
    translations: dict[str, dict[str, str]] = Field(default_factory=dict)
    default_locale: str = Field(default='en', max_length=8)
    usage_metadata: dict[str, Any] = Field(default_factory=dict)


class MessageTemplateResponse(BaseModel):
    id: int
    template_code: str
    template_type: str
    default_locale: str
    translations: dict[str, Any]
    usage_metadata: dict[str, Any]
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class ExternalIntegrationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    provider: str = Field(default='custom', max_length=64)
    entity_sync_types: list[str] = Field(default_factory=list)
    api_endpoint: Optional[str] = Field(default=None, max_length=512)
    sync_direction: str = Field(default='bidirectional', max_length=32)
    field_mappings: dict[str, str] = Field(default_factory=dict)
    integration_metadata: dict[str, Any] = Field(default_factory=dict)


class ExternalIntegrationResponse(BaseModel):
    id: int
    name: str
    provider: str
    status: str
    entity_sync_types: list[str]
    api_endpoint: Optional[str]
    sync_direction: str
    field_mappings: dict[str, Any]
    integration_metadata: dict[str, Any]
    last_sync_at: Optional[datetime]
    configured_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class IntegrationSyncRecordResponse(BaseModel):
    id: int
    integration_id: int
    entity_type: str
    entity_id: int
    sync_direction: str
    external_id: Optional[str]
    status: str
    sync_payload: dict[str, Any]
    error_message: Optional[str]
    synced_at: Optional[datetime]
    sync_metadata: dict[str, Any]
    created_at: datetime

    model_config = {
        'from_attributes': True,
    }


class EscalationCondition(BaseModel):
    field: str = Field(..., min_length=1)
    operator: str = Field(..., min_length=2)  # eq, ne, gt, gte, lt, lte, in, contains
    value: Any


class EscalationAction(BaseModel):
    action_type: str = Field(..., min_length=1)  # notify, create_alert, pause_order, etc.
    target: Optional[str] = None
    message: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EscalationRuleCreate(BaseModel):
    rule_code: str = Field(..., min_length=2, max_length=128)
    rule_type: str = Field(default='manual', max_length=32)
    entity_type: str = Field(default='order', max_length=32)
    conditions: list[EscalationCondition] = Field(..., min_items=1)
    actions: list[EscalationAction] = Field(..., min_items=1)
    priority: int = Field(default=5, ge=1, le=10)
    notify_roles: list[str] = Field(default_factory=list)
    sla_hours: Optional[int] = Field(default=None, ge=1)
    rule_metadata: dict[str, Any] = Field(default_factory=dict)


class EscalationRuleResponse(BaseModel):
    id: int
    rule_code: str
    rule_type: str
    entity_type: str
    status: str
    priority: int
    conditions: list[dict[str, Any]]
    actions: list[dict[str, Any]]
    notify_roles: list[str]
    sla_hours: Optional[int]
    rule_metadata: dict[str, Any]
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class EscalationRecordAction(BaseModel):
    action: str
    timestamp: str
    performed_by: str
    status: str


class EscalationRecordResponse(BaseModel):
    id: int
    rule_id: int
    entity_type: str
    entity_id: int
    trigger_reason: str
    severity: str
    status: str
    actions_taken: list[dict[str, Any]]
    resolution_notes: Optional[str]
    resolved_at: Optional[datetime]
    escalation_metadata: dict[str, Any]
    triggered_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class AIModelGovernanceCreate(BaseModel):
    model_name: str = Field(..., min_length=2, max_length=128)
    model_type: str = Field(default='negotiation', max_length=64)
    model_version: str = Field(..., min_length=1, max_length=64)
    approval_required: bool = True
    evaluation_metrics: dict[str, Any] = Field(default_factory=dict)
    governance_metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str = Field(default='mlops', max_length=128)


class AIModelGovernanceReviewRequest(BaseModel):
    decision: str = Field(..., min_length=8, max_length=16)  # approved/rejected
    reviewed_by: str = Field(default='mlops-review', max_length=128)
    note: Optional[str] = Field(default=None, max_length=2000)


class AIModelGovernanceRollbackRequest(BaseModel):
    model_name: str = Field(..., min_length=2, max_length=128)
    from_version: str = Field(..., min_length=1, max_length=64)
    to_version: str = Field(..., min_length=1, max_length=64)
    reason: str = Field(default='rollback requested', max_length=2000)
    performed_by: str = Field(default='mlops', max_length=128)


class AIModelGovernanceResponse(BaseModel):
    id: int
    model_name: str
    model_type: str
    model_version: str
    status: str
    approval_required: bool
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rollback_to_version: Optional[str] = None
    rollback_reason: Optional[str] = None
    evaluation_metrics: dict[str, Any] = Field(default_factory=dict)
    governance_metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class CurrencyExchangeRateUpsertRequest(BaseModel):
    base_currency: str = Field(..., min_length=3, max_length=8)
    quote_currency: str = Field(..., min_length=3, max_length=8)
    rate: float = Field(..., gt=0.0)
    source: str = Field(default='manual', max_length=64)
    rate_metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str = Field(default='finance', max_length=128)


class CurrencyExchangeRateResponse(BaseModel):
    id: int
    base_currency: str
    quote_currency: str
    rate: float
    source: str
    as_of: datetime
    rate_metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class TaxComplianceRuleUpsertRequest(BaseModel):
    region: str = Field(default='GLOBAL', max_length=64)
    country_code: str = Field(..., min_length=2, max_length=8)
    tax_name: str = Field(..., min_length=2, max_length=64)
    tax_type: str = Field(default='exclusive', max_length=16)
    tax_rate: float = Field(..., ge=0.0)
    applies_to: str = Field(default='order', max_length=32)
    rule_metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str = Field(default='finance', max_length=128)


class TaxComplianceRuleResponse(BaseModel):
    id: int
    region: str
    country_code: str
    tax_name: str
    tax_type: str
    tax_rate: float
    applies_to: str
    status: str
    effective_from: datetime
    effective_to: Optional[datetime] = None
    rule_metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class MultiCurrencyTaxPreviewRequest(BaseModel):
    amount: float = Field(..., ge=0.0)
    from_currency: str = Field(default='USD', min_length=3, max_length=8)
    to_currency: str = Field(default='USD', min_length=3, max_length=8)
    country_code: str = Field(default='US', min_length=2, max_length=8)


class MultiCurrencyTaxPreviewResponse(BaseModel):
    base_amount: float
    base_currency: str
    target_currency: str
    fx_rate: float
    converted_amount: float
    tax_name: str
    tax_amount: float
    total_amount: float
    country_code: str


class NurtureReengagementTriggerRunRequest(BaseModel):
    abandoned_after_hours: int = Field(default=24, ge=0, le=720)
    lookback_days: int = Field(default=30, ge=1, le=365)
    limit: int = Field(default=200, ge=1, le=500)
    performed_by: str = Field(default='marketing', max_length=128)


class NurtureReengagementTriggerResponse(BaseModel):
    id: int
    lead_id: Optional[int] = None
    source_type: str
    source_id: int
    campaign_type: str
    reason: str
    status: str
    trigger_metadata: dict[str, Any] = Field(default_factory=dict)
    triggered_by: str
    triggered_at: datetime
    created_at: datetime

    model_config = {
        'from_attributes': True,
    }


class MarketSignalIngestItem(BaseModel):
    source_name: str = Field(..., min_length=2, max_length=128)
    signal_type: str = Field(default='trend', min_length=2, max_length=64)
    product_name: str = Field(..., min_length=2, max_length=256)
    region: str = Field(default='GLOBAL', min_length=2, max_length=64)
    raw_score: float = Field(default=0.0, ge=0.0, le=100.0)
    sentiment: str = Field(default='neutral', min_length=4, max_length=16)
    price_drop_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    demand_spike_pct: float = Field(default=0.0, ge=0.0, le=300.0)
    signal_metadata: dict[str, Any] = Field(default_factory=dict)
    observed_at: Optional[datetime] = None


class MarketSignalIngestRequest(BaseModel):
    events: list[MarketSignalIngestItem] = Field(..., min_length=1)
    performed_by: str = Field(default='market-intelligence', max_length=128)


class MarketSignalIngestResponse(BaseModel):
    ingested: int
    opportunities_detected: int
    alerts_created: int


class MarketOpportunityResponse(BaseModel):
    id: int
    signal_event_id: int
    product_name: str
    region: str
    opportunity_score: float
    confidence_score: float
    status: str
    summary: Optional[str] = None
    validation_notes: Optional[str] = None
    opportunity_metadata: dict[str, Any] = Field(default_factory=dict)
    detected_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class MarketOpportunityValidateRequest(BaseModel):
    decision: str = Field(..., min_length=8, max_length=16)  # validated/rejected
    validator_type: str = Field(default='human', min_length=2, max_length=16)  # human/ai
    validation_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    rejection_reason: Optional[str] = Field(default=None, max_length=256)
    validation_notes: Optional[str] = Field(default=None, max_length=4000)
    validated_by: str = Field(default='system', max_length=128)


class MarketOpportunityValidationResponse(BaseModel):
    id: int
    opportunity_id: int
    from_status: str
    to_status: str
    validator_type: str
    validation_score: Optional[float] = None
    rejection_reason: Optional[str] = None
    validation_notes: Optional[str] = None
    validated_by: str
    created_at: datetime

    model_config = {
        'from_attributes': True,
    }


class MarketValidationRegionMetrics(BaseModel):
    region: str
    total_validations: int
    approved: int
    rejected: int
    precision: float


class MarketOpportunityValidationMetricsResponse(BaseModel):
    lookback_days: int
    total_validations: int
    approved: int
    rejected: int
    precision: float
    false_positive_rate: float
    by_region: list[MarketValidationRegionMetrics]


class MarketSourceReliabilityResponse(BaseModel):
    id: int
    source_name: str
    reliability_score: float
    sample_count: int
    last_signal_at: Optional[datetime] = None
    reliability_metadata: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class MarketIntelligenceSummaryResponse(BaseModel):
    total_opportunities: int
    high_priority: int
    average_score: float
    top_regions: dict[str, int]


class ABTestCampaignRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=256)
    description: Optional[str] = Field(default=None, max_length=1024)
    target_segment: str = Field(default='all', max_length=128)
    variants: dict[str, Any] = Field(default_factory=dict)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: str = Field(default='draft', min_length=4, max_length=32)


class ABTestCampaignResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    target_segment: str
    variants: dict[str, Any]
    start_date: datetime
    end_date: Optional[datetime] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class ABTestResultRequest(BaseModel):
    campaign_id: int
    lead_id: Optional[int] = None
    variant: str = Field(..., min_length=1, max_length=64)
    outcome: str = Field(..., min_length=3, max_length=32)
    value: Optional[float] = None
    metadata: Optional[dict[str, Any]] = Field(default_factory=dict)


class ABTestResultResponse(BaseModel):
    id: int
    campaign_id: int
    lead_id: Optional[int] = None
    variant: str
    outcome: str
    value: Optional[float] = None
    result_metadata: dict[str, Any]
    created_at: datetime

    model_config = {
        'from_attributes': True,
    }


class LeadScoreUpdateRequest(BaseModel):
    lead_id: int
    score: int = Field(..., ge=0, le=100)
    source: str = Field(default='autoscoring', max_length=64)
    notes: Optional[str] = Field(default=None, max_length=512)


class LeadScoreUpdateResponse(BaseModel):
    lead_id: int
    old_score: int
    new_score: int
    source: str
    notes: Optional[str] = None
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class ConsentRecordRequest(BaseModel):
    lead_id: int
    consent_type: str = Field(default='email', min_length=3, max_length=32)
    status: str = Field(default='granted', min_length=7, max_length=32)
    source: str = Field(default='system', max_length=64)
    region: str = Field(default='GLOBAL', max_length=32)
    policy_version: str = Field(default='1.0', max_length=32)
    notes: Optional[str] = Field(default=None, max_length=512)


class ConsentRecordResponse(BaseModel):
    id: int
    lead_id: int
    consent_type: str
    status: str
    granted_at: datetime
    revoked_at: Optional[datetime] = None
    source: str
    region: str
    policy_version: str
    notes: Optional[str] = None
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class ConsentStatusResponse(BaseModel):
    lead_id: int
    consented: bool
    active: bool
    last_update: Optional[datetime] = None

    model_config = {
        'from_attributes': True,
    }


class PaidAPIDataSourceRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=256)
    endpoint: str = Field(..., min_length=8, max_length=512)
    api_key: str = Field(..., min_length=8, max_length=512)
    active: bool = True
    polling_interval_minutes: int = Field(default=60, ge=1, le=1440)
    source_metadata: Optional[dict[str, Any]] = Field(default_factory=dict)


class PaidAPIDataSourceResponse(BaseModel):
    id: int
    name: str
    endpoint: str
    active: bool
    polling_interval_minutes: int
    source_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class PaidAPIIngestionResponse(BaseModel):
    source_id: int
    fetched_at: datetime
    events_fetched: int
    opportunities_created: int
    alerts_created: int
    details: Optional[str] = None

    model_config = {
        'from_attributes': True,
    }


class CampaignFatigueRequest(BaseModel):
    campaign_id: int | None = None
    lead_id: int
    increment_by: int = Field(default=1, ge=1)
    notes: Optional[str] = None


class CampaignFatigueResponse(BaseModel):
    id: int
    campaign_id: Optional[int] = None
    lead_id: int
    outreach_count: int
    last_outreach_at: datetime
    status: str
    fatigue_metadata: dict[str, Any]

    model_config = {
        'from_attributes': True,
    }


class FeedbackLoopRecordRequest(BaseModel):
    campaign_id: int | None = None
    lead_id: int | None = None
    event_type: str = Field(..., min_length=3, max_length=64)
    event_value: Optional[float] = None
    event_details: Optional[str] = None


class FeedbackLoopRecordResponse(BaseModel):
    id: int
    campaign_id: Optional[int] = None
    lead_id: Optional[int] = None
    event_type: str
    event_value: Optional[float] = None
    event_details: Optional[str] = None
    recorded_at: datetime

    model_config = {
        'from_attributes': True,
    }


class SalesRepRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=128)
    email: Optional[str] = Field(default=None, max_length=128)
    team: Optional[str] = Field(default=None, max_length=64)
    active: bool = True


class SalesRepResponse(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    team: Optional[str] = None
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class LeadAssignmentRequest(BaseModel):
    lead_id: int
    sales_rep_id: int
    assignment_notes: Optional[str] = None


class LeadAssignmentResponse(BaseModel):
    id: int
    lead_id: int
    sales_rep_id: int
    assigned_at: datetime
    updated_at: datetime
    status: str
    assignment_notes: Optional[str] = None

    model_config = {
        'from_attributes': True,
    }


class ABMMetricResponse(BaseModel):
    id: int
    campaign_id: Optional[int] = None
    region: str
    account_segment: str
    opportunity_count: int
    expected_value: float
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class SalesCadenceRequest(BaseModel):
    sales_rep_id: int
    lead_id: int
    cadence_step: str = Field(default='initial_outreach', min_length=3, max_length=64)
    status: str = Field(default='scheduled', min_length=3, max_length=32)
    due_at: Optional[datetime] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


class SalesCadenceResponse(BaseModel):
    id: int
    sales_rep_id: int
    lead_id: int
    cadence_step: str
    status: str
    due_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class RepPerformanceSnapshotRequest(BaseModel):
    sales_rep_id: int
    period_start: datetime
    period_end: datetime
    quota_target: float = Field(default=0.0, ge=0.0)
    revenue_achieved: float = Field(default=0.0, ge=0.0)


class RepPerformanceSnapshotResponse(BaseModel):
    id: int
    sales_rep_id: int
    period_start: datetime
    period_end: datetime
    opportunities_total: int
    opportunities_won: int
    win_rate: float
    quota_target: float
    revenue_achieved: float
    forecast_revenue: float
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
    }


class WinLossRecordRequest(BaseModel):
    opportunity_id: int
    lead_id: Optional[int] = None
    sales_rep_id: Optional[int] = None
    outcome: str = Field(..., min_length=3, max_length=16)
    reason: str = Field(..., min_length=3, max_length=512)
    recorded_by: str = Field(default='system', max_length=128)


class WinLossRecordResponse(BaseModel):
    id: int
    opportunity_id: int
    lead_id: Optional[int] = None
    sales_rep_id: Optional[int] = None
    outcome: str
    reason: str
    recorded_by: str
    created_at: datetime

    model_config = {
        'from_attributes': True,
    }


class MarketingFunnelAnalyticsResponse(BaseModel):
    lookback_days: int
    awareness: int
    engagement: int
    conversion: int
    conversion_rate: float


class AlertResponse(BaseModel):
    id: int
    title: str
    severity: str
    detail: Optional[str] = None
    category: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    resolved: bool = False
    created_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = {
        'from_attributes': True,
    }


class DataSourceStatus(BaseModel):
    name: str
    last_synced: Optional[datetime] = None

    model_config = {
        'from_attributes': True,
    }


class MonitoringDashboard(BaseModel):
    data_sources: list[DataSourceStatus]
    alerts: list[AlertResponse]
    audit_log: list[ComplianceLogEntry]
    schema_warnings: list[str]

    model_config = {
        'from_attributes': True,
    }
