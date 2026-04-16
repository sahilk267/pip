from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit
from .alerting import create_alert

_SENTIMENT_SCORES = {
    'positive': 1.0,
    'neutral': 0.0,
    'negative': -1.0,
}


def _normalize_sentiment(value: str | None) -> tuple[str, float]:
    sentiment = str(value or 'neutral').strip().lower()
    if sentiment not in _SENTIMENT_SCORES:
        sentiment = 'neutral'
    return sentiment, float(_SENTIMENT_SCORES[sentiment])


def _upsert_source_reliability(db: Session, *, source_name: str, signal_score: float, observed_at: datetime) -> models.MarketDataSourceReliability:
    source = str(source_name or '').strip().lower()[:128]
    if not source:
        source = 'unknown'

    row = db.query(models.MarketDataSourceReliability).filter(models.MarketDataSourceReliability.source_name == source).first()
    if row is None:
        row = models.MarketDataSourceReliability(
            source_name=source,
            reliability_score=0.5,
            sample_count=0,
            last_signal_at=observed_at,
            reliability_metadata={},
        )

    sample_count = int(row.sample_count or 0) + 1
    prev = float(row.reliability_score or 0.5)
    target = max(0.0, min(float(signal_score) / 100.0, 1.0))
    alpha = min(0.25, 1.0 / max(1, sample_count))
    next_score = max(0.05, min(prev * (1.0 - alpha) + target * alpha, 0.99))

    row.sample_count = sample_count
    row.reliability_score = round(next_score, 4)
    row.last_signal_at = observed_at
    db.add(row)
    db.flush()
    return row


def _compute_opportunity_score(*, raw_score: float, sentiment_score: float, price_drop_pct: float, demand_spike_pct: float, source_reliability_score: float) -> tuple[float, float]:
    bounded_raw = max(0.0, min(raw_score, 100.0))
    bounded_drop = max(0.0, min(price_drop_pct, 100.0))
    bounded_spike = max(0.0, min(demand_spike_pct, 300.0))
    spike_component = min(bounded_spike / 3.0, 100.0)
    sentiment_component = (sentiment_score + 1.0) * 50.0

    base_score = (0.45 * bounded_raw) + (0.2 * bounded_drop) + (0.25 * spike_component) + (0.1 * sentiment_component)
    confidence = max(0.05, min(float(source_reliability_score), 0.99))
    final_score = round(max(0.0, min(base_score * (0.65 + 0.35 * confidence), 100.0)), 2)
    confidence_score = round(confidence * 100.0, 2)
    return final_score, confidence_score


def ingest_market_signals(db: Session, *, events: list[dict], performed_by: str = 'market-intelligence') -> dict:
    now = datetime.now(timezone.utc)
    ingested = 0
    opportunities: list[models.MarketOpportunity] = []
    alerts_created = 0

    for payload in events:
        source_name = str(payload.get('source_name') or 'unknown').strip()[:128] or 'unknown'
        signal_type = str(payload.get('signal_type') or 'trend').strip().lower()[:64] or 'trend'
        product_name = str(payload.get('product_name') or '').strip()[:256]
        if not product_name:
            continue
        region = str(payload.get('region') or 'GLOBAL').strip().upper()[:64] or 'GLOBAL'
        raw_score = float(payload.get('raw_score') or 0.0)
        price_drop_pct = float(payload.get('price_drop_pct') or 0.0)
        demand_spike_pct = float(payload.get('demand_spike_pct') or 0.0)
        sentiment, sentiment_score = _normalize_sentiment(payload.get('sentiment'))
        observed_at = payload.get('observed_at') or now
        if isinstance(observed_at, str):
            try:
                observed_at = datetime.fromisoformat(observed_at.replace('Z', '+00:00'))
            except Exception:
                observed_at = now
        if getattr(observed_at, 'tzinfo', None) is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)

        reliability = _upsert_source_reliability(
            db,
            source_name=source_name,
            signal_score=raw_score,
            observed_at=observed_at,
        )

        normalized_score, confidence_score = _compute_opportunity_score(
            raw_score=raw_score,
            sentiment_score=sentiment_score,
            price_drop_pct=price_drop_pct,
            demand_spike_pct=demand_spike_pct,
            source_reliability_score=float(reliability.reliability_score or 0.5),
        )

        event = models.MarketSignalEvent(
            source_name=source_name,
            signal_type=signal_type,
            product_name=product_name,
            region=region,
            raw_score=raw_score,
            sentiment=sentiment,
            sentiment_score=sentiment_score,
            price_drop_pct=price_drop_pct,
            demand_spike_pct=demand_spike_pct,
            source_reliability_score=float(reliability.reliability_score or 0.5),
            normalized_score=normalized_score,
            signal_metadata=dict(payload.get('signal_metadata') or {}),
            observed_at=observed_at,
            ingested_by=str(performed_by or 'market-intelligence').strip()[:128] or 'market-intelligence',
        )
        db.add(event)
        db.flush()

        if normalized_score >= 55.0:
            summary = f'{product_name} opportunity in {region}: score={normalized_score} from {signal_type}'
            opp = models.MarketOpportunity(
                signal_event_id=event.id,
                product_name=product_name,
                region=region,
                opportunity_score=normalized_score,
                confidence_score=confidence_score,
                status='detected',
                summary=summary[:512],
                opportunity_metadata={
                    'source_name': source_name,
                    'signal_type': signal_type,
                    'price_drop_pct': price_drop_pct,
                    'demand_spike_pct': demand_spike_pct,
                },
                detected_at=now,
            )
            db.add(opp)
            db.flush()
            opportunities.append(opp)

            if normalized_score >= 75.0:
                create_alert(
                    db,
                    title=f'Market opportunity spike: {product_name}',
                    detail=f'region={region} score={normalized_score} source={source_name} type={signal_type}',
                    severity='critical',
                    category='market-intelligence',
                    entity_type='market_opportunity',
                    entity_id=opp.id,
                )
                alerts_created += 1

        ingested += 1

    db.commit()

    log_audit(
        db,
        'market_intelligence',
        None,
        'market_signals_ingested',
        f'ingested={ingested} opportunities={len(opportunities)} alerts={alerts_created}',
        performed_by=str(performed_by or 'market-intelligence').strip()[:128] or 'market-intelligence',
    )

    return {
        'ingested': ingested,
        'opportunities_detected': len(opportunities),
        'alerts_created': alerts_created,
    }


