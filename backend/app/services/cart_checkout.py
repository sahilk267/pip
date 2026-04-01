from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit
from .b2c_commerce import apply_coupon_and_loyalty, award_loyalty_points_for_order
from .orders import create_b2c_order


def add_item_to_cart(
    db: Session,
    *,
    customer_id: int | None,
    lead_id: int | None,
    cart_token: str | None,
    currency: str,
    sku: str,
    name: str,
    unit_price: float,
    quantity: int,
    item_metadata: dict,
    performed_by: str = 'commerce',
) -> tuple[models.B2CCart, list[models.B2CCartItem]]:
    cart = _resolve_or_create_cart(
        db,
        customer_id=customer_id,
        lead_id=lead_id,
        cart_token=cart_token,
        currency=currency,
    )
    if cart.status != 'active':
        raise ValueError('Cart is not active')

    normalized_sku = str(sku or '').strip().upper()[:128]
    row = (
        db.query(models.B2CCartItem)
        .filter(models.B2CCartItem.cart_id == cart.id, models.B2CCartItem.sku == normalized_sku)
        .first()
    )
    if row is None:
        row = models.B2CCartItem(
            cart_id=cart.id,
            sku=normalized_sku,
            name=str(name or '').strip()[:256] or normalized_sku,
            unit_price=float(unit_price or 0.0),
            quantity=int(quantity or 1),
            item_metadata=item_metadata or {},
        )
    else:
        row.name = str(name or row.name).strip()[:256] or row.name
        row.unit_price = float(unit_price or row.unit_price or 0.0)
        row.quantity = int(row.quantity or 0) + int(quantity or 1)
        row.item_metadata = item_metadata or row.item_metadata or {}

    db.add(row)
    db.commit()

    _recompute_cart_totals(db, cart)
    items = _list_items(db, cart.id)

    log_audit(
        db,
        'cart',
        cart.id,
        'cart_item_added',
        f'sku={normalized_sku} qty={quantity}',
        performed_by=performed_by,
    )
    return cart, items


def get_active_cart(
    db: Session,
    *,
    customer_id: int | None,
    lead_id: int | None,
    cart_token: str | None,
) -> tuple[models.B2CCart, list[models.B2CCartItem]]:
    cart = _resolve_or_create_cart(
        db,
        customer_id=customer_id,
        lead_id=lead_id,
        cart_token=cart_token,
        currency='USD',
    )
    items = _list_items(db, cart.id)
    return cart, items


def remove_item_from_cart(
    db: Session,
    *,
    customer_id: int | None,
    lead_id: int | None,
    cart_token: str | None,
    sku: str,
    performed_by: str = 'commerce',
) -> tuple[models.B2CCart, list[models.B2CCartItem]]:
    cart = _resolve_or_create_cart(
        db,
        customer_id=customer_id,
        lead_id=lead_id,
        cart_token=cart_token,
        currency='USD',
    )
    if cart.status != 'active':
        raise ValueError('Cart is not active')

    normalized_sku = str(sku or '').strip().upper()[:128]
    row = (
        db.query(models.B2CCartItem)
        .filter(models.B2CCartItem.cart_id == cart.id, models.B2CCartItem.sku == normalized_sku)
        .first()
    )
    if row is None:
        raise ValueError('Cart item not found')

    db.delete(row)
    db.commit()

    _recompute_cart_totals(db, cart)
    items = _list_items(db, cart.id)

    log_audit(
        db,
        'cart',
        cart.id,
        'cart_item_removed',
        f'sku={normalized_sku}',
        performed_by=performed_by,
    )
    return cart, items


