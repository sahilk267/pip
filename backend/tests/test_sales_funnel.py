from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app import models
from backend.app.database import SessionLocal
from backend.app.services.sales_funnel import compute_sales_funnel_metrics


def test_stage_transitions_logged_and_listable():
    client = TestClient(app)

    lead_resp = client.post('/api/v1/leads', json={'full_name': 'Funnel Lead', 'source': 'web'})
    assert lead_resp.status_code == 200, lead_resp.text
    lead_id = lead_resp.json()['id']

    stage_resp = client.patch(
        f'/api/v1/leads/{lead_id}/stage',
        json={'stage': 'qualified', 'consented': 'yes'},
    )
    assert stage_resp.status_code == 200, stage_resp.text

    transitions_resp = client.get(f'/api/v1/leads/{lead_id}/transitions')
    assert transitions_resp.status_code == 200, transitions_resp.text
    rows = transitions_resp.json()
    assert len(rows) >= 2
    assert rows[0]['to_stage'] == 'lead'
    assert rows[-1]['to_stage'] == 'qualified'


def test_funnel_metrics_endpoint_and_service():
    with SessionLocal() as db:
        lead = models.Lead(full_name='Metric Lead', stage='converted')
        db.add(lead)
        db.commit()
        db.refresh(lead)

        now = datetime.now(timezone.utc)
        t1 = models.LeadStageTransition(
            lead_id=lead.id,
            from_stage=None,
            to_stage='lead',
            changed_at=now - timedelta(hours=6),
        )
        t2 = models.LeadStageTransition(
            lead_id=lead.id,
            from_stage='lead',
            to_stage='qualified',
            changed_at=now - timedelta(hours=4),
        )
        t3 = models.LeadStageTransition(
            lead_id=lead.id,
            from_stage='qualified',
            to_stage='converted',
            changed_at=now - timedelta(hours=1),
        )
        db.add_all([t1, t2, t3])
        db.commit()

        metrics = compute_sales_funnel_metrics(db, window_days=7)
        assert metrics['total_leads'] >= 1
        assert 'converted' in metrics['stage_counts']
        assert metrics['conversion_rates']

    client = TestClient(app)
    resp = client.get('/api/v1/crm/funnel?window_days=7')
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload['window_days'] == 7
    assert 'stage_counts' in payload
    assert 'conversion_rates' in payload
