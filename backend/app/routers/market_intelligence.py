from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..schemas import (
    MarketIntelligenceSummaryResponse,
    MarketOpportunityResponse,
    MarketOpportunityValidateRequest,
    MarketOpportunityValidationMetricsResponse,
    MarketOpportunityValidationResponse,
    MarketSignalIngestRequest,
    MarketSignalIngestResponse,
    MarketSourceReliabilityResponse,
    ABTestCampaignRequest,
    ABTestCampaignResponse,
    ABTestResultRequest,
    ABTestResultResponse,
    LeadScoreUpdateRequest,
    LeadScoreUpdateResponse,
    ConsentRecordRequest,
    ConsentRecordResponse,
    ConsentStatusResponse,
    PaidAPIDataSourceRequest,
    PaidAPIDataSourceResponse,
    PaidAPIIngestionResponse,
    CampaignFatigueRequest,
    CampaignFatigueResponse,
    FeedbackLoopRecordRequest,
    FeedbackLoopRecordResponse,
    SalesRepRequest,
    SalesRepResponse,
    LeadAssignmentRequest,
    LeadAssignmentResponse,
    ABMMetricResponse,
    SalesCadenceRequest,
    SalesCadenceResponse,
    RepPerformanceSnapshotRequest,
    RepPerformanceSnapshotResponse,
    WinLossRecordRequest,
    WinLossRecordResponse,
    MarketingFunnelAnalyticsResponse,
    RegionalLegalReviewCreate,
    RegionalLegalReviewResponse,
    MessageTemplateCreate,
    MessageTemplateResponse,
    ExternalIntegrationCreate,
    ExternalIntegrationResponse,
    IntegrationSyncRecordResponse,
    EscalationRuleCreate,
    EscalationRuleResponse,
    EscalationRecordResponse,
    AIModelGovernanceCreate,
    AIModelGovernanceReviewRequest,
    AIModelGovernanceRollbackRequest,
    AIModelGovernanceResponse,
    ComplianceReport,
    DealOutcomeRecordCreate,
    DealOutcomeRecordResponse,
    DealOutcomeAnalytics,
)
from ..services.market_intelligence import (
    ingest_market_signals,
    list_ab_test_campaigns,
    list_consent_records,
    list_market_opportunities,
    list_market_opportunity_validations,
    list_paid_api_data_sources,
    list_paid_api_ingestion_logs,
    list_source_reliability,
    market_intelligence_summary,
    market_opportunity_validation_metrics,
    create_ab_test_campaign,
    create_consent_record,
    create_paid_api_data_source,
    get_ab_test_metrics,
    get_consent_status,
    ingest_from_paid_api_source,
    list_campaign_fatigue_records,
    list_feedback_loop_records,
    record_campaign_fatigue,
    record_feedback_loop_event,
    list_sales_reps,
    create_sales_rep,
    assign_lead_to_sales_rep,
    list_lead_assignments,
    compute_abm_analytics,
    list_abm_metrics,
    create_sales_cadence_record,
    list_sales_cadence_records,
    create_rep_performance_snapshot,
    list_rep_performance_snapshots,
    create_win_loss_record,
    list_win_loss_records,
    marketing_funnel_analytics,
    update_lead_score,
    validate_market_opportunity,
    add_ab_test_result,
)
from ..services.legal_review import (
    get_checklist_template,
    get_region_regulations,
    record_legal_review,
    list_legal_reviews,
)
from ..services.message_templates import (
    create_message_template,
    get_localized_message,
    list_message_templates,
)
from ..services.external_integrations import (
    register_integration,
    list_integrations,
    record_sync,
    list_sync_records,
)
from ..services.escalation_rules import (
    create_escalation_rule,
    list_escalation_rules,
    trigger_escalation,
    list_escalation_records,
)
from ..services.ai_model_governance import (
    register_model_record,
    review_model_record,
    rollback_model_record,
    list_model_records,
)
from ..services.compliance import generate_compliance_report
from ..services.deal_outcomes import (
    record_deal_outcome,
    list_deal_outcomes,
    deal_outcome_analytics,
)
from ..services.lead_intelligence import apply_lead_segmentation
from ..services.marketing_automation import dispatch_campaigns, get_dispatch_statuses

router = APIRouter()


@router.post('/api/v1/market-intelligence/signals/ingest', response_model=MarketSignalIngestResponse)
def ingest_signals(payload: MarketSignalIngestRequest, db: Session = Depends(get_db)) -> MarketSignalIngestResponse:
    result = ingest_market_signals(
        db,
        events=[row.model_dump() for row in payload.events],
        performed_by=payload.performed_by,
    )
    return MarketSignalIngestResponse(**result)


