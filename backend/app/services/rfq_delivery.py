from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit
from .multi_channel_dedup import check_and_register_multi_channel_dedup
from .vendor_opt_out import get_blocked_vendor_ids_for_channel

_ALLOWED_DELIVERY_STATUS = {'queued', 'delivered', 'failed'}


def create_rfq_broadcast(
    db: Session,
    *,
    lead_id: int | None,
    vendor_ids: list[int],
    channel: str,
    message: str,
    auto_match_limit: int,
    performed_by: str,
) -> tuple[models.RFQBroadcast, list[models.RFQDeliveryAttempt]]:
    normalized_channel = str(channel or 'email').strip().lower() or 'email'
    selected_vendor_ids = _resolve_vendor_ids(db, vendor_ids=vendor_ids, auto_match_limit=auto_match_limit)
    blocked_vendor_ids = get_blocked_vendor_ids_for_channel(
        db,
        vendor_ids=selected_vendor_ids,
        channel=normalized_channel,
    )
    selected_vendor_ids = [vendor_id for vendor_id in selected_vendor_ids if vendor_id not in blocked_vendor_ids]
    if not selected_vendor_ids:
        raise ValueError('No vendors available for RFQ broadcast after blacklist/opt-out filtering')

    dedup_payload = {
        'lead_id': int(lead_id) if lead_id is not None else None,
        'vendor_ids': sorted([int(v) for v in selected_vendor_ids]),
        'message': str(message or '').strip().lower()[:400],
    }
    is_duplicate = check_and_register_multi_channel_dedup(
        db,
        entity_type='rfq_broadcast',
        dedup_key_raw=json.dumps(dedup_payload, sort_keys=True),
        channel=normalized_channel,
        window_hours=24,
        performed_by=performed_by,
    )
    if is_duplicate:
        raise ValueError('Duplicate RFQ broadcast detected across channels within deduplication window')

    broadcast = models.RFQBroadcast(
        lead_id=lead_id,
        channel=normalized_channel,
        status='pending',
        message=str(message or '').strip()[:2000],
        performed_by=performed_by,
    )
    db.add(broadcast)
    db.commit()
    db.refresh(broadcast)

    attempts: list[models.RFQDeliveryAttempt] = []
    for vendor_id in selected_vendor_ids:
        attempt = models.RFQDeliveryAttempt(
            broadcast_id=broadcast.id,
            vendor_id=vendor_id,
            status='queued',
        )
        db.add(attempt)
        attempts.append(attempt)

    broadcast.status = 'in_progress'
    db.add(broadcast)
    db.commit()

    attempts = list_delivery_attempts(db, broadcast_id=broadcast.id)

    log_audit(
        db,
        'rfq',
        broadcast.id,
        'rfq_broadcast_created',
        f'vendors={len(attempts)} channel={normalized_channel}',
        performed_by=performed_by,
    )
    if blocked_vendor_ids:
        log_audit(
            db,
            'rfq',
            broadcast.id,
            'rfq_vendor_opt_out_filtered',
            f'skipped={len(blocked_vendor_ids)} channel={normalized_channel}',
            performed_by=performed_by,
        )
    return broadcast, attempts


def list_rfq_broadcasts(db: Session, *, limit: int = 100) -> list[models.RFQBroadcast]:
    limit = max(1, min(int(limit), 500))
    return (
        db.query(models.RFQBroadcast)
        .order_by(models.RFQBroadcast.created_at.desc(), models.RFQBroadcast.id.desc())
        .limit(limit)
        .all()
    )


def list_delivery_attempts(db: Session, *, broadcast_id: int) -> list[models.RFQDeliveryAttempt]:
    return (
        db.query(models.RFQDeliveryAttempt)
        .filter(models.RFQDeliveryAttempt.broadcast_id == int(broadcast_id))
        .order_by(models.RFQDeliveryAttempt.attempted_at.asc(), models.RFQDeliveryAttempt.id.asc())
        .all()
    )


def update_delivery_attempt(
    db: Session,
    *,
    attempt_id: int,
    status: str,
    external_ref: str | None,
    error_detail: str | None,
    performed_by: str,
) -> models.RFQDeliveryAttempt:
    attempt = db.query(models.RFQDeliveryAttempt).filter(models.RFQDeliveryAttempt.id == int(attempt_id)).first()
    if attempt is None:
        raise ValueError('RFQ delivery attempt not found')

    normalized = str(status or '').strip().lower()
    if normalized not in _ALLOWED_DELIVERY_STATUS:
        raise ValueError('Unsupported RFQ delivery status')

    attempt.status = normalized
    if external_ref is not None:
        attempt.external_ref = str(external_ref or '').strip()[:128] or None
    if error_detail is not None:
        attempt.error_detail = str(error_detail or '').strip()[:2000] or None
    if normalized == 'delivered':
        attempt.delivered_at = datetime.now(timezone.utc)
        attempt.error_detail = None

    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    _refresh_broadcast_status(db, attempt.broadcast_id)

    log_audit(
        db,
        'rfq',
        attempt.broadcast_id,
        'rfq_delivery_status_update',
        f'attempt_id={attempt.id} status={normalized}',
        performed_by=performed_by,
    )
    return attempt


