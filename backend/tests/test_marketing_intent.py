from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app import models
from backend.app.database import SessionLocal
from backend.app.services.marketing_intent import refresh_marketing_intent_scores


def test_marketing_intent_event_updates_lead_score_and_signals():
    client = TestClient(app)
    lead_resp = client.post(
        '/api/v1/leads',
        json={'full_name': 'Intent Lead', 'email': 'intent@example.com', 'source': 'web'},
    )
    assert lead_resp.status_code == 200, lead_resp.text
    lead_id = lead_resp.json()['id']

    intent_resp = client.post(
        '/api/v1/marketing/intent/event',
        json={
            'lead_id': lead_id,
            'source': 'paid_ad',
            'signal_type': 'demo_request',
            'strength': 12,
            'metadata': {'campaign': 'spring-demo'},
        },
    )
    assert intent_resp.status_code == 200, intent_resp.text
    body = intent_resp.json()
    assert body['lead_id'] == lead_id
    assert body['marketing_intent_score'] > 0
    assert body['lead_score'] > 0
    assert body['attribution_channel'] == 'paid'
    assert 'demo_request' in body['marketing_intent_data']



def test_refresh_marketing_intent_scores_recomputes_from_stored_data():
    with SessionLocal() as db:
        lead = models.Lead(
            full_name='Stored Intent Lead',
            stage='qualified',
            marketing_intent_data={
                'download': {'count': 2, 'strength_total': 4, 'last_source': 'web'}
            },
            marketing_intent_score=0,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)

        stats = refresh_marketing_intent_scores(db, limit=50)
        assert stats['scanned'] >= 1

        refreshed = db.query(models.Lead).filter(models.Lead.id == lead.id).one()
        assert refreshed.marketing_intent_score > 0
        assert refreshed.lead_score > 0