@router.get('/api/v1/market-intelligence/opportunities', response_model=list[MarketOpportunityResponse])
def get_opportunities(
    region: str | None = Query(default=None),
    min_score: float = Query(default=0.0, ge=0.0, le=100.0),
    opportunity_status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[MarketOpportunityResponse]:
    rows = list_market_opportunities(
        db,
        region=region,
        min_score=min_score,
        status=opportunity_status,
        limit=limit,
    )
    return [MarketOpportunityResponse.model_validate(row) for row in rows]


@router.get('/api/v1/market-intelligence/sources/reliability', response_model=list[MarketSourceReliabilityResponse])
def get_source_reliability(
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[MarketSourceReliabilityResponse]:
    rows = list_source_reliability(db, limit=limit)
    return [MarketSourceReliabilityResponse.model_validate(row) for row in rows]


@router.get('/api/v1/market-intelligence/summary', response_model=MarketIntelligenceSummaryResponse)
def get_market_summary(
    region: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> MarketIntelligenceSummaryResponse:
    payload = market_intelligence_summary(db, region=region)
    return MarketIntelligenceSummaryResponse(**payload)


@router.post('/api/v1/market-intelligence/ab-tests', response_model=ABTestCampaignResponse)
def create_ab_test(
    payload: ABTestCampaignRequest,
    db: Session = Depends(get_db),
) -> ABTestCampaignResponse:
    try:
        row = create_ab_test_campaign(
            db,
            name=payload.name,
            description=payload.description,
            target_segment=payload.target_segment,
            variants=payload.variants,
            start_date=payload.start_date,
            end_date=payload.end_date,
            status=payload.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ABTestCampaignResponse.model_validate(row)


@router.get('/api/v1/market-intelligence/ab-tests', response_model=list[ABTestCampaignResponse])
def get_ab_tests(db: Session = Depends(get_db)) -> list[ABTestCampaignResponse]:
    rows = list_ab_test_campaigns(db)
    return [ABTestCampaignResponse.model_validate(row) for row in rows]


@router.post('/api/v1/market-intelligence/ab-tests/results', response_model=ABTestResultResponse)
def create_ab_test_result(
    payload: ABTestResultRequest,
    db: Session = Depends(get_db),
) -> ABTestResultResponse:
    try:
        row = add_ab_test_result(
            db,
            campaign_id=payload.campaign_id,
            variant=payload.variant,
            outcome=payload.outcome,
            lead_id=payload.lead_id,
            value=payload.value,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ABTestResultResponse.model_validate(row)


@router.get('/api/v1/market-intelligence/ab-tests/{campaign_id}/metrics')
def get_ab_test_report(campaign_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        payload = get_ab_test_metrics(db, campaign_id=campaign_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return payload


@router.post('/api/v1/market-intelligence/leads/{lead_id}/score', response_model=LeadScoreUpdateResponse)
def set_lead_score(
    lead_id: int,
    payload: LeadScoreUpdateRequest,
    db: Session = Depends(get_db),
) -> LeadScoreUpdateResponse:
    if payload.lead_id != lead_id:
        raise HTTPException(status_code=400, detail='lead_id mismatch')
    try:
        result = update_lead_score(
            db,
            lead_id=lead_id,
            score=payload.score,
            source=payload.source,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return LeadScoreUpdateResponse.model_validate(result)


@router.post('/api/v1/market-intelligence/leads/{lead_id}/consent', response_model=ConsentRecordResponse)
def set_lead_consent(
    lead_id: int,
    payload: ConsentRecordRequest,
    db: Session = Depends(get_db),
) -> ConsentRecordResponse:
    if payload.lead_id != lead_id:
        raise HTTPException(status_code=400, detail='lead_id mismatch')
    try:
        row = create_consent_record(
            db,
            lead_id=lead_id,
            consent_type=payload.consent_type,
            status=payload.status,
            source=payload.source,
            region=payload.region,
            policy_version=payload.policy_version,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ConsentRecordResponse.model_validate(row)


@router.get('/api/v1/market-intelligence/leads/{lead_id}/consent', response_model=ConsentStatusResponse)
def get_lead_consent_status(lead_id: int, db: Session = Depends(get_db)) -> ConsentStatusResponse:
    try:
        payload = get_consent_status(db, lead_id=lead_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ConsentStatusResponse.model_validate(payload)


@router.get('/api/v1/market-intelligence/leads/{lead_id}/consent/records', response_model=list[ConsentRecordResponse])
def get_lead_consent_records(lead_id: int, db: Session = Depends(get_db)) -> list[ConsentRecordResponse]:
    rows = list_consent_records(db, lead_id=lead_id)
    return [ConsentRecordResponse.model_validate(row) for row in rows]


@router.post('/api/v1/market-intelligence/ai-governance/models', response_model=AIModelGovernanceResponse)
def create_phase3_ai_model_record(
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


@router.post('/api/v1/market-intelligence/ai-governance/models/{record_id}/review', response_model=AIModelGovernanceResponse)
def review_phase3_ai_model_record(
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


@router.post('/api/v1/market-intelligence/ai-governance/models/rollback', response_model=AIModelGovernanceResponse)
def rollback_phase3_ai_model_record(
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


@router.get('/api/v1/market-intelligence/ai-governance/models', response_model=list[AIModelGovernanceResponse])
def get_phase3_ai_model_records(
    model_name: str | None = Query(default=None),
    governance_status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[AIModelGovernanceResponse]:
    rows = list_model_records(db, model_name=model_name, status=governance_status, limit=limit)
    return [AIModelGovernanceResponse.model_validate(row) for row in rows]


@router.get('/api/v1/market-intelligence/governance-compliance/records', response_model=ComplianceReport)
def get_phase3_governance_compliance_records(
    window_minutes: int = Query(default=1440, ge=1, le=10080),
    db: Session = Depends(get_db),
) -> ComplianceReport:
    payload = generate_compliance_report(db, window_minutes=window_minutes)
    return ComplianceReport(**payload)


@router.post('/api/v1/market-intelligence/competitive-campaigns', response_model=DealOutcomeRecordResponse)
def create_phase3_competitive_campaign_record(
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


@router.get('/api/v1/market-intelligence/competitive-campaigns', response_model=list[DealOutcomeRecordResponse])
def get_phase3_competitive_campaign_records(
    entity_type: str | None = Query(default=None),
    outcome: str | None = Query(default=None),
    reason_code: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[DealOutcomeRecordResponse]:
    rows = list_deal_outcomes(db, entity_type=entity_type, outcome=outcome, reason_code=reason_code, limit=limit)
    return [DealOutcomeRecordResponse.model_validate(row) for row in rows]


@router.get('/api/v1/market-intelligence/competitive-campaigns/analytics', response_model=DealOutcomeAnalytics)
def get_phase3_competitive_campaign_analytics(
    window_days: int = Query(default=90, ge=1, le=365),
    db: Session = Depends(get_db),
) -> DealOutcomeAnalytics:
    payload = deal_outcome_analytics(db, window_days=window_days)
    return DealOutcomeAnalytics(**payload)


@router.post('/api/v1/market-intelligence/marketing-segmentation/run')
def run_phase3_marketing_segmentation(
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> dict:
    result = apply_lead_segmentation(db, limit=limit)

    rows = (
        db.query(models.Lead.segment, models.Lead.id)
        .order_by(models.Lead.id.asc())
        .all()
    )
    leads_by_segment: dict[str, int] = {}
    for segment, _lead_id in rows:
        key = str(segment or 'unsegmented')
        leads_by_segment[key] = int(leads_by_segment.get(key, 0)) + 1

    return {
        'leads_scored': int(result.get('leads_scored', 0)),
        'total_leads': len(rows),
        'leads_by_segment': leads_by_segment,
    }


@router.get('/api/v1/market-intelligence/marketing-segmentation/summary')
def get_phase3_marketing_segmentation_summary(db: Session = Depends(get_db)) -> dict:
    rows = (
        db.query(models.Lead.segment, models.Lead.id)
        .order_by(models.Lead.id.asc())
        .all()
    )
    leads_by_segment: dict[str, int] = {}
    for segment, _lead_id in rows:
        key = str(segment or 'unsegmented')
        leads_by_segment[key] = int(leads_by_segment.get(key, 0)) + 1
    return {
        'total_leads': len(rows),
        'leads_by_segment': leads_by_segment,
    }


@router.post('/api/v1/market-intelligence/ad-platforms/dispatch')
def dispatch_phase3_ad_platform_campaigns(
    campaign_type: str = Query(default='nurture'),
    platform: str = Query(default='google_ads'),
    limit: int = Query(default=100, ge=1, le=500),
    performed_by: str = Query(default='marketing-ad-sync'),
    db: Session = Depends(get_db),
) -> dict:
    normalized_platform = str(platform or '').strip().lower()
    if normalized_platform not in {'google_ads', 'linkedin_ads'}:
        raise HTTPException(status_code=400, detail='platform must be google_ads or linkedin_ads')
    try:
        result = dispatch_campaigns(
            db,
            campaign_type=campaign_type,
            limit=limit,
            provider_override=normalized_platform,
            performed_by=performed_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        'platform': normalized_platform,
        'campaign_type': str(campaign_type).strip().lower(),
        'triggered': int(result.get('triggered', 0)),
        'dispatched': int(result.get('dispatched', 0)),
        'providers': result.get('providers', {}),
        'campaign_types': result.get('campaign_types', {}),
    }


@router.get('/api/v1/market-intelligence/ad-platforms/dispatches')
def get_phase3_ad_platform_dispatches(
    platform: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[dict]:
    provider = str(platform).strip().lower() if platform else None
    rows = get_dispatch_statuses(db, limit=limit, status=status, provider=provider)
    return [
        {
            'id': row.id,
            'lead_id': row.lead_id,
            'provider': row.provider,
            'campaign_type': row.campaign_type,
            'channel': row.channel,
            'status': row.status,
            'external_id': row.external_id,
            'payload': row.payload or {},
            'created_at': row.created_at,
            'dispatched_at': row.dispatched_at,
            'last_synced_at': row.last_synced_at,
        }
        for row in rows
    ]


@router.get('/api/v1/market-intelligence/b2c-product-trends')
def get_phase3_b2c_product_trends(
    window_days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    orders = (
        db.query(models.B2COrder)
        .filter(models.B2COrder.created_at >= cutoff)
        .order_by(models.B2COrder.created_at.asc(), models.B2COrder.id.asc())
        .all()
    )

    by_product: dict[str, dict] = {}
    for order in orders:
        for item in (order.order_items or []):
            if not isinstance(item, dict):
                continue
            name = str(item.get('name') or item.get('sku') or '').strip()
            if not name:
                continue
            qty = int(item.get('quantity') or 1)
            price = float(item.get('unit_price') or item.get('price') or 0.0)
            bucket = by_product.setdefault(name, {'product': name, 'orders': 0, 'units': 0, 'revenue': 0.0})
            bucket['orders'] += 1
            bucket['units'] += max(1, qty)
            bucket['revenue'] += max(0.0, price) * max(1, qty)

    ranked = sorted(
        by_product.values(),
        key=lambda row: (-int(row['units']), -float(row['revenue']), row['product']),
    )[:limit]

    for row in ranked:
        row['revenue'] = round(float(row['revenue']), 2)

    return {
        'window_days': window_days,
        'orders_analyzed': len(orders),
        'trending_products': ranked,
    }


@router.get('/api/v1/market-intelligence/b2c-personalization/recommendations')
def get_phase3_b2c_personalized_recommendations(
    lead_id: int | None = Query(default=None),
    top_k: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
) -> dict:
    order_query = db.query(models.B2COrder)
    if lead_id is not None:
        order_query = order_query.filter(models.B2COrder.lead_id == lead_id)
    orders = order_query.order_by(models.B2COrder.created_at.desc(), models.B2COrder.id.desc()).limit(300).all()

    if not orders:
        global_trends = (
            db.query(models.B2COrder)
            .order_by(models.B2COrder.created_at.desc(), models.B2COrder.id.desc())
            .limit(300)
            .all()
        )
    else:
        global_trends = orders

    counters: dict[str, int] = defaultdict(int)
    for order in global_trends:
        for item in (order.order_items or []):
            if not isinstance(item, dict):
                continue
            name = str(item.get('name') or item.get('sku') or '').strip()
            if not name:
                continue
            qty = int(item.get('quantity') or 1)
            counters[name] += max(1, qty)

    ranked = sorted(counters.items(), key=lambda row: (-row[1], row[0]))[:top_k]
    recommendations = [
        {
            'product': name,
            'score': int(score),
            'reason': 'Based on recent B2C purchase patterns and product momentum',
        }
        for name, score in ranked
    ]

    top_channel = (
        db.query(models.B2COrder.source_channel, func.count(models.B2COrder.id))
        .group_by(models.B2COrder.source_channel)
        .order_by(func.count(models.B2COrder.id).desc())
        .first()
    )

    return {
        'lead_id': lead_id,
        'recommendations': recommendations,
        'recommended_channel': (top_channel[0] if top_channel else 'web'),
        'orders_considered': len(global_trends),
    }


@router.get('/api/v1/market-intelligence/legal-review/template')
def get_phase3_legal_review_template(
    region: str = Query(default='GLOBAL'),
    regulation: str | None = Query(default=None),
) -> dict:
    regulations = [str(regulation).strip().upper()] if regulation else get_region_regulations(region)
    templates = {r: get_checklist_template(r, entity_type='campaign') for r in regulations}
    return {
        'region': str(region).strip().upper(),
        'regulations': regulations,
        'templates': templates,
    }


@router.post('/api/v1/market-intelligence/legal-review/records', response_model=RegionalLegalReviewResponse)
def create_phase3_legal_review_record(
    payload: RegionalLegalReviewCreate,
    db: Session = Depends(get_db),
) -> RegionalLegalReviewResponse:
    try:
        row = record_legal_review(
            db,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            region=payload.region,
            regulation=payload.regulation,
            checklist_items=payload.checklist_items,
            reviewer=payload.reviewer,
            notes=payload.notes,
            status=payload.status,
            performed_by='legal',
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RegionalLegalReviewResponse.model_validate(row)


@router.get('/api/v1/market-intelligence/legal-review/records', response_model=list[RegionalLegalReviewResponse])
def get_phase3_legal_review_records(
    entity_type: str | None = Query(default=None),
    region: str | None = Query(default=None),
    regulation: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[RegionalLegalReviewResponse]:
    rows = list_legal_reviews(
        db,
        entity_type=entity_type,
        region=region,
        regulation=regulation,
        status=status,
        limit=limit,
    )
    return [RegionalLegalReviewResponse.model_validate(r) for r in rows]


@router.post('/api/v1/market-intelligence/i18n/templates', response_model=MessageTemplateResponse)
def create_phase3_message_template(payload: MessageTemplateCreate, db: Session = Depends(get_db)) -> MessageTemplateResponse:
    try:
        row = create_message_template(
            db,
            template_code=payload.template_code,
            template_type=payload.template_type,
            translations=payload.translations,
            default_locale=payload.default_locale,
            usage_metadata=payload.usage_metadata,
            created_by='system',
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MessageTemplateResponse.model_validate(row)


@router.get('/api/v1/market-intelligence/i18n/templates', response_model=list[MessageTemplateResponse])
def get_phase3_message_templates(
    template_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[MessageTemplateResponse]:
    rows = list_message_templates(db, template_type=template_type, limit=limit)
    return [MessageTemplateResponse.model_validate(r) for r in rows]


@router.get('/api/v1/market-intelligence/i18n/templates/{template_code}/localized')
def get_phase3_localized_message(
    template_code: str,
    locale: str = Query(default='en'),
    product: str | None = Query(default=None),
    region: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    variables = {}
    if product:
        variables['product'] = product
    if region:
        variables['region'] = region
    message = get_localized_message(db, template_code=template_code, locale=locale, variables=variables)
    if not message:
        raise HTTPException(status_code=404, detail='Template or locale not found')
    return {'template_code': template_code, 'locale': locale, 'message': message}


@router.post('/api/v1/market-intelligence/integrations/external', response_model=ExternalIntegrationResponse)
def create_phase3_external_integration(payload: ExternalIntegrationCreate, db: Session = Depends(get_db)) -> ExternalIntegrationResponse:
    try:
        row = register_integration(
            db,
            name=payload.name,
            provider=payload.provider,
            entity_sync_types=payload.entity_sync_types,
            api_endpoint=payload.api_endpoint,
            sync_direction=payload.sync_direction,
            field_mappings=payload.field_mappings,
            integration_metadata=payload.integration_metadata,
            configured_by='system',
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ExternalIntegrationResponse.model_validate(row)


@router.get('/api/v1/market-intelligence/integrations/external', response_model=list[ExternalIntegrationResponse])
def get_phase3_external_integrations(
    provider: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[ExternalIntegrationResponse]:
    rows = list_integrations(db, provider=provider, status=status, limit=limit)
    return [ExternalIntegrationResponse.model_validate(r) for r in rows]


@router.post('/api/v1/market-intelligence/integrations/external/{integration_id}/sync', response_model=IntegrationSyncRecordResponse)
def create_phase3_integration_sync_record(
    integration_id: int,
    entity_type: str = Query(...),
    entity_id: int = Query(...),
    sync_direction: str = Query(default='outbound'),
    external_id: str | None = Query(default=None),
    status: str = Query(default='pending'),
    db: Session = Depends(get_db),
) -> IntegrationSyncRecordResponse:
    try:
        row = record_sync(
            db,
            integration_id=integration_id,
            entity_type=entity_type,
            entity_id=entity_id,
            sync_direction=sync_direction,
            external_id=external_id,
            status=status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return IntegrationSyncRecordResponse.model_validate(row)


@router.get('/api/v1/market-intelligence/integrations/sync-records', response_model=list[IntegrationSyncRecordResponse])
def get_phase3_integration_sync_records(
    integration_id: int | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[IntegrationSyncRecordResponse]:
    rows = list_sync_records(db, integration_id=integration_id, entity_type=entity_type, status=status, limit=limit)
    return [IntegrationSyncRecordResponse.model_validate(r) for r in rows]


@router.post('/api/v1/market-intelligence/escalation-playbook/rules', response_model=EscalationRuleResponse)
def create_phase3_escalation_rule(payload: EscalationRuleCreate, db: Session = Depends(get_db)) -> EscalationRuleResponse:
    try:
        row = create_escalation_rule(
            db,
            rule_code=payload.rule_code,
            rule_type=payload.rule_type,
            entity_type=payload.entity_type,
            conditions=[c.model_dump() for c in payload.conditions],
            actions=[a.model_dump() for a in payload.actions],
            priority=payload.priority,
            notify_roles=payload.notify_roles,
            sla_hours=payload.sla_hours,
            rule_metadata=payload.rule_metadata,
            created_by='system',
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return EscalationRuleResponse.model_validate(row)


@router.get('/api/v1/market-intelligence/escalation-playbook/rules', response_model=list[EscalationRuleResponse])
def get_phase3_escalation_rules(
    entity_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    rule_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[EscalationRuleResponse]:
    rows = list_escalation_rules(db, entity_type=entity_type, status=status, rule_type=rule_type, limit=limit)
    return [EscalationRuleResponse.model_validate(r) for r in rows]


@router.post('/api/v1/market-intelligence/escalation-playbook/trigger', response_model=EscalationRecordResponse)
def trigger_phase3_escalation(
    rule_id: int = Query(...),
    entity_type: str = Query(...),
    entity_id: int = Query(...),
    trigger_reason: str = Query(default='manual'),
    severity: str = Query(default='warning'),
    db: Session = Depends(get_db),
) -> EscalationRecordResponse:
    try:
        row = trigger_escalation(
            db,
            rule_id=rule_id,
            entity_type=entity_type,
            entity_id=entity_id,
            trigger_reason=trigger_reason,
            severity=severity,
            triggered_by='system',
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return EscalationRecordResponse.model_validate(row)


@router.get('/api/v1/market-intelligence/escalation-playbook/records', response_model=list[EscalationRecordResponse])
def get_phase3_escalation_records(
    rule_id: int | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[EscalationRecordResponse]:
    rows = list_escalation_records(
        db,
        rule_id=rule_id,
        entity_type=entity_type,
        status=status,
        severity=severity,
        limit=limit,
    )
    return [EscalationRecordResponse.model_validate(r) for r in rows]

@router.post('/api/v1/market-intelligence/sales-reps', response_model=SalesRepResponse)
def create_sales_rep_endpoint(payload: SalesRepRequest, db: Session = Depends(get_db)) -> SalesRepResponse:
    try:
        rep = create_sales_rep(
            db,
            name=payload.name,
            email=payload.email,
            team=payload.team,
            active=payload.active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SalesRepResponse.model_validate(rep)


@router.get('/api/v1/market-intelligence/sales-reps', response_model=list[SalesRepResponse])
def get_sales_reps(db: Session = Depends(get_db)) -> list[SalesRepResponse]:
    reps = list_sales_reps(db)
    return [SalesRepResponse.model_validate(rep) for rep in reps]


@router.post('/api/v1/market-intelligence/lead-assignments', response_model=LeadAssignmentResponse)
def assign_lead(payload: LeadAssignmentRequest, db: Session = Depends(get_db)) -> LeadAssignmentResponse:
    try:
        assignment = assign_lead_to_sales_rep(
            db,
            lead_id=payload.lead_id,
            sales_rep_id=payload.sales_rep_id,
            assignment_notes=payload.assignment_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return LeadAssignmentResponse.model_validate(assignment)


@router.get('/api/v1/market-intelligence/lead-assignments', response_model=list[LeadAssignmentResponse])
def get_lead_assignments(
    lead_id: int | None = Query(default=None),
    sales_rep_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[LeadAssignmentResponse]:
    rows = list_lead_assignments(db, lead_id=lead_id, sales_rep_id=sales_rep_id, limit=limit)
    return [LeadAssignmentResponse.model_validate(row) for row in rows]


@router.get('/api/v1/market-intelligence/abm-metrics', response_model=list[ABMMetricResponse])
def get_abm_metrics(
    region: str | None = Query(default=None),
    account_segment: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[ABMMetricResponse]:
    rows = list_abm_metrics(db, region=region, account_segment=account_segment, limit=limit)
    return [ABMMetricResponse.model_validate(row) for row in rows]


@router.post('/api/v1/market-intelligence/abm-metrics', response_model=ABMMetricResponse)
def update_abm_metrics(
    region: str = 'GLOBAL',
    account_segment: str = 'enterprise',
    db: Session = Depends(get_db),
) -> ABMMetricResponse:
    payload = compute_abm_analytics(db, region=region, account_segment=account_segment)
    row = db.query(models.ABMMetric).filter(models.ABMMetric.region == payload['region'], models.ABMMetric.account_segment == payload['account_segment']).first()
    if not row:
        raise HTTPException(status_code=500, detail='ABM metric record could not be created')
    return ABMMetricResponse.model_validate(row)

@router.post('/api/v1/market-intelligence/campaign-fatigue', response_model=CampaignFatigueResponse)
def apply_campaign_fatigue(payload: CampaignFatigueRequest, db: Session = Depends(get_db)) -> CampaignFatigueResponse:
    try:
        row = record_campaign_fatigue(
            db,
            lead_id=payload.lead_id,
            campaign_id=payload.campaign_id,
            increment_by=payload.increment_by,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CampaignFatigueResponse.model_validate({
        'id': row.id,
        'campaign_id': row.campaign_id,
        'lead_id': row.lead_id,
        'outreach_count': row.outreach_count,
        'last_outreach_at': row.last_outreach_at,
        'status': row.status,
        'fatigue_metadata': row.fatigue_metadata or {},
    })


@router.get('/api/v1/market-intelligence/campaign-fatigue', response_model=list[CampaignFatigueResponse])
def get_campaign_fatigue(
    lead_id: int | None = Query(default=None),
    campaign_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[CampaignFatigueResponse]:
    rows = list_campaign_fatigue_records(db, lead_id=lead_id, campaign_id=campaign_id, limit=limit)
    return [
        CampaignFatigueResponse.model_validate({
            'id': r.id,
            'campaign_id': r.campaign_id,
            'lead_id': r.lead_id,
            'outreach_count': r.outreach_count,
            'last_outreach_at': r.last_outreach_at,
            'status': r.status,
            'fatigue_metadata': r.fatigue_metadata or {},
        }) for r in rows
    ]


@router.post('/api/v1/market-intelligence/sales-cadence', response_model=SalesCadenceResponse)
def create_sales_cadence(payload: SalesCadenceRequest, db: Session = Depends(get_db)) -> SalesCadenceResponse:
    try:
        row = create_sales_cadence_record(
            db,
            sales_rep_id=payload.sales_rep_id,
            lead_id=payload.lead_id,
            cadence_step=payload.cadence_step,
            status=payload.status,
            due_at=payload.due_at,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SalesCadenceResponse.model_validate(row)


@router.get('/api/v1/market-intelligence/sales-cadence', response_model=list[SalesCadenceResponse])
def get_sales_cadence(
    sales_rep_id: int | None = Query(default=None),
    lead_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[SalesCadenceResponse]:
    rows = list_sales_cadence_records(db, sales_rep_id=sales_rep_id, lead_id=lead_id, status=status, limit=limit)
    return [SalesCadenceResponse.model_validate(r) for r in rows]


@router.post('/api/v1/market-intelligence/rep-performance', response_model=RepPerformanceSnapshotResponse)
def create_rep_performance(payload: RepPerformanceSnapshotRequest, db: Session = Depends(get_db)) -> RepPerformanceSnapshotResponse:
    row = create_rep_performance_snapshot(
        db,
        sales_rep_id=payload.sales_rep_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        quota_target=payload.quota_target,
        revenue_achieved=payload.revenue_achieved,
    )
    return RepPerformanceSnapshotResponse.model_validate(row)


@router.get('/api/v1/market-intelligence/rep-performance', response_model=list[RepPerformanceSnapshotResponse])
def get_rep_performance(
    sales_rep_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[RepPerformanceSnapshotResponse]:
    rows = list_rep_performance_snapshots(db, sales_rep_id=sales_rep_id, limit=limit)
    return [RepPerformanceSnapshotResponse.model_validate(r) for r in rows]


@router.post('/api/v1/market-intelligence/win-loss', response_model=WinLossRecordResponse)
def create_win_loss(payload: WinLossRecordRequest, db: Session = Depends(get_db)) -> WinLossRecordResponse:
    try:
        row = create_win_loss_record(
            db,
            opportunity_id=payload.opportunity_id,
            lead_id=payload.lead_id,
            sales_rep_id=payload.sales_rep_id,
            outcome=payload.outcome,
            reason=payload.reason,
            recorded_by=payload.recorded_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WinLossRecordResponse.model_validate(row)


@router.get('/api/v1/market-intelligence/win-loss', response_model=list[WinLossRecordResponse])
def get_win_loss(
    sales_rep_id: int | None = Query(default=None),
    outcome: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[WinLossRecordResponse]:
    rows = list_win_loss_records(db, sales_rep_id=sales_rep_id, outcome=outcome, limit=limit)
    return [WinLossRecordResponse.model_validate(r) for r in rows]


@router.get('/api/v1/market-intelligence/marketing-funnel', response_model=MarketingFunnelAnalyticsResponse)
def get_marketing_funnel(
    lookback_days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> MarketingFunnelAnalyticsResponse:
    payload = marketing_funnel_analytics(db, lookback_days=lookback_days)
    return MarketingFunnelAnalyticsResponse(**payload)


@router.post('/api/v1/market-intelligence/feedback-loop', response_model=FeedbackLoopRecordResponse)
def create_feedback_loop_event(payload: FeedbackLoopRecordRequest, db: Session = Depends(get_db)) -> FeedbackLoopRecordResponse:
    try:
        row = record_feedback_loop_event(
            db,
            campaign_id=payload.campaign_id,
            lead_id=payload.lead_id,
            event_type=payload.event_type,
            event_value=payload.event_value,
            event_details=payload.event_details,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FeedbackLoopRecordResponse.model_validate(row)


@router.get('/api/v1/market-intelligence/feedback-loop', response_model=list[FeedbackLoopRecordResponse])
def get_feedback_loop_events(
    campaign_id: int | None = Query(default=None),
    lead_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[FeedbackLoopRecordResponse]:
    rows = list_feedback_loop_records(db, campaign_id=campaign_id, lead_id=lead_id, limit=limit)
    return [FeedbackLoopRecordResponse.model_validate(r) for r in rows]


@router.post('/api/v1/market-intelligence/paid-sources', response_model=PaidAPIDataSourceResponse)
def create_paid_source(
    payload: PaidAPIDataSourceRequest,
    db: Session = Depends(get_db),
) -> PaidAPIDataSourceResponse:
    try:
        source = create_paid_api_data_source(
            db,
            name=payload.name,
            endpoint=payload.endpoint,
            api_key=payload.api_key,
            active=payload.active,
            polling_interval_minutes=payload.polling_interval_minutes,
            source_metadata=payload.source_metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PaidAPIDataSourceResponse.model_validate(source)


@router.get('/api/v1/market-intelligence/paid-sources', response_model=list[PaidAPIDataSourceResponse])
def get_paid_sources(db: Session = Depends(get_db)) -> list[PaidAPIDataSourceResponse]:
    rows = list_paid_api_data_sources(db)
    return [PaidAPIDataSourceResponse.model_validate(row) for row in rows]


@router.post('/api/v1/market-intelligence/paid-sources/{source_id}/ingest', response_model=PaidAPIIngestionResponse)
def ingest_paid_source_data(
    source_id: int,
    db: Session = Depends(get_db),
) -> PaidAPIIngestionResponse:
    try:
        result = ingest_from_paid_api_source(db, source_id=source_id)
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return PaidAPIIngestionResponse.model_validate(result)


@router.get('/api/v1/market-intelligence/paid-sources/{source_id}/ingestion-logs', response_model=list[PaidAPIIngestionResponse])
def get_paid_source_ingestion_logs(
    source_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[PaidAPIIngestionResponse]:
    rows = list_paid_api_ingestion_logs(db, source_id=source_id, limit=limit)
    # convert to response objects; this uses dumped fields
    return [PaidAPIIngestionResponse.model_validate({
        'source_id': r.source_id,
        'fetched_at': r.fetched_at,
        'events_fetched': r.events_fetched,
        'opportunities_created': r.opportunities_created,
        'alerts_created': r.alerts_created,
        'details': r.details,
    }) for r in rows]


@router.get('/api/v1/market-intelligence/opportunities/validation/metrics', response_model=MarketOpportunityValidationMetricsResponse)
def get_validation_metrics(
    lookback_days: int = Query(default=30, ge=1, le=365),
    region: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> MarketOpportunityValidationMetricsResponse:
    payload = market_opportunity_validation_metrics(
        db,
        lookback_days=lookback_days,
        region=region,
    )
    return MarketOpportunityValidationMetricsResponse(**payload)


@router.patch('/api/v1/market-intelligence/opportunities/{opportunity_id}/validate', response_model=MarketOpportunityValidationResponse)
def validate_opportunity(
    opportunity_id: int,
    payload: MarketOpportunityValidateRequest,
    db: Session = Depends(get_db),
) -> MarketOpportunityValidationResponse:
    try:
        row = validate_market_opportunity(
            db,
            opportunity_id=opportunity_id,
            decision=payload.decision,
            validator_type=payload.validator_type,
            validation_score=payload.validation_score,
            rejection_reason=payload.rejection_reason,
            validation_notes=payload.validation_notes,
            validated_by=payload.validated_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return MarketOpportunityValidationResponse.model_validate(row)


@router.get('/api/v1/market-intelligence/opportunities/{opportunity_id}/validations', response_model=list[MarketOpportunityValidationResponse])
def get_opportunity_validations(
    opportunity_id: int,
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[MarketOpportunityValidationResponse]:
    rows = list_market_opportunity_validations(db, opportunity_id=opportunity_id, limit=limit)
    return [MarketOpportunityValidationResponse.model_validate(row) for row in rows]
