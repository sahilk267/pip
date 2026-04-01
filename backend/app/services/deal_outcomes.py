from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit

_ALLOWED_OUTCOMES = {'won', 'lost', 'abandoned', 'expired'}

_REASON_CODES = {
    # loss
    'price_too_high', 'competitor_won', 'budget_cut', 'no_decision', 'product_fit',
    'delivery_timeline', 'quality_concern', 'trust_issue',
    # win
    'best_price', 'relationship', 'product_fit', 'fast_delivery', 'terms_agreed',
    # neutral
    'customer_cancelled', 'vendor_withdrew', 'expired_sla', 'duplicate', 'unspecified',
}


def record_deal_outcome(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    outcome: str,
    reason_code: str,
    reason_detail: str | None = None,
    competitor: str | None = None,
    deal_value: float | None = None,
    currency: str = 'USD',
    lead_id: int | None = None,
    customer_id: int | None = None,
    outcome_metadata: dict | None = None,
    recorded_by: str = 'sales',
) -> models.DealOutcomeRecord:
    normalized_outcome = str(outcome or '').strip().lower()
    if normalized_outcome not in _ALLOWED_OUTCOMES:
        raise ValueError('outcome must be one of: won, lost, abandoned, expired')

    normalized_entity_type = str(entity_type or '').strip().lower()
    if normalized_entity_type not in ('order', 'rfq'):
        raise ValueError('entity_type must be order or rfq')

    row = models.DealOutcomeRecord(
        entity_type=normalized_entity_type,
        entity_id=int(entity_id),
        lead_id=int(lead_id) if lead_id is not None else None,
        customer_id=int(customer_id) if customer_id is not None else None,
        outcome=normalized_outcome,
        reason_code=str(reason_code or 'unspecified').strip()[:64] or 'unspecified',
        reason_detail=str(reason_detail or '').strip()[:4000] or None,
        competitor=str(competitor or '').strip()[:256] or None,
        deal_value=float(deal_value) if deal_value is not None else None,
        currency=str(currency or 'USD').strip().upper()[:8] or 'USD',
        recorded_by=str(recorded_by or 'sales').strip()[:128] or 'sales',
        outcome_metadata=outcome_metadata or {},
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit(
        db,
        normalized_entity_type,
        int(entity_id),
        'deal_outcome_recorded',
        f'outcome={row.outcome} reason_code={row.reason_code}',
        performed_by=row.recorded_by,
    )
    return row


def list_deal_outcomes(
    db: Session,
    *,
    entity_type: str | None = None,
    outcome: str | None = None,
    reason_code: str | None = None,
    limit: int = 200,
) -> list[models.DealOutcomeRecord]:
    limit = max(1, min(int(limit), 500))
    q = db.query(models.DealOutcomeRecord)
    if entity_type is not None:
        q = q.filter(models.DealOutcomeRecord.entity_type == str(entity_type).strip().lower())
    if outcome is not None:
        q = q.filter(models.DealOutcomeRecord.outcome == str(outcome).strip().lower())
    if reason_code is not None:
        q = q.filter(models.DealOutcomeRecord.reason_code == str(reason_code).strip().lower())
    return q.order_by(models.DealOutcomeRecord.created_at.desc(), models.DealOutcomeRecord.id.desc()).limit(limit).all()


def deal_outcome_analytics(db: Session, *, window_days: int = 90) -> dict:
    window_days = max(1, int(window_days))
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    rows = (
        db.query(models.DealOutcomeRecord)
        .filter(models.DealOutcomeRecord.created_at >= cutoff)
        .all()
    )

    by_outcome: dict[str, int] = defaultdict(int)
    by_reason: dict[str, int] = defaultdict(int)
    by_entity_type: dict[str, int] = defaultdict(int)
    total_deal_value: float = 0.0
    won_deal_value: float = 0.0
    total = len(rows)

    for row in rows:
        by_outcome[row.outcome] += 1
        by_reason[row.reason_code] += 1
        by_entity_type[row.entity_type] += 1
        dv = float(row.deal_value or 0.0)
        total_deal_value += dv
        if row.outcome == 'won':
            won_deal_value += dv

    won = int(by_outcome.get('won', 0))
    lost = int(by_outcome.get('lost', 0))
    win_rate = round(won / (won + lost), 4) if (won + lost) > 0 else 0.0

    top_loss_reasons = sorted(
        [(k, v) for k, v in by_reason.items() if any(
            r.reason_code == k and r.outcome == 'lost' for r in rows
        )],
        key=lambda x: -x[1],
    )[:10]

    return {
        'generated_at': datetime.now(timezone.utc),
        'window_days': window_days,
        'total_deals': total,
        'by_outcome': dict(by_outcome),
        'by_entity_type': dict(by_entity_type),
        'by_reason_code': dict(by_reason),
        'win_rate': win_rate,
        'total_deal_value': round(total_deal_value, 2),
        'won_deal_value': round(won_deal_value, 2),
        'top_loss_reasons': [{'reason_code': k, 'count': v} for k, v in top_loss_reasons],
    }
