"""Payments router — Stripe-compatible payment flow."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Any

from ..database import get_db
from ..services import payment_gateway as pg

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


class PaymentIntentRequest(BaseModel):
    order_id: int
    gateway: str = "stripe"
    amount: float | None = None
    currency: str = "USD"
    created_by: str = "checkout"


class ConfirmPaymentRequest(BaseModel):
    payment_method: str = "card"
    confirmed_by: str = "customer"


class RefundRequest(BaseModel):
    amount: float | None = None
    reason: str = "customer_request"
    refunded_by: str = "support"


@router.post("/intent", status_code=status.HTTP_201_CREATED)
def create_payment_intent(body: PaymentIntentRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Create a payment intent/order via the selected gateway (Stripe / Razorpay / mock)."""
    try:
        return pg.create_payment_intent(
            db,
            order_id=body.order_id,
            gateway=body.gateway,
            amount=body.amount,
            currency=body.currency,
            created_by=body.created_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Payment gateway error: {exc}") from exc


@router.post("/{transaction_id}/confirm")
def confirm_payment(
    transaction_id: int,
    body: ConfirmPaymentRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Confirm a pending payment transaction."""
    try:
        return pg.confirm_payment(
            db,
            transaction_id=transaction_id,
            payment_method=body.payment_method,
            confirmed_by=body.confirmed_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{transaction_id}/refund")
def refund_payment(
    transaction_id: int,
    body: RefundRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Issue a full or partial refund on a confirmed transaction."""
    try:
        return pg.refund_payment(
            db,
            transaction_id=transaction_id,
            amount=body.amount,
            reason=body.reason,
            refunded_by=body.refunded_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/webhook/stripe")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
    stripe_signature: str = Header(default="", alias="stripe-signature"),
) -> dict[str, Any]:
    """Stripe webhook endpoint — verifies signature and processes events."""
    payload = await request.body()
    event = pg.verify_stripe_webhook(payload, stripe_signature)
    if event is None:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    return pg.handle_webhook_event(db, event)


@router.post("/webhook/razorpay")
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Razorpay webhook endpoint."""
    try:
        event = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    return pg.handle_webhook_event(db, event)


@router.get("/gateways")
def list_gateways() -> dict[str, Any]:
    """List available payment gateways and their configuration status."""
    return {
        "gateways": [
            {
                "code": "stripe",
                "name": "Stripe",
                "configured": bool(pg.STRIPE_SECRET_KEY),
                "currencies": ["USD", "EUR", "GBP", "INR", "AUD", "CAD"],
                "test_mode": pg.STRIPE_SECRET_KEY.startswith("sk_test_") if pg.STRIPE_SECRET_KEY else True,
            },
            {
                "code": "razorpay",
                "name": "Razorpay",
                "configured": bool(pg.RAZORPAY_KEY_ID),
                "currencies": ["INR", "USD"],
                "test_mode": not bool(pg.RAZORPAY_KEY_ID),
            },
            {
                "code": "mock",
                "name": "Mock (Development)",
                "configured": True,
                "currencies": ["USD", "EUR", "GBP", "INR"],
                "test_mode": True,
            },
        ],
        "default_gateway": pg.DEFAULT_GATEWAY,
    }
