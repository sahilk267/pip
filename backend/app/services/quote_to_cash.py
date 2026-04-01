from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit
from .sales_notifications import create_sales_notification


_ALLOWED_STATUSES = {'quoted', 'approved', 'invoiced', 'paid', 'synced'}
_ALLOWED_PAYMENT_STATUS = {'pending', 'paid', 'failed'}


def create_quote_to_cash_record(
    db: Session,
    *,
    quote_id: int | None,
    order_id: int | None,
    customer_id: int | None,
    external_system: str | None,
    created_by: str,
) -> models.QuoteToCashRecord:
    if quote_id is None and order_id is None:
        raise ValueError('quote_id or order_id is required')

    quote = None if quote_id is None else db.query(models.RFQParsedQuote).filter(models.RFQParsedQuote.id == int(quote_id)).first()
    if quote_id is not None and quote is None:
        raise ValueError('RFQ parsed quote not found')

    order = None if order_id is None else db.query(models.B2COrder).filter(models.B2COrder.id == int(order_id)).first()
    if order_id is not None and order is None:
        raise ValueError('Order not found')

    attempt = None if quote is None else db.query(models.RFQDeliveryAttempt).filter(models.RFQDeliveryAttempt.id == int(quote.attempt_id)).first()
    broadcast = None if attempt is None else db.query(models.RFQBroadcast).filter(models.RFQBroadcast.id == int(attempt.broadcast_id)).first()
    lead_id = None
    if order is not None and order.lead_id is not None:
        lead_id = int(order.lead_id)
    elif broadcast is not None and broadcast.lead_id is not None:
        lead_id = int(broadcast.lead_id)

    invoice_amount, currency = _resolve_amount_currency(quote=quote, order=order)
    row = models.QuoteToCashRecord(
        quote_id=int(quote.id) if quote is not None else None,
        order_id=int(order.id) if order is not None else None,
        lead_id=lead_id,
        customer_id=int(customer_id) if customer_id is not None else (int(order.customer_id) if order is not None and order.customer_id is not None else None),
        status='quoted',
        payment_status='pending',
        invoice_amount=invoice_amount,
        currency=currency,
        external_system=str(external_system or '').strip()[:64] or None,
        created_by=str(created_by or 'system').strip()[:128] or 'system',
        qtc_metadata={},
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit(db, 'quote_to_cash', row.id, 'quote_to_cash_created', f'quote_id={row.quote_id} order_id={row.order_id}', performed_by=row.created_by)
    create_sales_notification(
        db,
        entity_type='quote_to_cash',
        entity_id=row.id,
        notification_type='quote_to_cash_created',
        message=f'Quote-to-cash record {row.id} created',
        priority='medium',
        lead_id=row.lead_id,
        recipient='sales',
        metadata={'quote_id': row.quote_id, 'order_id': row.order_id},
        performed_by=row.created_by,
    )
    return row


def list_quote_to_cash_records(
    db: Session,
    *,
    status: str | None = None,
    limit: int = 200,
) -> list[models.QuoteToCashRecord]:
    limit = max(1, min(int(limit), 500))
    query = db.query(models.QuoteToCashRecord)
    if status is not None:
        query = query.filter(models.QuoteToCashRecord.status == str(status).strip().lower())
    return query.order_by(models.QuoteToCashRecord.created_at.desc(), models.QuoteToCashRecord.id.desc()).limit(limit).all()


def advance_quote_to_cash_record(
    db: Session,
    *,
    record_id: int,
    status: str,
    payment_status: str | None,
    external_reference: str | None,
    performed_by: str,
) -> models.QuoteToCashRecord:
    normalized_status = str(status or '').strip().lower()
    if normalized_status not in _ALLOWED_STATUSES:
        raise ValueError('Unsupported quote-to-cash status')

    row = db.query(models.QuoteToCashRecord).filter(models.QuoteToCashRecord.id == int(record_id)).first()
    if row is None:
        raise ValueError('Quote-to-cash record not found')

    row.status = normalized_status
    if payment_status is not None:
        normalized_payment = str(payment_status).strip().lower()
        if normalized_payment not in _ALLOWED_PAYMENT_STATUS:
            raise ValueError('Unsupported payment status')
        row.payment_status = normalized_payment
    if external_reference is not None:
        row.external_reference = str(external_reference or '').strip()[:128] or None

    now = datetime.now(timezone.utc)
    if normalized_status == 'invoiced' and not row.invoice_number:
        row.invoice_number = f'INV-{uuid.uuid4().hex[:10].upper()}'
        row.invoiced_at = now
    elif normalized_status == 'paid':
        row.paid_at = now
        row.payment_status = 'paid'
    elif normalized_status == 'synced':
        row.synced_at = now

    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit(db, 'quote_to_cash', row.id, 'quote_to_cash_advanced', f'status={row.status} payment_status={row.payment_status}', performed_by=performed_by)
    create_sales_notification(
        db,
        entity_type='quote_to_cash',
        entity_id=row.id,
        notification_type='quote_to_cash_advanced',
        message=f'Quote-to-cash record {row.id} advanced to {row.status}',
        priority='medium' if row.status != 'paid' else 'high',
        lead_id=row.lead_id,
        recipient='finance' if row.status in {'invoiced', 'paid', 'synced'} else 'sales',
        metadata={'payment_status': row.payment_status},
        performed_by=performed_by,
    )
    return row


def _resolve_amount_currency(*, quote: models.RFQParsedQuote | None, order: models.B2COrder | None) -> tuple[float, str]:
    if order is not None:
        return float(order.total_amount or 0.0), str(order.currency or 'USD')
    assert quote is not None
    amount = float(quote.total_price or 0.0)
    if amount <= 0 and quote.unit_price is not None and quote.quantity is not None:
        amount = float(quote.unit_price) * int(quote.quantity)
    return round(amount, 2), str(quote.currency or 'USD')
