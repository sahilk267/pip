from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def _create_lead(email: str) -> int:
    res = client.post('/api/v1/leads', json={'full_name': 'Dedup Lead', 'email': email, 'source': 'web'})
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def _create_vendor(name: str) -> int:
    res = client.post('/api/v1/vendors', json={'name': name, 'source': 'dedup-test'})
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def test_rfq_multi_channel_dedup_blocks_duplicate_broadcasts():
    lead_id = _create_lead('dedup-rfq@example.com')
    vendor_id = _create_vendor('Dedup RFQ Vendor')

    first = client.post(
        '/api/v1/rfq/broadcasts',
        json={
            'lead_id': lead_id,
            'vendor_ids': [vendor_id],
            'channel': 'email',
            'message': 'Please share quote for 500 units.',
            'performed_by': 'sales-1',
        },
    )
    assert first.status_code == 200, first.text

    duplicate = client.post(
        '/api/v1/rfq/broadcasts',
        json={
            'lead_id': lead_id,
            'vendor_ids': [vendor_id],
            'channel': 'whatsapp',
            'message': 'Please share quote for 500 units.',
            'performed_by': 'sales-2',
        },
    )
    assert duplicate.status_code == 400, duplicate.text
    assert 'Duplicate RFQ broadcast detected across channels' in duplicate.json()['detail']


def test_b2c_order_multi_channel_dedup_blocks_duplicate_orders():
    payload = {
        'currency': 'usd',
        'total_amount': 120.0,
        'order_items': [{'sku': 'DEDUP-1', 'qty': 1, 'price': 120.0}],
        'shipping_address': {'city': 'Pune', 'country': 'IN'},
    }

    first = client.post('/api/v1/orders/b2c', json={**payload, 'source_channel': 'web'})
    assert first.status_code == 200, first.text

    duplicate = client.post('/api/v1/orders/b2c', json={**payload, 'source_channel': 'mobile_app'})
    assert duplicate.status_code == 400, duplicate.text
    assert 'Duplicate order detected across channels' in duplicate.json()['detail']
