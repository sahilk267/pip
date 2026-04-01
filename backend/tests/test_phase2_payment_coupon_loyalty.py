from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def _create_lead(full_name: str, email: str) -> int:
    res = client.post('/api/v1/leads', json={'full_name': full_name, 'email': email, 'source': 'web'})
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def _add_cart_item(lead_id: int, sku: str, price: float, qty: int = 1) -> int:
    res = client.post('/api/v1/cart/items', json={
        'lead_id': lead_id,
        'currency': 'USD',
        'item': {
            'sku': sku,
            'name': sku,
            'unit_price': price,
            'quantity': qty,
            'item_metadata': {},
        },
        'performed_by': 'commerce-test',
    })
    assert res.status_code == 200, res.text
    return int(res.json()['cart_id'])


def _checkout(lead_id: int, coupon_code: str | None = None, loyalty_points_to_redeem: int = 0) -> dict:
    payload = {
        'lead_id': lead_id,
        'shipping_address': {'line1': '1 Test Lane', 'city': 'Mumbai', 'country': 'IN'},
        'performed_by': 'commerce-test',
        'loyalty_points_to_redeem': loyalty_points_to_redeem,
    }
    if coupon_code is not None:
        payload['coupon_code'] = coupon_code

    res = client.post('/api/v1/checkout', json=payload)
    assert res.status_code == 200, res.text
    return res.json()


def test_payment_gateway_intent_confirm_and_list():
    lead_id = _create_lead('Payment User', 'payment-user@example.com')
    _add_cart_item(lead_id, 'SKU-PAY', 250.0, 1)
    checkout = _checkout(lead_id)
    order_id = int(checkout['order']['id'])

    gw = client.post('/api/v1/payments/gateways', json={
        'gateway_code': 'razorpay',
        'display_name': 'Razorpay',
        'supported_currencies': ['USD', 'INR'],
        'configured_by': 'finance',
    })
    assert gw.status_code == 200, gw.text

    intent = client.post(f'/api/v1/orders/b2c/{order_id}/payments/intent', json={
        'gateway_code': 'razorpay',
        'created_by': 'checkout',
    })
    assert intent.status_code == 200, intent.text
    transaction_id = int(intent.json()['id'])
    assert intent.json()['status'] == 'created'

    confirm = client.post(f'/api/v1/orders/b2c/payments/{transaction_id}/confirm', json={
        'status': 'captured',
        'external_reference': 'rzp_txn_001',
        'performed_by': 'razorpay-webhook',
    })
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()['status'] == 'captured'

    payments = client.get(f'/api/v1/orders/b2c/{order_id}/payments')
    assert payments.status_code == 200, payments.text
    assert any(int(row['id']) == transaction_id and row['status'] == 'captured' for row in payments.json())


def test_coupon_and_loyalty_checkout_logic():
    lead_id = _create_lead('Coupon User', 'coupon-user@example.com')

    # First checkout to earn loyalty points
    _add_cart_item(lead_id, 'SKU-EARN', 120.0, 1)
    first_checkout = _checkout(lead_id)
    assert first_checkout['order']['total_amount'] == 120.0

    loyalty = client.post('/api/v1/cart/loyalty/accounts', json={'lead_id': lead_id})
    assert loyalty.status_code == 200, loyalty.text
    assert loyalty.json()['points_balance'] >= 12

    coupon = client.post('/api/v1/cart/coupons', json={
        'code': 'SAVE10',
        'promotion_type': 'percent',
        'discount_value': 10.0,
        'min_order_amount': 50.0,
        'created_by': 'marketing',
    })
    assert coupon.status_code == 200, coupon.text

    # Second checkout: coupon + loyalty redemption
    _add_cart_item(lead_id, 'SKU-DISC', 200.0, 1)
    second_checkout = _checkout(lead_id, coupon_code='SAVE10', loyalty_points_to_redeem=10)

    cart_payload = second_checkout['cart']
    order_payload = second_checkout['order']

    assert cart_payload['coupon_code'] == 'SAVE10'
    assert cart_payload['coupon_discount_amount'] > 0.0
    assert cart_payload['loyalty_discount_amount'] > 0.0
    assert float(order_payload['total_amount']) < 200.0
