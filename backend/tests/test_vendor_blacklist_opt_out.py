from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def _create_vendor(name: str) -> int:
    res = client.post('/api/v1/vendors', json={'name': name, 'source': 'optout-test'})
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def _create_lead(email: str) -> int:
    res = client.post('/api/v1/leads', json={'full_name': 'OptOut Lead', 'email': email, 'source': 'web'})
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def test_vendor_channel_opt_out_blocks_rfq_on_that_channel_only():
    lead_id = _create_lead('optout-channel@example.com')
    vendor_id = _create_vendor('OptOut Channel Vendor')

    rule = client.post(
        f'/api/v1/vendors/{vendor_id}/opt-out',
        json={
            'channel': 'email',
            'is_opted_out': True,
            'rule_type': 'opt_out',
            'reason': 'Do not send email RFQs',
            'created_by': 'compliance',
        },
    )
    assert rule.status_code == 200, rule.text
    assert rule.json()['vendor_id'] == vendor_id
    assert rule.json()['channel'] == 'email'

    blocked = client.post(
        '/api/v1/rfq/broadcasts',
        json={
            'lead_id': lead_id,
            'vendor_ids': [vendor_id],
            'channel': 'email',
            'message': 'Please quote 100 units.',
            'performed_by': 'sales-ops',
        },
    )
    assert blocked.status_code == 400, blocked.text
    assert 'No vendors available for RFQ broadcast after blacklist/opt-out filtering' in blocked.json()['detail']

    allowed = client.post(
        '/api/v1/rfq/broadcasts',
        json={
            'lead_id': lead_id,
            'vendor_ids': [vendor_id],
            'channel': 'whatsapp',
            'message': 'Please quote 100 units.',
            'performed_by': 'sales-ops',
        },
    )
    assert allowed.status_code == 200, allowed.text


def test_vendor_blacklist_all_channels_filtered_from_automatch():
    lead_id = _create_lead('optout-all@example.com')
    blocked_vendor_id = _create_vendor('OptOut All Vendor')
    allowed_vendor_id = _create_vendor('Open Vendor')

    rule = client.post(
        f'/api/v1/vendors/{blocked_vendor_id}/opt-out',
        json={
            'channel': 'all',
            'is_opted_out': True,
            'rule_type': 'blacklist',
            'reason': 'Repeated compliance violations',
            'created_by': 'risk-team',
        },
    )
    assert rule.status_code == 200, rule.text

    res = client.post(
        '/api/v1/rfq/broadcasts',
        json={
            'lead_id': lead_id,
            'vendor_ids': [],
            'auto_match_limit': 5,
            'channel': 'email',
            'message': 'Need quote for 250 units.',
            'performed_by': 'sales-automation',
        },
    )
    assert res.status_code == 200, res.text

    broadcast_id = int(res.json()['id'])
    deliveries = client.get(f'/api/v1/rfq/broadcasts/{broadcast_id}/deliveries')
    assert deliveries.status_code == 200, deliveries.text
    vendor_ids = {int(row['vendor_id']) for row in deliveries.json()}
    assert allowed_vendor_id in vendor_ids
    assert blocked_vendor_id not in vendor_ids

    rules = client.get('/api/v1/vendors/opt-out?only_active=true')
    assert rules.status_code == 200, rules.text
    matched = [row for row in rules.json() if int(row['vendor_id']) == blocked_vendor_id]
    assert len(matched) == 1
    assert matched[0]['rule_type'] == 'blacklist'
