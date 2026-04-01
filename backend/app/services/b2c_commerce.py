from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit

_POINT_VALUE = 0.1


def register_payment_gateway(
    db: Session,
    *,
    gateway_code: str,
    display_name: str,
    supported_currencies: list[str] | None = None,
    configured_by: str = 'finance',
) -> models.PaymentGatewayConfig:
    code = str(gateway_code or '').strip().lower()[:64]
    if not code:
        raise ValueError('gateway_code is required')

    row = db.query(models.PaymentGatewayConfig).filter(models.PaymentGatewayConfig.gateway_code == code).first()
    if row is None:
        row = models.PaymentGatewayConfig(
            gateway_code=code,
            display_name=str(display_name or code).strip()[:128] or code,
            status='active',
            supported_currencies=[str(c).strip().upper()[:8] for c in (supported_currencies or ['USD']) if str(c).strip()],
            configured_by=str(configured_by or 'finance').strip()[:128] or 'finance',
        )
    else:
        row.display_name = str(display_name or row.display_name).strip()[:128] or row.display_name
        row.supported_currencies = [str(c).strip().upper()[:8] for c in (supported_currencies or row.supported_currencies or ['USD']) if str(c).strip()]
        row.status = 'active'

    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_payment_gateways(db: Session, *, status: str | None = 'active', limit: int = 200) -> list[models.PaymentGatewayConfig]:
    query = db.query(models.PaymentGatewayConfig)
    if status:
        query = query.filter(models.PaymentGatewayConfig.status == str(status).strip().lower())
    return query.order_by(models.PaymentGatewayConfig.gateway_code.asc()).limit(max(1, min(int(limit), 500))).all()


