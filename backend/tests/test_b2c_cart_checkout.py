from fastapi.testclient import TestClient

from backend.app.main import app


def test_b2c_cart_add_remove_and_checkout_flow():
    client = TestClient(app)

    lead = client.post(
        '/api/v1/leads',
        json={
            'full_name': 'Checkout Buyer',
            'email': 'checkout@example.com',
            'source': 'web',
        },
    )
    assert lead.status_code == 200, lead.text
    lead_id = int(lead.json()['id'])

    add_1 = client.post(
        '/api/v1/cart/items',
        json={
            'lead_id': lead_id,
            'currency': 'usd',
            'item': {
                'sku': 'NTM-300',
                'name': 'Nova Thermal Module',
                'unit_price': 120.0,
                'quantity': 2,
                'item_metadata': {'warranty': '2y'},
            },
        },
    )
    assert add_1.status_code == 200, add_1.text
    cart = add_1.json()
    assert cart['total_items'] == 2
    assert cart['total_amount'] == 240.0

    add_2 = client.post(
        '/api/v1/cart/items',
        json={
            'lead_id': lead_id,
            'currency': 'usd',
            'item': {
                'sku': 'ACC-1',
                'name': 'Accessory Pack',
                'unit_price': 30.0,
                'quantity': 1,
                'item_metadata': {'color': 'black'},
            },
        },
    )
    assert add_2.status_code == 200, add_2.text
    cart = add_2.json()
    assert cart['total_items'] == 3
    assert cart['total_amount'] == 270.0

    read_cart = client.get('/api/v1/cart', params={'lead_id': lead_id})
    assert read_cart.status_code == 200, read_cart.text
    cart = read_cart.json()
    assert len(cart['items']) == 2

    remove = client.post(
        '/api/v1/cart/items/remove',
        json={
            'lead_id': lead_id,
            'sku': 'ACC-1',
        },
    )
    assert remove.status_code == 200, remove.text
    cart = remove.json()
    assert cart['total_items'] == 2
    assert len(cart['items']) == 1
    assert cart['total_amount'] == 240.0

    checkout = client.post(
        '/api/v1/checkout',
        json={
            'lead_id': lead_id,
            'shipping_address': {'city': 'Pune', 'country': 'IN'},
        },
    )
    assert checkout.status_code == 200, checkout.text
    body = checkout.json()
    assert body['cart']['status'] == 'checked_out'
    assert body['order']['lead_id'] == lead_id
    assert body['order']['total_amount'] == 240.0
    assert body['order']['order_items'][0]['sku'] == 'NTM-300'

    second_checkout = client.post(
        '/api/v1/checkout',
        json={
            'lead_id': lead_id,
            'shipping_address': {'city': 'Pune', 'country': 'IN'},
        },
    )
    assert second_checkout.status_code == 400
