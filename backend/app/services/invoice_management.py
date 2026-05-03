"""Invoice generation and management service."""
from datetime import datetime, timedelta, timezone
from typing import Any
from sqlalchemy.orm import Session
from .. import models
from ..models_extended import Invoice, InvoiceItem


def generate_invoice_from_quote(
    db: Session,
    quote_id: int,
    po_number: str,
    payment_terms: str = "Net 30",
    generated_by: str = "system",
) -> dict[str, Any]:
    """Generate invoice from a quote/PO."""
    quote = db.query(models.RFQParsedQuote).filter(models.RFQParsedQuote.id == quote_id).first()
    if not quote:
        raise ValueError(f"Quote {quote_id} not found")

    vendor = quote.vendor
    total = (quote.unit_price or 0) * (quote.quantity or 1)

    # Generate invoice number
    inv_count = db.query(Invoice).count()
    invoice_number = f"INV-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{inv_count + 1:04d}"

    # Calculate due date
    days_map = {"Net 15": 15, "Net 30": 30, "Net 60": 60}
    due_days = days_map.get(payment_terms, 30)
    due_date = datetime.now(timezone.utc) + timedelta(days=due_days)

    invoice = Invoice(
        invoice_number=invoice_number,
        vendor_id=quote.vendor_id,
        po_number=po_number,
        quote_id=quote_id,
        total_amount=total,
        currency=quote.currency or "USD",
        status="draft",
        due_date=due_date,
        payment_terms=payment_terms,
        created_by=generated_by,
    )
    db.add(invoice)
    db.flush()

    # Add line item
    item = InvoiceItem(
        invoice_id=invoice.id,
        description=f"{quote.quantity} x {quote.quantity} units (RFQ #{quote.response_id})",
        quantity=quote.quantity or 1,
        unit_price=quote.unit_price or 0,
        total_price=total,
    )
    db.add(item)
    db.commit()
    db.refresh(invoice)

    return {
        "invoice_id": invoice.id,
        "invoice_number": invoice_number,
        "vendor_id": quote.vendor_id,
        "vendor_name": vendor.name if vendor else "Unknown",
        "po_number": po_number,
        "total_amount": total,
        "currency": invoice.currency,
        "due_date": due_date.isoformat(),
        "payment_terms": payment_terms,
        "status": "draft",
    }


def send_invoice(
    db: Session,
    invoice_id: int,
    sent_by: str = "system",
) -> dict[str, Any]:
    """Send invoice to vendor."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise ValueError(f"Invoice {invoice_id} not found")

    invoice.status = "sent"
    db.add(invoice)
    db.commit()

    # TODO: Send email to vendor

    return {
        "invoice_id": invoice_id,
        "invoice_number": invoice.invoice_number,
        "status": "sent",
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }


def record_payment(
    db: Session,
    invoice_id: int,
    amount_paid: float | None = None,
) -> dict[str, Any]:
    """Record payment for invoice."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise ValueError(f"Invoice {invoice_id} not found")

    if amount_paid is None:
        amount_paid = invoice.total_amount

    invoice.status = "paid"
    invoice.paid_date = datetime.now(timezone.utc)
    db.add(invoice)
    db.commit()

    return {
        "invoice_id": invoice_id,
        "invoice_number": invoice.invoice_number,
        "status": "paid",
        "amount_paid": amount_paid,
        "paid_at": invoice.paid_date.isoformat() if invoice.paid_date else None,
    }


def get_invoices(
    db: Session,
    vendor_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Get invoices with optional filters."""
    query = db.query(Invoice)

    if vendor_id:
        query = query.filter(Invoice.vendor_id == vendor_id)
    if status:
        query = query.filter(Invoice.status == status)

    invoices = query.order_by(Invoice.created_at.desc()).limit(limit).all()

    return [
        {
            "invoice_id": inv.id,
            "invoice_number": inv.invoice_number,
            "vendor_id": inv.vendor_id,
            "total_amount": inv.total_amount,
            "currency": inv.currency,
            "status": inv.status,
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
        }
        for inv in invoices
    ]
