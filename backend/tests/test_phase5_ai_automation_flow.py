"""Phase 5: AI Automation integration tests."""
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def _create_lead(full_name: str, email: str, source: str = 'web') -> int:
    res = client.post('/api/v1/leads', json={'full_name': full_name, 'email': email, 'source': source})
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def _create_order(lead_id: int, amount: float = 99.0, channel: str = 'website') -> int:
    res = client.post(
        '/api/v1/orders/b2c',
        json={
            'lead_id': lead_id,
            'source_channel': channel,
            'total_amount': amount,
            'currency': 'USD',
            'order_items': [{'name': 'Widget', 'sku': 'W1', 'quantity': 1, 'unit_price': amount}],
        },
    )
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def test_phase5_feedback_loop():
    lead_id = _create_lead('Feedback Phase5', 'feedback_phase5@test.com')
    order_id = _create_order(lead_id, amount=250.0)

    res = client.post(
        '/api/v1/automation/feedback-loop',
        json={
            'entity_type': 'order',
            'entity_id': order_id,
            'rating': 5,
            'outcome': 'positive',
            'comments': 'AI recommendation worked well',
            'performed_by': 'phase5_test',
        },
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload['entity_type'] == 'order'
    assert payload['entity_id'] == order_id
    assert payload['rating'] == 5


def test_phase5_explainability_endpoint():
    lead_id = _create_lead('Explain Phase5', 'explain_phase5@test.com')
    order_id = _create_order(lead_id, amount=550.0)

    res = client.get(
        '/api/v1/automation/explainability',
        params={'entity_type': 'order', 'entity_id': order_id, 'context': 'pricing decision'},
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload['entity_type'] == 'order'
    assert payload['entity_id'] == order_id
    assert 'explanation' in payload
    assert payload['confidence'] >= 0.0


def test_phase5_model_drift_status():
    res = client.get('/api/v1/automation/model-drift', params={'window_days': 30})
    assert res.status_code == 200, res.text
    payload = res.json()
    assert 'drift_score' in payload
    assert isinstance(payload['retrain_recommended'], bool)


def test_phase5_human_override_toggle():
    res = client.post(
        '/api/v1/automation/human-override',
        json={'action': 'enable', 'reason': 'manual review', 'performed_by': 'phase5_test'},
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload['override_enabled'] is True

    status_res = client.get('/api/v1/automation/human-override')
    assert status_res.status_code == 200, status_res.text
    status_payload = status_res.json()
    assert status_payload['override_enabled'] is True
    assert status_payload['performed_by'] == 'phase5_test'


def test_phase5_fraud_risk_assessment():
    lead_id = _create_lead('Fraud Phase5', 'fraud_phase5@test.com')
    order_id = _create_order(lead_id, amount=1800.0, channel='guest')

    res = client.get('/api/v1/automation/fraud-risk', params={'order_id': order_id})
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload['order_id'] == order_id
    assert payload['risk_level'] in {'low', 'medium', 'high'}


def test_phase5_inventory_forecast():
    lead_id = _create_lead('Forecast Phase5', 'forecast_phase5@test.com')
    _create_order(lead_id, amount=120.0, channel='website')

    res = client.get('/api/v1/automation/inventory/forecast', params={'sku': 'W1', 'days': 30})
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload['sku'] == 'W1'
    assert payload['forecast_days'] == 30


def test_phase5_personalized_recommendations():
    lead_id = _create_lead('Recommend Phase5', 'recommend_phase5@test.com')
    _create_order(lead_id, amount=300.0, channel='website')

    res = client.get('/api/v1/automation/recommendations/personalized', params={'lead_id': lead_id, 'limit': 3})
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload['lead_id'] == lead_id
    assert isinstance(payload['recommendations'], list)
    assert len(payload['recommendations']) >= 1


def test_phase5_chatbot_escalation():
    res = client.post(
        '/api/v1/automation/chatbot/escalation',
        json={
            'issue_description': 'Unable to complete automated checkout flow',
            'fallback_channel': 'human_support',
            'performed_by': 'phase5_chatbot',
        },
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload['status'] == 'escalated'
    assert payload['fallback_channel'] == 'human_support'


def test_phase5_data_ethics_review():
    res = client.get('/api/v1/automation/data-ethics', params={'scope': 'automation', 'region': 'EU'})
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload['scope'] == 'automation'
    assert payload['region'] == 'EU'
    assert payload['review_status'] == 'completed'


def test_phase5_competitor_monitoring():
    lead_id = _create_lead('Competitor Phase5', 'competitor_phase5@test.com')
    _create_order(lead_id, amount=200.0, channel='web')

    res = client.get('/api/v1/automation/competitor-monitoring', params={'product_name': 'Widget', 'limit': 5})
    assert res.status_code == 200, res.text
    payload = res.json()
    assert 'records' in payload
    assert isinstance(payload['records'], list)


def test_phase5_external_integrations_list():
    create_res = client.post(
        '/api/v1/integrations/external',
        json={
            'name': 'Phase5 Automation Export',
            'provider': 'custom',
            'entity_sync_types': ['orders', 'customers'],
            'api_endpoint': 'https://api.example.com/sync',
            'sync_direction': 'bidirectional',
            'field_mappings': {'order_id': 'ext_order_id'},
            'integration_metadata': {'phase': '5'},
        },
    )
    assert create_res.status_code == 200, create_res.text
    integration_id = int(create_res.json()['id'])

    res = client.get('/api/v1/automation/integrations/external', params={'provider': 'custom', 'status': 'active'})
    assert res.status_code == 200, res.text
    payload = res.json()
    assert isinstance(payload, list)
    assert any(entry['id'] == integration_id for entry in payload)


def test_phase5_dynamic_pricing():
    res = client.get('/api/v1/automation/dynamic-pricing', params={'sku': 'W1', 'base_price': 120.0, 'demand_factor': 1.4})
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload['sku'] == 'W1'
    assert payload['base_price'] == 120.0
    assert payload['recommended_price'] >= 0.0


def test_phase5_fraud_feedback_endpoint():
    lead_id = _create_lead('FraudFeedback Phase5', 'fraudfeedback_phase5@test.com')
    order_id = _create_order(lead_id, amount=500.0, channel='web')

    res = client.post(
        '/api/v1/automation/fraud-feedback',
        json={
            'order_id': order_id,
            'feedback': 'Order matched high-risk pattern',
            'severity': 'high',
            'performed_by': 'fraud_team',
        },
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload['order_id'] == order_id
    assert payload['severity'] == 'high'


def test_phase5_bias_fairness():
    res = client.get('/api/v1/automation/bias-fairness', params={'model_name': 'ai_auto'})
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload['model_name'] == 'ai_auto'
    assert 'bias_issues' in payload


def test_phase5_sales_process_enforcement():
    res = client.get('/api/v1/automation/sales-process/enforcement', params={'sales_rep_id': 1, 'entity_type': 'order', 'entity_id': 1})
    assert res.status_code == 200, res.text
    payload = res.json()
    assert 'compliance_issues' in payload
    assert 'recommended_actions' in payload
