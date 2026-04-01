from fastapi.testclient import TestClient

from backend.app.main import app


def test_marketing_analytics_overview_aggregates_events_and_conversions():
    client = TestClient(app)

    lead_1 = client.post(
        '/api/v1/leads',
        json={'full_name': 'Analytics Lead 1', 'email': 'a1@example.com', 'source': 'paid_ad'},
    )
    assert lead_1.status_code == 200, lead_1.text
    lead_1_id = lead_1.json()['id']

    lead_2 = client.post(
        '/api/v1/leads',
        json={'full_name': 'Analytics Lead 2', 'email': 'a2@example.com', 'source': 'referral'},
    )
    assert lead_2.status_code == 200, lead_2.text
    lead_2_id = lead_2.json()['id']

    converted = client.patch(
        f'/api/v1/leads/{lead_1_id}/stage',
        json={'stage': 'converted'},
    )
    assert converted.status_code == 200, converted.text

    auto_1 = client.post(
        '/api/v1/marketing/automation/event',
        json={
            'provider': 'hubspot',
            'event_type': 'campaign.sent',
            'payload': {'campaign_id': 'cmp-1'},
        },
    )
    assert auto_1.status_code == 200, auto_1.text

    auto_2 = client.post(
        '/api/v1/marketing/automation/event',
        json={
            'provider': 'mailchimp',
            'event_type': 'email.click',
            'payload': {'campaign_id': 'cmp-2'},
        },
    )
    assert auto_2.status_code == 200, auto_2.text

    intent_1 = client.post(
        '/api/v1/marketing/intent/event',
        json={
            'lead_id': lead_1_id,
            'source': 'google_ads',
            'signal_type': 'demo_request',
            'strength': 15,
        },
    )
    assert intent_1.status_code == 200, intent_1.text

    intent_2 = client.post(
        '/api/v1/marketing/intent/event',
        json={
            'lead_id': lead_2_id,
            'source': 'website',
            'signal_type': 'pricing_view',
            'strength': 8,
        },
    )
    assert intent_2.status_code == 200, intent_2.text

    overview = client.get('/api/v1/marketing/analytics', params={'window_days': 30})
    assert overview.status_code == 200, overview.text
    body = overview.json()

    assert body['window_days'] == 30
    assert body['total_automation_events'] == 2
    assert body['automation_events_by_provider']['hubspot'] == 1
    assert body['automation_events_by_provider']['mailchimp'] == 1
    assert body['automation_events_by_type']['campaign.sent'] == 1
    assert body['automation_events_by_type']['email.click'] == 1

    assert body['intent_signals_by_type']['demo_request'] == 1
    assert body['intent_signals_by_type']['pricing_view'] == 1
    assert body['intent_sources']['google_ads'] == 1
    assert body['intent_sources']['website'] == 1

    conversion_by_channel = {row['channel']: row for row in body['conversion_by_channel']}
    assert conversion_by_channel['paid']['leads'] >= 1
    assert conversion_by_channel['paid']['converted'] >= 1
    assert conversion_by_channel['paid']['conversion_rate'] > 0

    assert body['lead_attribution']['paid'] >= 1
    assert body['lead_attribution']['web'] >= 1
