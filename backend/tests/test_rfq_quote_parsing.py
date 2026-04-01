from fastapi.testclient import TestClient

from backend.app.main import app


def _create_vendor(client: TestClient, name: str) -> int:
    res = client.post('/api/v1/vendors', json={'name': name, 'source': 'quote-parser-test'})
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def _create_lead(client: TestClient, email: str) -> int:
    res = client.post(
        '/api/v1/leads',
        json={'full_name': 'Quote Parse Buyer', 'email': email, 'source': 'web'},
    )
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def _create_response(client: TestClient) -> int:
    lead_id = _create_lead(client, 'quote-parse@example.com')
    vendor_id = _create_vendor(client, 'Quote Parse Vendor')

    broadcast = client.post(
        '/api/v1/rfq/broadcasts',
        json={
            'lead_id': lead_id,
            'vendor_ids': [vendor_id],
            'channel': 'email',
            'message': 'Please quote 250 units.',
            'performed_by': 'quote-parser',
        },
    )
    assert broadcast.status_code == 200, broadcast.text
    broadcast_id = int(broadcast.json()['id'])

    deliveries = client.get(f'/api/v1/rfq/broadcasts/{broadcast_id}/deliveries')
    assert deliveries.status_code == 200, deliveries.text
    attempt_id = int(deliveries.json()[0]['id'])

    delivered = client.patch(
        f'/api/v1/rfq/deliveries/{attempt_id}',
        json={'status': 'delivered', 'performed_by': 'quote-parser'},
    )
    assert delivered.status_code == 200, delivered.text

    response = client.post(
        f'/api/v1/rfq/deliveries/{attempt_id}/response',
        json={
            'response_status': 'replied',
            'response_text': 'USD 12.5 each for 250 units. Lead time 14 days. MOQ 100.',
            'recorded_by': 'quote-parser',
        },
    )
    assert response.status_code == 200, response.text
    return int(response.json()['id'])


def test_parse_unstructured_quote_response():
    client = TestClient(app)
    response_id = _create_response(client)

    parsed = client.post(
        f'/api/v1/rfq/responses/{response_id}/parse',
        json={'parser_version': 'rule-v1', 'performed_by': 'quote-parser'},
    )
    assert parsed.status_code == 200, parsed.text
    body = parsed.json()

    assert body['currency'] == 'USD'
    assert body['unit_price'] == 12.5
    assert body['quantity'] == 250
    assert body['lead_time_days'] == 14
    assert body['minimum_order_quantity'] == 100
    assert body['total_price'] == 3125.0
    assert body['confidence'] > 0.0

    listed = client.get(f'/api/v1/rfq/responses/{response_id}/parsed-quotes')
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert len(rows) == 1
    assert rows[0]['response_id'] == response_id


def test_quote_parsing_summary():
    client = TestClient(app)
    response_id = _create_response(client)

    parsed = client.post(
        f'/api/v1/rfq/responses/{response_id}/parse',
        json={'parser_version': 'rule-v1', 'performed_by': 'quote-parser'},
    )
    assert parsed.status_code == 200, parsed.text

    summary = client.get('/api/v1/rfq/quote-parsing-summary?window_days=60')
    assert summary.status_code == 200, summary.text
    body = summary.json()

    assert body['total_quotes'] >= 1
    assert body['parsed_with_unit_price'] >= 1
    assert body['parsed_with_lead_time'] >= 1
    assert body['parsed_with_quantity'] >= 1
    assert 0.0 <= body['average_confidence'] <= 1.0