def list_market_opportunities(
    db: Session,
    *,
    region: str | None = None,
    min_score: float = 0.0,
    status: str | None = None,
    limit: int = 200,
) -> list[models.MarketOpportunity]:
    query = db.query(models.MarketOpportunity)
    if region:
        query = query.filter(models.MarketOpportunity.region == str(region).strip().upper()[:64])
    if min_score > 0:
        query = query.filter(models.MarketOpportunity.opportunity_score >= float(min_score))
    if status:
        query = query.filter(models.MarketOpportunity.status == str(status).strip().lower())

    return (
        query
        .order_by(models.MarketOpportunity.opportunity_score.desc(), models.MarketOpportunity.id.desc())
        .limit(max(1, min(int(limit), 500)))
        .all()
    )


def list_source_reliability(db: Session, *, limit: int = 200) -> list[models.MarketDataSourceReliability]:
    return (
        db.query(models.MarketDataSourceReliability)
        .order_by(models.MarketDataSourceReliability.reliability_score.desc(), models.MarketDataSourceReliability.source_name.asc())
        .limit(max(1, min(int(limit), 500)))
        .all()
    )


def market_intelligence_summary(db: Session, *, region: str | None = None) -> dict:
    opportunities = list_market_opportunities(db, region=region, min_score=0.0, status=None, limit=500)
    if not opportunities:
        return {
            'total_opportunities': 0,
            'high_priority': 0,
            'average_score': 0.0,
            'top_regions': {},
        }

    top_regions: dict[str, int] = {}
    high_priority = 0
    total_score = 0.0

    for row in opportunities:
        reg = str(row.region or 'GLOBAL')
        top_regions[reg] = int(top_regions.get(reg, 0)) + 1
        if float(row.opportunity_score or 0.0) >= 75.0:
            high_priority += 1
        total_score += float(row.opportunity_score or 0.0)

    return {
        'total_opportunities': len(opportunities),
        'high_priority': high_priority,
        'average_score': round(total_score / max(1, len(opportunities)), 2),
        'top_regions': top_regions,
    }


