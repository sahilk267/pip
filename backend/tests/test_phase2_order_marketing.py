from fastapi.testclient import TestClient

from backend.app.main import app


def _create_marketing_ready_lead(client: TestClient) -> int:
    lead_res = client.post(
        '/api/v1/leads',
        json={
            'full_name': 'Taylor Buyer',
            'email': 'taylor@example.com',
            'company': 'Acme Retail',
            'source': 'web',
        },
    )
    assert lead_res.status_code == 200, lead_res.text
    lead_id = int(lead_res.json()['id'])

    pref_res = client.patch(
        f'/api/v1/leads/{lead_id}/preferences',
        json={'marketing_consent': 'yes', 'unsubscribe': False},
    )
    assert pref_res.status_code == 200, pref_res.text

    intent_res = client.post(
        '/api/v1/marketing/intent/event',
        json={
            'lead_id': lead_id,
            'source': 'email_click',
            'signal_type': 'click',
            'strength': 12,
            'metadata': {'campaign': 'spring-promo'},
        },
    )
    assert intent_res.status_code == 200, intent_res.text
    return lead_id


def test_marketing_dispatch_status_and_sync_flow():
    client = TestClient(app)
    lead_id = _create_marketing_ready_lead(client)

    dispatch_res = client.post(
        '/api/v1/marketing/campaigns/dispatch',
        json={
            'campaign_type': 'auto',
            'limit': 25,
            'performed_by': 'test-suite',
        },
    )
    assert dispatch_res.status_code == 200, dispatch_res.text
    body = dispatch_res.json()
    assert body['dispatched'] >= 1

    list_res = client.get('/api/v1/marketing/dispatches', params={'limit': 20})
    assert list_res.status_code == 200, list_res.text
    rows = list_res.json()
    assert rows
    assert any(row['lead_id'] == lead_id and row['status'] == 'sent' for row in rows)

    sync_res = client.post('/api/v1/marketing/dispatches/sync', params={'limit': 100, 'performed_by': 'test-sync'})
    assert sync_res.status_code == 200, sync_res.text
    sync_body = sync_res.json()
    assert sync_body['scanned'] >= 1

    delivered_res = client.get('/api/v1/marketing/dispatches', params={'status': 'delivered', 'limit': 50})
    assert delivered_res.status_code == 200, delivered_res.text
    delivered_rows = delivered_res.json()
    assert any(row['lead_id'] == lead_id for row in delivered_rows)


def test_b2c_order_tracking_and_fulfillment_timeline():
    client = TestClient(app)

    create_res = client.post(
        '/api/v1/orders/b2c',
        json={
            'currency': 'usd',
            'total_amount': 149.99,
            'order_items': [
                {'sku': 'NTM-300', 'qty': 1, 'price': 149.99},
            ],
            'shipping_address': {'city': 'Pune', 'country': 'IN'},
        },
    )
    assert create_res.status_code == 200, create_res.text
    order = create_res.json()
    order_id = int(order['id'])
    assert order['fulfillment_status'] == 'pending'

    ship_res = client.patch(
        f'/api/v1/orders/b2c/{order_id}/fulfillment',
        json={
            'fulfillment_status': 'shipped',
            'tracking_number': 'TRK-12345',
            'carrier': 'BlueDart',
            'location': 'Mumbai Hub',
            'note': 'Package left origin facility',
            'performed_by': 'ops-test',
        },
    )
    assert ship_res.status_code == 200, ship_res.text
    shipped = ship_res.json()
    assert shipped['tracking_number'] == 'TRK-12345'
    assert shipped['fulfillment_status'] == 'shipped'

    delivered_res = client.patch(
        f'/api/v1/orders/b2c/{order_id}/fulfillment',
        json={
            'fulfillment_status': 'delivered',
            'tracking_number': 'TRK-12345',
            'carrier': 'BlueDart',
            'location': 'Customer Doorstep',
            'note': 'Delivered successfully',
            'performed_by': 'ops-test',
        },
    )
    assert delivered_res.status_code == 200, delivered_res.text
    delivered = delivered_res.json()
    assert delivered['fulfillment_status'] == 'delivered'
    assert delivered['delivered_at'] is not None

    tracking_res = client.get(f'/api/v1/orders/b2c/{order_id}/tracking')
    assert tracking_res.status_code == 200, tracking_res.text
    tracking = tracking_res.json()
    assert tracking['tracking_number'] == 'TRK-12345'
    assert len(tracking['events']) >= 3
    statuses = [event['status'] for event in tracking['events']]
    assert statuses[0] == 'created'
    assert 'shipped' in statuses
    assert statuses[-1] == 'delivered'
