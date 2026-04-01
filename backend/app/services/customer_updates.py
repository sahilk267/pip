from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit

_ALLOWED_STATUS = {'queued', 'dispatched', 'failed'}

_EVENT_SUBJECTS = {
    'order_created': 'Your order has been placed',
    'order_shipped': 'Your order has shipped',
    'order_in_transit': 'Your order is on the way',
    'order_delivered': 'Your order has been delivered',
    'order_failed': 'There was a problem with your order',
    'order_returned': 'Your return has been initiated',
    'shipment_booked': 'Shipment booked for your order',
    'shipment_out_for_delivery': 'Your order is out for delivery',
}


def dispatch_customer_update(
    db: Session,
    *,
    order_id: int,
    event_type: str,
    message: str,
    lead_id: int | None = None,
    customer_id: int | None = None,
    channel: str = 'email',
    recipient_address: str | None = None,
    update_metadata: dict | None = None,
    performed_by: str = 'system',
) -> models.CustomerUpdateNotification:
    normalized_event = str(event_type or 'order_status').strip().lower()[:64] or 'order_status'
    subject = _EVENT_SUBJECTS.get(normalized_event, f'Update on your order #{order_id}')

    row = models.CustomerUpdateNotification(
        order_id=int(order_id),
        lead_id=int(lead_id) if lead_id is not None else None,
        customer_id=int(customer_id) if customer_id is not None else None,
        event_type=normalized_event,
        channel=str(channel or 'email').strip()[:32] or 'email',
        recipient_address=str(recipient_address or '').strip()[:256] or None,
        subject=subject[:256],
        message=str(message or '').strip()[:4000] or 'Order update',
        status='dispatched',
        update_metadata=update_metadata or {},
        dispatched_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit(
        db,
        'order',
        int(order_id),
        'customer_update_dispatched',
        f'event={row.event_type} channel={row.channel}',
        performed_by=performed_by,
    )
    return row


def list_customer_updates(
    db: Session,
    *,
    order_id: int | None = None,
    lead_id: int | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[models.CustomerUpdateNotification]:
    limit = max(1, min(int(limit), 500))
    q = db.query(models.CustomerUpdateNotification)
    if order_id is not None:
        q = q.filter(models.CustomerUpdateNotification.order_id == int(order_id))
    if lead_id is not None:
        q = q.filter(models.CustomerUpdateNotification.lead_id == int(lead_id))
    if status is not None:
        q = q.filter(models.CustomerUpdateNotification.status == str(status).strip().lower())
    return q.order_by(models.CustomerUpdateNotification.created_at.desc(), models.CustomerUpdateNotification.id.desc()).limit(limit).all()
