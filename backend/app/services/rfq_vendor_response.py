from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit
from .sales_notifications import create_sales_notification

_ALLOWED_RESPONSE_STATUSES = {'replied', 'no_response', 'opened'}


def record_vendor_response(
    db: Session,
    *,
    attempt_id: int,
    response_status: str,
    response_text: str | None,
    quoted_price: float | None,
    recorded_by: str,
) -> models.RFQVendorResponse:
    attempt = (
        db.query(models.RFQDeliveryAttempt)
        .filter(models.RFQDeliveryAttempt.id == int(attempt_id))
        .first()
    )
    if attempt is None:
        raise ValueError('RFQ delivery attempt not found')

    normalized_status = str(response_status or 'replied').strip().lower() or 'replied'
    if normalized_status not in _ALLOWED_RESPONSE_STATUSES:
        raise ValueError(f'Unsupported response_status; allowed: {sorted(_ALLOWED_RESPONSE_STATUSES)}')

    response = models.RFQVendorResponse(
        attempt_id=int(attempt_id),
        vendor_id=int(attempt.vendor_id),
        response_status=normalized_status,
        response_text=str(response_text or '').strip()[:4000] or None,
        quoted_price=float(quoted_price) if quoted_price is not None else None,
        recorded_by=str(recorded_by or 'system').strip()[:128] or 'system',
        responded_at=datetime.now(timezone.utc),
    )
    db.add(response)
    db.commit()
    db.refresh(response)

    log_audit(
        db,
        'rfq',
        attempt.broadcast_id,
        'rfq_vendor_response_recorded',
        f'attempt_id={attempt_id} vendor_id={attempt.vendor_id} status={normalized_status}',
        performed_by=recorded_by,
    )
    broadcast = (
        db.query(models.RFQBroadcast)
        .filter(models.RFQBroadcast.id == int(attempt.broadcast_id))
        .first()
    )
    create_sales_notification(
        db,
        entity_type='rfq_response',
        entity_id=int(response.id),
        notification_type='vendor_response_received',
        message=f'Vendor {attempt.vendor_id} responded with status {normalized_status}',
        priority='high' if normalized_status == 'replied' else 'medium',
        lead_id=None if broadcast is None or broadcast.lead_id is None else int(broadcast.lead_id),
        recipient='sales',
        metadata={'attempt_id': int(attempt.id), 'broadcast_id': int(attempt.broadcast_id)},
        performed_by=recorded_by,
    )
    return response


def list_responses_for_attempt(
    db: Session,
    *,
    attempt_id: int,
) -> list[models.RFQVendorResponse]:
    return (
        db.query(models.RFQVendorResponse)
        .filter(models.RFQVendorResponse.attempt_id == int(attempt_id))
        .order_by(models.RFQVendorResponse.responded_at.asc(), models.RFQVendorResponse.id.asc())
        .all()
    )


def vendor_response_analytics(db: Session, *, window_days: int = 30) -> dict:
    """Compute vendor reply/open rates across delivered RFQ attempts in the given window."""
    window_days = max(1, int(window_days))
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

    # All delivered/failed attempts (not queued) in window — these are the denominator
    attempts = (
        db.query(models.RFQDeliveryAttempt, models.RFQBroadcast.channel, models.Vendor.name)
        .join(models.RFQBroadcast, models.RFQBroadcast.id == models.RFQDeliveryAttempt.broadcast_id)
        .join(models.Vendor, models.Vendor.id == models.RFQDeliveryAttempt.vendor_id)
        .filter(models.RFQDeliveryAttempt.attempted_at >= cutoff)
        .filter(models.RFQDeliveryAttempt.status != 'queued')
        .all()
    )

    attempt_ids = [row[0].id for row in attempts]

    # All vendor responses for those attempts
    responses: list[models.RFQVendorResponse] = []
    if attempt_ids:
        responses = (
            db.query(models.RFQVendorResponse)
            .filter(models.RFQVendorResponse.attempt_id.in_(attempt_ids))
            .all()
        )

    # Map attempt_id → response_status (take latest if multiple)
    attempt_response_map: dict[int, str] = {}
    for resp in responses:
        attempt_response_map[int(resp.attempt_id)] = str(resp.response_status or 'replied').strip().lower()

    # Aggregate
    Bucket = lambda: {
        'total_deliveries': 0,
        'responses': 0,
        'opens': 0,
        'replies': 0,
        'no_responses': 0,
    }

    by_vendor: dict[str, dict] = defaultdict(Bucket)
    by_channel: dict[str, dict] = defaultdict(Bucket)
    totals = Bucket()

    for attempt, channel, vendor_name in attempts:
        aid = int(attempt.id)
        ch = str(channel or 'unknown').strip().lower() or 'unknown'
        vname = str(vendor_name or f'vendor_{attempt.vendor_id}').strip()[:64] or f'vendor_{attempt.vendor_id}'

        for bucket in (totals, by_vendor[vname], by_channel[ch]):
            bucket['total_deliveries'] += 1

        if aid in attempt_response_map:
            status = attempt_response_map[aid]
            for bucket in (totals, by_vendor[vname], by_channel[ch]):
                bucket['responses'] += 1
                if status == 'opened':
                    bucket['opens'] += 1
                elif status == 'replied':
                    bucket['replies'] += 1
                elif status == 'no_response':
                    bucket['no_responses'] += 1

    def _rates(bucket: dict) -> dict:
        total = bucket['total_deliveries']
        return {
            **bucket,
            'reply_rate': round(bucket['replies'] / total, 4) if total else 0.0,
            'open_rate': round((bucket['opens'] + bucket['replies']) / total, 4) if total else 0.0,
        }

    total_deliveries = totals['total_deliveries']
    return {
        'generated_at': datetime.now(timezone.utc),
        'window_days': window_days,
        'total_deliveries': total_deliveries,
        'total_responses': totals['responses'],
        'reply_rate': round(totals['replies'] / total_deliveries, 4) if total_deliveries else 0.0,
        'open_rate': round((totals['opens'] + totals['replies']) / total_deliveries, 4) if total_deliveries else 0.0,
        'by_vendor': {k: _rates(v) for k, v in sorted(by_vendor.items())},
        'by_channel': {k: _rates(v) for k, v in sorted(by_channel.items())},
    }
