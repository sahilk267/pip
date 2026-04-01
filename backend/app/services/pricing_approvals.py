from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit
from .sales_notifications import create_sales_notification
from .versioning import capture_order_version, capture_quote_version


_ALLOWED_ENTITY_TYPES = {'order', 'quote'}
_ALLOWED_DECISIONS = {'approved', 'rejected'}


def create_pricing_approval_request(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    requested_discount_pct: float | None,
    requested_discount_amount: float | None,
    reason: str | None,
    requested_by: str,
    metadata: dict | None = None,
) -> models.PricingApprovalRequest:
    normalized_entity_type = str(entity_type or '').strip().lower()
    if normalized_entity_type not in _ALLOWED_ENTITY_TYPES:
        raise ValueError('entity_type must be order or quote')

    entity, lead_id, currency = _resolve_entity(db, entity_type=normalized_entity_type, entity_id=entity_id)

    row = models.PricingApprovalRequest(
        entity_type=normalized_entity_type,
        entity_id=int(entity_id),
        lead_id=lead_id,
        requested_discount_pct=float(requested_discount_pct) if requested_discount_pct is not None else None,
        requested_discount_amount=float(requested_discount_amount) if requested_discount_amount is not None else None,
        currency=currency,
        reason=str(reason or '').strip()[:2000] or None,
        status='pending',
        request_metadata=metadata or {},
        requested_by=str(requested_by or 'sales').strip()[:128] or 'sales',
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    create_sales_notification(
        db,
        entity_type=normalized_entity_type,
        entity_id=int(entity_id),
        notification_type='pricing_approval_requested',
        message=f'{normalized_entity_type} {entity_id} requires pricing approval',
        priority='high',
        lead_id=lead_id,
        recipient='sales-manager',
        metadata={'approval_request_id': row.id},
        performed_by=row.requested_by,
    )
    log_audit(
        db,
        normalized_entity_type,
        int(entity_id),
        'pricing_approval_requested',
        f'approval_request_id={row.id}',
        performed_by=row.requested_by,
    )
    return row


def list_pricing_approval_requests(
    db: Session,
    *,
    entity_type: str | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[models.PricingApprovalRequest]:
    limit = max(1, min(int(limit), 500))
    query = db.query(models.PricingApprovalRequest)
    if entity_type is not None:
        query = query.filter(models.PricingApprovalRequest.entity_type == str(entity_type).strip().lower())
    if status is not None:
        query = query.filter(models.PricingApprovalRequest.status == str(status).strip().lower())
    return query.order_by(models.PricingApprovalRequest.created_at.desc(), models.PricingApprovalRequest.id.desc()).limit(limit).all()


def review_pricing_approval_request(
    db: Session,
    *,
    request_id: int,
    decision: str,
    approved_discount_pct: float | None,
    approved_discount_amount: float | None,
    review_note: str | None,
    reviewed_by: str,
) -> models.PricingApprovalRequest:
    normalized_decision = str(decision or '').strip().lower()
    if normalized_decision not in _ALLOWED_DECISIONS:
        raise ValueError('decision must be approved or rejected')

    row = db.query(models.PricingApprovalRequest).filter(models.PricingApprovalRequest.id == int(request_id)).first()
    if row is None:
        raise ValueError('Pricing approval request not found')
    if row.status != 'pending':
        raise ValueError('Pricing approval request already reviewed')

    row.status = normalized_decision
    row.reviewed_by = str(reviewed_by or 'sales-manager').strip()[:128] or 'sales-manager'
    row.review_note = str(review_note or '').strip()[:2000] or None
    row.approved_discount_pct = float(approved_discount_pct) if approved_discount_pct is not None else row.requested_discount_pct
    row.approved_discount_amount = float(approved_discount_amount) if approved_discount_amount is not None else row.requested_discount_amount
    row.reviewed_at = datetime.now(timezone.utc)

    if normalized_decision == 'approved':
        _apply_discount(
            db,
            entity_type=row.entity_type,
            entity_id=int(row.entity_id),
            discount_pct=row.approved_discount_pct,
            discount_amount=row.approved_discount_amount,
            performed_by=row.reviewed_by,
        )

    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit(
        db,
        row.entity_type,
        int(row.entity_id),
        'pricing_approval_reviewed',
        f'approval_request_id={row.id} decision={row.status}',
        performed_by=row.reviewed_by,
    )
    create_sales_notification(
        db,
        entity_type=row.entity_type,
        entity_id=int(row.entity_id),
        notification_type='pricing_approval_reviewed',
        message=f'Pricing approval {row.id} {row.status}',
        priority='high' if row.status == 'approved' else 'medium',
        lead_id=row.lead_id,
        recipient='sales',
        metadata={'approval_request_id': row.id, 'decision': row.status},
        performed_by=row.reviewed_by,
    )
    return row


def _resolve_entity(db: Session, *, entity_type: str, entity_id: int) -> tuple[object, int | None, str]:
    if entity_type == 'order':
        row = db.query(models.B2COrder).filter(models.B2COrder.id == int(entity_id)).first()
        if row is None:
            raise ValueError('Order not found')
        return row, int(row.lead_id) if row.lead_id is not None else None, str(row.currency or 'USD')

    row = db.query(models.RFQParsedQuote).filter(models.RFQParsedQuote.id == int(entity_id)).first()
    if row is None:
        raise ValueError('RFQ parsed quote not found')
    attempt = db.query(models.RFQDeliveryAttempt).filter(models.RFQDeliveryAttempt.id == int(row.attempt_id)).first()
    broadcast = None if attempt is None else db.query(models.RFQBroadcast).filter(models.RFQBroadcast.id == int(attempt.broadcast_id)).first()
    lead_id = None if broadcast is None or broadcast.lead_id is None else int(broadcast.lead_id)
    return row, lead_id, str(row.currency or 'USD')


def _apply_discount(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    discount_pct: float | None,
    discount_amount: float | None,
    performed_by: str,
) -> None:
    if entity_type == 'order':
        order = db.query(models.B2COrder).filter(models.B2COrder.id == int(entity_id)).first()
        if order is None:
            raise ValueError('Order not found')
        original_total = float(order.total_amount or 0.0)
        new_total = _discounted_value(original_total, discount_pct=discount_pct, discount_amount=discount_amount)
        order.total_amount = new_total
        db.add(order)
        db.commit()
        db.refresh(order)
        capture_order_version(db, order=order, reason='pricing_approval_applied', performed_by=performed_by)
        log_audit(db, 'order', order.id, 'approved_discount_applied', f'from={original_total} to={new_total}', performed_by=performed_by)
        return

    quote = db.query(models.RFQParsedQuote).filter(models.RFQParsedQuote.id == int(entity_id)).first()
    if quote is None:
        raise ValueError('RFQ parsed quote not found')
    original_unit = float(quote.unit_price or 0.0)
    new_unit = _discounted_value(original_unit, discount_pct=discount_pct, discount_amount=discount_amount)
    quote.unit_price = new_unit
    if quote.quantity is not None:
        quote.total_price = round(new_unit * int(quote.quantity), 2)
    metadata = quote.parse_metadata or {}
    metadata['approved_discount_pct'] = discount_pct
    metadata['approved_discount_amount'] = discount_amount
    quote.parse_metadata = metadata
    db.add(quote)
    db.commit()
    db.refresh(quote)
    capture_quote_version(db, quote=quote, reason='pricing_approval_applied', performed_by=performed_by)
    log_audit(db, 'quote', quote.id, 'approved_discount_applied', f'from={original_unit} to={new_unit}', performed_by=performed_by)


def _discounted_value(value: float, *, discount_pct: float | None, discount_amount: float | None) -> float:
    result = float(value or 0.0)
    if discount_pct is not None:
        result = result * max(0.0, 1.0 - (float(discount_pct) / 100.0))
    if discount_amount is not None:
        result = max(0.0, result - float(discount_amount))
    return round(result, 2)
