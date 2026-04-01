from fastapi.testclient import TestClient

from backend.app.main import app


def _create_vendor(client: TestClient, name: str) -> int:
    res = client.post(
        '/api/v1/vendors',
        json={
            'name': name,
            'source': 'test-suite-vra',
        },
    )
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def _create_broadcast_with_delivery(client: TestClient) -> tuple[int, int]:
    """Return (broadcast_id, attempt_id) for a 1-vendor broadcast after syncing to delivered."""
    lead = client.post(
        '/api/v1/leads',
        json={
            'full_name': 'VRA Buyer',
            'email': 'vra-buyer@example.com',
            'source': 'web',
        },
    )
    assert lead.status_code == 200, lead.text
    lead_id = int(lead.json()['id'])

    vendor_id = _create_vendor(client, 'VRA Vendor Alpha')

    broadcast = client.post(
        '/api/v1/rfq/broadcasts',
        json={
            'lead_id': lead_id,
            'vendor_ids': [vendor_id],
            'channel': 'email',
            'message': 'Please quote 200 units.',
            'performed_by': 'vra-sales',
        },
    )
    assert broadcast.status_code == 200, broadcast.text
    broadcast_id = int(broadcast.json()['id'])

    deliveries = client.get(f'/api/v1/rfq/broadcasts/{broadcast_id}/deliveries')
    assert deliveries.status_code == 200, deliveries.text
    attempt_id = int(deliveries.json()[0]['id'])

    # Mark the delivery as delivered so it counts in analytics denominator
    patched = client.patch(
        f'/api/v1/rfq/deliveries/{attempt_id}',
        json={'status': 'delivered', 'performed_by': 'vra-sales'},
    )
    assert patched.status_code == 200, patched.text

    return broadcast_id, attempt_id


def test_vendor_response_record_and_list():
    client = TestClient(app)
    _, attempt_id = _create_broadcast_with_delivery(client)

    # Record a vendor reply
    res = client.post(
        f'/api/v1/rfq/deliveries/{attempt_id}/response',
        json={
            'response_status': 'replied',
            'response_text': 'We can supply 200 units at $15 each.',
            'quoted_price': 3000.0,
            'recorded_by': 'vra-sales',
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body['response_status'] == 'replied'
    assert body['attempt_id'] == attempt_id
    assert body['quoted_price'] == 3000.0

    # List responses for attempt
    list_res = client.get(f'/api/v1/rfq/deliveries/{attempt_id}/responses')
    assert list_res.status_code == 200, list_res.text
    rows = list_res.json()
    assert len(rows) >= 1
    assert rows[0]['response_status'] == 'replied'


def test_vendor_response_analytics():
    client = TestClient(app)
    _, attempt_id = _create_broadcast_with_delivery(client)

    # Record an opened event
    res = client.post(
        f'/api/v1/rfq/deliveries/{attempt_id}/response',
        json={
            'response_status': 'opened',
            'recorded_by': 'vra-sales',
        },
    )
    assert res.status_code == 200, res.text

    analytics = client.get('/api/v1/rfq/vendor-response-analytics?window_days=60')
    assert analytics.status_code == 200, analytics.text
    body = analytics.json()

    assert 'total_deliveries' in body
    assert 'total_responses' in body
    assert 'reply_rate' in body
    assert 'open_rate' in body
    assert 'by_vendor' in body
    assert 'by_channel' in body

    # There must be at least one delivered attempt in the analytics window
    assert body['total_deliveries'] >= 1
    # And the response we just recorded should contribute
    assert body['total_responses'] >= 1
    # open_rate must be a fraction [0, 1]
    assert 0.0 <= body['open_rate'] <= 1.0

    # email channel should exist
    assert 'email' in body['by_channel']
    email_bucket = body['by_channel']['email']
    assert email_bucket['total_deliveries'] >= 1