def create_ab_test_campaign(
    db: Session,
    *,
    name: str,
    description: str | None = None,
    target_segment: str = 'all',
    variants: dict[str, Any] | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    status: str = 'draft',
) -> models.ABTestCampaign:
    if not name or len(name.strip()) < 3:
        raise ValueError('campaign name must be provided and at least 3 chars')
    if status not in {'draft', 'running', 'completed'}:
        raise ValueError('status must be draft, running, or completed')

    existing = db.query(models.ABTestCampaign).filter(models.ABTestCampaign.name == name.strip()).first()
    if existing:
        raise ValueError('campaign already exists')

    now = datetime.now(timezone.utc)
    row = models.ABTestCampaign(
        name=name.strip(),
        description=description,
        target_segment=target_segment.strip() if target_segment else 'all',
        variants=variants or {},
        start_date=start_date or now,
        end_date=end_date,
        status=status,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit(db, 'ab_test_campaign', row.id, 'create', f'name={row.name} status={row.status}')
    return row


def list_ab_test_campaigns(db: Session) -> list[models.ABTestCampaign]:
    return db.query(models.ABTestCampaign).order_by(models.ABTestCampaign.created_at.desc()).all()


def add_ab_test_result(
    db: Session,
    *,
    campaign_id: int,
    variant: str,
    outcome: str,
    lead_id: int | None = None,
    value: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> models.ABTestResult:
    campaign = db.query(models.ABTestCampaign).filter(models.ABTestCampaign.id == campaign_id).first()
    if not campaign:
        raise ValueError('A/B test campaign not found')
    if campaign.status not in {'running', 'completed'}:
        raise ValueError('campaign must be running or completed to record results')

    row = models.ABTestResult(
        campaign_id=campaign.id,
        lead_id=lead_id,
        variant=str(variant or '').strip()[:64] or 'A',
        outcome=str(outcome or '').strip()[:32],
        value=float(value) if value is not None else None,
        result_metadata=metadata or {},
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit(db, 'ab_test_result', row.id, 'create', f'campaign={campaign_id} variant={row.variant} outcome={row.outcome}')
    return row


def get_ab_test_metrics(db: Session, *, campaign_id: int) -> dict:
    campaign = db.query(models.ABTestCampaign).filter(models.ABTestCampaign.id == campaign_id).first()
    if not campaign:
        raise ValueError('A/B test campaign not found')

    rows = db.query(models.ABTestResult).filter(models.ABTestResult.campaign_id == campaign_id).all()
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        v = row.variant or 'A'
        stats = counts.setdefault(v, {'total': 0, 'conversions': 0, 'clicks': 0, 'opens': 0})
        stats['total'] += 1
        if row.outcome == 'conversion':
            stats['conversions'] += 1
        if row.outcome == 'click':
            stats['clicks'] += 1
        if row.outcome == 'open':
            stats['opens'] += 1

    return {
        'campaign_id': campaign_id,
        'campaign_name': campaign.name,
        'variant_metrics': {
            variant: {
                'total': data['total'],
                'conversion_rate': round(data['conversions'] / max(1, data['total']), 4),
                'click_rate': round(data['clicks'] / max(1, data['total']), 4),
                'open_rate': round(data['opens'] / max(1, data['total']), 4),
            }
            for variant, data in counts.items()
        },
    }


def update_lead_score(
    db: Session,
    *,
    lead_id: int,
    score: int,
    source: str = 'autoscoring',
    notes: str | None = None,
) -> dict:
    row = db.query(models.Lead).filter(models.Lead.id == lead_id).first()
    if not row:
        raise ValueError('Lead not found')

    old_score = int(row.lead_score or 0)
    new_score = max(0, min(int(score), 100))
    row.lead_score = new_score
    row.marketing_intent_score = int(row.marketing_intent_score or 0)
    row.updated_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()

    log_audit(db, 'lead', lead_id, 'score_updated', f'old={old_score} new={new_score} source={source} notes={notes or ""}')
    return {
        'lead_id': lead_id,
        'old_score': old_score,
        'new_score': new_score,
        'source': source,
        'notes': notes,
        'updated_at': row.updated_at,
    }


def create_consent_record(
    db: Session,
    *,
    lead_id: int,
    consent_type: str = 'email',
    status: str = 'granted',
    source: str = 'system',
    region: str = 'GLOBAL',
    policy_version: str = '1.0',
    notes: str | None = None,
) -> models.ConsentRecord:
    lead = db.query(models.Lead).filter(models.Lead.id == lead_id).first()
    if not lead:
        raise ValueError('Lead not found')

    status_norm = str(status or '').strip().lower()
    if status_norm not in {'granted', 'revoked'}:
        raise ValueError('status must be granted or revoked')

    row = models.ConsentRecord(
        lead_id=lead_id,
        consent_type=str(consent_type or 'email').strip()[:32],
        status=status_norm,
        source=str(source or 'system').strip()[:64],
        region=str(region or 'GLOBAL').strip()[:32],
        policy_version=str(policy_version or '1.0').strip()[:64],
        notes=notes,
        revoked_at=None if status_norm == 'granted' else datetime.now(timezone.utc),
    )
    db.add(row)
    if status_norm == 'revoked':
        lead.marketing_consent = 'no'
        lead.unsubscribed_at = datetime.now(timezone.utc)
    else:
        lead.marketing_consent = 'yes'
    db.add(lead)
    db.commit()
    db.refresh(row)

    log_audit(db, 'consent_record', row.id, 'update', f'lead={lead_id} status={status_norm} type={row.consent_type}')
    return row


def get_consent_status(db: Session, *, lead_id: int) -> dict:
    lead = db.query(models.Lead).filter(models.Lead.id == lead_id).first()
    if not lead:
        raise ValueError('Lead not found')

    latest = (
        db.query(models.ConsentRecord)
        .filter(models.ConsentRecord.lead_id == lead_id)
        .order_by(models.ConsentRecord.updated_at.desc())
        .first()
    )
    consented = False
    active = False
    last_update = None
    if latest:
        consented = latest.status == 'granted'
        active = latest.status == 'granted'
        last_update = latest.updated_at

    return {
        'lead_id': lead_id,
        'consented': consented,
        'active': active,
        'last_update': last_update,
    }


def list_consent_records(db: Session, *, lead_id: int) -> list[models.ConsentRecord]:
    return (
        db.query(models.ConsentRecord)
        .filter(models.ConsentRecord.lead_id == lead_id)
        .order_by(models.ConsentRecord.updated_at.desc())
        .all()
    )


def create_paid_api_data_source(
    db: Session,
    *,
    name: str,
    endpoint: str,
    api_key: str,
    active: bool = True,
    polling_interval_minutes: int = 60,
    source_metadata: dict[str, Any] | None = None,
) -> models.PaidAPIDataSource:
    if not name or len(name.strip()) < 3:
        raise ValueError('name must be at least 3 characters')

    existing = db.query(models.PaidAPIDataSource).filter(models.PaidAPIDataSource.name == name.strip()).first()
    if existing:
        raise ValueError('Paid API data source already exists')

    row = models.PaidAPIDataSource(
        name=name.strip(),
        endpoint=endpoint.strip(),
        api_key=api_key.strip(),
        active=bool(active),
        polling_interval_minutes=max(1, min(int(polling_interval_minutes), 1440)),
        source_metadata=source_metadata or {},
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit(db, 'paid_api_data_source', row.id, 'create', f'name={row.name} endpoint={row.endpoint}')
    return row


def list_paid_api_data_sources(db: Session) -> list[models.PaidAPIDataSource]:
    return db.query(models.PaidAPIDataSource).order_by(models.PaidAPIDataSource.created_at.desc()).all()


def _fetch_paid_api_source_data(endpoint: str, api_key: str) -> list[dict]:
    # Placeholder for connecting to a paid data feed (HTTP request or SDK call).
    # In production this should use a real HTTP client with error handling.
    # Here we simulate with synthetic data for deterministic tests.
    sample = [
        {
            'source_name': 'paid_source',
            'signal_type': 'paid_signal',
            'product_name': 'Premium Product X',
            'region': 'GLOBAL',
            'raw_score': 90.0,
            'sentiment': 'positive',
            'price_drop_pct': 35.0,
            'demand_spike_pct': 220.0,
            'signal_metadata': {'paid_endpoint': endpoint},
        },
        {
            'source_name': 'paid_source',
            'signal_type': 'paid_signal',
            'product_name': 'Premium Product Y',
            'region': 'EU',
            'raw_score': 78.0,
            'sentiment': 'neutral',
            'price_drop_pct': 15.0,
            'demand_spike_pct': 110.0,
            'signal_metadata': {'paid_endpoint': endpoint},
        },
    ]
    return sample


def ingest_from_paid_api_source(db: Session, *, source_id: int, performed_by: str = 'paid-api-sync') -> dict:
    source = db.query(models.PaidAPIDataSource).filter(models.PaidAPIDataSource.id == source_id).first()
    if not source:
        raise ValueError('Paid API source not found')
    if not source.active:
        raise ValueError('Paid API source is not active')

    events = _fetch_paid_api_source_data(source.endpoint, source.api_key)
    # reuse existing ingestion flows to keep scoring and alerts consistent
    ingest_summary = ingest_market_signals(db, events=events, performed_by=performed_by)

    log = models.PaidAPIIngestionLog(
        source_id=source.id,
        events_fetched=len(events),
        opportunities_created=ingest_summary.get('opportunities_detected', 0),
        alerts_created=ingest_summary.get('alerts_created', 0),
        details=f"endpoint={source.endpoint} fetched={len(events)}"
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    log_audit(
        db,
        'paid_api_ingestion',
        log.id,
        'ingest',
        f'source_id={source.id} events={len(events)} opportunities={ingest_summary.get("opportunities_detected",0)} alerts={ingest_summary.get("alerts_created",0)}',
        performed_by=performed_by,
    )

    return {
        'source_id': source.id,
        'fetched_at': log.fetched_at,
        'events_fetched': log.events_fetched,
        'opportunities_created': log.opportunities_created,
        'alerts_created': log.alerts_created,
        'details': log.details,
    }


def list_paid_api_ingestion_logs(db: Session, *, source_id: int, limit: int = 100) -> list[models.PaidAPIIngestionLog]:
    return (
        db.query(models.PaidAPIIngestionLog)
        .filter(models.PaidAPIIngestionLog.source_id == source_id)
        .order_by(models.PaidAPIIngestionLog.fetched_at.desc())
        .limit(max(1, min(int(limit), 500)))
        .all()
    )


def record_campaign_fatigue(
    db: Session,
    *,
    lead_id: int,
    campaign_id: int | None = None,
    increment_by: int = 1,
    notes: str | None = None,
) -> models.CampaignFatigueRecord:
    row = (
        db.query(models.CampaignFatigueRecord)
        .filter(models.CampaignFatigueRecord.lead_id == int(lead_id))
        .filter(models.CampaignFatigueRecord.campaign_id == campaign_id)
        .first()
    )
    if row is None:
        row = models.CampaignFatigueRecord(
            campaign_id=campaign_id,
            lead_id=lead_id,
            outreach_count=0,
            status='active',
            fatigue_metadata={},
        )
    row.outreach_count = int(row.outreach_count or 0) + max(1, int(increment_by))
    row.last_outreach_at = datetime.now(timezone.utc)

    # throttle when exceeds threshold
    if row.outreach_count >= 5:
        row.status = 'throttled'
        row.fatigue_metadata = dict(row.fatigue_metadata or {})
        row.fatigue_metadata['throttle_reason'] = 'outreach_exceeded_threshold'

    if notes:
        row.fatigue_metadata = dict(row.fatigue_metadata or {})
        row.fatigue_metadata['last_note'] = notes

    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit(
        db,
        'campaign_fatigue',
        row.id,
        'update' if row.id else 'create',
        f'lead={lead_id} campaign={campaign_id} outreach_count={row.outreach_count} status={row.status}',
    )
    return row


def get_campaign_fatigue_status(db: Session, *, lead_id: int, campaign_id: int | None = None) -> models.CampaignFatigueRecord | None:
    return (
        db.query(models.CampaignFatigueRecord)
        .filter(models.CampaignFatigueRecord.lead_id == int(lead_id))
        .filter(models.CampaignFatigueRecord.campaign_id == campaign_id)
        .first()
    )


def list_campaign_fatigue_records(db: Session, *, lead_id: int | None = None, campaign_id: int | None = None, limit: int = 100) -> list[models.CampaignFatigueRecord]:
    query = db.query(models.CampaignFatigueRecord)
    if lead_id is not None:
        query = query.filter(models.CampaignFatigueRecord.lead_id == int(lead_id))
    if campaign_id is not None:
        query = query.filter(models.CampaignFatigueRecord.campaign_id == int(campaign_id))
    return query.order_by(models.CampaignFatigueRecord.last_outreach_at.desc()).limit(max(1, min(int(limit), 500))).all()


def record_feedback_loop_event(
    db: Session,
    *,
    event_type: str,
    campaign_id: int | None = None,
    lead_id: int | None = None,
    event_value: float | None = None,
    event_details: str | None = None,
) -> models.FeedbackLoopRecord:
    row = models.FeedbackLoopRecord(
        campaign_id=campaign_id,
        lead_id=lead_id,
        event_type=str(event_type or '').strip()[:64],
        event_value=float(event_value) if event_value is not None else None,
        event_details=event_details,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit(
        db,
        'feedback_loop',
        row.id,
        'record',
        f'campaign={campaign_id} lead={lead_id} event_type={event_type} value={event_value}',
    )
    return row


def list_feedback_loop_records(db: Session, *, campaign_id: int | None = None, lead_id: int | None = None, limit: int = 100) -> list[models.FeedbackLoopRecord]:
    query = db.query(models.FeedbackLoopRecord)
    if campaign_id is not None:
        query = query.filter(models.FeedbackLoopRecord.campaign_id == int(campaign_id))
    if lead_id is not None:
        query = query.filter(models.FeedbackLoopRecord.lead_id == int(lead_id))
    return (
        query
        .order_by(models.FeedbackLoopRecord.recorded_at.desc())
        .limit(max(1, min(int(limit), 500)))
        .all()
    )


def create_sales_rep(db: Session, *, name: str, email: str | None = None, team: str | None = None, active: bool = True) -> models.SalesRep:
    name_clean = str(name or '').strip()
    if len(name_clean) < 2:
        raise ValueError('Sales rep name must be at least 2 characters')

    rep = models.SalesRep(
        name=name_clean,
        email=(str(email).strip() if email else None),
        team=(str(team).strip() if team else None),
        active=bool(active),
    )
    db.add(rep)
    db.commit()
    db.refresh(rep)

    log_audit(db, 'sales_rep', rep.id, 'create', f'name={rep.name} team={rep.team}')
    return rep


def list_sales_reps(db: Session) -> list[models.SalesRep]:
    return db.query(models.SalesRep).order_by(models.SalesRep.name.asc()).all()


def assign_lead_to_sales_rep(db: Session, *, lead_id: int, sales_rep_id: int, assignment_notes: str | None = None) -> models.LeadAssignment:
    lead = db.query(models.Lead).filter(models.Lead.id == int(lead_id)).first()
    if not lead:
        raise ValueError('Lead not found')

    rep = db.query(models.SalesRep).filter(models.SalesRep.id == int(sales_rep_id)).first()
    if not rep or not rep.active:
        raise ValueError('Sales rep not found or inactive')

    assignment = models.LeadAssignment(
        lead_id=lead.id,
        sales_rep_id=rep.id,
        status='active',
        assignment_notes=assignment_notes,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    log_audit(db, 'lead_assignment', assignment.id, 'assign', f'lead={lead_id} sales_rep={sales_rep_id}')
    return assignment


def list_lead_assignments(db: Session, *, lead_id: int | None = None, sales_rep_id: int | None = None, limit: int = 100) -> list[models.LeadAssignment]:
    query = db.query(models.LeadAssignment)
    if lead_id is not None:
        query = query.filter(models.LeadAssignment.lead_id == int(lead_id))
    if sales_rep_id is not None:
        query = query.filter(models.LeadAssignment.sales_rep_id == int(sales_rep_id))
    return query.order_by(models.LeadAssignment.assigned_at.desc()).limit(max(1, min(int(limit), 500))).all()


def compute_abm_analytics(db: Session, *, region: str = 'GLOBAL', account_segment: str = 'enterprise') -> dict:
    # Basic ABM analytics aggregation for opportunity detection and expected value.
    total_opps = (
        db.query(models.MarketOpportunity)
        .filter(models.MarketOpportunity.region == str(region).strip().upper())
        .count()
    )
    avg_score = (
        db.query(models.MarketOpportunity)
        .filter(models.MarketOpportunity.region == str(region).strip().upper())
        .with_entities(func.avg(models.MarketOpportunity.opportunity_score))
        .scalar() or 0.0
    )

    expected_value = round(total_opps * (avg_score / 100.0) * 50000.0, 2)

    existing = (
        db.query(models.ABMMetric)
        .filter(models.ABMMetric.region == str(region).strip().upper())
        .filter(models.ABMMetric.account_segment == str(account_segment).strip().lower())
        .first()
    )
    if existing is None:
        existing = models.ABMMetric(
            region=str(region).strip().upper(),
            account_segment=str(account_segment).strip().lower(),
            opportunity_count=total_opps,
            expected_value=expected_value,
        )
    else:
        existing.opportunity_count = total_opps
        existing.expected_value = expected_value

    db.add(existing)
    db.commit()
    db.refresh(existing)

    return {
        'region': region,
        'account_segment': account_segment,
        'opportunity_count': total_opps,
        'expected_value': expected_value,
    }


def list_abm_metrics(db: Session, *, region: str | None = None, account_segment: str | None = None, limit: int = 100) -> list[models.ABMMetric]:
    query = db.query(models.ABMMetric)
    if region is not None:
        query = query.filter(models.ABMMetric.region == str(region).strip().upper())
    if account_segment is not None:
        query = query.filter(models.ABMMetric.account_segment == str(account_segment).strip().lower())
    return query.order_by(models.ABMMetric.updated_at.desc()).limit(max(1, min(int(limit), 500))).all()


def create_sales_cadence_record(
    db: Session,
    *,
    sales_rep_id: int,
    lead_id: int,
    cadence_step: str = 'initial_outreach',
    status: str = 'scheduled',
    due_at: datetime | None = None,
    notes: str | None = None,
) -> models.SalesCadenceRecord:
    row = models.SalesCadenceRecord(
        sales_rep_id=int(sales_rep_id),
        lead_id=int(lead_id),
        cadence_step=str(cadence_step or 'initial_outreach').strip()[:64],
        status=str(status or 'scheduled').strip().lower()[:32],
        due_at=due_at,
        notes=notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    log_audit(db, 'sales_cadence', row.id, 'create', f'lead={lead_id} rep={sales_rep_id} step={row.cadence_step} status={row.status}')
    return row


def list_sales_cadence_records(
    db: Session,
    *,
    sales_rep_id: int | None = None,
    lead_id: int | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[models.SalesCadenceRecord]:
    query = db.query(models.SalesCadenceRecord)
    if sales_rep_id is not None:
        query = query.filter(models.SalesCadenceRecord.sales_rep_id == int(sales_rep_id))
    if lead_id is not None:
        query = query.filter(models.SalesCadenceRecord.lead_id == int(lead_id))
    if status:
        query = query.filter(models.SalesCadenceRecord.status == str(status).strip().lower())
    return query.order_by(models.SalesCadenceRecord.updated_at.desc()).limit(max(1, min(int(limit), 500))).all()


def create_rep_performance_snapshot(
    db: Session,
    *,
    sales_rep_id: int,
    period_start: datetime,
    period_end: datetime,
    quota_target: float = 0.0,
    revenue_achieved: float = 0.0,
) -> models.RepPerformanceSnapshot:
    wins = (
        db.query(models.WinLossRecord)
        .filter(models.WinLossRecord.sales_rep_id == int(sales_rep_id), models.WinLossRecord.outcome == 'win')
        .count()
    )
    total = (
        db.query(models.WinLossRecord)
        .filter(models.WinLossRecord.sales_rep_id == int(sales_rep_id))
        .count()
    )
    win_rate = round((wins / total), 4) if total else 0.0
    # simple forecast: scale recent achieved by win-rate adjustment
    forecast_revenue = round(float(revenue_achieved) * (1.0 + (win_rate * 0.3)), 2)

    row = models.RepPerformanceSnapshot(
        sales_rep_id=int(sales_rep_id),
        period_start=period_start,
        period_end=period_end,
        opportunities_total=total,
        opportunities_won=wins,
        win_rate=win_rate,
        quota_target=float(quota_target),
        revenue_achieved=float(revenue_achieved),
        forecast_revenue=forecast_revenue,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    log_audit(db, 'rep_performance', row.id, 'snapshot', f'rep={sales_rep_id} total={total} wins={wins} win_rate={win_rate} forecast={forecast_revenue}')
    return row


def list_rep_performance_snapshots(
    db: Session,
    *,
    sales_rep_id: int | None = None,
    limit: int = 100,
) -> list[models.RepPerformanceSnapshot]:
    query = db.query(models.RepPerformanceSnapshot)
    if sales_rep_id is not None:
        query = query.filter(models.RepPerformanceSnapshot.sales_rep_id == int(sales_rep_id))
    return query.order_by(models.RepPerformanceSnapshot.updated_at.desc()).limit(max(1, min(int(limit), 500))).all()


def create_win_loss_record(
    db: Session,
    *,
    opportunity_id: int,
    lead_id: int | None = None,
    sales_rep_id: int | None = None,
    outcome: str,
    reason: str,
    recorded_by: str = 'system',
) -> models.WinLossRecord:
    outcome_value = str(outcome or '').strip().lower()
    if outcome_value not in {'win', 'loss'}:
        raise ValueError('outcome must be win or loss')
    row = models.WinLossRecord(
        opportunity_id=int(opportunity_id),
        lead_id=lead_id,
        sales_rep_id=sales_rep_id,
        outcome=outcome_value,
        reason=str(reason or '').strip()[:512],
        recorded_by=str(recorded_by or 'system').strip()[:128],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    log_audit(db, 'win_loss', row.id, 'record', f'opportunity={opportunity_id} outcome={outcome_value} rep={sales_rep_id}')
    return row


def list_win_loss_records(
    db: Session,
    *,
    sales_rep_id: int | None = None,
    outcome: str | None = None,
    limit: int = 100,
) -> list[models.WinLossRecord]:
    query = db.query(models.WinLossRecord)
    if sales_rep_id is not None:
        query = query.filter(models.WinLossRecord.sales_rep_id == int(sales_rep_id))
    if outcome:
        query = query.filter(models.WinLossRecord.outcome == str(outcome).strip().lower())
    return query.order_by(models.WinLossRecord.created_at.desc()).limit(max(1, min(int(limit), 500))).all()


def marketing_funnel_analytics(db: Session, *, lookback_days: int = 30) -> dict:
    days = max(1, min(int(lookback_days), 365))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    awareness = (
        db.query(models.FeedbackLoopRecord)
        .filter(models.FeedbackLoopRecord.recorded_at >= cutoff, models.FeedbackLoopRecord.event_type.in_(['view', 'open']))
        .count()
    )
    engagement = (
        db.query(models.FeedbackLoopRecord)
        .filter(models.FeedbackLoopRecord.recorded_at >= cutoff, models.FeedbackLoopRecord.event_type.in_(['click', 'reply']))
        .count()
    )
    conversion = (
        db.query(models.FeedbackLoopRecord)
        .filter(models.FeedbackLoopRecord.recorded_at >= cutoff, models.FeedbackLoopRecord.event_type == 'conversion')
        .count()
    )
    conversion_rate = round((conversion / awareness), 4) if awareness else 0.0
    return {
        'lookback_days': days,
        'awareness': awareness,
        'engagement': engagement,
        'conversion': conversion,
        'conversion_rate': conversion_rate,
    }



def validate_market_opportunity(
    db: Session,
    *,
    opportunity_id: int,
    decision: str,
    validator_type: str = 'human',
    validation_score: float | None = None,
    rejection_reason: str | None = None,
    validation_notes: str | None = None,
    validated_by: str = 'system',
) -> models.MarketOpportunityValidation:
    row = db.query(models.MarketOpportunity).filter(models.MarketOpportunity.id == opportunity_id).first()
    if row is None:
        raise ValueError('Market opportunity not found')

    decision_value = str(decision or '').strip().lower()
    if decision_value not in {'validated', 'rejected'}:
        raise ValueError('decision must be one of: validated, rejected')

    validator = str(validator_type or 'human').strip().lower()
    if validator not in {'human', 'ai'}:
        raise ValueError('validator_type must be one of: human, ai')

    from_status = str(row.status or 'detected').strip().lower()
    reason = str(rejection_reason or '').strip()
    if decision_value == 'rejected' and not reason:
        raise ValueError('rejection_reason is required when decision=rejected')
    if decision_value != 'rejected':
        reason = ''

    score_value = None
    if validation_score is not None:
        score_value = max(0.0, min(float(validation_score), 1.0))

    notes = str(validation_notes or '').strip()
    actor = str(validated_by or 'system').strip()[:128] or 'system'

    row.status = decision_value
    if notes:
        row.validation_notes = notes
    elif reason:
        row.validation_notes = reason

    opportunity_metadata = dict(row.opportunity_metadata or {})
    opportunity_metadata['last_validation'] = {
        'from_status': from_status,
        'to_status': decision_value,
        'validator_type': validator,
        'validation_score': score_value,
        'rejection_reason': reason or None,
        'validated_by': actor,
        'validated_at': datetime.now(timezone.utc).isoformat(),
    }
    row.opportunity_metadata = opportunity_metadata

    validation = models.MarketOpportunityValidation(
        opportunity_id=row.id,
        from_status=from_status,
        to_status=decision_value,
        validator_type=validator,
        validation_score=score_value,
        rejection_reason=reason or None,
        validation_notes=notes or None,
        validated_by=actor,
    )
    db.add(validation)
    db.add(row)
    db.commit()
    db.refresh(validation)

    log_audit(
        db,
        'market_opportunity',
        row.id,
        'validate',
        f'from={from_status} to={decision_value} validator={validator} reason={reason or "n/a"}',
        performed_by=actor,
    )
    return validation


def list_market_opportunity_validations(
    db: Session,
    *,
    opportunity_id: int,
    limit: int = 200,
) -> list[models.MarketOpportunityValidation]:
    return (
        db.query(models.MarketOpportunityValidation)
        .filter(models.MarketOpportunityValidation.opportunity_id == int(opportunity_id))
        .order_by(models.MarketOpportunityValidation.created_at.desc(), models.MarketOpportunityValidation.id.desc())
        .limit(max(1, min(int(limit), 500)))
        .all()
    )


def market_opportunity_validation_metrics(
    db: Session,
    *,
    lookback_days: int = 30,
    region: str | None = None,
) -> dict:
    days = max(1, min(int(lookback_days), 365))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    query = db.query(models.MarketOpportunityValidation, models.MarketOpportunity).join(
        models.MarketOpportunity,
        models.MarketOpportunity.id == models.MarketOpportunityValidation.opportunity_id,
    )
    query = query.filter(models.MarketOpportunityValidation.created_at >= cutoff)
    if region:
        query = query.filter(models.MarketOpportunity.region == str(region).strip().upper()[:64])

    rows = query.all()
    approved = 0
    rejected = 0
    by_region_acc: dict[str, dict[str, int]] = {}

    for validation, opportunity in rows:
        state = str(validation.to_status or '').strip().lower()
        region_key = str(opportunity.region or 'GLOBAL').strip().upper() or 'GLOBAL'
        bucket = by_region_acc.setdefault(region_key, {'total': 0, 'approved': 0, 'rejected': 0})
        bucket['total'] += 1

        if state == 'validated':
            approved += 1
            bucket['approved'] += 1
        elif state == 'rejected':
            rejected += 1
            bucket['rejected'] += 1

    total = approved + rejected
    precision = round((approved / total) if total else 0.0, 4)
    false_positive_rate = round((rejected / total) if total else 0.0, 4)

    region_metrics = []
    for region_key, counts in sorted(by_region_acc.items()):
        region_total = int(counts['approved']) + int(counts['rejected'])
        region_precision = round((int(counts['approved']) / region_total) if region_total else 0.0, 4)
        region_metrics.append(
            {
                'region': region_key,
                'total_validations': int(counts['total']),
                'approved': int(counts['approved']),
                'rejected': int(counts['rejected']),
                'precision': region_precision,
            }
        )

    return {
        'lookback_days': days,
        'total_validations': total,
        'approved': approved,
        'rejected': rejected,
        'precision': precision,
        'false_positive_rate': false_positive_rate,
        'by_region': region_metrics,
    }
