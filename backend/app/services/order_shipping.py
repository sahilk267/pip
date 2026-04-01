from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit
from .customer_updates import dispatch_customer_update


_ALLOWED_SHIPMENT_STATUS = {'booked', 'in_transit', 'out_for_delivery', 'delivered', 'failed', 'returned'}
_STATUS_TO_FULFILLMENT = {
    'booked': 'shipped',
    'in_transit': 'in_transit',
    'out_for_delivery': 'in_transit',
    'delivered': 'delivered',
    'failed': 'failed',
    'returned': 'returned',
}


def create_shipping_shipment(
    db: Session,
    *,
    order_id: int,
    provider: str,
    service_level: str,
    shipping_cost: float,
    estimated_delivery_days: int,
    shipment_metadata: dict,
    performed_by: str,
) -> models.OrderShippingShipment:
    order = db.query(models.B2COrder).filter(models.B2COrder.id == int(order_id)).first()
    if order is None:
        raise ValueError('Order not found')

    if not order.shipping_address:
        raise ValueError('Order has no shipping address')

    external_shipment_id = f'SHP-{uuid.uuid4().hex[:12].upper()}'
    tracking_number = f'TRK-{uuid.uuid4().hex[:10].upper()}'
    now = datetime.now(timezone.utc)
    eta = now + timedelta(days=max(1, int(estimated_delivery_days)))

    shipment = models.OrderShippingShipment(
        order_id=int(order.id),
        provider=str(provider or 'mockship').strip()[:64] or 'mockship',
        service_level=str(service_level or 'standard').strip()[:32] or 'standard',
        external_shipment_id=external_shipment_id,
        tracking_number=tracking_number,
        status='booked',
        estimated_delivery_at=eta,
        shipping_cost=float(shipping_cost or 0.0),
        shipment_metadata=shipment_metadata or {},
    )
    db.add(shipment)
    db.commit()
    db.refresh(shipment)

    order.tracking_number = shipment.tracking_number
    order.carrier = shipment.provider
    order.fulfillment_status = 'shipped'
    order.shipped_at = order.shipped_at or now
    db.add(order)
    db.commit()

    _append_order_event(
        db,
        order=order,
        status='shipped',
        location='origin_warehouse',
        note=f'Shipment booked via {shipment.provider} ({shipment.external_shipment_id})',
        performed_by=performed_by,
    )

    log_audit(
        db,
        'order',
        order.id,
        'shipping_shipment_created',
        f'shipment_id={shipment.id} provider={shipment.provider} tracking={shipment.tracking_number}',
        performed_by=performed_by,
    )
    return shipment


def list_shipping_shipments_for_order(db: Session, *, order_id: int) -> list[models.OrderShippingShipment]:
    return (
        db.query(models.OrderShippingShipment)
        .filter(models.OrderShippingShipment.order_id == int(order_id))
        .order_by(models.OrderShippingShipment.created_at.desc(), models.OrderShippingShipment.id.desc())
        .all()
    )


def sync_shipping_shipment_status(
    db: Session,
    *,
    shipment_id: int,
    status: str,
    current_location: str | None,
    note: str | None,
    performed_by: str,
) -> models.OrderShippingShipment:
    shipment = db.query(models.OrderShippingShipment).filter(models.OrderShippingShipment.id == int(shipment_id)).first()
    if shipment is None:
        raise ValueError('Shipping shipment not found')

    normalized = str(status or '').strip().lower()
    if normalized not in _ALLOWED_SHIPMENT_STATUS:
        raise ValueError('Unsupported shipping status')

    now = datetime.now(timezone.utc)
    shipment.status = normalized
    if current_location is not None:
        shipment.current_location = str(current_location).strip()[:128] or None
    if normalized == 'delivered':
        shipment.delivered_at = now
    db.add(shipment)
    db.commit()
    db.refresh(shipment)

    order = db.query(models.B2COrder).filter(models.B2COrder.id == int(shipment.order_id)).first()
    if order is not None:
        order.fulfillment_status = _STATUS_TO_FULFILLMENT.get(normalized, order.fulfillment_status)
        order.carrier = shipment.provider
        order.tracking_number = shipment.tracking_number
        if normalized in {'in_transit', 'out_for_delivery'}:
            order.shipped_at = order.shipped_at or now
        if normalized == 'delivered':
            order.delivered_at = now
            order.status = 'fulfilled'
        db.add(order)
        db.commit()

        _append_order_event(
            db,
            order=order,
            status=order.fulfillment_status,
            location=shipment.current_location,
            note=note or f'Shipping status synced to {normalized}',
            performed_by=performed_by,
        )

    log_audit(
        db,
        'order',
        shipment.order_id,
        'shipping_status_synced',
        f'shipment_id={shipment.id} status={shipment.status} location={shipment.current_location or "n/a"}',
        performed_by=performed_by,
    )
    if order is not None and normalized in {'in_transit', 'out_for_delivery', 'delivered', 'failed'}:
        dispatch_customer_update(
            db,
            order_id=int(shipment.order_id),
            event_type=f'shipment_{normalized}',
            message=f'Your shipment for order #{shipment.order_id} is now {normalized}. Tracking: {shipment.tracking_number}',
            lead_id=order.lead_id,
            customer_id=order.customer_id,
            update_metadata={'tracking_number': shipment.tracking_number, 'carrier': shipment.provider, 'location': shipment.current_location},
            performed_by=performed_by,
        )
    return shipment


def _append_order_event(
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
        note=(note or '').strip()[:256] or None,
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
