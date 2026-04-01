from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app import models
from backend.app.database import SessionLocal


def test_upsell_cross_sell_trigger_dispatches_campaigns():
    client = TestClient(app)

    converted = client.post(
        '/api/v1/leads',
        json={
            'full_name': 'Upsell Lead',
            'email': 'upsell@example.com',
            'source': 'referral',
            'revenue_estimate': '$25K',
        },
    )
    assert converted.status_code == 200, converted.text
    converted_id = converted.json()['id']

    engaged = client.post(
        '/api/v1/leads',
        json={
            'full_name': 'Cross Sell Lead',
            'email': 'cross@example.com',
            'source': 'web',
            'revenue_estimate': '$9K',
        },
    )
    assert engaged.status_code == 200, engaged.text
    engaged_id = engaged.json()['id']

    for lead_id in (converted_id, engaged_id):
        prefs = client.patch(
            f'/api/v1/leads/{lead_id}/preferences',
            json={'marketing_consent': 'yes', 'unsubscribe': False},
        )
        assert prefs.status_code == 200, prefs.text

    to_converted = client.patch(f'/api/v1/leads/{converted_id}/stage', json={'stage': 'converted'})
    assert to_converted.status_code == 200, to_converted.text

    to_engaged = client.patch(f'/api/v1/leads/{engaged_id}/stage', json={'stage': 'engaged'})
    assert to_engaged.status_code == 200, to_engaged.text

    intent = client.post(
        '/api/v1/marketing/intent/event',
        json={
            'lead_id': engaged_id,
            'source': 'website',
            'signal_type': 'demo_request',
            'strength': 22,
        },
    )
    assert intent.status_code == 200, intent.text

    trigger = client.post(
        '/api/v1/marketing/campaigns/upsell-cross-sell/trigger',
        json={'limit': 50, 'performed_by': 'qa'},
    )
    assert trigger.status_code == 200, trigger.text
    body = trigger.json()

    assert body['campaign_type'] == 'upsell_cross_sell'
    assert body['triggered'] >= 1
    assert body['dispatched'] >= 1

    campaign_types = body['campaign_types']
    assert 'upsell' in campaign_types or 'cross_sell' in campaign_types

    with SessionLocal() as db:
        trigger_logs = (
            db.query(models.AuditLog)
            .filter(models.AuditLog.action.in_(['upsell_campaign_trigger', 'cross_sell_campaign_trigger']))
            .all()
        )
        assert trigger_logs

        event_logs = (
            db.query(models.AuditLog)
            .filter(models.AuditLog.action == 'automation_event')
            .all()
        )
        assert any('campaign.upsell.enqueue' in (row.detail or '') or 'campaign.cross_sell.enqueue' in (row.detail or '') for row in event_logs)
