from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app import models
from backend.app.database import SessionLocal
from backend.app.services.sales_playbooks import build_sales_playbook, build_sales_playbook_queue


def test_lead_sales_playbook_endpoint_returns_actions():
    client = TestClient(app)
    lead_resp = client.post(
        '/api/v1/leads',
        json={
            'full_name': 'Playbook Lead',
            'email': 'lead@example.com',
            'source': 'web',
        },
    )
    assert lead_resp.status_code == 200, lead_resp.text
    lead_id = lead_resp.json()['id']

    comm_resp = client.post(
        '/api/v1/crm/communications',
        json={
            'lead_id': lead_id,
            'channel': 'email',
            'direction': 'outbound',
            'message': 'Initial outreach',
            'follow_up_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        },
    )
    assert comm_resp.status_code == 200, comm_resp.text

    playbook_resp = client.get(f'/api/v1/leads/{lead_id}/playbook')
    assert playbook_resp.status_code == 200, playbook_resp.text
    payload = playbook_resp.json()
    assert payload['lead_id'] == lead_id
    assert payload['recommended_channel'] == 'email'
    assert payload['steps']


def test_sales_playbook_queue_prioritizes_high_value_leads():
    with SessionLocal() as db:
        lead1 = models.Lead(full_name='High Score', stage='qualified', lead_score=42, email='high@example.com')
        lead2 = models.Lead(full_name='Low Score', stage='lead', lead_score=8, email='low@example.com')
        db.add_all([lead1, lead2])
        db.commit()
        db.refresh(lead1)
        db.refresh(lead2)

        queue = build_sales_playbook_queue(db, limit=10)
        assert queue['leads']
        assert queue['leads'][0]['lead_id'] == lead1.id

        single = build_sales_playbook(db, lead1)
        assert single['priority'] in {'urgent', 'high', 'medium', 'low', 'blocked'}
        assert single['steps']

    client = TestClient(app)
    resp = client.get('/api/v1/crm/playbook-queue?limit=10')
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body['leads']
    assert 'generated_at' in body
