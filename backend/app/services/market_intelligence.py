from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
