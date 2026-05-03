"""Intelligent vendor engagement bot — auto-replies and escalation rules."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import Session
from .. import models
from ..services import email_service
from ..crud import log_audit

# ─── Auto-Reply Templates ────────────────────────────────────────────────────

TEMPLATES = {
    "rfq_received": {
        "subject": "RFQ #{rfq_id} Received — {product_name}",
        "body": """Hi {vendor_name},

Thank you for receiving our RFQ #{rfq_id} for {product_name}.

Details:
- Quantity: {quantity}
- Target Price: {currency} {target_price}
- Delivery Deadline: {deadline}
- Notes: {notes}

Please reply with your best quote and delivery timeline. We're actively comparing bids and will respond to competitive offers within 24 hours.

Best regards,
Procurement Team""",
    },
    "quote_acknowledged": {
        "subject": "Quote Acknowledged — {vendor_name} ({rfq_id})",
        "body": """Hi {vendor_name},

Thank you for your quote submission for RFQ #{rfq_id}. We've received your offer at {unit_price} {currency} per unit with {lead_time} day delivery.

Status: Under review with {competitor_count} other vendors.

We'll notify you of our decision within 48 hours. If you'd like to improve your quote, please respond ASAP.

Best regards,
Procurement Team""",
    },
    "winner_notification": {
        "subject": "Order Award — RFQ #{rfq_id} {product_name}",
        "body": """Hi {vendor_name},

Congratulations! We've selected your quote for RFQ #{rfq_id} ({product_name}).

Order Details:
- Unit Price: {currency} {unit_price}
- Quantity: {quantity}
- Total: {currency} {total_amount}
- Delivery Deadline: {deadline}

Next steps: We'll send a formal PO within 24 hours. Please confirm your availability and provide shipping details.

Best regards,
Procurement Team""",
    },
    "escalation_reminder": {
        "subject": "Friendly Reminder — Your Quote for RFQ #{rfq_id}",
        "body": """Hi {vendor_name},

Just checking in on your quote for RFQ #{rfq_id} ({product_name}).

Your response would help us move forward. Current best offer: {best_price} {currency} per unit.

Reply with your competitive quote to stay in the running.

Best regards,
Procurement Team""",
    },
}

# ─── Escalation Rules ─────────────────────────────────────────────────────

ESCALATION_RULES = {
    "no_response_24h": {
        "trigger": "quote_not_received_after_hours",
        "hours": 24,
        "action": "send_reminder",
        "template": "escalation_reminder",
    },
    "late_response_48h": {
        "trigger": "quote_not_received_after_hours",
        "hours": 48,
        "action": "reassign_to_backup",
        "template": None,
    },
    "winner_low_confidence": {
        "trigger": "winning_quote_confidence_below",
        "confidence_threshold": 0.75,
        "action": "request_verification",
        "template": "escalation_reminder",
    },
}

# ─── Functions ────────────────────────────────────────────────────────────

def send_auto_reply(
    db: Session,
    rfq_id: int,
    vendor_id: int,
    reply_type: str = "rfq_received",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send auto-reply to vendor with templated message."""
    rfq = db.query(models.RFQBroadcast).filter(models.RFQBroadcast.id == rfq_id).first()
    if not rfq:
        raise ValueError(f"RFQ {rfq_id} not found")

    vendor = db.query(models.Vendor).filter(models.Vendor.id == vendor_id).first()
    if not vendor or not vendor.contact_email:
        raise ValueError(f"Vendor {vendor_id} not found or has no email")

    tpl = TEMPLATES.get(reply_type)
    if not tpl:
        raise ValueError(f"Unknown reply template: {reply_type}")

    # Parse RFQ message for context
    ctx = context or {}
    if rfq.message and not ctx:
        lines = rfq.message.split('\n')
        for line in lines:
            if 'Product:' in line:
                ctx['product_name'] = line.split('Product:')[1].strip()
            elif 'Quantity:' in line:
                ctx['quantity'] = line.split('Quantity:')[1].strip()
            elif 'Target Price:' in line:
                ctx['target_price'] = line.split('Target Price:')[1].strip()
            elif 'Delivery by:' in line:
                ctx['deadline'] = line.split('Delivery by:')[1].strip()

    # Format template
    ctx.setdefault('rfq_id', rfq_id)
    ctx.setdefault('vendor_name', vendor.name)
    ctx.setdefault('currency', 'USD')
    ctx.setdefault('product_name', 'Inquiry')
    ctx.setdefault('quantity', '—')
    ctx.setdefault('target_price', '—')
    ctx.setdefault('deadline', '—')
    ctx.setdefault('notes', '—')

    subject = tpl['subject'].format(**ctx)
    body = tpl['body'].format(**ctx)

    # Send email (non-blocking best-effort)
    try:
        email_service.send_email(
            to=vendor.contact_email,
            subject=subject,
            html_body=body,
        )
    except Exception as e:
        pass  # Log but don't fail

    # Record bot action
    log_audit(
        db,
        entity_type="rfq_vendor_interaction",
        entity_id=rfq_id,
        action=f"auto_reply_{reply_type}",
        detail=f"to {vendor.name} ({vendor.contact_email})",
        performed_by="vendor_bot",
    )

    return {
        "rfq_id": rfq_id,
        "vendor_id": vendor_id,
        "vendor_name": vendor.name,
        "reply_type": reply_type,
        "subject": subject,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }


def check_escalations(db: Session, rfq_id: int) -> list[dict[str, Any]]:
    """Check and apply escalation rules for RFQ."""
    rfq = db.query(models.RFQBroadcast).filter(models.RFQBroadcast.id == rfq_id).first()
    if not rfq:
        return []

    escalations = []
    now = datetime.now(timezone.utc)

    # Check 24h no-response rule
    created_ago = (now - (rfq.created_at or now)).total_seconds() / 3600
    if 24 <= created_ago < 48:
        # Send reminders to vendors who haven't quoted
        quotes = db.query(models.Quote).filter(models.Quote.broadcast_id == rfq_id).all()
        quoted_vendors = {q.vendor_id for q in quotes}

        # Find vendors who received the RFQ but haven't quoted
        attempts = db.query(models.RFQDeliveryAttempt).filter(
            models.RFQDeliveryAttempt.broadcast_id == rfq_id
        ).all()
        attempted_vendors = {a.vendor_id for a in attempts}

        for vendor_id in attempted_vendors:
            if vendor_id not in quoted_vendors:
                try:
                    send_auto_reply(db, rfq_id, vendor_id, "escalation_reminder")
                    escalations.append({
                        "rule": "no_response_24h",
                        "vendor_id": vendor_id,
                        "action": "reminder_sent",
                    })
                except Exception:
                    pass

    return escalations


def record_vendor_interaction(
    db: Session,
    rfq_id: int,
    vendor_id: int,
    interaction_type: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record vendor interaction for engagement tracking."""
    log_audit(
        db,
        entity_type="rfq_vendor_interaction",
        entity_id=rfq_id,
        action=interaction_type,
        detail=json.dumps({"vendor_id": vendor_id, **(details or {})}),
        performed_by="vendor_bot",
    )

    return {
        "rfq_id": rfq_id,
        "vendor_id": vendor_id,
        "interaction_type": interaction_type,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
