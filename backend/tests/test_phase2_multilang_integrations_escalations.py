from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_message_template_create_and_localize():
    """Test creating and retrieves localized message templates."""
    payload = {
        'template_code': 'order_confirmation',
        'template_type': 'email',
        'default_locale': 'en',
        'translations': {
            'en': {
                'subject': 'Order Confirmed #{order_id}',
                'body': 'Your order for {product_name} has been confirmed.',
            },
            'hi': {
                'subject': 'ऑर्डर की पुष्टि #{order_id}',
                'body': 'आपके {product_name} के लिए ऑर्डर की पुष्टि हो गई है।',
            },
        },
    }
    
    create_res = client.post('/api/v1/messages/templates', json=payload)
    assert create_res.status_code == 200
    assert create_res.json()['template_code'] == 'order_confirmation'
    assert 'en' in create_res.json()['translations']
    assert 'hi' in create_res.json()['translations']

    # Retrieve template
    fetch_res = client.get('/api/v1/messages/templates/order_confirmation')
    assert fetch_res.status_code == 200
    assert fetch_res.json()['template_code'] == 'order_confirmation'

    # Get localized with variable substitution
    loc_res = client.get(
        '/api/v1/messages/templates/order_confirmation/localized',
        params={'locale': 'hi', 'order_id': '12345', 'product_name': 'Widget Pro'},
    )
    assert loc_res.status_code == 200
    assert 'ऑर्डर' in loc_res.json()['message']['subject']


def test_message_template_list():
    """Test listing message templates by type."""
    create_res = client.post('/api/v1/messages/templates', json={
        'template_code': 'shipment_notification',
        'template_type': 'sms',
        'translations': {'en': {'body': 'Your shipment is on the way.'}},
    })
    assert create_res.status_code == 200

    # List by template_type
    list_res = client.get('/api/v1/messages/templates', params={'template_type': 'sms'})
    assert list_res.status_code == 200
    assert any(t['template_code'] == 'shipment_notification' for t in list_res.json())


def test_external_integration_register_and_list():
    """Test registering external system integrations."""
    payload = {
        'name': 'Salesforce CRM',
        'provider': 'salesforce',
        'entity_sync_types': ['order', 'lead', 'deal'],
        'api_endpoint': 'https://api.salesforce.com/v1',
        'sync_direction': 'bidirectional',
        'field_mappings': {
            'order.id': 'Account.Order_ID__c',
            'lead.email': 'Lead.Email',
        },
    }
    
    create_res = client.post('/api/v1/integrations/external', json=payload)
    assert create_res.status_code == 200
    integration_id = create_res.json()['id']
    assert create_res.json()['status'] == 'active'

    # Fetch integration
    fetch_res = client.get(f'/api/v1/integrations/external/{integration_id}')
    assert fetch_res.status_code == 200
    assert fetch_res.json()['name'] == 'Salesforce CRM'

    # List all integrations
    list_res = client.get('/api/v1/integrations/external', params={'provider': 'salesforce'})
    assert list_res.status_code == 200
    assert any(i['name'] == 'Salesforce CRM' for i in list_res.json())

    # Update integration status
    update_res = client.patch(f'/api/v1/integrations/external/{integration_id}', json={
        'status': 'paused',
    })
    assert update_res.status_code == 200
    assert update_res.json()['status'] == 'paused'


def test_integration_sync_record_and_history():
    """Test recording and querying sync history."""
    # Register an integration first
    int_res = client.post('/api/v1/integrations/external', json={
        'name': 'HubSpot',
        'provider': 'hubspot',
        'entity_sync_types': ['order'],
    })
    integration_id = int_res.json()['id']

    # Record a sync
    sync_res = client.post(
        '/api/v1/integrations/sync-records',
        params={
            'integration_id': integration_id,
            'entity_type': 'order',
            'entity_id': 123,
            'sync_direction': 'outbound',
            'external_id': 'hubspot-order-456',
            'status': 'synced',
        },
    )
    assert sync_res.status_code == 200
    assert sync_res.json()['external_id'] == 'hubspot-order-456'

    # Record a failed sync
    fail_res = client.post(
        '/api/v1/integrations/sync-records',
        params={
            'integration_id': integration_id,
            'entity_type': 'order',
            'entity_id': 124,
            'status': 'failed',
            'error_message': 'API timeout',
        },
    )
    assert fail_res.status_code == 200

    # List sync records
    list_res = client.get(
        '/api/v1/integrations/sync-records',
        params={'integration_id': integration_id, 'status': 'synced'},
    )
    assert list_res.status_code == 200
    assert len([r for r in list_res.json() if r['status'] == 'synced']) >= 1