def checkout_cart(
    db: Session,
    *,
    customer_id: int | None,
    lead_id: int | None,
    cart_token: str | None,
    shipping_address: dict,
    coupon_code: str | None = None,
    loyalty_points_to_redeem: int = 0,
    performed_by: str = 'commerce',
) -> tuple[models.B2CCart, list[models.B2CCartItem], models.B2COrder]:
    cart = _resolve_or_create_cart(
        db,
        customer_id=customer_id,
        lead_id=lead_id,
        cart_token=cart_token,
        currency='USD',
    )
    if cart.status != 'active':
        raise ValueError('Cart is not active')

    items = _list_items(db, cart.id)
    if not items:
        raise ValueError('Cart has no items')

    order_payload = [
        {
            'sku': row.sku,
            'name': row.name,
            'unit_price': float(row.unit_price or 0.0),
            'quantity': int(row.quantity or 0),
            'line_total': round(float(row.unit_price or 0.0) * int(row.quantity or 0), 2),
            'metadata': row.item_metadata or {},
        }
        for row in items
    ]
    subtotal = sum(float(item['line_total']) for item in order_payload)
    total_amount, coupon_discount, loyalty_discount, applied_coupon_code, points_redeemed = apply_coupon_and_loyalty(
        db,
        cart=cart,
        subtotal=subtotal,
        coupon_code=coupon_code,
        loyalty_points_to_redeem=loyalty_points_to_redeem,
        performed_by=performed_by,
    )

    order = create_b2c_order(
        db,
        customer_id=cart.customer_id,
        lead_id=cart.lead_id,
        currency=cart.currency,
        total_amount=total_amount,
        order_items=order_payload,
        source_channel='checkout',
        shipping_address=shipping_address or {},
        enable_dedup=False,
        performed_by=performed_by,
    )
    order.external_order_id = order.external_order_id or f'cart-{cart.id}-order-{order.id}'
    metadata = list(order.order_items or [])
    metadata.append(
        {
            'checkout_adjustments': {
                'subtotal': round(float(subtotal), 2),
                'coupon_code': applied_coupon_code,
                'coupon_discount': round(float(coupon_discount), 2),
                'loyalty_discount': round(float(loyalty_discount), 2),
                'loyalty_points_redeemed': int(points_redeemed),
            }
        }
    )
    order.order_items = metadata
    db.add(order)

    cart.status = 'checked_out'
    cart.checked_out_at = datetime.now(timezone.utc)
    cart.total_amount = float(total_amount)
    db.add(cart)
    db.commit()
    db.refresh(cart)
    db.refresh(order)

    awarded_points = award_loyalty_points_for_order(db, order=order, performed_by=performed_by)

    log_audit(
        db,
        'cart',
        cart.id,
        'cart_checked_out',
        (
            f'order_id={order.id} subtotal={round(float(subtotal), 2)} total_amount={total_amount} '
            f'coupon_discount={coupon_discount} loyalty_discount={loyalty_discount} points_awarded={awarded_points}'
        ),
        performed_by=performed_by,
    )
    return cart, items, order


def _resolve_or_create_cart(
    db: Session,
    *,
    customer_id: int | None,
    lead_id: int | None,
    cart_token: str | None,
    currency: str,
) -> models.B2CCart:
    normalized_token = str(cart_token or '').strip()[:128] or None

    query = db.query(models.B2CCart).filter(models.B2CCart.status == 'active')
    if customer_id is not None:
        query = query.filter(models.B2CCart.customer_id == int(customer_id))
    elif lead_id is not None:
        query = query.filter(models.B2CCart.lead_id == int(lead_id))
    elif normalized_token is not None:
        query = query.filter(models.B2CCart.cart_token == normalized_token)
    else:
        raise ValueError('Cart locator is required')

    cart = query.order_by(models.B2CCart.id.desc()).first()
    if cart is not None:
        return cart

    cart = models.B2CCart(
        customer_id=customer_id,
        lead_id=lead_id,
        cart_token=normalized_token,
        status='active',
        currency=str(currency or 'USD').strip().upper()[:8] or 'USD',
        total_amount=0.0,
    )
    db.add(cart)
    db.commit()
    db.refresh(cart)
    return cart


def _list_items(db: Session, cart_id: int) -> list[models.B2CCartItem]:
    return (
        db.query(models.B2CCartItem)
        .filter(models.B2CCartItem.cart_id == int(cart_id))
        .order_by(models.B2CCartItem.created_at.asc(), models.B2CCartItem.id.asc())
        .all()
    )


def _recompute_cart_totals(db: Session, cart: models.B2CCart) -> None:
    items = _list_items(db, cart.id)
    cart.total_amount = round(
        sum(float(row.unit_price or 0.0) * int(row.quantity or 0) for row in items),
        2,
    )
    db.add(cart)
    db.commit()
    db.refresh(cart)
