"""Smart quote negotiation and counter-offer management."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import Session
from .. import models
from ..services import email_service
from ..crud import log_audit

# ─── Quote Negotiation ────────────────────────────────────────────────────

def make_counter_offer(
    db: Session,
    quote_id: int,
    counter_unit_price: float,
    counter_lead_time: int | None = None,
    notes: str = "",
    offered_by: str = "buyer",
) -> dict[str, Any]:
    """Make a counter-offer on a quote."""
    quote = db.query(models.RFQParsedQuote).filter(models.RFQParsedQuote.id == quote_id).first()
    if not quote:
        raise ValueError(f"Quote {quote_id} not found")

    # Log counter offer (no dedicated negotiation model yet)
    # Future: create QuoteNegotiation model for tracking rounds

    # Notify vendor
    vendor = db.query(models.Vendor).filter(models.Vendor.id == quote.vendor_id).first()
    if vendor and vendor.contact_email:
        try:
            price_diff = quote.unit_price - counter_unit_price if quote.unit_price else 0
            pct = (price_diff / quote.unit_price * 100) if quote.unit_price else 0
            subject = f"Counter-Offer for RFQ #{quote.broadcast_id} — Price Improvement"
            body = f"""Hi {vendor.name},

We're interested in your quote for RFQ #{quote.broadcast_id}. We'd like to negotiate:

Your Quote: ${quote.unit_price:.2f} per unit ({quote.lead_time_days} days delivery)
Our Counter: ${counter_unit_price:.2f} per unit ({counter_lead_time or quote.lead_time_days} days)
Your Savings Opportunity: {pct:.1f}%

Notes: {notes or "Please advise if you can meet this pricing."}

Can you match or improve on this counter-offer? Reply ASAP to stay in the running.

Best regards,
Procurement Team"""
            email_service.send_email(
                to=vendor.contact_email,
                subject=subject,
                html_body=body,
            )
        except Exception:
            pass

    log_audit(
        db,
        entity_type="quote_negotiation",
        entity_id=quote_id,
        action="counter_offer_made",
        detail=f"price=${counter_unit_price:.2f} lead_time={counter_lead_time} days",
        performed_by=offered_by,
    )

    vendor_name = vendor.name if vendor else "Unknown"
    return {
        "quote_id": quote_id,
        "counter_price": counter_unit_price,
        "original_price": quote.unit_price,
        "savings_pct": ((quote.unit_price - counter_unit_price) / quote.unit_price * 100) if quote.unit_price else 0,
        "vendor_name": vendor_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def accept_quote(
    db: Session,
    quote_id: int,
    accepted_by: str = "buyer",
) -> dict[str, Any]:
    """Accept a quote and prepare for PO generation."""
    quote = db.query(models.RFQParsedQuote).filter(models.RFQParsedQuote.id == quote_id).first()
    if not quote:
        raise ValueError(f"Quote {quote_id} not found")

    # Log acceptance (no status field on RFQParsedQuote)
    db.commit()

    # Notify vendor of acceptance
    vendor = db.query(models.Vendor).filter(models.Vendor.id == quote.vendor_id).first()
    if vendor and vendor.contact_email:
        try:
            email_service.send_email(
                to=vendor.contact_email,
                subject=f"Quote Accepted — RFQ #{quote.broadcast_id}",
                html_body=f"""Hi {vendor.name},

Great news! We've accepted your quote for RFQ #{quote.broadcast_id}.

Quote Details:
- Unit Price: ${quote.unit_price:.2f}
- Quantity: {quote.quantity}
- Total: ${(quote.unit_price or 0) * (quote.quantity or 1):.2f}
- Delivery: {quote.lead_time_days} days

Next Steps: We'll send a formal Purchase Order within 24 hours. Please confirm your warehouse address and preferred payment terms.