def test_escalation_rule_create_and_evaluate():
    """Test creating and evaluating escalation rules."""
    payload = {
        'rule_code': 'order_delay_escalation',
        'rule_type': 'order_delay',
        'entity_type': 'order',
        'priority': 3,
        'conditions': [
            {
                'field': 'days_pending',
                'operator': 'gte',
                'value': 5,
            },
        ],
        'actions': [
            {
                'action_type': 'notify',
                'target': 'manager',
                'message': 'Order delayed beyond SLA',
            },
        ],
        'notify_roles': ['sales', 'manager'],
        'sla_hours': 120,
    }
    
    create_res = client.post('/api/v1/escalations/rules', json=payload)
    assert create_res.status_code == 200
    rule_id = create_res.json()['id']
    assert create_res.json()['status'] == 'active'

    # Fetch rule
    fetch_res = client.get(f'/api/v1/escalations/rules/{rule_id}')
    assert fetch_res.status_code == 200
    assert fetch_res.json()['rule_code'] == 'order_delay_escalation'

    # List rules by entity_type
    list_res = client.get('/api/v1/escalations/rules', params={'entity_type': 'order'})
    assert list_res.status_code == 200
    assert any(r['rule_code'] == 'order_delay_escalation' for r in list_res.json())

    # Update rule status
    update_res = client.patch(f'/api/v1/escalations/rules/{rule_id}', json={
        'status': 'paused',
    })
    assert update_res.status_code == 200
    assert update_res.json()['status'] == 'paused'


def test_escalation_trigger_and_resolve():
    """Test triggering and resolving escalations."""
    # Create a rule first
    rule_res = client.post('/api/v1/escalations/rules', json={
        'rule_code': 'no_response_escalation',
        'rule_type': 'no_response',
        'entity_type': 'order',
        'conditions': [{'field': 'hours_waiting', 'operator': 'gte', 'value': 24}],
        'actions': [{'action_type': 'notify', 'target': 'support'}],
    })
    rule_id = rule_res.json()['id']

    # Trigger escalation
    trigger_res = client.post(
        '/api/v1/escalations/trigger',
        params={
            'rule_id': rule_id,
            'entity_type': 'order',
            'entity_id': 999,
            'trigger_reason': 'customer_waiting_24h',
            'severity': 'critical',
        },
    )
    assert trigger_res.status_code == 200
    escalation_id = trigger_res.json()['id']
    assert trigger_res.json()['status'] == 'open'
    assert trigger_res.json()['severity'] == 'critical'

    # List escalations
    list_res = client.get(
        '/api/v1/escalations/records',
        params={'rule_id': rule_id},
    )
    assert list_res.status_code == 200
    assert any(r['id'] == escalation_id for r in list_res.json())

    # Resolve escalation
    resolve_res = client.patch(
        f'/api/v1/escalations/records/{escalation_id}/resolve',
        params={'resolution_notes': 'Customer contacted, issue resolved'},
    )
    assert resolve_res.status_code == 200
    assert resolve_res.json()['status'] == 'resolved'
    assert resolve_res.json()['resolved_at'] is not None


def test_escalation_filter_by_severity_and_status():
    """Test filtering escalation records by severity and status."""
    rule_res = client.post('/api/v1/escalations/rules', json={
        'rule_code': 'critical_price_deviation',
        'rule_type': 'price_deviation',
        'entity_type': 'order',
        'conditions': [{'field': 'price_variance_pct', 'operator': 'gte', 'value': 20}],
        'actions': [{'action_type': 'alert'}],
    })
    rule_id = rule_res.json()['id']

    # Trigger critical escalation
    trigger1 = client.post(
        '/api/v1/escalations/trigger',
        params={
            'rule_id': rule_id,
            'entity_type': 'order',
            'entity_id': 1001,
            'severity': 'critical',
        },
    )
    escalation1_id = trigger1.json()['id']

    # Trigger warning escalation
    trigger2 = client.post(
        '/api/v1/escalations/trigger',
        params={
            'rule_id': rule_id,
            'entity_type': 'order',
            'entity_id': 1002,
            'severity': 'warning',
        },
    )

    # Resolve first escalation
    client.patch(f'/api/v1/escalations/records/{escalation1_id}/resolve')

    # List only critical, unresolved
    list_res = client.get(
        '/api/v1/escalations/records',
        params={'severity': 'critical', 'status': 'open'},
    )
    assert list_res.status_code == 200
    # Should not include the resolved critical one
    assert not any(r['id'] == escalation1_id for r in list_res.json())
