from fastapi.testclient import TestClient

from backend.app.main import app


def _create_vendor(client: TestClient, name: str) -> int:
    res = client.post('/api/v1/vendors', json={'name': name, 'source': 'rrl-test'})
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def _create_lead(client: TestClient, email: str) -> int:
    res = client.post(
        '/api/v1/leads',
        json={'full_name': 'RRL Lead', 'email': email, 'source': 'web'},
    )
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def test_rate_limit_rule_crud():
    client = TestClient(app)

    # Create a lead-level rule
    res = client.post(
        '/api/v1/rfq/rate-limit/rules',
        json={
            'entity_type': 'lead',
            'entity_key': '999',
            'max_per_window': 3,
            'window_hours': 24,
            'is_active': True,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body['entity_type'] == 'lead'
    assert body['entity_key'] == '999'
    assert body['max_per_window'] == 3

    # Upserting the same rule changes max
    res2 = client.post(
        '/api/v1/rfq/rate-limit/rules',
        json={
            'entity_type': 'lead',
            'entity_key': '999',
            'max_per_window': 5,
            'window_hours': 12,
            'is_active': True,
        },
    )
    assert res2.status_code == 200, res2.text
    assert res2.json()['max_per_window'] == 5
    assert res2.json()['id'] == body['id']  # same row

    # List rules — should contain the upserted rule
    list_res = client.get('/api/v1/rfq/rate-limit/rules')
    assert list_res.status_code == 200, list_res.text
    rule_keys = [(r['entity_type'], r['entity_key']) for r in list_res.json()]
    assert ('lead', '999') in rule_keys


def test_rate_limit_enforcement_and_usage():
    client = TestClient(app)

    lead_id = _create_lead(client, 'rrl-test@example.com')
    vendor_id = _create_vendor(client, 'RRL Vendor')

    # Set a very tight lead rule: max 2 per 24h
    client.post(
        '/api/v1/rfq/rate-limit/rules',
        json={
            'entity_type': 'lead',
            'entity_key': str(lead_id),
            'max_per_window': 2,
            'window_hours': 24,
            'is_active': True,
        },
    )

    def _broadcast():
        return client.post(
            '/api/v1/rfq/broadcasts',
            json={
                'lead_id': lead_id,
                'vendor_ids': [vendor_id],
                'channel': 'email',
                'message': 'Rate limit test broadcast.',
                'performed_by': 'rrl-sales',
            },
        )

    # First and second should succeed
    r1 = _broadcast()
    assert r1.status_code == 200, r1.text
    r2 = _broadcast()
    assert r2.status_code == 200, r2.text

    # Third must be blocked (429)
    r3 = _broadcast()
    assert r3.status_code == 429, r3.text
    assert 'rate limit exceeded' in r3.json()['detail'].lower()

    # Usage endpoint should show the lead as limited
    usage = client.get('/api/v1/rfq/rate-limit/usage?window_hours=24')
    assert usage.status_code == 200, usage.text
    buckets = usage.json()['buckets']
    lead_buckets = [b for b in buckets if b['entity_type'] == 'lead' and b['entity_key'] == str(lead_id)]
    assert len(lead_buckets) == 1
    assert lead_buckets[0]['broadcasts_in_window'] >= 2
    assert lead_buckets[0]['is_limited'] is True
