"""Tests for Quote authenticity validation feature."""
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def _create_vendor(name: str) -> int:
    res = client.post('/api/v1/vendors', json={'name': name, 'source': 'auth-test'})
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def _create_lead(email: str) -> int:
    res = client.post('/api/v1/leads', json={'full_name': 'Auth Test Buyer', 'email': email, 'source': 'web'})
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def _create_broadcast(lead_id: int, vendor_ids: list[int], channel: str = 'email') -> int:
    res = client.post(
        '/api/v1/rfq/broadcasts',
        json={
            'lead_id': lead_id,
            'vendor_ids': vendor_ids,
            'channel': channel,
            'message': 'Please quote 200 units of Item X.',
            'performed_by': 'auth-test',
        },
    )
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def _delivery_attempt_for_vendor(broadcast_id: int, vendor_id: int) -> int:
    deliveries = client.get(f'/api/v1/rfq/broadcasts/{broadcast_id}/deliveries')
    assert deliveries.status_code == 200, deliveries.text
    for attempt in deliveries.json():
        if attempt['vendor_id'] == vendor_id:
            return int(attempt['id'])
    raise AssertionError(f'No delivery attempt found for vendor {vendor_id} in broadcast {broadcast_id}')


def _deliver_and_respond(attempt_id: int, response_text: str, quoted_price: float | None = None) -> int:
    delivered = client.patch(
        f'/api/v1/rfq/deliveries/{attempt_id}',
        json={'status': 'delivered', 'performed_by': 'auth-test'},
    )
    assert delivered.status_code == 200, delivered.text

    payload: dict = {
        'response_status': 'replied',
        'response_text': response_text,
        'recorded_by': 'auth-test',
    }
    if quoted_price is not None:
        payload['quoted_price'] = quoted_price

    response = client.post(f'/api/v1/rfq/deliveries/{attempt_id}/response', json=payload)
    assert response.status_code == 200, response.text
    return int(response.json()['id'])


def _parse_response(response_id: int) -> int:
    parsed = client.post(
        f'/api/v1/rfq/responses/{response_id}/parse',
        json={'parser_version': 'rule-v1', 'performed_by': 'auth-test'},
    )
    assert parsed.status_code == 200, parsed.text
    return int(parsed.json()['id'])


def test_authentic_quote_validates_cleanly():
    """A well-formed, unique quote from a single vendor should be marked authentic."""
    lead_id = _create_lead('auth-clean@example.com')
    vendor_id = _create_vendor('Auth Clean Vendor')
    broadcast_id = _create_broadcast(lead_id, [vendor_id])
    attempt_id = _delivery_attempt_for_vendor(broadcast_id, vendor_id)
    response_id = _deliver_and_respond(
        attempt_id,
        'USD 15.00 each for 200 units. Lead time 10 days. MOQ 50.',
    )
    quote_id = _parse_response(response_id)

    check = client.post(
        f'/api/v1/rfq/quotes/{quote_id}/validate-authenticity',
        json={'performed_by': 'auth-test'},
    )
    assert check.status_code == 200, check.text
    body = check.json()
    assert body['quote_id'] == quote_id
    assert body['broadcast_id'] == broadcast_id
    assert body['verdict'] == 'authentic'
    assert body['flags'] == []
    assert body['confidence_score'] == 1.0

    # Re-running validation returns same verdict (upsert)
    check2 = client.post(
        f'/api/v1/rfq/quotes/{quote_id}/validate-authenticity',
        json={'performed_by': 'auth-test'},
    )
    assert check2.status_code == 200, check2.text
    assert check2.json()['id'] == body['id'], 'Should upsert, not create duplicate'

    # Check appears in list endpoint
    listed = client.get(f'/api/v1/rfq/quotes/authenticity-checks?broadcast_id={broadcast_id}')
    assert listed.status_code == 200, listed.text
    ids = [r['id'] for r in listed.json()]
    assert body['id'] in ids

    # Summary endpoint is responsive
    summary = client.get('/api/v1/rfq/quotes/authenticity-summary')
    assert summary.status_code == 200, summary.text
    assert summary.json()['total_checks'] >= 1


def test_duplicate_cross_vendor_quote_is_rejected():
    """If two vendors in the same broadcast submit identical response text, the second is flagged."""
    lead_id = _create_lead('auth-crossdup@example.com')
    vendor1_id = _create_vendor('Auth CrossDup Vendor Alpha')
    vendor2_id = _create_vendor('Auth CrossDup Vendor Beta')

    # Single broadcast to both vendors
    broadcast_id = _create_broadcast(lead_id, [vendor1_id, vendor2_id])

    attempt1_id = _delivery_attempt_for_vendor(broadcast_id, vendor1_id)
    attempt2_id = _delivery_attempt_for_vendor(broadcast_id, vendor2_id)

    identical_text = 'USD 9.50 each for 100 units. Lead time 5 days. MOQ 50.'

    response1_id = _deliver_and_respond(attempt1_id, identical_text)
    response2_id = _deliver_and_respond(attempt2_id, identical_text)

    quote1_id = _parse_response(response1_id)

    # First quote should be authentic (no sibling yet)
    check1 = client.post(
        f'/api/v1/rfq/quotes/{quote1_id}/validate-authenticity',
        json={'performed_by': 'auth-test'},
    )
    assert check1.status_code == 200, check1.text
    assert check1.json()['verdict'] == 'authentic'

    # Second quote has same raw_excerpt from a different vendor → duplicate_cross_vendor → rejected
    quote2_id = _parse_response(response2_id)
    check2 = client.post(
        f'/api/v1/rfq/quotes/{quote2_id}/validate-authenticity',
        json={'performed_by': 'auth-test'},
    )
    assert check2.status_code == 200, check2.text
    body2 = check2.json()
    assert 'duplicate_cross_vendor' in body2['flags']
    assert body2['verdict'] == 'rejected'
    assert body2['duplicate_of_quote_id'] == quote1_id

    # Check summary shows at least one rejection
    summary = client.get('/api/v1/rfq/quotes/authenticity-summary')
    assert summary.status_code == 200, summary.text
    sdata = summary.json()
    assert sdata['by_verdict'].get('rejected', 0) >= 1
    assert sdata['flag_counts'].get('duplicate_cross_vendor', 0) >= 1


def test_low_confidence_quote_is_suspicious():
    """A quote that can't be parsed well (no price extracted) should be suspicious."""
    lead_id = _create_lead('auth-lowconf@example.com')
    vendor_id = _create_vendor('Auth LowConf Vendor')
    broadcast_id = _create_broadcast(lead_id, [vendor_id])
    attempt_id = _delivery_attempt_for_vendor(broadcast_id, vendor_id)
    # Gibberish text — no parseable price, quantity, etc.
    response_id = _deliver_and_respond(attempt_id, 'We will get back to you shortly.')
    quote_id = _parse_response(response_id)

    check = client.post(
        f'/api/v1/rfq/quotes/{quote_id}/validate-authenticity',
        json={'performed_by': 'auth-test'},
    )
    assert check.status_code == 200, check.text
    body = check.json()
    # Confidence below 0.3 → low_confidence flag; missing unit_price → missing_unit_price flag
    assert 'low_confidence' in body['flags'] or 'missing_unit_price' in body['flags']
    assert body['verdict'] in ('suspicious',)

    # Filter by verdict
    suspicious_list = client.get('/api/v1/rfq/quotes/authenticity-checks?verdict=suspicious')
    assert suspicious_list.status_code == 200, suspicious_list.text
    ids = [r['id'] for r in suspicious_list.json()]
    assert body['id'] in ids
