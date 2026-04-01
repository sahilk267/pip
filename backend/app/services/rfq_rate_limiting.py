from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit

# Default limits used when no rule is configured
_DEFAULT_LEAD_MAX = 10
_DEFAULT_OPERATOR_MAX = 100
_DEFAULT_WINDOW_HOURS = 24


def _active_rule(
    db: Session,
    entity_type: str,
    entity_key: str,
) -> models.RFQRateLimitRule | None:
    return (
        db.query(models.RFQRateLimitRule)
        .filter(
            models.RFQRateLimitRule.entity_type == entity_type,
            models.RFQRateLimitRule.entity_key == entity_key,
            models.RFQRateLimitRule.is_active.is_(True),
        )
        .first()
    )


def _count_broadcasts_in_window(
    db: Session,
    *,
    lead_id: int | None,
    performed_by: str,
    window_hours: int,
) -> tuple[int, int]:
    """Return (lead_count, operator_count) within the rolling window."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    lead_count = 0
    if lead_id:
        lead_count = (
            db.query(models.RFQBroadcast)
            .filter(
                models.RFQBroadcast.lead_id == int(lead_id),
                models.RFQBroadcast.created_at >= cutoff,
            )
            .count()
        )
    operator_count = (
        db.query(models.RFQBroadcast)
        .filter(
            models.RFQBroadcast.performed_by == str(performed_by),
            models.RFQBroadcast.created_at >= cutoff,
        )
        .count()
    )
    return lead_count, operator_count


def check_rfq_rate_limit(
    db: Session,
    *,
    lead_id: int | None,
    performed_by: str,
) -> None:
    """Raise ValueError with 429-style message if any rate limit is exceeded."""
    # Resolve lead rule
    lead_rule = _active_rule(db, 'lead', str(lead_id)) if lead_id else None
    lead_max = int(lead_rule.max_per_window) if lead_rule else _DEFAULT_LEAD_MAX
    lead_window = int(lead_rule.window_hours) if lead_rule else _DEFAULT_WINDOW_HOURS

    # Resolve operator rule
    op_rule = _active_rule(db, 'operator', str(performed_by))
    op_max = int(op_rule.max_per_window) if op_rule else _DEFAULT_OPERATOR_MAX
    op_window = int(op_rule.window_hours) if op_rule else _DEFAULT_WINDOW_HOURS

    # Use the stricter window for the combined count
    window = min(lead_window, op_window)
    lead_count, op_count = _count_broadcasts_in_window(
        db, lead_id=lead_id, performed_by=performed_by, window_hours=window
    )

    if lead_id and lead_count >= lead_max:
        raise ValueError(
            f'RFQ rate limit exceeded for lead {lead_id}: '
            f'{lead_count}/{lead_max} broadcasts in the last {lead_window}h'
        )
    if op_count >= op_max:
        raise ValueError(
            f'RFQ rate limit exceeded for operator "{performed_by}": '
            f'{op_count}/{op_max} broadcasts in the last {op_window}h'
        )


def upsert_rate_limit_rule(
    db: Session,
    *,
    entity_type: str,
    entity_key: str,
    max_per_window: int,
    window_hours: int,
    is_active: bool,
    performed_by: str = 'admin',
) -> models.RFQRateLimitRule:
    normalized_type = str(entity_type or '').strip().lower()
    if normalized_type not in ('lead', 'operator', 'global'):
        raise ValueError("entity_type must be 'lead', 'operator', or 'global'")

    entity_key = str(entity_key or '').strip()[:128]
    if not entity_key:
        raise ValueError('entity_key must not be empty')

    existing = (
        db.query(models.RFQRateLimitRule)
        .filter(
            models.RFQRateLimitRule.entity_type == normalized_type,
            models.RFQRateLimitRule.entity_key == entity_key,
        )
        .first()
    )
    if existing:
        existing.max_per_window = max(1, int(max_per_window))
        existing.window_hours = max(1, int(window_hours))
        existing.is_active = bool(is_active)
        rule = existing
    else:
        rule = models.RFQRateLimitRule(
            entity_type=normalized_type,
            entity_key=entity_key,
            max_per_window=max(1, int(max_per_window)),
            window_hours=max(1, int(window_hours)),
            is_active=bool(is_active),
        )
        db.add(rule)

    db.commit()
    db.refresh(rule)
    log_audit(
        db,
        'rfq',
        rule.id,
        'rfq_rate_limit_rule_upserted',
        f'entity_type={normalized_type} entity_key={entity_key} max={max_per_window} window={window_hours}h',
        performed_by=performed_by,
    )
    return rule


def list_rate_limit_rules(db: Session) -> list[models.RFQRateLimitRule]:
    return (
        db.query(models.RFQRateLimitRule)
        .order_by(models.RFQRateLimitRule.entity_type.asc(), models.RFQRateLimitRule.entity_key.asc())
        .all()
    )


def get_rate_limit_usage_summary(db: Session, *, window_hours: int = 24) -> dict:
    """Return current broadcast counts for all entities with active rules, plus defaults."""
    window_hours = max(1, int(window_hours))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)

    # Count broadcasts per lead and per operator in window
    lead_rows = (
        db.query(models.RFQBroadcast.lead_id, models.RFQBroadcast.performed_by)
        .filter(models.RFQBroadcast.created_at >= cutoff, models.RFQBroadcast.lead_id.isnot(None))
        .all()
    )
    op_rows = (
        db.query(models.RFQBroadcast.performed_by)
        .filter(models.RFQBroadcast.created_at >= cutoff)
        .all()
    )

    lead_counts: dict[str, int] = defaultdict(int)
    op_counts: dict[str, int] = defaultdict(int)
    for row in lead_rows:
        lead_counts[str(row.lead_id)] += 1
    for row in op_rows:
        op_counts[str(row.performed_by)] += 1

    rules = list_rate_limit_rules(db)
    rules_by_key = {(r.entity_type, r.entity_key): r for r in rules}

    buckets = []

    for lead_key, count in sorted(lead_counts.items()):
        rule = rules_by_key.get(('lead', lead_key))
        limit = int(rule.max_per_window) if rule else _DEFAULT_LEAD_MAX
        buckets.append({
            'entity_type': 'lead',
            'entity_key': lead_key,
            'broadcasts_in_window': count,
            'limit': limit,
            'window_hours': window_hours,
            'remaining': max(0, limit - count),
            'is_limited': count >= limit,
        })

    for op_key, count in sorted(op_counts.items()):
        rule = rules_by_key.get(('operator', op_key))
        limit = int(rule.max_per_window) if rule else _DEFAULT_OPERATOR_MAX
        buckets.append({
            'entity_type': 'operator',
            'entity_key': op_key,
            'broadcasts_in_window': count,
            'limit': limit,
            'window_hours': window_hours,
            'remaining': max(0, limit - count),
            'is_limited': count >= limit,
        })

    return {
        'generated_at': datetime.now(timezone.utc),
        'window_hours': window_hours,
        'buckets': buckets,
    }
