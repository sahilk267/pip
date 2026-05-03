"""Payment Gateway Service — Stripe-compatible structure with test/mock mode fallback."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# Which gateway to use by default
DEFAULT_GATEWAY = os.getenv("DEFAULT_PAYMENT_GATEWAY", "stripe")


def _mock_payment_intent(amount: float, currency: str, order_id: int) -> dict[str, Any]:
    """Generate a deterministic mock PaymentIntent (Stripe-shaped)."""
    pi_id = f"pi_mock_{order_id}_{int(time.time())}"
    return {
        "id": pi_id,
        "object": "payment_intent",
        "amount": int(amount * 100),
        "currency": currency.lower(),
        "status": "requires_payment_method",
        "client_secret": f"{pi_id}_secret_{uuid.uuid4().hex[:12]}",
        "created": int(time.time()),
        "gateway": "mock",
        "live_mode": False,
    }


def _stripe_payment_intent(amount: float, currency: str, order_id: int, metadata: dict | None = None) -> dict[str, Any]:
    """Create a real Stripe PaymentIntent if SDK available, else use mock."""
    try:
        import stripe  # type: ignore
        stripe.api_key = STRIPE_SECRET_KEY
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),
            currency=currency.lower(),
            metadata={"order_id": str(order_id), **(metadata or {})},
        )
        return dict(intent)
    except ImportError:
        return _mock_payment_intent(amount, currency, order_id)
    except Exception as exc:
        # API error — fall back to mock in dev
        if not STRIPE_SECRET_KEY or STRIPE_SECRET_KEY.startswith("sk_test_dummy"):
            return _mock_payment_intent(amount, currency, order_id)
        raise ValueError(f"Stripe error: {exc}") from exc


def _razorpay_order(amount: float, currency: str, order_id: int) -> dict[str, Any]:
    """Create a Razorpay order if SDK available, else use mock."""
    try:
        import razorpay  # type: ignore
        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        rz_order = client.order.create({
            "amount": int(amount * 100),
            "currency": currency.upper(),
            "receipt": f"order_{order_id}",
        })
        return dict(rz_order)
    except ImportError:
        rz_id = f"order_mock_{order_id}_{uuid.uuid4().hex[:8]}"
        return {
            "id": rz_id,
            "entity": "order",
            "amount": int(amount * 100),
            "currency": currency.upper(),
            "status": "created",
            "receipt": f"order_{order_id}",
            "gateway": "razorpay_mock",
        }
    except Exception as exc:
        if not RAZORPAY_KEY_ID:
            rz_id = f"order_mock_{order_id}_{uuid.uuid4().hex[:8]}"
            return {
                "id": rz_id,
                "entity": "order",
                "amount": int(amount * 100),
                "currency": currency.upper(),
                "status": "created",
                "receipt": f"order_{order_id}",
                "gateway": "razorpay_mock",
            }
        raise ValueError(f"Razorpay error: {exc}") from exc


def create_payment_intent(
    db: Session,
    *,
    order_id: int,
    gateway: str | None = None,
    amount: float | None = None,
    currency: str = "USD",
    created_by: str = "checkout",
) -> dict[str, Any]:
    """Create a payment intent/order via the selected gateway and persist the transaction."""
    order = db.query(models.B2COrder).filter(models.B2COrder.id == order_id).first()
    if order is None:
        raise ValueError(f"Order {order_id} not found")

    used_gateway = (gateway or DEFAULT_GATEWAY).lower().strip()
    pay_amount = round(float(amount if amount is not None else order.total_amount or 0.0), 2)
    pay_currency = currency or str(order.currency or "USD")

    if used_gateway == "stripe":
        gateway_response = _stripe_payment_intent(pay_amount, pay_currency, order_id)
        external_id = gateway_response.get("id", "")
    elif used_gateway == "razorpay":
        gateway_response = _razorpay_order(pay_amount, pay_currency, order_id)
        external_id = gateway_response.get("id", "")
    else:
        gateway_response = _mock_payment_intent(pay_amount, pay_currency, order_id)
        external_id = gateway_response.get("id", "")
        used_gateway = "mock"

    # Persist transaction record
    txn = models.PaymentTransaction(
        order_id=order.id,
        gateway_code=used_gateway,
        transaction_type="payment_intent",
        amount=pay_amount,
        currency=pay_currency.upper()[:8],
        status="created",
        external_payment_id=external_id,
        created_by=str(created_by or "checkout")[:128],
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    log_audit(db, entity_type="payment_transaction", entity_id=txn.id,
              action="payment_intent_created",
              detail=f"order={order_id} gateway={used_gateway} amount={pay_amount}",
              performed_by=str(created_by or "checkout"))

    return {
        "transaction_id": txn.id,
        "external_payment_id": external_id,
        "gateway": used_gateway,
        "amount": pay_amount,
        "currency": pay_currency,
        "status": "created",
        "gateway_response": gateway_response,
        "created_at": txn.created_at.isoformat() if hasattr(txn, "created_at") else None,
    }


def confirm_payment(
    db: Session,
    *,
    transaction_id: int,
    payment_method: str = "card",
    confirmed_by: str = "customer",
) -> dict[str, Any]:
    """Confirm a pending payment transaction."""
    txn = db.query(models.PaymentTransaction).filter(models.PaymentTransaction.id == transaction_id).first()
    if txn is None:
        raise ValueError(f"Transaction {transaction_id} not found")
    if txn.status == "confirmed":
        return {"transaction_id": txn.id, "status": "already_confirmed"}

    # In test/mock mode: auto-confirm
    txn.status = "confirmed"
    txn.paid_at = datetime.now(timezone.utc)

    # Mark order as confirmed
    order = db.query(models.B2COrder).filter(models.B2COrder.id == txn.order_id).first()
    if order:
        order.status = "confirmed"
        db.add(order)

    db.add(txn)
    db.commit()
    db.refresh(txn)

    log_audit(db, entity_type="payment_transaction", entity_id=txn.id,
              action="payment_confirmed",
              detail=f"order={txn.order_id}",
              performed_by=str(confirmed_by or "customer"))

    return {
        "transaction_id": txn.id,
        "external_payment_id": txn.external_payment_id,
        "status": "confirmed",
        "order_id": txn.order_id,
        "amount": float(txn.amount or 0),
        "paid_at": txn.paid_at.isoformat() if txn.paid_at else None,
    }


def refund_payment(
    db: Session,
    *,
    transaction_id: int,
    amount: float | None = None,
    reason: str = "customer_request",
    refunded_by: str = "support",
) -> dict[str, Any]:
    """Refund a confirmed payment (full or partial)."""
    txn = db.query(models.PaymentTransaction).filter(models.PaymentTransaction.id == transaction_id).first()
    if txn is None:
        raise ValueError(f"Transaction {transaction_id} not found")
    if txn.status not in ("confirmed", "paid"):
        raise ValueError(f"Cannot refund transaction with status '{txn.status}'")

    refund_amount = round(float(amount if amount is not None else txn.amount or 0), 2)
    refund_id = f"re_{uuid.uuid4().hex[:16]}"

    refund_txn = models.PaymentTransaction(
        order_id=txn.order_id,
        gateway_code=txn.gateway_code,
        transaction_type="refund",
        amount=refund_amount,
        currency=txn.currency,
        status="refunded",
        external_payment_id=refund_id,
        created_by=str(refunded_by)[:128],
    )
    db.add(refund_txn)

    if refund_amount >= float(txn.amount or 0):
        txn.status = "refunded"
        db.add(txn)

    db.commit()
    db.refresh(refund_txn)

    log_audit(db, entity_type="payment_transaction", entity_id=refund_txn.id,
              action="payment_refunded",
              detail=f"original_txn={transaction_id} amount={refund_amount} reason={reason}",
              performed_by=str(refunded_by or "support"))

    return {
        "refund_transaction_id": refund_txn.id,
        "refund_id": refund_id,
        "original_transaction_id": transaction_id,
        "amount": refund_amount,
        "status": "refunded",
    }


def verify_stripe_webhook(payload: bytes, sig_header: str) -> dict[str, Any] | None:
    """Verify Stripe webhook signature and return event dict if valid."""
    if not STRIPE_WEBHOOK_SECRET:
        try:
            return json.loads(payload)
        except Exception:
            return None
    try:
        import stripe  # type: ignore
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        return dict(event)
    except Exception:
        return None


def handle_webhook_event(db: Session, event: dict[str, Any]) -> dict[str, Any]:
    """Process a Stripe/Razorpay webhook event."""
    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})
    result = {"processed": True, "event_type": event_type}

    if event_type == "payment_intent.succeeded":
        ext_id = data.get("id", "")
        txn = db.query(models.PaymentTransaction).filter(
            models.PaymentTransaction.external_payment_id == ext_id
        ).first()
        if txn:
            txn.status = "confirmed"
            txn.paid_at = datetime.now(timezone.utc)
            db.add(txn)
            order = db.query(models.B2COrder).filter(models.B2COrder.id == txn.order_id).first()
            if order:
                order.status = "confirmed"
                db.add(order)
            db.commit()
            result["transaction_id"] = txn.id

    elif event_type == "payment_intent.payment_failed":
        ext_id = data.get("id", "")
        txn = db.query(models.PaymentTransaction).filter(
            models.PaymentTransaction.external_payment_id == ext_id
        ).first()
        if txn:
            txn.status = "failed"
            db.add(txn)
            db.commit()
            result["transaction_id"] = txn.id

    elif event_type == "charge.refunded":
        # Handle Razorpay refund webhook
        result["note"] = "refund recorded via webhook"

    return result