Best regards,
Procurement Team""",
            )
        except Exception:
            pass

    log_audit(
        db,
        entity_type="quote",
        entity_id=quote_id,
        action="quote_accepted",
        detail=f"vendor={vendor_name} price=${quote.unit_price}",
        performed_by=accepted_by,
    )

    vendor_name = vendor.name if vendor else "Unknown"
    return {
        "quote_id": quote_id,
        "status": "accepted",
        "vendor_name": vendor_name,
        "unit_price": quote.unit_price,
        "quantity": quote.quantity,
        "total_amount": (quote.unit_price or 0) * (quote.quantity or 1),
        "lead_time_days": quote.lead_time_days,
    }


def reject_quote(
    db: Session,
    quote_id: int,
    reason: str = "Selected another vendor",
    rejected_by: str = "buyer",
) -> dict[str, Any]:
    """Reject a quote and notify vendor."""
    quote = db.query(models.RFQParsedQuote).filter(models.RFQParsedQuote.id == quote_id).first()
    if not quote:
        raise ValueError(f"Quote {quote_id} not found")

    # Log rejection (no status field on RFQParsedQuote)
    db.commit()

    # Notify vendor
    vendor = db.query(models.Vendor).filter(models.Vendor.id == quote.vendor_id).first()
    if vendor and vendor.contact_email:
        try:
            email_service.send_email(
                to=vendor.contact_email,
                subject=f"Quote Status Update — RFQ #{quote.broadcast_id}",
                html_body=f"""Hi {vendor.name},

Thank you for your quote on RFQ #{quote.broadcast_id}. After careful consideration, we've decided to move forward with another vendor.

Reason: {reason}

We value your partnership and will consider you for future RFQs. Feel free to reach out if you'd like feedback on your quote.

Best regards,
Procurement Team""",
            )
        except Exception:
            pass

    log_audit(
        db,
        entity_type="quote",
        entity_id=quote_id,
        action="quote_rejected",
        detail=f"reason={reason}",
        performed_by=rejected_by,
    )

    vendor_name = vendor.name if vendor else "Unknown"
    return {
        "quote_id": quote_id,
        "status": "rejected",
        "vendor_name": vendor_name,
        "reason": reason,
    }


def generate_purchase_order(
    db: Session,
    quote_id: int,
    po_number: str | None = None,
    payment_terms: str = "Net 30",
    delivery_address: dict[str, str] | None = None,
    generated_by: str = "system",
) -> dict[str, Any]:
    """Generate a PO from an accepted quote."""
    quote = db.query(models.RFQParsedQuote).filter(models.RFQParsedQuote.id == quote_id).first()
    if not quote:
        raise ValueError(f"Quote {quote_id} not found")

    vendor = db.query(models.Vendor).filter(models.Vendor.id == quote.vendor_id).first()

    # Generate PO number if not provided
    if not po_number:
        po_number = f"PO-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{quote_id:04d}"

    # Prepare PO data
    po_data = {
        "po_number": po_number,
        "vendor_id": quote.vendor_id,
        "quote_id": quote_id,
        "amount": (quote.unit_price or 0) * (quote.quantity or 1),
        "currency": quote.currency or "USD",
        "payment_terms": payment_terms,
        "delivery_address": json.dumps(delivery_address or {}),
        "status": "generated",
    }

    db.commit()

    # Send PO to vendor
    if vendor and vendor.contact_email:
        try:
            email_service.send_email(
                to=vendor.contact_email,
                subject=f"Purchase Order {po_number} — RFQ #{quote.broadcast_id}",
                html_body=f"""Hi {vendor.name},

Please find attached or below your Purchase Order for RFQ #{quote.broadcast_id}.

PO Details:
- PO Number: {po_number}
- Quantity: {quote.quantity} units
- Unit Price: ${quote.unit_price:.2f}
- Total Amount: ${po_data["amount"]:.2f}
- Delivery Timeline: {quote.lead_time_days} days
- Payment Terms: {payment_terms}
- Delivery Address: {json.dumps(delivery_address or {}, indent=2)}

Please confirm receipt and your delivery schedule ASAP.

Best regards,
Procurement Team""",
            )
        except Exception:
            pass

    log_audit(
        db,
        entity_type="purchase_order",
        entity_id=quote_id,
        action="po_generated",
        detail=f"po_number={po_number} amount=${po_data['amount']:.2f}",
        performed_by=generated_by,
    )

    return {
        "po_number": po_number,
        "quote_id": quote_id,
        "vendor_name": vendor.name if vendor else "Unknown",
        "amount": po_data["amount"],
        "quantity": quote.quantity,
        "unit_price": quote.unit_price,
        "payment_terms": payment_terms,
        "delivery_days": quote.lead_time_days,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
