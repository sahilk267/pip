from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app import models
from backend.app.database import SessionLocal


def test_marketing_campaign_triggers_nurture_and_reengagement_for_eligible_leads():
    client = TestClient(app)

    nurture_lead = client.post(
        '/api/v1/leads',
        json={'full_name': 'Nurture Lead', 'email': 'nurture@example.com', 'source': 'web'},
    )
    assert nurture_lead.status_code == 200, nurture_lead.text
    nurture_lead_id = nurture_lead.json()['id']

    prefs = client.patch(
        f'/api/v1/leads/{nurture_lead_id}/preferences',
        json={'marketing_consent': 'yes', 'unsubscribe': False},
    )
    assert prefs.status_code == 200, prefs.text

    intent = client.post(
        '/api/v1/marketing/intent/event',
        json={
            'lead_id': nurture_lead_id,
            'source': 'website',
            'signal_type': 'download',
            'strength': 10,
        },
    )
    assert intent.status_code == 200, intent.text

    reengage_lead = client.post(
        '/api/v1/leads',
        json={'full_name': 'Reengage Lead', 'email': 'reengage@example.com', 'source': 'event'},
    )
    assert reengage_lead.status_code == 200, reengage_lead.text
    reengage_lead_id = reengage_lead.json()['id']

    prefs_re = client.patch(
        f'/api/v1/leads/{reengage_lead_id}/preferences',
        json={'marketing_consent': 'yes', 'unsubscribe': False},
    )
    assert prefs_re.status_code == 200, prefs_re.text

    stage = client.patch(
        f'/api/v1/leads/{reengage_lead_id}/stage',
        json={'stage': 'lost'},
    )
    assert stage.status_code == 200, stage.text

    blocked_lead = client.post(
        '/api/v1/leads',
        json={'full_name': 'Blocked Lead', 'email': 'blocked@example.com', 'source': 'paid_ad'},
    )
    assert blocked_lead.status_code == 200, blocked_lead.text
    blocked_lead_id = blocked_lead.json()['id']

    blocked_prefs = client.patch(
        f'/api/v1/leads/{blocked_lead_id}/preferences',
        json={'marketing_consent': 'yes', 'unsubscribe': True},
    )
    assert blocked_prefs.status_code == 200, blocked_prefs.text

    trigger = client.post(
        '/api/v1/marketing/campaigns/trigger',
        json={'campaign_type': 'auto', 'limit': 50, 'performed_by': 'qa'},
    )
    assert trigger.status_code == 200, trigger.text

    body = trigger.json()
    assert body['campaign_type'] == 'auto'
    assert body['triggered'] >= 2

    targeted = {row['lead_id']: row for row in body['targets']}
    assert nurture_lead_id in targeted
    assert reengage_lead_id in targeted
    assert blocked_lead_id not in targeted

    assert targeted[nurture_lead_id]['campaign_type'] == 'nurture'
    assert targeted[reengage_lead_id]['campaign_type'] == 'reengagement'

    with SessionLocal() as db:
        campaign_audits = (
            db.query(models.AuditLog)
            .filter(models.AuditLog.action.in_(['nurture_campaign_trigger', 'reengagement_campaign_trigger']))
            .all()
        )
        assert campaign_audits
