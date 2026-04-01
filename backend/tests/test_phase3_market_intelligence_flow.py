from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_market_intelligence_ingest_score_alert_and_apis():
    ingest = client.post(
        '/api/v1/market-intelligence/signals/ingest',
        json={
            'performed_by': 'market-cron',
            'events': [
                {
                    'source_name': 'forumwatch',
                    'signal_type': 'price_drop',
                    'product_name': 'Solar Inverter 5KW',
                    'region': 'IN',
                    'raw_score': 100.0,
                    'sentiment': 'positive',
                    'price_drop_pct': 80.0,
                    'demand_spike_pct': 300.0,
                    'signal_metadata': {'url': 'https://example.com/forum/topic-1'},
                },
                {
                    'source_name': 'socialpulse',
                    'signal_type': 'trend',
                    'product_name': 'Solar Inverter 5KW',
                    'region': 'IN',
                    'raw_score': 68.0,
                    'sentiment': 'neutral',
                    'price_drop_pct': 10.0,
                    'demand_spike_pct': 90.0,
                    'signal_metadata': {'tag': '#solar'},
                },
            ],
        },
    )
    assert ingest.status_code == 200, ingest.text
    payload = ingest.json()
    assert payload['ingested'] == 2
    assert payload['opportunities_detected'] >= 1
    assert payload['alerts_created'] >= 1

    opps = client.get('/api/v1/market-intelligence/opportunities', params={'region': 'IN', 'min_score': 70})
    assert opps.status_code == 200, opps.text
    opp_rows = opps.json()
    assert len(opp_rows) >= 1
    assert any(float(row['opportunity_score']) >= 70.0 for row in opp_rows)

    rel = client.get('/api/v1/market-intelligence/sources/reliability')
    assert rel.status_code == 200, rel.text
    rel_rows = rel.json()
    assert any(row['source_name'] == 'forumwatch' for row in rel_rows)
    assert any(row['source_name'] == 'socialpulse' for row in rel_rows)

    summary = client.get('/api/v1/market-intelligence/summary', params={'region': 'IN'})
    assert summary.status_code == 200, summary.text
    summary_payload = summary.json()
    assert summary_payload['total_opportunities'] >= 1
    assert summary_payload['average_score'] > 0

    dashboard = client.get('/api/v1/monitoring/dashboard')
    assert dashboard.status_code == 200, dashboard.text
    alerts = dashboard.json().get('alerts', [])
    assert any(str(a.get('category')) == 'market-intelligence' for a in alerts)


def test_market_opportunity_validation_transitions_and_precision_metrics():
    ingest = client.post(
        '/api/v1/market-intelligence/signals/ingest',
        json={
            'performed_by': 'market-validator',
            'events': [
                {
                    'source_name': 'trendpulse',
                    'signal_type': 'bulk_clearance',
                    'product_name': 'Industrial Valve X2',
                    'region': 'EU',
                    'raw_score': 96.0,
                    'sentiment': 'positive',
                    'price_drop_pct': 55.0,
                    'demand_spike_pct': 250.0,
                },
                {
                    'source_name': 'marketbuzz',
                    'signal_type': 'trend',
                    'product_name': 'Industrial Valve Y1',
                    'region': 'EU',
                    'raw_score': 98.0,
                    'sentiment': 'positive',
                    'price_drop_pct': 45.0,
                    'demand_spike_pct': 260.0,
                },
            ],
        },
    )
    assert ingest.status_code == 200, ingest.text

    opps = client.get('/api/v1/market-intelligence/opportunities', params={'region': 'EU', 'min_score': 55})
    assert opps.status_code == 200, opps.text
    rows = opps.json()
    assert len(rows) >= 2
    first_id = int(rows[0]['id'])
    second_id = int(rows[1]['id'])

    reject_missing_reason = client.patch(
        f'/api/v1/market-intelligence/opportunities/{first_id}/validate',
        json={
            'decision': 'rejected',
            'validator_type': 'human',
            'validated_by': 'qa-reviewer',
        },
    )
    assert reject_missing_reason.status_code == 400

    accept = client.patch(
        f'/api/v1/market-intelligence/opportunities/{first_id}/validate',
        json={
            'decision': 'validated',
            'validator_type': 'human',
            'validation_notes': 'Confirmed against partner purchase intent',
            'validated_by': 'qa-reviewer',
        },
    )
    assert accept.status_code == 200, accept.text
    accepted_payload = accept.json()
    assert accepted_payload['from_status'] in {'detected', 'validated', 'rejected'}
    assert accepted_payload['to_status'] == 'validated'

    reject = client.patch(
        f'/api/v1/market-intelligence/opportunities/{second_id}/validate',
        json={
            'decision': 'rejected',
            'validator_type': 'ai',
            'validation_score': 0.22,
            'rejection_reason': 'Duplicate signal with no sustained demand',
            'validated_by': 'validator-bot',
        },
    )
    assert reject.status_code == 200, reject.text
    rejected_payload = reject.json()
    assert rejected_payload['to_status'] == 'rejected'
    assert rejected_payload['rejection_reason'] == 'Duplicate signal with no sustained demand'

    history = client.get(f'/api/v1/market-intelligence/opportunities/{second_id}/validations')
    assert history.status_code == 200, history.text
    history_rows = history.json()
    assert len(history_rows) >= 1
    assert history_rows[0]['to_status'] == 'rejected'

    metrics = client.get('/api/v1/market-intelligence/opportunities/validation/metrics', params={'lookback_days': 30, 'region': 'EU'})
    assert metrics.status_code == 200, metrics.text
    metrics_payload = metrics.json()
    assert metrics_payload['total_validations'] >= 2
    assert metrics_payload['approved'] >= 1
    assert metrics_payload['rejected'] >= 1
    assert 0.0 <= float(metrics_payload['precision']) <= 1.0
    assert 0.0 <= float(metrics_payload['false_positive_rate']) <= 1.0
    assert any(row['region'] == 'EU' for row in metrics_payload['by_region'])