def sync_delivery_attempts(
    db: Session,
    *,
    limit: int = 300,
    performed_by: str = 'rfq-sync',
) -> dict[str, int]:
    limit = max(1, min(int(limit), 1000))
    attempts = (
        db.query(models.RFQDeliveryAttempt)
        .filter(models.RFQDeliveryAttempt.status == 'queued')
        .order_by(models.RFQDeliveryAttempt.id.asc())
        .limit(limit)
        .all()
    )

    delivered = 0
    failed = 0
    touched_broadcast_ids: set[int] = set()
    now = datetime.now(timezone.utc)

    for row in attempts:
        touched_broadcast_ids.add(int(row.broadcast_id))
        if row.id % 6 == 0:
            row.status = 'failed'
            row.error_detail = row.error_detail or 'Provider returned delivery failure'
            failed += 1
        else:
            row.status = 'delivered'
            row.delivered_at = row.delivered_at or now
            row.external_ref = row.external_ref or f'rfq-{row.broadcast_id}-v{row.vendor_id}-a{row.id}'
            row.error_detail = None
            delivered += 1
        db.add(row)

    db.commit()

    for broadcast_id in touched_broadcast_ids:
        _refresh_broadcast_status(db, broadcast_id)

    log_audit(
        db,
        'rfq',
        None,
        'rfq_delivery_sync',
        f'scanned={len(attempts)} delivered={delivered} failed={failed}',
        performed_by=performed_by,
    )

    return {
        'scanned': len(attempts),
        'delivered': delivered,
        'failed': failed,
    }


def delivery_summary(db: Session, *, window_days: int = 30) -> dict:
    window_days = max(1, int(window_days))
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

    attempts = (
        db.query(models.RFQDeliveryAttempt, models.RFQBroadcast.channel)
        .join(models.RFQBroadcast, models.RFQBroadcast.id == models.RFQDeliveryAttempt.broadcast_id)
        .filter(models.RFQDeliveryAttempt.attempted_at >= cutoff)
        .all()
    )

    by_status: dict[str, int] = defaultdict(int)
    by_channel: dict[str, dict[str, int]] = defaultdict(lambda: {'total': 0, 'delivered': 0, 'failed': 0, 'queued': 0})

    for attempt, channel in attempts:
        status = str(attempt.status or 'queued').strip().lower() or 'queued'
        key_channel = str(channel or 'unknown').strip().lower() or 'unknown'
        by_status[status] += 1
        by_channel[key_channel]['total'] += 1
        by_channel[key_channel][status] = int(by_channel[key_channel].get(status, 0)) + 1

    total_attempts = len(attempts)
    return {
        'generated_at': datetime.now(timezone.utc),
        'window_days': window_days,
        'total_attempts': total_attempts,
        'delivered': int(by_status.get('delivered', 0)),
        'failed': int(by_status.get('failed', 0)),
        'queued': int(by_status.get('queued', 0)),
        'by_channel': {k: dict(v) for k, v in sorted(by_channel.items())},
        'by_status': dict(sorted(by_status.items())),
    }


def _resolve_vendor_ids(db: Session, *, vendor_ids: list[int], auto_match_limit: int) -> list[int]:
    explicit = sorted({int(vendor_id) for vendor_id in vendor_ids if int(vendor_id) > 0})
    if explicit:
        rows = (
            db.query(models.Vendor.id)
            .filter(models.Vendor.id.in_(explicit))
            .all()
        )
        return sorted({int(row.id) for row in rows})

    limit = max(0, min(int(auto_match_limit or 0), 100))
    if limit <= 0:
        return []

    rows = (
        db.query(models.Vendor.id)
        .order_by(models.Vendor.updated_at.desc(), models.Vendor.id.asc())
        .limit(limit)
        .all()
    )
    return [int(row.id) for row in rows]


def _refresh_broadcast_status(db: Session, broadcast_id: int) -> None:
    attempts = list_delivery_attempts(db, broadcast_id=broadcast_id)
    if not attempts:
        return

    statuses = {str(row.status or 'queued').strip().lower() or 'queued' for row in attempts}
    broadcast = db.query(models.RFQBroadcast).filter(models.RFQBroadcast.id == int(broadcast_id)).first()
    if broadcast is None:
        return

    if statuses == {'delivered'}:
        broadcast.status = 'completed'
    elif statuses == {'failed'}:
        broadcast.status = 'failed'
    elif 'queued' in statuses:
        broadcast.status = 'in_progress'
    else:
        broadcast.status = 'partial_failed'

    db.add(broadcast)
    db.commit()
