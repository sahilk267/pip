from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app import models
from backend.app.database import SessionLocal


def test_marketing_automation_dispatch_emits_provider_events():
    client = TestClient(app)

    lead = client.post(
        '/api/v1/leads',
        json={'full_name': 'Dispatch Lead', 'email': 'dispatch@example.com', 'source': 'paid_ad'},
    )
    assert lead.status_code == 200, lead.text
    lead_id = lead.json()['id']

    prefs = client.patch(
        f'/api/v1/leads/{lead_id}/preferences',
        json={'marketing_consent': 'yes', 'unsubscribe': False},
    )
    assert prefs.status_code == 200, prefs.text

    intent = client.post(
        '/api/v1/marketing/intent/event',
        json={
            'lead_id': lead_id,
            'source': 'paid_ad',
            'signal_type': 'download',
            'strength': 8,
        },
    )
    assert intent.status_code == 200, intent.text

    dispatch = client.post(
        '/api/v1/marketing/campaigns/dispatch',
        json={'campaign_type': 'auto', 'limit': 25, 'performed_by': 'qa'},
    )
    assert dispatch.status_code == 200, dispatch.text

    body = dispatch.json()
    assert body['campaign_type'] == 'auto'
    assert body['triggered'] >= 1
    assert body['dispatched'] >= 1
    assert body['providers']

    with SessionLocal() as db:
        events = (
            db.query(models.AuditLog)
            .filter(models.AuditLog.action == 'automation_event')
            .all()
        )
        assert events
        assert any('campaign.nurture.enqueue' in (row.detail or '') for row in events)
