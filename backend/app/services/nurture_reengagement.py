from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit

_ALLOWED_CONSENT = {'yes', 'true', 'opt_in'}


def _is_marketing_allowed(lead: models.Lead | None) -> bool:
    if lead is None:
        return False
    if lead.unsubscribed_at is not None:
        return False
    return str(lead.marketing_consent or '').strip().lower() in _ALLOWED_CONSENT


def _already_triggered(
    db: Session,
    *,
    source_type: str,
    source_id: int,
    campaign_type: str,
    within_hours: int = 24,
) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, int(within_hours)))
    row = (
        db.query(models.NurtureReengagementTrigger)
        .filter(
            models.NurtureReengagementTrigger.source_type == source_type,
            models.NurtureReengagementTrigger.source_id == int(source_id),
            models.NurtureReengagementTrigger.campaign_type == campaign_type,
            models.NurtureReengagementTrigger.created_at >= cutoff,
        )
        .first()
    )
    return row is not None


def trigger_from_abandoned_carts(
    db: Session,
    *,
    abandoned_after_hours: int = 24,
    limit: int = 200,
    performed_by: str = 'marketing',
) -> list[models.NurtureReengagementTrigger]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(0, min(int(abandoned_after_hours), 24 * 30)))
    rows = (
        db.query(models.B2CCart)
        .filter(
            models.B2CCart.status == 'active',
            models.B2CCart.updated_at <= cutoff,
        )
        .order_by(models.B2CCart.updated_at.asc(), models.B2CCart.id.asc())
        .limit(max(1, min(int(limit), 500)))
        .all()
    )

    triggered: list[models.NurtureReengagementTrigger] = []

    for cart in rows:
        if _already_triggered(db, source_type='abandoned_cart', source_id=cart.id, campaign_type='reengagement'):
            continue

        lead = None
        if cart.lead_id is not None:
            lead = db.query(models.Lead).filter(models.Lead.id == int(cart.lead_id)).first()
        if not _is_marketing_allowed(lead):
            continue

        trigger = models.NurtureReengagementTrigger(
            lead_id=cart.lead_id,
            source_type='abandoned_cart',
            source_id=cart.id,
            campaign_type='reengagement',
            reason='active cart inactive beyond threshold',
            status='triggered',
            trigger_metadata={
                'cart_total_amount': float(cart.total_amount or 0.0),
                'currency': str(cart.currency or 'USD'),
                'abandoned_after_hours': int(abandoned_after_hours),
            },
            triggered_by=str(performed_by or 'marketing').strip()[:128] or 'marketing',
            triggered_at=datetime.now(timezone.utc),
        )
        db.add(trigger)

        cart.status = 'abandoned'
        db.add(cart)

        dispatch = models.MarketingCampaignDispatch(
            lead_id=cart.lead_id,
            provider='mailchimp',
            campaign_type='reengagement',
            channel='web',
            status='sent',
            payload={
                'source_type': 'abandoned_cart',
                'source_id': cart.id,
                'performed_by': performed_by,
            },
            dispatched_at=datetime.now(timezone.utc),
        )
        db.add(dispatch)
        triggered.append(trigger)

        log_audit(
            db,
            'marketing',
            cart.id,
            'abandoned_cart_reengagement_triggered',
            f'cart_id={cart.id} lead_id={cart.lead_id}',
            performed_by=performed_by,
        )

    db.commit()
    for row in triggered:
        db.refresh(row)
    return triggered


def trigger_from_deal_outcomes(
    db: Session,
    *,
    lookback_days: int = 30,
    limit: int = 200,
    performed_by: str = 'marketing',
) -> list[models.NurtureReengagementTrigger]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, min(int(lookback_days), 365)))
    outcomes = (
        db.query(models.DealOutcomeRecord)
        .filter(
            models.DealOutcomeRecord.created_at >= cutoff,
            models.DealOutcomeRecord.outcome.in_(['lost', 'abandoned', 'expired']),
            models.DealOutcomeRecord.lead_id.isnot(None),
        )
        .order_by(models.DealOutcomeRecord.created_at.desc(), models.DealOutcomeRecord.id.desc())
        .limit(max(1, min(int(limit), 500)))
        .all()
    )

    triggered: list[models.NurtureReengagementTrigger] = []

    for outcome in outcomes:
        if _already_triggered(db, source_type='deal_outcome', source_id=outcome.id, campaign_type='nurture'):
            continue

        lead = db.query(models.Lead).filter(models.Lead.id == int(outcome.lead_id)).first()
        if not _is_marketing_allowed(lead):
            continue

        trigger = models.NurtureReengagementTrigger(
            lead_id=outcome.lead_id,
            source_type='deal_outcome',
            source_id=outcome.id,
            campaign_type='nurture',
            reason=f'deal_outcome={outcome.outcome}',
            status='triggered',
            trigger_metadata={
                'entity_type': outcome.entity_type,
                'entity_id': int(outcome.entity_id),
                'outcome': str(outcome.outcome),
                'reason_code': str(outcome.reason_code or 'unspecified'),
            },
            triggered_by=str(performed_by or 'marketing').strip()[:128] or 'marketing',
            triggered_at=datetime.now(timezone.utc),
        )
        db.add(trigger)

        dispatch = models.MarketingCampaignDispatch(
            lead_id=outcome.lead_id,
            provider='hubspot',
            campaign_type='nurture',
            channel='email',
            status='sent',
            payload={
                'source_type': 'deal_outcome',
                'source_id': outcome.id,
                'performed_by': performed_by,
            },
            dispatched_at=datetime.now(timezone.utc),
        )
        db.add(dispatch)
        triggered.append(trigger)

        log_audit(
            db,
            'marketing',
            outcome.id,
            'deal_outcome_nurture_triggered',
            f'outcome_id={outcome.id} lead_id={outcome.lead_id} outcome={outcome.outcome}',
            performed_by=performed_by,
        )

    db.commit()
    for row in triggered:
        db.refresh(row)
    return triggered


def list_nurture_triggers(
    db: Session,
    *,
    source_type: str | None = None,
    campaign_type: str | None = None,
    lead_id: int | None = None,
    limit: int = 200,
) -> list[models.NurtureReengagementTrigger]:
    query = db.query(models.NurtureReengagementTrigger)
    if source_type:
        query = query.filter(models.NurtureReengagementTrigger.source_type == str(source_type).strip().lower())
    if campaign_type:
        query = query.filter(models.NurtureReengagementTrigger.campaign_type == str(campaign_type).strip().lower())
    if lead_id is not None:
        query = query.filter(models.NurtureReengagementTrigger.lead_id == int(lead_id))

    return (
        query
        .order_by(models.NurtureReengagementTrigger.created_at.desc(), models.NurtureReengagementTrigger.id.desc())
        .limit(max(1, min(int(limit), 500)))
        .all()
    )
