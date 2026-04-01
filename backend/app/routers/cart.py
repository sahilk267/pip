from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..schemas import (
    B2CCartAddItemRequest,
    B2CCartCheckoutRequest,
    B2CCartItemResponse,
    B2CCartRemoveItemRequest,
    B2CCartResponse,
    B2CCheckoutResponse,
    B2COrderResponse,
    CouponPromotionCreate,
    CouponPromotionResponse,
    LoyaltyAccountCreateOrUpdate,
    LoyaltyAccountResponse,
)
from ..services.b2c_commerce import create_coupon, ensure_loyalty_account
from ..services.cart_checkout import add_item_to_cart, checkout_cart, get_active_cart, remove_item_from_cart

router = APIRouter()


def _to_cart_response(cart, items) -> B2CCartResponse:
    return B2CCartResponse(
        cart_id=cart.id,
        customer_id=cart.customer_id,
        lead_id=cart.lead_id,
        cart_token=cart.cart_token,
        status=cart.status,
        currency=cart.currency,
        total_amount=float(cart.total_amount or 0.0),
        coupon_code=cart.coupon_code,
        coupon_discount_amount=float(cart.coupon_discount_amount or 0.0),
        loyalty_discount_amount=float(cart.loyalty_discount_amount or 0.0),
        total_items=sum(int(row.quantity or 0) for row in items),
        items=[B2CCartItemResponse.model_validate(row) for row in items],
        checked_out_at=cart.checked_out_at,
        created_at=cart.created_at,
        updated_at=cart.updated_at,
    )


@router.post('/api/v1/cart/items', response_model=B2CCartResponse)
def add_cart_item(payload: B2CCartAddItemRequest, db: Session = Depends(get_db)) -> B2CCartResponse:
    try:
        cart, items = add_item_to_cart(
            db,
            customer_id=payload.customer_id,
            lead_id=payload.lead_id,
            cart_token=payload.cart_token,
            currency=payload.currency,
            sku=payload.item.sku,
            name=payload.item.name,
            unit_price=payload.item.unit_price,
            quantity=payload.item.quantity,
            item_metadata=payload.item.item_metadata,
            performed_by=payload.performed_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _to_cart_response(cart, items)


@router.get('/api/v1/cart', response_model=B2CCartResponse)
def get_cart(
    customer_id: int | None = Query(default=None),
    lead_id: int | None = Query(default=None),
    cart_token: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> B2CCartResponse:
    if customer_id is None and lead_id is None and not cart_token:
        raise HTTPException(status_code=400, detail='At least one cart locator is required')

    cart, items = get_active_cart(
        db,
        customer_id=customer_id,
        lead_id=lead_id,
        cart_token=cart_token,
    )
    return _to_cart_response(cart, items)


@router.post('/api/v1/cart/items/remove', response_model=B2CCartResponse)
def remove_cart_item(payload: B2CCartRemoveItemRequest, db: Session = Depends(get_db)) -> B2CCartResponse:
    try:
        cart, items = remove_item_from_cart(
            db,
            customer_id=payload.customer_id,
            lead_id=payload.lead_id,
            cart_token=payload.cart_token,
            sku=payload.sku,
            performed_by=payload.performed_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if detail == 'Cart item not found' else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return _to_cart_response(cart, items)


@router.post('/api/v1/checkout', response_model=B2CCheckoutResponse)
def run_checkout(payload: B2CCartCheckoutRequest, db: Session = Depends(get_db)) -> B2CCheckoutResponse:
    try:
        cart, items, order = checkout_cart(
            db,
            customer_id=payload.customer_id,
            lead_id=payload.lead_id,
            cart_token=payload.cart_token,
            shipping_address=payload.shipping_address,
            coupon_code=payload.coupon_code,
            loyalty_points_to_redeem=payload.loyalty_points_to_redeem,
            performed_by=payload.performed_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return B2CCheckoutResponse(
        cart=_to_cart_response(cart, items),
        order=B2COrderResponse.model_validate(order),
    )


@router.post('/api/v1/cart/coupons', response_model=CouponPromotionResponse)
def create_coupon_promotion(payload: CouponPromotionCreate, db: Session = Depends(get_db)) -> CouponPromotionResponse:
    try:
        row = create_coupon(
            db,
            code=payload.code,
            promotion_type=payload.promotion_type,
            discount_value=payload.discount_value,
            min_order_amount=payload.min_order_amount,
            max_discount_amount=payload.max_discount_amount,
            usage_limit=payload.usage_limit,
            created_by=payload.created_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CouponPromotionResponse.model_validate(row)


@router.post('/api/v1/cart/loyalty/accounts', response_model=LoyaltyAccountResponse)
def upsert_loyalty_account(payload: LoyaltyAccountCreateOrUpdate, db: Session = Depends(get_db)) -> LoyaltyAccountResponse:
    try:
        row = ensure_loyalty_account(db, customer_id=payload.customer_id, lead_id=payload.lead_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return LoyaltyAccountResponse.model_validate(row)


@router.get('/api/v1/cart/loyalty/accounts', response_model=LoyaltyAccountResponse)
def get_loyalty_account(
    customer_id: int | None = Query(default=None),
    lead_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> LoyaltyAccountResponse:
    query = db.query(models.LoyaltyAccount)
    if customer_id is not None:
        query = query.filter(models.LoyaltyAccount.customer_id == int(customer_id))
    elif lead_id is not None:
        query = query.filter(models.LoyaltyAccount.lead_id == int(lead_id))
    else:
        raise HTTPException(status_code=400, detail='customer_id or lead_id is required')

    row = query.first()
    if row is None:
        raise HTTPException(status_code=404, detail='Loyalty account not found')
    return LoyaltyAccountResponse.model_validate(row)
