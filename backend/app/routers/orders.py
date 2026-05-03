from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import (
    B2COrderCreate,
    OrderDealFeedbackCreate,
    OrderDealFeedbackResponse,
    OrderDealFeedbackSummary,
    B2COrderFulfillmentPatch,
    B2COrderResponse,
    B2COrderShippingCreate,
    B2COrderShippingShipmentResponse,
    B2COrderShippingSyncPatch,
    B2COrderTrackingEventResponse,
    B2COrderTrackingResponse,
    EntityVersionRecordResponse,
    EntityVersionRollbackRequest,
    PaymentConfirmRequest,
    PaymentGatewayConfigCreate,
    PaymentGatewayConfigResponse,
    PaymentIntentCreateRequest,
    PaymentTransactionResponse,
)
from ..services.b2c_commerce import (
    confirm_payment,
    create_payment_intent,
    list_order_payments,
    list_payment_gateways,
    register_payment_gateway,
)
from ..services.orders import (
    create_b2c_order,
    list_b2c_orders,
    order_tracking_timeline,
    update_fulfillment_status,
)
from ..services.versioning import list_entity_versions, rollback_order_version
from ..services.order_shipping import (
    create_shipping_shipment,
    list_shipping_shipments_for_order,
    sync_shipping_shipment_status,
)
from ..services.order_feedback import (
    list_order_deal_feedback,
    order_deal_feedback_summary,
    record_order_deal_feedback,
)

router = APIRouter()


@router.post('/api/v1/orders/b2c', response_model=B2COrderResponse)
def create_order(payload: B2COrderCreate, db: Session = Depends(get_db)) -> B2COrderResponse:
    try:
        order = create_b2c_order(
            db,
            customer_id=payload.customer_id,
            lead_id=payload.lead_id,
            currency=payload.currency,
            total_amount=payload.total_amount,
            order_items=payload.order_items,
            source_channel=payload.source_channel,
            shipping_address=payload.shipping_address,
        )
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(status_code=400, detail=detail) from exc
    return B2COrderResponse.model_validate(order)


