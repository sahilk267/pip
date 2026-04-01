from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import (
    ExternalIntegrationEvent,
    IntegrationAck,
    MarketingAnalyticsOverview,
    MarketingAutomationDispatchRequest,
    MarketingAutomationDispatchResponse,
    MarketingCampaignTriggerRequest,
    MarketingCampaignTriggerResponse,
    MarketingDispatchStatusResponse,
    MarketingDispatchSyncResponse,
    MarketingIntentEvent,
    MarketingIntentResponse,
    MarketingOrderAnalyticsOverview,
    MarketingROIOverview,
    MarketingUpsellCrossSellTriggerRequest,
    NurtureReengagementTriggerResponse,
    NurtureReengagementTriggerRunRequest,
)
from ..crud import log_audit
from ..services.i18n_preview import strings_for_locale
from ..services.marketing_automation import dispatch_campaigns, get_dispatch_statuses, sync_dispatch_statuses
from ..services.marketing_campaigns import trigger_campaigns
from ..services.marketing_analytics import compute_marketing_analytics
from ..services.marketing_intent import record_marketing_intent_event
from ..services.marketing_order_analytics import compute_marketing_order_analytics
from ..services.marketing_roi import compute_campaign_roi
from ..services.nurture_reengagement import (
    list_nurture_triggers,
    trigger_from_abandoned_carts,
    trigger_from_deal_outcomes,
)

router = APIRouter()


@router.post('/api/v1/marketing/automation/event', response_model=IntegrationAck)
def marketing_automation_event(
    event: ExternalIntegrationEvent,
    db: Session = Depends(get_db),
    locale: str = 'en',
) -> IntegrationAck:
    """Marketing automation webhook/event stub.

    In Phase 1 this just records the event in AuditLog so downstream integrations
    can be wired later without losing traceability.
    """
    detail = f"{event.provider}:{event.event_type} keys={list(event.payload.keys())[:8]}"
    log_audit(
        db,
        'marketing',
        None,
        'automation_event',
        detail,
        performed_by=event.performed_by,
    )
    return IntegrationAck(
        status='accepted',
        detail=strings_for_locale(locale).get(
            'marketing.automation.accepted_detail',
            'Logged to AuditLog; configure marketing provider in Phase 2.',
        ),
    )


@router.post('/api/v1/marketing/intent/event', response_model=MarketingIntentResponse)
def marketing_intent_event(
    event: MarketingIntentEvent,
    db: Session = Depends(get_db),
) -> MarketingIntentResponse:
    lead = record_marketing_intent_event(
        db,
        lead_id=event.lead_id,
        source=event.source,
        signal_type=event.signal_type,
        strength=event.strength,
        metadata=event.metadata,
        performed_by=event.performed_by,
    )
    return MarketingIntentResponse(
        lead_id=lead.id,
        marketing_intent_score=int(lead.marketing_intent_score or 0),
        lead_score=int(lead.lead_score or 0),
        attribution_channel=lead.attribution_channel,
        marketing_intent_data=lead.marketing_intent_data or {},
    )


