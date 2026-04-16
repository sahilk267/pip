from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import (
    AIModelGovernanceCreate,
    AIModelGovernanceResponse,
    AIModelGovernanceReviewRequest,
    AIModelGovernanceRollbackRequest,
    ChatbotEscalationRequest,
    ChatbotEscalationResponse,
    ExplainabilityResponse,
    EthicsReviewResponse,
    FraudFeedbackRequest,
    FraudFeedbackResponse,
    FraudRiskResponse,
    HumanOverrideRequest,
    HumanOverrideStatusResponse,
    InventoryForecastResponse,
    ModelDriftStatusResponse,
    PersonalizedRecommendationsResponse,
    SalesProcessEnforcementResponse,
    SelfLearningFeedbackRequest,
    SelfLearningFeedbackResponse,
    BiasFairnessResponse,
    CompetitorMonitoringResponse,
    DynamicPricingResponse,
    ExternalIntegrationResponse,
    MessageTemplateResponse,
    RegionalLegalReviewResponse,
    MarketingAutomationDispatchRequest,
    MarketingAutomationDispatchResponse,
    CurrencyExchangeRateResponse,
    CurrencyExchangeRateUpsertRequest,
    CustomerUpdateNotificationResponse,
    DealOutcomeAnalytics,
    DealOutcomeRecordCreate,
    DealOutcomeRecordResponse,
    MultiCurrencyTaxPreviewRequest,
    MultiCurrencyTaxPreviewResponse,
    PricingApprovalRequestCreate,
    PricingApprovalRequestResponse,
    PricingApprovalReviewRequest,
    QuoteToCashRecordAdvanceRequest,
    QuoteToCashRecordCreate,
    QuoteToCashRecordResponse,
    SalesRepNotificationCreate,
    SalesRepNotificationResponse,
    SalesRepNotificationStatusPatch,
    TaxComplianceRuleResponse,
    TaxComplianceRuleUpsertRequest,
)
from ..services.ai_model_governance import (
    list_model_records,
    register_model_record,
    review_model_record,
    rollback_model_record,
)
from ..services.currency_tax import (
    pricing_preview,
    upsert_exchange_rate,
    upsert_tax_rule,
)
from ..services.customer_updates import list_customer_updates
from ..services.deal_outcomes import (
    deal_outcome_analytics,
    list_deal_outcomes,
    record_deal_outcome,
)
from ..services.pricing_approvals import (
    create_pricing_approval_request,
    list_pricing_approval_requests,
    review_pricing_approval_request,
)
from ..services.quote_to_cash import (
    advance_quote_to_cash_record,
    create_quote_to_cash_record,
    list_quote_to_cash_records,
)
from ..services.sales_notifications import (
    create_sales_notification,
    list_sales_notifications,
    update_sales_notification_status,
)
from ..services.external_integrations import list_integrations
from ..services.legal_review import list_legal_reviews
from ..services.message_templates import list_message_templates
from ..services.marketing_automation import dispatch_campaigns
from ..services.ai_automation import (
    assess_bias_fairness,
    assess_fraud_risk,
    evaluate_data_ethics_review,
    evaluate_model_drift,
    evaluate_sales_process_enforcement,
    generate_explainability,
    generate_personalized_recommendations,
    forecast_inventory_demand,
    get_human_override_status,
    monitor_competitor_pricing,
    record_fraud_feedback,
    record_human_override,
    record_self_learning_feedback,
    recommend_dynamic_pricing,
    trigger_chatbot_escalation,
)

router = APIRouter()


