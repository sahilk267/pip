from fastapi.testclient import TestClient

from backend.app.main import app


def test_b2b_lead_enrichment_sets_revenue_and_decision_maker():
    client = TestClient(app)

    r = client.post(
        '/api/v1/leads',
        json={
            'full_name': 'Contact One',
            'company': 'Aurora Supply Partners',
            'source': 'web',
        },
    )
    assert r.status_code == 200, r.text
    lead_id = r.json()['id']

    r2 = client.post('/api/v1/enrichment/leads/b2b?limit=50')
    assert r2.status_code == 200, r2.text

    r3 = client.get('/api/v1/leads?limit=10')
    assert r3.status_code == 200, r3.text
    leads = r3.json()
    updated = next(l for l in leads if l['id'] == lead_id)

    assert updated['revenue_estimate'] == '$12M'
    assert updated['decision_maker'] == 'Ravi Patel'
    assert updated['b2b_score'] == 'A'

