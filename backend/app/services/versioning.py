from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit


def capture_order_version(
    db: Session,
    *,
    order: models.B2COrder,
    reason: str,
    performed_by: str,
) -> models.EntityVersionRecord:
    snapshot = {
        'status': order.status,
        'fulfillment_status': order.fulfillment_status,
        'currency': order.currency,
        'total_amount': float(order.total_amount or 0.0),
        'order_items': order.order_items or [],
        'source_channel': order.source_channel,
        'shipping_address': order.shipping_address or {},
        'tracking_number': order.tracking_number,
        'carrier': order.carrier,
        'external_order_id': order.external_order_id,
        'shipped_at': _iso(order.shipped_at),
        'delivered_at': _iso(order.delivered_at),
    }
    return _create_version(
        db,
        entity_type='order',
        entity_id=int(order.id),
        snapshot=snapshot,
        reason=reason,
        performed_by=performed_by,
    )


def capture_quote_version(
    db: Session,
    *,
    quote: models.RFQParsedQuote,
    reason: str,
    performed_by: str,
) -> models.EntityVersionRecord:
    snapshot = {
        'response_id': int(quote.response_id),
        'attempt_id': int(quote.attempt_id),
        'vendor_id': int(quote.vendor_id),
        'currency': quote.currency,
        'unit_price': quote.unit_price,
        'total_price': quote.total_price,
        'quantity': quote.quantity,
        'lead_time_days': quote.lead_time_days,
        'minimum_order_quantity': quote.minimum_order_quantity,
        'confidence': float(quote.confidence or 0.0),
        'parser_version': quote.parser_version,
        'raw_excerpt': quote.raw_excerpt,
        'parse_metadata': quote.parse_metadata or {},
    }
    return _create_version(
        db,
        entity_type='quote',
        entity_id=int(quote.id),
        snapshot=snapshot,
        reason=reason,
        performed_by=performed_by,
    )


def list_entity_versions(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    limit: int = 100,
) -> list[models.EntityVersionRecord]:
    limit = max(1, min(int(limit), 500))
    return (
        db.query(models.EntityVersionRecord)
        .filter(
            models.EntityVersionRecord.entity_type == str(entity_type),
            models.EntityVersionRecord.entity_id == int(entity_id),
        )
        .order_by(models.EntityVersionRecord.version_number.desc(), models.EntityVersionRecord.id.desc())
        .limit(limit)
        .all()
    )


def rollback_order_version(
    db: Session,
    *,
    order_id: int,
    version_number: int,
    reason: str,
    performed_by: str,
) -> models.B2COrder:
    order = db.query(models.B2COrder).filter(models.B2COrder.id == int(order_id)).first()
    if order is None:
        raise ValueError('Order not found')

    version = _get_version(db, entity_type='order', entity_id=order.id, version_number=version_number)
    snapshot = version.snapshot or {}

    order.status = str(snapshot.get('status') or order.status)
    order.fulfillment_status = str(snapshot.get('fulfillment_status') or order.fulfillment_status)
    order.currency = str(snapshot.get('currency') or order.currency)
    order.total_amount = float(snapshot.get('total_amount') if snapshot.get('total_amount') is not None else order.total_amount)
    order.order_items = snapshot.get('order_items') or []
    order.source_channel = str(snapshot.get('source_channel') or order.source_channel)
    order.shipping_address = snapshot.get('shipping_address') or {}
    order.tracking_number = snapshot.get('tracking_number')
    order.carrier = snapshot.get('carrier')
    order.external_order_id = snapshot.get('external_order_id')
    order.shipped_at = _parse_iso(snapshot.get('shipped_at'))
    order.delivered_at = _parse_iso(snapshot.get('delivered_at'))

    db.add(order)
    db.commit()
    db.refresh(order)

    capture_order_version(
        db,
        order=order,
        reason=f'rollback_to_v{version_number}:{reason}',
        performed_by=performed_by,
    )
    log_audit(
        db,
        'order',
        order.id,
        'order_version_rollback',
        f'rolled_back_to=v{version_number} reason={reason}',
        performed_by=performed_by,
    )
    return order


def rollback_quote_version(
    db: Session,
    *,
    quote_id: int,
    version_number: int,
    reason: str,
    performed_by: str,
) -> models.RFQParsedQuote:
    quote = db.query(models.RFQParsedQuote).filter(models.RFQParsedQuote.id == int(quote_id)).first()
    if quote is None:
        raise ValueError('RFQ parsed quote not found')

    version = _get_version(db, entity_type='quote', entity_id=quote.id, version_number=version_number)
    snapshot = version.snapshot or {}

    quote.currency = str(snapshot.get('currency') or quote.currency)
    quote.unit_price = snapshot.get('unit_price')
    quote.total_price = snapshot.get('total_price')
    quote.quantity = snapshot.get('quantity')
    quote.lead_time_days = snapshot.get('lead_time_days')
    quote.minimum_order_quantity = snapshot.get('minimum_order_quantity')
    quote.confidence = float(snapshot.get('confidence') if snapshot.get('confidence') is not None else quote.confidence)
    quote.parser_version = str(snapshot.get('parser_version') or quote.parser_version)
    quote.raw_excerpt = snapshot.get('raw_excerpt')
    quote.parse_metadata = snapshot.get('parse_metadata') or {}

    db.add(quote)
    db.commit()
    db.refresh(quote)

    capture_quote_version(
        db,
        quote=quote,
        reason=f'rollback_to_v{version_number}:{reason}',
        performed_by=performed_by,
    )
    log_audit(
        db,
        'rfq',
        quote.attempt_id,
        'quote_version_rollback',
        f'quote_id={quote.id} rolled_back_to=v{version_number} reason={reason}',
        performed_by=performed_by,
    )
    return quote


def _create_version(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    snapshot: dict[str, Any],
    reason: str,
    performed_by: str,
) -> models.EntityVersionRecord:
    current_max = (
        db.query(func.max(models.EntityVersionRecord.version_number))
        .filter(
            models.EntityVersionRecord.entity_type == str(entity_type),
            models.EntityVersionRecord.entity_id == int(entity_id),
        )
        .scalar()
    )
    next_version = int(current_max or 0) + 1

    row = models.EntityVersionRecord(
        entity_type=str(entity_type),
        entity_id=int(entity_id),
        version_number=next_version,
        snapshot=snapshot,
        change_reason=str(reason or '').strip()[:2000] or None,
        changed_by=str(performed_by or 'system').strip()[:128] or 'system',
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit(
        db,
        entity_type,
        entity_id,
        'entity_version_created',
        f'version=v{next_version} reason={reason}',
        performed_by=performed_by,
    )
    return row


def _get_version(db: Session, *, entity_type: str, entity_id: int, version_number: int) -> models.EntityVersionRecord:
    row = (
        db.query(models.EntityVersionRecord)
        .filter(
            models.EntityVersionRecord.entity_type == str(entity_type),
            models.EntityVersionRecord.entity_id == int(entity_id),
            models.EntityVersionRecord.version_number == int(version_number),
        )
        .first()
    )
    if row is None:
        raise ValueError('Version not found')
    return row


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None
