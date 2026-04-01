from __future__ import annotations

from datetime import datetime, timezone
import json

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit
from .multi_channel_dedup import check_and_register_multi_channel_dedup
from .versioning import capture_order_version
from .customer_updates import dispatch_customer_update


_ALLOWED_FULFILLMENT = {'pending', 'packed', 'shipped', 'in_transit', 'delivered', 'failed', 'returned'}


def create_b2c_order(
    db: Session,
    *,
    customer_id: int | None,
    lead_id: int | None,
    currency: str,
    total_amount: float,
    order_items: list[dict],
    source_channel: str,
    shipping_address: dict,
    dedup_window_hours: int = 24,
    enable_dedup: bool = True,
    performed_by: str = 'commerce',
) -> models.B2COrder:
    normalized_channel = str(source_channel or 'web').strip().lower()[:32] or 'web'
    dedup_payload = {
        'customer_id': int(customer_id) if customer_id is not None else None,
        'lead_id': int(lead_id) if lead_id is not None else None,
        'currency': str(currency or 'USD').strip().upper()[:8],
        'total_amount': round(float(total_amount or 0.0), 2),
        'order_items': sorted(
            [
                {
                    'sku': str(item.get('sku', '')).strip().lower(),
                    'qty': int(item.get('qty', item.get('quantity', 0)) or 0),
                    'price': round(float(item.get('price', item.get('unit_price', 0.0)) or 0.0), 2),
                }
                for item in (order_items or [])
            ],
            key=lambda x: (x['sku'], x['qty'], x['price']),
        ),
        'shipping_city': str((shipping_address or {}).get('city', '')).strip().lower(),
        'shipping_country': str((shipping_address or {}).get('country', '')).strip().lower(),
    }
    if enable_dedup:
        is_duplicate = check_and_register_multi_channel_dedup(
            db,
            entity_type='b2c_order',
            dedup_key_raw=json.dumps(dedup_payload, sort_keys=True),
            channel=normalized_channel,
            window_hours=dedup_window_hours,
            performed_by=performed_by,
        )
        if is_duplicate:
            raise ValueError('Duplicate order detected across channels within deduplication window')

    order = models.B2COrder(
        customer_id=customer_id,
        lead_id=lead_id,
        currency=str(currency or 'USD').strip().upper()[:8],
        total_amount=float(total_amount or 0.0),
        order_items=order_items or [],
        source_channel=normalized_channel,
        shipping_address=shipping_address or {},
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    _append_event(
        db,
        order=order,
        status='created',
        location='order-intake',
        note='Order created',
        performed_by=performed_by,
    )
    capture_order_version(db, order=order, reason='order_created', performed_by=performed_by)
    dispatch_customer_update(
        db,
        order_id=order.id,
        event_type='order_created',
        message=f'Your order #{order.id} has been placed successfully. Total: {order.currency} {order.total_amount}',
        lead_id=order.lead_id,
        customer_id=order.customer_id,
        performed_by=performed_by,
    )
    log_audit(
        db,
        'order',
        order.id,
        'order_created',
        f'amount={order.total_amount} channel={order.source_channel}',
        performed_by=performed_by,
    )
    return order


def list_b2c_orders(db: Session, *, limit: int = 100) -> list[models.B2COrder]:
    limit = max(1, min(int(limit), 500))
    return (
        db.query(models.B2COrder)
        .order_by(models.B2COrder.created_at.desc(), models.B2COrder.id.desc())
        .limit(limit)
        .all()
    )


def get_b2c_order(db: Session, order_id: int) -> models.B2COrder | None:
    return db.query(models.B2COrder).filter(models.B2COrder.id == int(order_id)).first()


def update_fulfillment_status(
    db: Session,
    *,
    order_id: int,
    fulfillment_status: str,
    tracking_number: str | None,
    carrier: str | None,
    location: str | None,
    note: str | None,
    performed_by: str = 'operations',
) -> models.B2COrder:
    order = get_b2c_order(db, order_id)
    if order is None:
        raise ValueError('Order not found')

    status = str(fulfillment_status or '').strip().lower()
    if status not in _ALLOWED_FULFILLMENT:
        raise ValueError('Unsupported fulfillment status')

    now = datetime.now(timezone.utc)
    order.fulfillment_status = status
    order.status = 'fulfilled' if status == 'delivered' else order.status
    if tracking_number is not None:
        order.tracking_number = tracking_number
    if carrier is not None:
        order.carrier = carrier
    if status in {'shipped', 'in_transit'}:
        order.shipped_at = order.shipped_at or now
    if status == 'delivered':
        order.delivered_at = now

    db.add(order)
    db.commit()
    db.refresh(order)

    _append_event(
        db,
        order=order,
        status=status,
        location=location,
        note=note or f'Fulfillment status changed to {status}',
        performed_by=performed_by,
    )
    capture_order_version(db, order=order, reason=f'fulfillment_{status}', performed_by=performed_by)
    dispatch_customer_update(
        db,
        order_id=order.id,
        event_type=f'order_{status}',
        message=f'Your order #{order.id} status has been updated to: {status}.',
        lead_id=order.lead_id,
        customer_id=order.customer_id,
        update_metadata={'tracking_number': order.tracking_number, 'carrier': order.carrier},
        performed_by=performed_by,
    )
    log_audit(
        db,
        'order',
        order.id,
        'order_fulfillment_updated',
        f'fulfillment_status={status} tracking={order.tracking_number or "n/a"}',
        performed_by=performed_by,
    )
    return order


def order_tracking_timeline(db: Session, *, order_id: int) -> tuple[models.B2COrder, list[models.OrderFulfillmentEvent]]:
    order = get_b2c_order(db, order_id)
    if order is None:
        raise ValueError('Order not found')

    events = (
        db.query(models.OrderFulfillmentEvent)
        .filter(models.OrderFulfillmentEvent.order_id == order.id)
        .order_by(models.OrderFulfillmentEvent.occurred_at.asc(), models.OrderFulfillmentEvent.id.asc())
        .all()
    )
    return order, events


def _append_event(
    db: Session,
    *,
    order: models.B2COrder,
    status: str,
    location: str | None,
    note: str | None,
    performed_by: str,
) -> None:
    event = models.OrderFulfillmentEvent(
        order_id=order.id,
        status=status,
        location=(location or '').strip() or None,
        note=(note or '').strip() or None,
        tracking_number=order.tracking_number,
        carrier=order.carrier,
    )
    db.add(event)
    db.commit()

    log_audit(
        db,
        'order',
        order.id,
        'fulfillment_event',
        f'status={status} tracking={order.tracking_number or "n/a"}',
        performed_by=performed_by,
    )