@router.get('/api/v1/orders/b2c', response_model=list[B2COrderResponse])
def list_orders(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[B2COrderResponse]:
    orders = list_b2c_orders(db, limit=limit)
    return [B2COrderResponse.model_validate(order) for order in orders]


@router.patch('/api/v1/orders/b2c/{order_id}/fulfillment', response_model=B2COrderResponse)
def patch_fulfillment(
    order_id: int,
    payload: B2COrderFulfillmentPatch,
    db: Session = Depends(get_db),
) -> B2COrderResponse:
    try:
        order = update_fulfillment_status(
            db,
            order_id=order_id,
            fulfillment_status=payload.fulfillment_status,
            tracking_number=payload.tracking_number,
            carrier=payload.carrier,
            location=payload.location,
            note=payload.note,
            performed_by=payload.performed_by,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == 'Order not found':
            raise HTTPException(status_code=404, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc
    return B2COrderResponse.model_validate(order)


@router.get('/api/v1/orders/b2c/{order_id}/tracking', response_model=B2COrderTrackingResponse)
def get_order_tracking(order_id: int, db: Session = Depends(get_db)) -> B2COrderTrackingResponse:
    try:
        order, events = order_tracking_timeline(db, order_id=order_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return B2COrderTrackingResponse(
        order_id=order.id,
        status=order.status,
        fulfillment_status=order.fulfillment_status,
        tracking_number=order.tracking_number,
        carrier=order.carrier,
        shipped_at=order.shipped_at,
        delivered_at=order.delivered_at,
        events=[B2COrderTrackingEventResponse.model_validate(event) for event in events],
    )


@router.get('/api/v1/orders/b2c/{order_id}/versions', response_model=list[EntityVersionRecordResponse])
def list_order_versions(
    order_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[EntityVersionRecordResponse]:
    rows = list_entity_versions(db, entity_type='order', entity_id=order_id, limit=limit)
    return [EntityVersionRecordResponse.model_validate(row) for row in rows]


@router.post('/api/v1/security/dr/backup/orders/b2c/{order_id}/versions/{version_number}/rollback', response_model=B2COrderResponse)
@router.post('/api/v1/orders/b2c/{order_id}/versions/{version_number}/rollback', response_model=B2COrderResponse)
def rollback_order(
    order_id: int,
    version_number: int,
    payload: EntityVersionRollbackRequest,
    db: Session = Depends(get_db),
) -> B2COrderResponse:
    try:
        row = rollback_order_version(
            db,
            order_id=order_id,
            version_number=version_number,
            reason=payload.reason,
            performed_by=payload.performed_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if detail in {'Order not found', 'Version not found'} else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return B2COrderResponse.model_validate(row)


@router.post('/api/v1/orders/b2c/{order_id}/shipping/shipments', response_model=B2COrderShippingShipmentResponse)
def create_order_shipping_shipment(
    order_id: int,
    payload: B2COrderShippingCreate,
    db: Session = Depends(get_db),
) -> B2COrderShippingShipmentResponse:
    try:
        shipment = create_shipping_shipment(
            db,
            order_id=order_id,
            provider=payload.provider,
            service_level=payload.service_level,
            shipping_cost=payload.shipping_cost,
            estimated_delivery_days=payload.estimated_delivery_days,
            shipment_metadata=payload.shipment_metadata,
            performed_by=payload.performed_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if detail == 'Order not found' else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return B2COrderShippingShipmentResponse.model_validate(shipment)


@router.get('/api/v1/orders/b2c/{order_id}/shipping/shipments', response_model=list[B2COrderShippingShipmentResponse])
def list_order_shipping_shipments(order_id: int, db: Session = Depends(get_db)) -> list[B2COrderShippingShipmentResponse]:
    rows = list_shipping_shipments_for_order(db, order_id=order_id)
    return [B2COrderShippingShipmentResponse.model_validate(row) for row in rows]


@router.patch('/api/v1/orders/b2c/shipping/shipments/{shipment_id}', response_model=B2COrderShippingShipmentResponse)
def patch_shipping_shipment_status(
    shipment_id: int,
    payload: B2COrderShippingSyncPatch,
    db: Session = Depends(get_db),
) -> B2COrderShippingShipmentResponse:
    try:
        shipment = sync_shipping_shipment_status(
            db,
            shipment_id=shipment_id,
            status=payload.status,
            current_location=payload.current_location,
            note=payload.note,
            performed_by=payload.performed_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if detail == 'Shipping shipment not found' else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return B2COrderShippingShipmentResponse.model_validate(shipment)


@router.post('/api/v1/orders/b2c/{order_id}/feedback', response_model=OrderDealFeedbackResponse)
def create_order_feedback(
    order_id: int,
    payload: OrderDealFeedbackCreate,
    db: Session = Depends(get_db),
) -> OrderDealFeedbackResponse:
    try:
        row = record_order_deal_feedback(
            db,
            order_id=order_id,
            actor_type=payload.actor_type,
            actor_id=payload.actor_id,
            sentiment=payload.sentiment,
            rating=payload.rating,
            feedback_text=payload.feedback_text,
            feedback_metadata=payload.feedback_metadata,
            created_by=payload.created_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if detail == 'Order not found' else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return OrderDealFeedbackResponse.model_validate(row)


@router.get('/api/v1/orders/b2c/feedback/summary', response_model=OrderDealFeedbackSummary)
def get_order_feedback_summary(
    window_days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> OrderDealFeedbackSummary:
    payload = order_deal_feedback_summary(db, window_days=window_days)
    return OrderDealFeedbackSummary(**payload)


@router.get('/api/v1/orders/b2c/{order_id}/feedback', response_model=list[OrderDealFeedbackResponse])
def get_order_feedback(order_id: int, db: Session = Depends(get_db)) -> list[OrderDealFeedbackResponse]:
    try:
        rows = list_order_deal_feedback(db, order_id=order_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [OrderDealFeedbackResponse.model_validate(row) for row in rows]


@router.post('/api/v1/payments/gateways', response_model=PaymentGatewayConfigResponse)
def create_payment_gateway(payload: PaymentGatewayConfigCreate, db: Session = Depends(get_db)) -> PaymentGatewayConfigResponse:
    try:
        row = register_payment_gateway(
            db,
            gateway_code=payload.gateway_code,
            display_name=payload.display_name,
            supported_currencies=payload.supported_currencies,
            configured_by=payload.configured_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PaymentGatewayConfigResponse.model_validate(row)


@router.get('/api/v1/payments/gateways', response_model=list[PaymentGatewayConfigResponse])
def get_payment_gateways(
    gateway_status: str | None = Query(default='active'),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[PaymentGatewayConfigResponse]:
    rows = list_payment_gateways(db, status=gateway_status, limit=limit)
    return [PaymentGatewayConfigResponse.model_validate(row) for row in rows]


@router.post('/api/v1/orders/b2c/{order_id}/payments/intent', response_model=PaymentTransactionResponse)
def create_order_payment_intent(
    order_id: int,
    payload: PaymentIntentCreateRequest,
    db: Session = Depends(get_db),
) -> PaymentTransactionResponse:
    try:
        row = create_payment_intent(
            db,
            order_id=order_id,
            gateway_code=payload.gateway_code,
            amount=payload.amount,
            created_by=payload.created_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if detail == 'Order not found' else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return PaymentTransactionResponse.model_validate(row)


@router.post('/api/v1/orders/b2c/payments/{transaction_id}/confirm', response_model=PaymentTransactionResponse)
def confirm_order_payment(
    transaction_id: int,
    payload: PaymentConfirmRequest,
    db: Session = Depends(get_db),
) -> PaymentTransactionResponse:
    try:
        row = confirm_payment(
            db,
            transaction_id=transaction_id,
            status=payload.status,
            external_reference=payload.external_reference,
            performed_by=payload.performed_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return PaymentTransactionResponse.model_validate(row)


@router.get('/api/v1/orders/b2c/{order_id}/payments', response_model=list[PaymentTransactionResponse])
def get_order_payments(
    order_id: int,
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[PaymentTransactionResponse]:
    rows = list_order_payments(db, order_id=order_id, limit=limit)
    return [PaymentTransactionResponse.model_validate(row) for row in rows]