@router.get('/api/v1/marketing/analytics', response_model=MarketingAnalyticsOverview)
def marketing_analytics_overview(
    window_days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> MarketingAnalyticsOverview:
    metrics = compute_marketing_analytics(db, window_days=window_days)
    return MarketingAnalyticsOverview(**metrics)


@router.post('/api/v1/marketing/campaigns/trigger', response_model=MarketingCampaignTriggerResponse)
def trigger_marketing_campaigns(
    payload: MarketingCampaignTriggerRequest,
    db: Session = Depends(get_db),
) -> MarketingCampaignTriggerResponse:
    response = trigger_campaigns(
        db,
        campaign_type=payload.campaign_type,
        limit=payload.limit,
        performed_by=payload.performed_by,
    )
    return MarketingCampaignTriggerResponse(**response)


@router.post('/api/v1/marketing/campaigns/dispatch', response_model=MarketingAutomationDispatchResponse)
def dispatch_marketing_campaigns(
    payload: MarketingAutomationDispatchRequest,
    db: Session = Depends(get_db),
) -> MarketingAutomationDispatchResponse:
    response = dispatch_campaigns(
        db,
        campaign_type=payload.campaign_type,
        limit=payload.limit,
        provider_override=payload.provider_override,
        performed_by=payload.performed_by,
    )
    return MarketingAutomationDispatchResponse(**response)


@router.post('/api/v1/marketing/campaigns/upsell-cross-sell/trigger', response_model=MarketingAutomationDispatchResponse)
def trigger_upsell_cross_sell_campaigns(
    payload: MarketingUpsellCrossSellTriggerRequest,
    db: Session = Depends(get_db),
) -> MarketingAutomationDispatchResponse:
    response = dispatch_campaigns(
        db,
        campaign_type='upsell_cross_sell',
        limit=payload.limit,
        provider_override=payload.provider_override,
        performed_by=payload.performed_by,
    )
    return MarketingAutomationDispatchResponse(**response)


@router.get('/api/v1/marketing/roi', response_model=MarketingROIOverview)
def marketing_campaign_roi(
    window_days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> MarketingROIOverview:
    payload = compute_campaign_roi(db, window_days=window_days)
    return MarketingROIOverview(**payload)


@router.get('/api/v1/marketing/orders/attribution', response_model=MarketingOrderAnalyticsOverview)
def marketing_order_attribution(
    window_days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> MarketingOrderAnalyticsOverview:
    payload = compute_marketing_order_analytics(db, window_days=window_days)
    return MarketingOrderAnalyticsOverview(**payload)


@router.get('/api/v1/marketing/dispatches', response_model=list[MarketingDispatchStatusResponse])
def list_marketing_dispatches(
    limit: int = Query(default=100, ge=1, le=500),
    status: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[MarketingDispatchStatusResponse]:
    rows = get_dispatch_statuses(db, limit=limit, status=status, provider=provider)
    return [MarketingDispatchStatusResponse.model_validate(row) for row in rows]


@router.post('/api/v1/marketing/dispatches/sync', response_model=MarketingDispatchSyncResponse)
def sync_marketing_dispatches(
    limit: int = Query(default=200, ge=1, le=1000),
    performed_by: str = Query(default='marketing-sync'),
    db: Session = Depends(get_db),
) -> MarketingDispatchSyncResponse:
    result = sync_dispatch_statuses(db, limit=limit, performed_by=performed_by)
    return MarketingDispatchSyncResponse(**result)


@router.post('/api/v1/marketing/campaigns/nurture-reengagement/trigger')
def run_nurture_reengagement_triggers(
    payload: NurtureReengagementTriggerRunRequest,
    db: Session = Depends(get_db),
) -> dict:
    abandoned = trigger_from_abandoned_carts(
        db,
        abandoned_after_hours=payload.abandoned_after_hours,
        limit=payload.limit,
        performed_by=payload.performed_by,
    )
    outcomes = trigger_from_deal_outcomes(
        db,
        lookback_days=payload.lookback_days,
        limit=payload.limit,
        performed_by=payload.performed_by,
    )
    return {
        'abandoned_cart_triggers': len(abandoned),
        'deal_outcome_triggers': len(outcomes),
        'total_triggers': len(abandoned) + len(outcomes),
    }


@router.get('/api/v1/marketing/campaigns/nurture-reengagement/triggers', response_model=list[NurtureReengagementTriggerResponse])
def get_nurture_reengagement_triggers(
    source_type: str | None = Query(default=None),
    campaign_type: str | None = Query(default=None),
    lead_id: int | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[NurtureReengagementTriggerResponse]:
    rows = list_nurture_triggers(
        db,
        source_type=source_type,
        campaign_type=campaign_type,
        lead_id=lead_id,
        limit=limit,
    )
    return [NurtureReengagementTriggerResponse.model_validate(row) for row in rows]

