from fastapi.testclient import TestClient

from backend.app.main import app


def test_marketing_automation_event_stub_logs_ack():
    client = TestClient(app)
    r = client.post(
        '/api/v1/marketing/automation/event',
        params={'locale': 'hi'},
        json={
            'provider': 'hubspot',
            'event_type': 'campaign.sent',
            'payload': {'campaign_id': 'c-1', 'lead_count': 12},
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()['status'] == 'accepted'
    assert 'ऑडिट लॉग' in r.json()['detail'] or 'ऑडिट' in r.json()['detail']

