from fastapi.testclient import TestClient

from backend.app.main import app


def _create_lead_with_consent(client: TestClient, *, name: str, email: str, source: str) -> int:
    res = client.post(
        '/api/v1/leads',
        json={
            'full_name': name,
            'email': email,
            'source': source,
        },
    )
    assert res.status_code == 200, res.text
    lead_id = int(res.json()['id'])

    pref = client.patch(
        f'/api/v1/leads/{lead_id}/preferences',
        json={'marketing_consent': 'yes', 'unsubscribe': False},
    )
    assert pref.status_code == 200, pref.text
    return lead_id


def test_marketing_order_attribution_endpoint_attributes_orders_to_dispatches():
    client = TestClient(app)

    lead_id = _create_lead_with_consent(
        client,
        name='Attribution Lead',
        email='attrib@example.com',
        source='web',
    )

    intent = client.post(
        '/api/v1/marketing/intent/event',
        json={
            'lead_id': lead_id,
            'source': 'email_click',
            'signal_type': 'click',
            'strength': 10,
        },
    )
    assert intent.status_code == 200, intent.text

    dispatch = client.post(
        '/api/v1/marketing/campaigns/dispatch',
        json={'campaign_type': 'auto', 'limit': 25, 'performed_by': 'qa-attribution'},
    )
    assert dispatch.status_code == 200, dispatch.text
    assert dispatch.json()['dispatched'] >= 1

    order = client.post(
        '/api/v1/orders/b2c',
        json={
            'lead_id': lead_id,
            'currency': 'USD',
            'total_amount': 219.50,
            'order_items': [{'sku': 'NTM-300', 'qty': 1, 'price': 219.50}],
            'shipping_address': {'city': 'Delhi', 'country': 'IN'},
        },
    )
    assert order.status_code == 200, order.text

    unattributed = client.post(
        '/api/v1/orders/b2c',
        json={
            'currency': 'USD',
            'total_amount': 35.00,
            'order_items': [{'sku': 'ADD-1', 'qty': 1, 'price': 35.00}],
            'shipping_address': {'city': 'Delhi', 'country': 'IN'},
        },
    )
    assert unattributed.status_code == 200, unattributed.text

    report = client.get('/api/v1/marketing/orders/attribution', params={'window_days': 30})
    assert report.status_code == 200, report.text
    body = report.json()

    assert body['orders_total'] == 2
    assert body['orders_attributed'] == 1
    assert body['orders_unattributed'] == 1
    assert body['attributed_revenue'] == 219.5
    assert body['unattributed_revenue'] == 35.0

    assert 'mailchimp' in body['attribution_by_provider']
    assert body['attribution_by_provider']['mailchimp']['orders'] == 1
    assert body['attribution_by_provider']['mailchimp']['revenue'] == 219.5

    assert body['attribution_by_channel']['other']['orders'] == 1
    assert body['attribution_by_campaign_type']['nurture']['orders'] == 1
