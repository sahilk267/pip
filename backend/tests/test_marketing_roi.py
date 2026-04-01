from fastapi.testclient import TestClient

from backend.app.main import app


def test_marketing_campaign_roi_endpoint_returns_channel_metrics():
    client = TestClient(app)

    lead_paid = client.post(
        '/api/v1/leads',
        json={
            'full_name': 'ROI Paid Lead',
            'email': 'roi-paid@example.com',
            'source': 'paid_ad',
            'revenue_estimate': '$10K',
        },
    )
    assert lead_paid.status_code == 200, lead_paid.text
    lead_paid_id = lead_paid.json()['id']

    lead_web = client.post(
        '/api/v1/leads',
        json={
            'full_name': 'ROI Web Lead',
            'email': 'roi-web@example.com',
            'source': 'web',
            'revenue_estimate': '$8K',
        },
    )
    assert lead_web.status_code == 200, lead_web.text
    lead_web_id = lead_web.json()['id']

    for lead_id in (lead_paid_id, lead_web_id):
        prefs = client.patch(
            f'/api/v1/leads/{lead_id}/preferences',
            json={'marketing_consent': 'yes', 'unsubscribe': False},
        )
        assert prefs.status_code == 200, prefs.text

        intent = client.post(
            '/api/v1/marketing/intent/event',
            json={
                'lead_id': lead_id,
                'source': 'website',
                'signal_type': 'download',
                'strength': 8,
            },
        )
        assert intent.status_code == 200, intent.text

    # Dispatch creates automation events with provider/channel details.
    dispatch = client.post(
        '/api/v1/marketing/campaigns/dispatch',
        json={'campaign_type': 'auto', 'limit': 20, 'performed_by': 'qa'},
    )
    assert dispatch.status_code == 200, dispatch.text

    # Convert leads to produce attributable revenue in ROI window.
    converted_paid = client.patch(f'/api/v1/leads/{lead_paid_id}/stage', json={'stage': 'converted'})
    assert converted_paid.status_code == 200, converted_paid.text
    converted_web = client.patch(f'/api/v1/leads/{lead_web_id}/stage', json={'stage': 'converted'})
    assert converted_web.status_code == 200, converted_web.text

    roi = client.get('/api/v1/marketing/roi', params={'window_days': 30})
    assert roi.status_code == 200, roi.text
    body = roi.json()

    assert body['window_days'] == 30
    assert body['total_automation_events'] >= 1
    assert body['total_converted_leads'] >= 2
    assert body['estimated_spend'] > 0
    assert body['estimated_revenue'] > 0
    assert body['roi_by_channel']

    channels = {row['channel']: row for row in body['roi_by_channel']}
    assert 'web' in channels or 'paid' in channels