@router.post('/api/v1/automation/sales-notifications', response_model=SalesRepNotificationResponse)
def create_notification(
    payload: SalesRepNotificationCreate,
    db: Session = Depends(get_db),
) -> SalesRepNotificationResponse:
    try:
        row = create_sales_notification(
            db,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            notification_type=payload.notification_type,
            message=payload.message,
            priority=payload.priority,
            lead_id=payload.lead_id,
            recipient=payload.recipient,
            channel=payload.channel,
            metadata=payload.metadata,
            performed_by=payload.performed_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SalesRepNotificationResponse.model_validate(row)


@router.get('/api/v1/automation/sales-notifications', response_model=list[SalesRepNotificationResponse])
def get_notifications(
    notification_status: str | None = Query(default=None),
    recipient: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[SalesRepNotificationResponse]:
    rows = list_sales_notifications(db, status=notification_status, recipient=recipient, limit=limit)
    return [SalesRepNotificationResponse.model_validate(row) for row in rows]


@router.patch('/api/v1/automation/sales-notifications/{notification_id}', response_model=SalesRepNotificationResponse)
def patch_notification_status(
    notification_id: int,
    payload: SalesRepNotificationStatusPatch,
    db: Session = Depends(get_db),
) -> SalesRepNotificationResponse:
    try:
        row = update_sales_notification_status(
            db,
            notification_id=notification_id,
            status=payload.status,
            performed_by=payload.performed_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if detail == 'Sales notification not found' else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return SalesRepNotificationResponse.model_validate(row)


@router.post('/api/v1/automation/pricing-approvals', response_model=PricingApprovalRequestResponse)
def create_approval_request(
    payload: PricingApprovalRequestCreate,
    db: Session = Depends(get_db),
) -> PricingApprovalRequestResponse:
    try:
        row = create_pricing_approval_request(
            db,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            requested_discount_pct=payload.requested_discount_pct,
            requested_discount_amount=payload.requested_discount_amount,
            reason=payload.reason,
            requested_by=payload.requested_by,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return PricingApprovalRequestResponse.model_validate(row)


@router.get('/api/v1/automation/pricing-approvals', response_model=list[PricingApprovalRequestResponse])
def get_approval_requests(
    entity_type: str | None = Query(default=None),
    approval_status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[PricingApprovalRequestResponse]:
    rows = list_pricing_approval_requests(db, entity_type=entity_type, status=approval_status, limit=limit)
    return [PricingApprovalRequestResponse.model_validate(row) for row in rows]


@router.post('/api/v1/automation/pricing-approvals/{request_id}/review', response_model=PricingApprovalRequestResponse)
def review_approval_request(
    request_id: int,
    payload: PricingApprovalReviewRequest,
    db: Session = Depends(get_db),
) -> PricingApprovalRequestResponse:
    try:
        row = review_pricing_approval_request(
            db,
            request_id=request_id,
            decision=payload.decision,
            approved_discount_pct=payload.approved_discount_pct,
            approved_discount_amount=payload.approved_discount_amount,
            review_note=payload.review_note,
            reviewed_by=payload.reviewed_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return PricingApprovalRequestResponse.model_validate(row)


@router.post('/api/v1/automation/quote-to-cash', response_model=QuoteToCashRecordResponse)
def create_qtc_record(
    payload: QuoteToCashRecordCreate,
    db: Session = Depends(get_db),
) -> QuoteToCashRecordResponse:
    try:
        row = create_quote_to_cash_record(
            db,
            quote_id=payload.quote_id,
            order_id=payload.order_id,
            customer_id=payload.customer_id,
            external_system=payload.external_system,
            created_by=payload.created_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return QuoteToCashRecordResponse.model_validate(row)


@router.get('/api/v1/automation/quote-to-cash', response_model=list[QuoteToCashRecordResponse])
def get_qtc_records(
    qtc_status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[QuoteToCashRecordResponse]:
    rows = list_quote_to_cash_records(db, status=qtc_status, limit=limit)
    return [QuoteToCashRecordResponse.model_validate(row) for row in rows]


@router.post('/api/v1/automation/quote-to-cash/{record_id}/advance', response_model=QuoteToCashRecordResponse)
def advance_qtc_record(
    record_id: int,
    payload: QuoteToCashRecordAdvanceRequest,
    db: Session = Depends(get_db),
) -> QuoteToCashRecordResponse:
    try:
        row = advance_quote_to_cash_record(
            db,
            record_id=record_id,
            status=payload.status,
            payment_status=payload.payment_status,
            external_reference=payload.external_reference,
            performed_by=payload.performed_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return QuoteToCashRecordResponse.model_validate(row)


# ---------- Customer update notifications ----------

@router.get('/api/v1/automation/customer-updates', response_model=list[CustomerUpdateNotificationResponse])
def get_customer_updates(
    order_id: int | None = Query(default=None),
    lead_id: int | None = Query(default=None),
    update_status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[CustomerUpdateNotificationResponse]:
    rows = list_customer_updates(db, order_id=order_id, lead_id=lead_id, status=update_status, limit=limit)
    return [CustomerUpdateNotificationResponse.model_validate(row) for row in rows]


# ---------- Win/loss reason capture ----------

@router.post('/api/v1/automation/deal-outcomes', response_model=DealOutcomeRecordResponse)
def create_deal_outcome(
    payload: DealOutcomeRecordCreate,
    db: Session = Depends(get_db),
) -> DealOutcomeRecordResponse:
    try:
        row = record_deal_outcome(
            db,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            outcome=payload.outcome,
            reason_code=payload.reason_code,
            reason_detail=payload.reason_detail,
            competitor=payload.competitor,
            deal_value=payload.deal_value,
            currency=payload.currency,
            lead_id=payload.lead_id,
            customer_id=payload.customer_id,
            outcome_metadata=payload.outcome_metadata,
            recorded_by=payload.recorded_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DealOutcomeRecordResponse.model_validate(row)


@router.get('/api/v1/automation/deal-outcomes', response_model=list[DealOutcomeRecordResponse])
def get_deal_outcomes(
    entity_type: str | None = Query(default=None),
    deal_outcome: str | None = Query(default=None),
    reason_code: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[DealOutcomeRecordResponse]:
    rows = list_deal_outcomes(db, entity_type=entity_type, outcome=deal_outcome, reason_code=reason_code, limit=limit)
    return [DealOutcomeRecordResponse.model_validate(row) for row in rows]


@router.get('/api/v1/automation/deal-outcomes/analytics', response_model=DealOutcomeAnalytics)
def get_deal_outcome_analytics(
    window_days: int = Query(default=90, ge=1, le=365),
    db: Session = Depends(get_db),
) -> DealOutcomeAnalytics:
    payload = deal_outcome_analytics(db, window_days=window_days)
    return DealOutcomeAnalytics(**payload)


# ---------- AI model governance ----------

@router.post('/api/v1/automation/ai-governance/models', response_model=AIModelGovernanceResponse)
def create_ai_model_record(
    payload: AIModelGovernanceCreate,
    db: Session = Depends(get_db),
) -> AIModelGovernanceResponse:
    try:
        row = register_model_record(
            db,
            model_name=payload.model_name,
            model_type=payload.model_type,
            model_version=payload.model_version,
            approval_required=payload.approval_required,
            evaluation_metrics=payload.evaluation_metrics,
            governance_metadata=payload.governance_metadata,
            created_by=payload.created_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AIModelGovernanceResponse.model_validate(row)


@router.post('/api/v1/automation/ai-governance/models/{record_id}/review', response_model=AIModelGovernanceResponse)
def review_ai_model_record(
    record_id: int,
    payload: AIModelGovernanceReviewRequest,
    db: Session = Depends(get_db),
) -> AIModelGovernanceResponse:
    try:
        row = review_model_record(
            db,
            record_id=record_id,
            decision=payload.decision,
            reviewed_by=payload.reviewed_by,
            note=payload.note,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return AIModelGovernanceResponse.model_validate(row)


@router.post('/api/v1/automation/ai-governance/models/rollback', response_model=AIModelGovernanceResponse)
def rollback_ai_model_record(
    payload: AIModelGovernanceRollbackRequest,
    db: Session = Depends(get_db),
) -> AIModelGovernanceResponse:
    try:
        row = rollback_model_record(
            db,
            model_name=payload.model_name,
            from_version=payload.from_version,
            to_version=payload.to_version,
            reason=payload.reason,
            performed_by=payload.performed_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return AIModelGovernanceResponse.model_validate(row)


@router.get('/api/v1/automation/ai-governance/models', response_model=list[AIModelGovernanceResponse])
def get_ai_model_records(
    model_name: str | None = Query(default=None),
    governance_status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[AIModelGovernanceResponse]:
    rows = list_model_records(db, model_name=model_name, status=governance_status, limit=limit)
    return [AIModelGovernanceResponse.model_validate(row) for row in rows]


@router.post('/api/v1/automation/feedback-loop', response_model=SelfLearningFeedbackResponse)
def submit_feedback_loop(
    payload: SelfLearningFeedbackRequest,
    db: Session = Depends(get_db),
) -> SelfLearningFeedbackResponse:
    result = record_self_learning_feedback(
        db,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        rating=payload.rating,
        outcome=payload.outcome,
        comments=payload.comments,
        performed_by=payload.performed_by,
    )
    return SelfLearningFeedbackResponse(**result)


@router.get('/api/v1/automation/explainability', response_model=ExplainabilityResponse)
def get_ai_explainability(
    entity_type: str = Query(default='order', min_length=2, max_length=64),
    entity_id: int = Query(..., ge=1),
    model_name: str | None = Query(default='ai_auto'),
    context: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ExplainabilityResponse:
    result = generate_explainability(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        model_name=model_name or 'ai_auto',
        context=context,
    )
    return ExplainabilityResponse(**result)


@router.get('/api/v1/automation/model-drift', response_model=ModelDriftStatusResponse)
def get_model_drift(
    model_name: str | None = Query(default=None),
    window_days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> ModelDriftStatusResponse:
    result = evaluate_model_drift(db, model_name=model_name, window_days=window_days)
    return ModelDriftStatusResponse(**result)


@router.post('/api/v1/automation/human-override', response_model=HumanOverrideStatusResponse)
def post_human_override(
    payload: HumanOverrideRequest,
    db: Session = Depends(get_db),
) -> HumanOverrideStatusResponse:
    result = record_human_override(
        db,
        action=payload.action,
        reason=payload.reason,
        performed_by=payload.performed_by,
    )
    return HumanOverrideStatusResponse(**result)


@router.get('/api/v1/automation/human-override', response_model=HumanOverrideStatusResponse)
def get_human_override(
    db: Session = Depends(get_db),
) -> HumanOverrideStatusResponse:
    result = get_human_override_status(db)
    return HumanOverrideStatusResponse(**result)


@router.get('/api/v1/automation/fraud-risk', response_model=FraudRiskResponse)
def get_fraud_risk(
    order_id: int | None = Query(default=None, ge=1),
    total_amount: float | None = Query(default=None, ge=0.0),
    source_channel: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> FraudRiskResponse:
    result = assess_fraud_risk(db, order_id=order_id, total_amount=total_amount, source_channel=source_channel)
    return FraudRiskResponse(**result)


@router.get('/api/v1/automation/inventory/forecast', response_model=InventoryForecastResponse)
def get_inventory_forecast(
    sku: str | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=180),
    db: Session = Depends(get_db),
) -> InventoryForecastResponse:
    result = forecast_inventory_demand(db, sku=sku, days=days)
    return InventoryForecastResponse(**result)


@router.get('/api/v1/automation/recommendations/personalized', response_model=PersonalizedRecommendationsResponse)
def get_personalized_recommendations(
    lead_id: int | None = Query(default=None, ge=1),
    customer_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
) -> PersonalizedRecommendationsResponse:
    result = generate_personalized_recommendations(db, lead_id=lead_id, customer_id=customer_id, limit=limit)
    return PersonalizedRecommendationsResponse(**result)


@router.post('/api/v1/automation/chatbot/escalation', response_model=ChatbotEscalationResponse)
def create_chatbot_escalation(
    payload: ChatbotEscalationRequest,
    db: Session = Depends(get_db),
) -> ChatbotEscalationResponse:
    result = trigger_chatbot_escalation(
        db,
        issue_description=payload.issue_description,
        fallback_channel=payload.fallback_channel,
        performed_by=payload.performed_by,
    )
    return ChatbotEscalationResponse(**result)


@router.post('/api/v1/automation/marketing/dispatch', response_model=MarketingAutomationDispatchResponse)
def dispatch_automation_marketing_campaign(
    payload: MarketingAutomationDispatchRequest,
    db: Session = Depends(get_db),
) -> MarketingAutomationDispatchResponse:
    try:
        result = dispatch_campaigns(
            db,
            campaign_type=payload.campaign_type,
            limit=payload.limit,
            provider_override=payload.provider_override,
            performed_by=payload.performed_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MarketingAutomationDispatchResponse(**result)


@router.get('/api/v1/automation/data-ethics', response_model=EthicsReviewResponse)
def get_data_ethics_review(
    scope: str = Query(default='automation', min_length=3, max_length=64),
    region: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> EthicsReviewResponse:
    result = evaluate_data_ethics_review(db, scope=scope, region=region)
    return EthicsReviewResponse(**result)


@router.get('/api/v1/automation/legal-reviews', response_model=list[RegionalLegalReviewResponse])
def get_automation_legal_reviews(
    region: str | None = Query(default=None),
    regulation: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[RegionalLegalReviewResponse]:
    rows = list_legal_reviews(
        db,
        region=region,
        regulation=regulation,
        status=review_status,
        limit=limit,
    )
    return [RegionalLegalReviewResponse.model_validate(row) for row in rows]


@router.get('/api/v1/automation/competitor-monitoring', response_model=CompetitorMonitoringResponse)
def get_competitor_monitoring(
    product_name: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> CompetitorMonitoringResponse:
    result = monitor_competitor_pricing(db, product_name=product_name, limit=limit)
    return CompetitorMonitoringResponse(**result)


@router.get('/api/v1/automation/dynamic-pricing', response_model=DynamicPricingResponse)
def get_dynamic_pricing(
    sku: str | None = Query(default=None),
    base_price: float = Query(default=100.0, ge=0.0),
    demand_factor: float = Query(default=1.0, ge=0.1, le=3.0),
    db: Session = Depends(get_db),
) -> DynamicPricingResponse:
    result = recommend_dynamic_pricing(db, sku=sku, base_price=base_price, demand_factor=demand_factor)
    return DynamicPricingResponse(**result)


@router.post('/api/v1/automation/fraud-feedback', response_model=FraudFeedbackResponse)
def post_fraud_feedback(
    payload: FraudFeedbackRequest,
    db: Session = Depends(get_db),
) -> FraudFeedbackResponse:
    result = record_fraud_feedback(
        db,
        order_id=payload.order_id,
        feedback=payload.feedback,
        severity=payload.severity,
        performed_by=payload.performed_by,
    )
    return FraudFeedbackResponse(**result)


@router.get('/api/v1/automation/bias-fairness', response_model=BiasFairnessResponse)
def get_bias_fairness(
    model_name: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> BiasFairnessResponse:
    result = assess_bias_fairness(db, model_name=model_name)
    return BiasFairnessResponse(**result)


@router.get('/api/v1/automation/sales-process/enforcement', response_model=SalesProcessEnforcementResponse)
def get_sales_process_enforcement(
    sales_rep_id: int | None = Query(default=None, ge=1),
    entity_type: str | None = Query(default=None),
    entity_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> SalesProcessEnforcementResponse:
    result = evaluate_sales_process_enforcement(
        db,
        sales_rep_id=sales_rep_id,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    return SalesProcessEnforcementResponse(**result)


@router.get('/api/v1/automation/integrations/external', response_model=list[ExternalIntegrationResponse])
def list_automation_external_integrations(
    provider: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[ExternalIntegrationResponse]:
    rows = list_integrations(db, provider=provider, status=status, limit=limit)
    return [ExternalIntegrationResponse.model_validate(row) for row in rows]


@router.get('/api/v1/automation/governance/multi-language', response_model=list[MessageTemplateResponse])
def get_automation_multi_language_templates(
    template_type: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[MessageTemplateResponse]:
    rows = list_message_templates(db, template_type=template_type, limit=limit)
    return [MessageTemplateResponse.model_validate(row) for row in rows]


# ---------- Multi-currency & tax compliance ----------

@router.post('/api/v1/automation/currency-rates', response_model=CurrencyExchangeRateResponse)
def create_currency_rate(
    payload: CurrencyExchangeRateUpsertRequest,
    db: Session = Depends(get_db),
) -> CurrencyExchangeRateResponse:
    try:
        row = upsert_exchange_rate(
            db,
            base_currency=payload.base_currency,
            quote_currency=payload.quote_currency,
            rate=payload.rate,
            source=payload.source,
            rate_metadata=payload.rate_metadata,
            created_by=payload.created_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CurrencyExchangeRateResponse.model_validate(row)


@router.post('/api/v1/automation/tax-rules', response_model=TaxComplianceRuleResponse)
def create_tax_rule(
    payload: TaxComplianceRuleUpsertRequest,
    db: Session = Depends(get_db),
) -> TaxComplianceRuleResponse:
    try:
        row = upsert_tax_rule(
            db,
            region=payload.region,
            country_code=payload.country_code,
            tax_name=payload.tax_name,
            tax_type=payload.tax_type,
            tax_rate=payload.tax_rate,
            applies_to=payload.applies_to,
            rule_metadata=payload.rule_metadata,
            created_by=payload.created_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TaxComplianceRuleResponse.model_validate(row)


@router.post('/api/v1/automation/pricing/preview', response_model=MultiCurrencyTaxPreviewResponse)
def get_pricing_preview(
    payload: MultiCurrencyTaxPreviewRequest,
    db: Session = Depends(get_db),
) -> MultiCurrencyTaxPreviewResponse:
    try:
        result = pricing_preview(
            db,
            amount=payload.amount,
            from_currency=payload.from_currency,
            to_currency=payload.to_currency,
            country_code=payload.country_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MultiCurrencyTaxPreviewResponse(**result)