def create_payment_intent(
    db: Session,
    *,
    order_id: int,
    gateway_code: str,
    amount: float | None = None,
    created_by: str = 'checkout',
) -> models.PaymentTransaction:
    order = db.query(models.B2COrder).filter(models.B2COrder.id == int(order_id)).first()
    if order is None:
        raise ValueError('Order not found')

    gateway = db.query(models.PaymentGatewayConfig).filter(
        models.PaymentGatewayConfig.gateway_code == str(gateway_code).strip().lower(),
        models.PaymentGatewayConfig.status == 'active',
    ).first()
    if gateway is None:
        raise ValueError('Payment gateway not found or inactive')

    txn = models.PaymentTransaction(
        order_id=order.id,
        gateway_code=gateway.gateway_code,
        transaction_type='payment_intent',
        amount=round(float(amount if amount is not None else order.total_amount or 0.0), 2),
        currency=str(order.currency or 'USD').strip().upper()[:8],
        status='created',
        external_payment_id=f"{gateway.gateway_code}-pi-{order.id}-{int(datetime.now(timezone.utc).timestamp())}",
        created_by=str(created_by or 'checkout').strip()[:128] or 'checkout',
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    log_audit(
        db,
        'payment',
        txn.id,
        'payment_intent_created',
        f'order_id={order.id} gateway={txn.gateway_code} amount={txn.amount} {txn.currency}',
        performed_by=txn.created_by,
    )
    return txn


def confirm_payment(
    db: Session,
    *,
    transaction_id: int,
    status: str,
    external_reference: str | None = None,
    performed_by: str = 'payment-webhook',
) -> models.PaymentTransaction:
    txn = db.query(models.PaymentTransaction).filter(models.PaymentTransaction.id == int(transaction_id)).first()
    if txn is None:
        raise ValueError('Payment transaction not found')

    normalized = str(status or '').strip().lower()
    if normalized not in {'authorized', 'captured', 'failed', 'cancelled'}:
        raise ValueError('Unsupported payment status')

    txn.status = normalized
    txn.external_reference = str(external_reference or '').strip()[:256] or txn.external_reference
    if normalized in {'authorized', 'captured'}:
        txn.paid_at = datetime.now(timezone.utc)
    db.add(txn)

    order = db.query(models.B2COrder).filter(models.B2COrder.id == int(txn.order_id)).first()
    if order is not None and normalized == 'captured':
        order.status = 'confirmed'
        db.add(order)

    db.commit()
    db.refresh(txn)

    log_audit(
        db,
        'payment',
        txn.id,
        'payment_status_updated',
        f'status={txn.status} order_id={txn.order_id}',
        performed_by=str(performed_by or 'payment-webhook').strip()[:128] or 'payment-webhook',
    )
    return txn


def list_order_payments(db: Session, *, order_id: int, limit: int = 200) -> list[models.PaymentTransaction]:
    return (
        db.query(models.PaymentTransaction)
        .filter(models.PaymentTransaction.order_id == int(order_id))
        .order_by(models.PaymentTransaction.created_at.desc(), models.PaymentTransaction.id.desc())
        .limit(max(1, min(int(limit), 500)))
        .all()
    )


def create_coupon(
    db: Session,
    *,
    code: str,
    promotion_type: str,
    discount_value: float,
    min_order_amount: float = 0.0,
    max_discount_amount: float | None = None,
    usage_limit: int | None = None,
    created_by: str = 'marketing',
) -> models.CouponPromotion:
    coupon_code = str(code or '').strip().upper()[:64]
    if not coupon_code:
        raise ValueError('Coupon code is required')

    promo_type = str(promotion_type or '').strip().lower()
    if promo_type not in {'percent', 'fixed'}:
        raise ValueError('promotion_type must be percent or fixed')

    row = db.query(models.CouponPromotion).filter(models.CouponPromotion.code == coupon_code).first()
    if row is None:
        row = models.CouponPromotion(code=coupon_code)

    row.promotion_type = promo_type
    row.discount_value = float(discount_value or 0.0)
    row.min_order_amount = float(min_order_amount or 0.0)
    row.max_discount_amount = float(max_discount_amount) if max_discount_amount is not None else None
    row.usage_limit = int(usage_limit) if usage_limit is not None else None
    row.status = 'active'
    row.created_by = str(created_by or 'marketing').strip()[:128] or 'marketing'

    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def ensure_loyalty_account(
    db: Session,
    *,
    customer_id: int | None,
    lead_id: int | None,
) -> models.LoyaltyAccount:
    query = db.query(models.LoyaltyAccount)
    if customer_id is not None:
        query = query.filter(models.LoyaltyAccount.customer_id == int(customer_id))
    elif lead_id is not None:
        query = query.filter(models.LoyaltyAccount.lead_id == int(lead_id))
    else:
        raise ValueError('customer_id or lead_id required')

    row = query.first()
    if row is not None:
        return row

    row = models.LoyaltyAccount(
        customer_id=int(customer_id) if customer_id is not None else None,
        lead_id=int(lead_id) if lead_id is not None else None,
        points_balance=0,
        tier='standard',
        status='active',
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def apply_coupon_and_loyalty(
    db: Session,
    *,
    cart: models.B2CCart,
    subtotal: float,
    coupon_code: str | None,
    loyalty_points_to_redeem: int,
    performed_by: str,
) -> tuple[float, float, float, str | None, int]:
    subtotal = round(float(subtotal or 0.0), 2)
    coupon_discount = 0.0
    applied_coupon_code: str | None = None

    if coupon_code:
        code = str(coupon_code).strip().upper()[:64]
        promo = db.query(models.CouponPromotion).filter(
            models.CouponPromotion.code == code,
            models.CouponPromotion.status == 'active',
        ).first()
        if promo is None:
            raise ValueError('Coupon not found or inactive')
        if promo.usage_limit is not None and int(promo.usage_count or 0) >= int(promo.usage_limit):
            raise ValueError('Coupon usage limit reached')
        if promo.expires_at is not None and promo.expires_at <= datetime.now(timezone.utc):
            raise ValueError('Coupon has expired')
        if subtotal < float(promo.min_order_amount or 0.0):
            raise ValueError('Coupon minimum order amount not met')

        if promo.promotion_type == 'percent':
            coupon_discount = subtotal * (float(promo.discount_value or 0.0) / 100.0)
        else:
            coupon_discount = float(promo.discount_value or 0.0)

        if promo.max_discount_amount is not None:
            coupon_discount = min(coupon_discount, float(promo.max_discount_amount))
        coupon_discount = round(max(0.0, min(coupon_discount, subtotal)), 2)
        applied_coupon_code = code

        promo.usage_count = int(promo.usage_count or 0) + 1
        db.add(promo)

        redemption = models.CouponRedemption(
            coupon_id=promo.id,
            cart_id=cart.id,
            lead_id=cart.lead_id,
            customer_id=cart.customer_id,
            discount_amount=coupon_discount,
            status='applied',
        )
        db.add(redemption)

    remaining_after_coupon = round(max(0.0, subtotal - coupon_discount), 2)
    loyalty_discount = 0.0
    points_redeemed = 0

    if int(loyalty_points_to_redeem or 0) > 0:
        account = ensure_loyalty_account(db, customer_id=cart.customer_id, lead_id=cart.lead_id)
        points_redeemed = min(int(loyalty_points_to_redeem), int(account.points_balance or 0))
        loyalty_discount = round(min(remaining_after_coupon, points_redeemed * _POINT_VALUE), 2)
        if points_redeemed > 0:
            account.points_balance = int(account.points_balance or 0) - points_redeemed
            db.add(account)
            db.add(
                models.LoyaltyLedgerEntry(
                    loyalty_account_id=account.id,
                    entry_type='redeem',
                    points=points_redeemed,
                    source_type='cart',
                    source_id=cart.id,
                    note='Redeemed at checkout',
                    created_by=str(performed_by or 'commerce').strip()[:128] or 'commerce',
                )
            )

    total = round(max(0.0, subtotal - coupon_discount - loyalty_discount), 2)

    cart.coupon_code = applied_coupon_code
    cart.coupon_discount_amount = coupon_discount
    cart.loyalty_discount_amount = loyalty_discount
    db.add(cart)
    db.commit()

    log_audit(
        db,
        'cart',
        cart.id,
        'checkout_discounts_applied',
        f'coupon={applied_coupon_code} coupon_discount={coupon_discount} loyalty_discount={loyalty_discount}',
        performed_by=str(performed_by or 'commerce').strip()[:128] or 'commerce',
    )
    return total, coupon_discount, loyalty_discount, applied_coupon_code, points_redeemed


def award_loyalty_points_for_order(
    db: Session,
    *,
    order: models.B2COrder,
    performed_by: str,
) -> int:
    if order.customer_id is None and order.lead_id is None:
        return 0

    account = ensure_loyalty_account(db, customer_id=order.customer_id, lead_id=order.lead_id)
    points = max(0, int(float(order.total_amount or 0.0) // 10))
    if points <= 0:
        return 0

    account.points_balance = int(account.points_balance or 0) + points
    db.add(account)
    db.add(
        models.LoyaltyLedgerEntry(
            loyalty_account_id=account.id,
            entry_type='earn',
            points=points,
            source_type='order',
            source_id=order.id,
            note='Earned from checkout',
            created_by=str(performed_by or 'commerce').strip()[:128] or 'commerce',
        )
    )
    db.commit()

    log_audit(
        db,
        'loyalty',
        account.id,
        'loyalty_points_awarded',
        f'order_id={order.id} points={points}',
        performed_by=str(performed_by or 'commerce').strip()[:128] or 'commerce',
    )
    return points
