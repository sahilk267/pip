from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit
from .lead_intelligence import apply_metrics_to_lead, normalize_attribution_channel

_SIGNAL_WEIGHTS = {
    'web_visit': 2,
    'pricing_page_view': 6,
    'download': 8,
    'email_open': 2,
    'email_click': 5,
    'demo_request': 15,
    'rfq_request': 18,
    'cart_abandon': 7,
    'webinar_signup': 9,
}


def _intent_score(intent_data: dict) -> int:
    total = 0
    for signal_type, payload in intent_data.items():
        if not isinstance(payload, dict):
            continue
        count = int(payload.get('count', 0) or 0)
        strength = int(payload.get('strength_total', 0) or 0)
        weight = _SIGNAL_WEIGHTS.get(signal_type, 1)
        total += min(40, count * weight + strength)
    return min(100, total)


def record_marketing_intent_event(
    db: Session,
    *,
    lead_id: int,
    source: str,
    signal_type: str,
    strength: int = 1,
    metadata: dict | None = None,
    performed_by: str = 'marketing',
) -> models.Lead:
    lead = db.query(models.Lead).filter(models.Lead.id == lead_id).first()
    if not lead:
        raise ValueError('Lead not found')

    metadata = metadata or {}
    signal_key = signal_type.strip().lower()
    intent_data = dict(lead.marketing_intent_data or {})
    row = dict(intent_data.get(signal_key) or {})
    row['count'] = int(row.get('count', 0) or 0) + 1
    row['strength_total'] = int(row.get('strength_total', 0) or 0) + int(strength)
    row['last_source'] = source.strip().lower()
    row['last_seen_at'] = datetime.now(timezone.utc).isoformat()
    if metadata:
        row['metadata'] = metadata
    intent_data[signal_key] = row

    lead.marketing_intent_data = intent_data
    lead.last_intent_at = datetime.now(timezone.utc)
    lead.marketing_intent_score = _intent_score(intent_data)
    if source:
        lead.source = source
        lead.attribution_channel = normalize_attribution_channel(source)
    apply_metrics_to_lead(lead)
    db.add(lead)
    db.commit()
    db.refresh(lead)

    log_audit(
        db,
        'lead',
        lead.id,
        'marketing_intent',
        f'marketing intent signal={signal_key} source={source} strength={strength}',
        performed_by=performed_by,
    )
    return lead


def refresh_marketing_intent_scores(db: Session, limit: int = 500) -> dict[str, int]:
    leads = db.query(models.Lead).order_by(models.Lead.id.asc()).limit(limit).all()
    updated = 0
    for lead in leads:
        before_intent = int(lead.marketing_intent_score or 0)
        intent_data = dict(lead.marketing_intent_data or {})
        lead.marketing_intent_score = _intent_score(intent_data)
        apply_metrics_to_lead(lead)
        db.add(lead)
        if int(lead.marketing_intent_score or 0) != before_intent:
            updated += 1
    db.commit()
    return {'leads_scored': updated, 'scanned': len(leads)}
