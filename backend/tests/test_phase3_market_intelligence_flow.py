from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def _create_lead(full_name: str, email: str) -> int:
    res = client.post('/api/v1/leads', json={'full_name': full_name, 'email': email, 'source': 'web'})
    assert res.status_code == 200, res.text
    return int(res.json().get('id'))


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


def test_ab_testing_lead_scoring_and_gdpr_consent_workflow():
    # Create lead and enforce GDPR consent tracking
    lead_id = _create_lead('ConsentNorm User', 'consent-norm@example.com')

    consent_set = client.post(
        f'/api/v1/market-intelligence/leads/{lead_id}/consent',
        json={
            'lead_id': lead_id,
            'consent_type': 'email',
            'status': 'granted',
            'source': 'signup',
            'region': 'EU',
            'policy_version': '1.0',
            'notes': 'User opted in after GDPR notice',
        },
    )
    assert consent_set.status_code == 200, consent_set.text
    consent_payload = consent_set.json()
    assert consent_payload['lead_id'] == lead_id
    assert consent_payload['status'] == 'granted'

    consent_status = client.get(f'/api/v1/market-intelligence/leads/{lead_id}/consent')
    assert consent_status.status_code == 200, consent_status.text
    status_payload = consent_status.json()
    assert status_payload['consented'] is True
    assert status_payload['active'] is True

    # Update lead score
    score_res = client.post(
        f'/api/v1/market-intelligence/leads/{lead_id}/score',
        json={'lead_id': lead_id, 'score': 78, 'source': 'auto-model', 'notes': 'Automatic prioritization'},
    )
    assert score_res.status_code == 200, score_res.text
    score_payload = score_res.json()
    assert score_payload['lead_id'] == lead_id
    assert score_payload['new_score'] == 78

    # Create A/B test campaign
    ab_test_res = client.post(
        '/api/v1/market-intelligence/ab-tests',
        json={
            'name': 'email_subject_test',
            'description': 'Test subject lines for NVs',
            'target_segment': 'active_eu',
            'variants': {'A': 'Buy now', 'B': 'Limited offer'},
            'status': 'running',
        },
    )
    assert ab_test_res.status_code == 200, ab_test_res.text
    ab_test_payload = ab_test_res.json()
    campaign_id = int(ab_test_payload['id'])

    # Add A/B test results
    for variant, outcome in [('A', 'open'), ('A', 'click'), ('B', 'open'), ('B', 'conversion')]:
        result_res = client.post(
            '/api/v1/market-intelligence/ab-tests/results',
            json={'campaign_id': campaign_id, 'lead_id': lead_id, 'variant': variant, 'outcome': outcome},
        )
        assert result_res.status_code == 200, result_res.text

    metrics_res = client.get(f'/api/v1/market-intelligence/ab-tests/{campaign_id}/metrics')
    assert metrics_res.status_code == 200, metrics_res.text
    metrics_payload = metrics_res.json()
    assert metrics_payload['campaign_id'] == campaign_id
    assert 'variant_metrics' in metrics_payload
    assert metrics_payload['variant_metrics']['A']['total'] == 2
    assert metrics_payload['variant_metrics']['B']['total'] == 2


def test_campaign_fatigue_and_feedback_loop():
    lead_id = _create_lead('Fatigue User', 'fatigue@example.com')

    fatigue_res = client.post('/api/v1/market-intelligence/campaign-fatigue', json={
        'lead_id': lead_id,
        'increment_by': 1,
        'notes': 'Initial outreach',
    })
    assert fatigue_res.status_code == 200, fatigue_res.text
    fatigue_payload = fatigue_res.json()
    assert fatigue_payload['lead_id'] == lead_id
    assert fatigue_payload['outreach_count'] == 1
    assert fatigue_payload['status'] == 'active'

    # Simulate high frequency trigger
    for i in range(5):
        resp = client.post('/api/v1/market-intelligence/campaign-fatigue', json={'lead_id': lead_id, 'increment_by': 1})
        assert resp.status_code == 200

    status_res = client.get('/api/v1/market-intelligence/campaign-fatigue', params={'lead_id': lead_id})
    assert status_res.status_code == 200
    status_payload = status_res.json()
    assert len(status_payload) == 1
    assert status_payload[0]['status'] == 'throttled'

    # record automated feedback loop event
    feedback_res = client.post('/api/v1/market-intelligence/feedback-loop', json={
        'lead_id': lead_id,
        'event_type': 'conversion',
        'event_value': 1.0,
        'event_details': 'Campaign auto-feedback event recorded',
    })
    assert feedback_res.status_code == 200
    feedback_payload = feedback_res.json()
    assert feedback_payload['event_type'] == 'conversion'

    feedback_list = client.get('/api/v1/market-intelligence/feedback-loop', params={'lead_id': lead_id})
    assert feedback_list.status_code == 200
    assert len(feedback_list.json()) >= 1


def test_lead_assignment_and_abm_metrics():
    lead_id = _create_lead('ABM User', 'abm-user@example.com')

    rep_res = client.post('/api/v1/market-intelligence/sales-reps', json={'name': 'Alice Rep', 'email': 'alice@example.com', 'team': 'Enterprise'})
    assert rep_res.status_code == 200
    rep_id = int(rep_res.json()['id'])

    assign_res = client.post('/api/v1/market-intelligence/lead-assignments', json={'lead_id': lead_id, 'sales_rep_id': rep_id, 'assignment_notes': 'Initial assignment'})
    assert assign_res.status_code == 200
    assign_payload = assign_res.json()
    assert assign_payload['lead_id'] == lead_id
    assert assign_payload['sales_rep_id'] == rep_id

    leadership = client.get('/api/v1/market-intelligence/lead-assignments', params={'lead_id': lead_id})
    assert leadership.status_code == 200
    assert len(leadership.json()) >= 1

    abm_res = client.post('/api/v1/market-intelligence/abm-metrics', json={'region': 'GLOBAL', 'account_segment': 'enterprise'})
    assert abm_res.status_code == 200
    abm_payload = abm_res.json()
    assert abm_payload['region'] == 'GLOBAL'
    assert abm_payload['account_segment'] == 'enterprise'

    abm_list = client.get('/api/v1/market-intelligence/abm-metrics', params={'region': 'GLOBAL'})
    assert abm_list.status_code == 200
    assert len(abm_list.json()) >= 1




def test_paid_api_integration_source_ingest_and_history():
    # Register paid source
    source_res = client.post(
        '/api/v1/market-intelligence/paid-sources',
        json={
            'name': 'Digital Insights Pro',
            'endpoint': 'https://api.paid-intel.example/v1/signals',
            'api_key': 'secret-1234',
            'active': True,
            'polling_interval_minutes': 60,
            'source_metadata': {'contract': 'c-001'},
        },
    )
    assert source_res.status_code == 200, source_res.text
    source_payload = source_res.json()
    source_id = int(source_payload['id'])

    list_res = client.get('/api/v1/market-intelligence/paid-sources')
    assert list_res.status_code == 200, list_res.text
    assert any(src['id'] == source_id for src in list_res.json())

    ingest_res = client.post(f'/api/v1/market-intelligence/paid-sources/{source_id}/ingest')
    assert ingest_res.status_code == 200, ingest_res.text
    ingest_payload = ingest_res.json()
    assert ingest_payload['source_id'] == source_id
    assert ingest_payload['events_fetched'] >= 1
    assert ingest_payload['opportunities_created'] >= 1

    logs_res = client.get(f'/api/v1/market-intelligence/paid-sources/{source_id}/ingestion-logs')
    assert logs_res.status_code == 200, logs_res.text
    logs_payload = logs_res.json()
    assert len(logs_payload) >= 1

    opps_res = client.get('/api/v1/market-intelligence/opportunities', params={'region': 'GLOBAL', 'min_score': 50})
    assert opps_res.status_code == 200, opps_res.text
    assert len(opps_res.json()) >= 1


def _create_sales_rep(name: str, email: str) -> int:
    res = client.post('/api/v1/market-intelligence/sales-reps', json={'name': name, 'email': email, 'team': 'Field'})
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def _create_opportunity_for_tests(product_name: str = 'Test Product') -> int:
    ingest = client.post(
        '/api/v1/market-intelligence/signals/ingest',
        json={
            'performed_by': 'test-suite',
            'events': [
                {
                    'source_name': 'qa-source',
                    'signal_type': 'trend',
                    'product_name': product_name,
                    'region': 'GLOBAL',
                    'raw_score': 98.0,
                    'sentiment': 'positive',
                    'price_drop_pct': 40.0,
                    'demand_spike_pct': 250.0,
                }
            ],
        },
    )
    assert ingest.status_code == 200, ingest.text
    opps = client.get('/api/v1/market-intelligence/opportunities', params={'region': 'GLOBAL', 'min_score': 55})
    assert opps.status_code == 200, opps.text
    rows = opps.json()
    assert len(rows) >= 1
    return int(rows[0]['id'])


def test_sales_cadence_endpoints():
    lead_id = _create_lead('Cadence User', 'cadence-user@example.com')
    rep_id = _create_sales_rep('Cadence Rep', 'cadence-rep@example.com')

    created = client.post(
        '/api/v1/market-intelligence/sales-cadence',
        json={
            'sales_rep_id': rep_id,
            'lead_id': lead_id,
            'cadence_step': 'follow_up_1',
            'status': 'scheduled',
            'notes': 'Schedule first follow up',
        },
    )
    assert created.status_code == 200, created.text
    payload = created.json()
    assert payload['sales_rep_id'] == rep_id
    assert payload['lead_id'] == lead_id

    listed = client.get('/api/v1/market-intelligence/sales-cadence', params={'lead_id': lead_id})
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) >= 1


def test_rep_performance_endpoints_with_forecast():
    lead_id = _create_lead('Forecast Lead', 'forecast-lead@example.com')
    rep_id = _create_sales_rep('Forecast Rep', 'forecast-rep@example.com')
    opportunity_id = _create_opportunity_for_tests('Forecast Product')

    wl = client.post(
        '/api/v1/market-intelligence/win-loss',
        json={
            'opportunity_id': opportunity_id,
            'lead_id': lead_id,
            'sales_rep_id': rep_id,
            'outcome': 'win',
            'reason': 'Strong urgency and pricing fit',
            'recorded_by': 'qa',
        },
    )
    assert wl.status_code == 200, wl.text

    perf = client.post(
        '/api/v1/market-intelligence/rep-performance',
        json={
            'sales_rep_id': rep_id,
            'period_start': '2026-04-01T00:00:00Z',
            'period_end': '2026-04-30T23:59:59Z',
            'quota_target': 120000.0,
            'revenue_achieved': 80000.0,
        },
    )
    assert perf.status_code == 200, perf.text
    perf_payload = perf.json()
    assert perf_payload['sales_rep_id'] == rep_id
    assert float(perf_payload['forecast_revenue']) >= 0.0

    listed = client.get('/api/v1/market-intelligence/rep-performance', params={'sales_rep_id': rep_id})
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) >= 1


def test_win_loss_endpoints():
    lead_id = _create_lead('WinLoss Lead', 'winloss-lead@example.com')
    rep_id = _create_sales_rep('WinLoss Rep', 'winloss-rep@example.com')
    opportunity_id = _create_opportunity_for_tests('WinLoss Product')

    created = client.post(
        '/api/v1/market-intelligence/win-loss',
        json={
            'opportunity_id': opportunity_id,
            'lead_id': lead_id,
            'sales_rep_id': rep_id,
            'outcome': 'loss',
            'reason': 'Lead paused budget cycle',
            'recorded_by': 'qa',
        },
    )
    assert created.status_code == 200, created.text
    payload = created.json()
    assert payload['outcome'] == 'loss'

    listed = client.get('/api/v1/market-intelligence/win-loss', params={'sales_rep_id': rep_id, 'outcome': 'loss'})
    assert listed.status_code == 200, listed.text
    assert any(row['outcome'] == 'loss' for row in listed.json())


def test_marketing_funnel_analytics_endpoint():
    lead_id = _create_lead('Funnel Lead', 'funnel-lead@example.com')
    for event_type in ['view', 'open', 'click', 'conversion']:
        res = client.post(
            '/api/v1/market-intelligence/feedback-loop',
            json={'lead_id': lead_id, 'event_type': event_type, 'event_value': 1.0, 'event_details': 'funnel test'},
        )
        assert res.status_code == 200, res.text

    analytics = client.get('/api/v1/market-intelligence/marketing-funnel', params={'lookback_days': 30})
    assert analytics.status_code == 200, analytics.text
    payload = analytics.json()
    assert payload['awareness'] >= 1
    assert payload['engagement'] >= 1
    assert payload['conversion'] >= 1
    assert 0.0 <= float(payload['conversion_rate']) <= 1.0


def test_phase3_regional_legal_review_checklist_endpoints():
    template_res = client.get('/api/v1/market-intelligence/legal-review/template', params={'region': 'EU'})
    assert template_res.status_code == 200, template_res.text
    template_payload = template_res.json()
    assert template_payload['region'] == 'EU'
    assert 'GDPR' in template_payload['regulations']
    assert 'GDPR' in template_payload['templates']
    assert len(template_payload['templates']['GDPR']) >= 1

    checklist_items = template_payload['templates']['GDPR']
    create_res = client.post(
        '/api/v1/market-intelligence/legal-review/records',
        json={
            'entity_type': 'campaign',
            'entity_id': 101,
            'region': 'EU',
            'regulation': 'GDPR',
            'checklist_items': checklist_items,
            'reviewer': 'legal-team',
            'status': 'approved',
            'notes': 'Checklist completed for launch campaign',
        },
    )
    assert create_res.status_code == 200, create_res.text
    create_payload = create_res.json()
    assert create_payload['regulation'] == 'GDPR'
    assert create_payload['status'] == 'approved'

    list_res = client.get('/api/v1/market-intelligence/legal-review/records', params={'region': 'EU', 'regulation': 'GDPR'})
    assert list_res.status_code == 200, list_res.text
    assert any(row['id'] == create_payload['id'] for row in list_res.json())


def test_phase3_multi_language_message_template_endpoints():
    create_res = client.post(
        '/api/v1/market-intelligence/i18n/templates',
        json={
            'template_code': 'phase3_launch_notice',
            'template_type': 'campaign',
            'default_locale': 'en',
            'translations': {
                'en': {
                    'subject': 'Launch update for {product}',
                    'body': 'Campaign is active in {region}.',
                },
                'hi': {
                    'subject': '{product} ke liye update',
                    'body': '{region} mein campaign active hai.',
                },
            },
            'usage_metadata': {'team': 'marketing'},
        },
    )
    assert create_res.status_code == 200, create_res.text
    payload = create_res.json()
    assert payload['template_code'] == 'phase3_launch_notice'

    localized_res = client.get(
        '/api/v1/market-intelligence/i18n/templates/phase3_launch_notice/localized',
        params={'locale': 'hi', 'product': 'Solar Kit', 'region': 'IN'},
    )
    assert localized_res.status_code == 200, localized_res.text
    localized_payload = localized_res.json()
    assert localized_payload['locale'] == 'hi'
    assert 'Solar Kit' in localized_payload['message']['subject']
    assert 'IN' in localized_payload['message']['body']

    list_res = client.get('/api/v1/market-intelligence/i18n/templates', params={'template_type': 'campaign'})
    assert list_res.status_code == 200, list_res.text
    assert any(row['template_code'] == 'phase3_launch_notice' for row in list_res.json())


def test_phase3_external_integration_endpoints():
    create_res = client.post(
        '/api/v1/market-intelligence/integrations/external',
        json={
            'name': 'HubSpot Bridge',
            'provider': 'hubspot',
            'entity_sync_types': ['lead', 'campaign'],
            'api_endpoint': 'https://api.hubapi.com/crm/v3/objects',
            'sync_direction': 'bidirectional',
            'field_mappings': {'lead_email': 'email'},
            'integration_metadata': {'scope': 'phase3'},
        },
    )
    assert create_res.status_code == 200, create_res.text
    integration = create_res.json()
    integration_id = int(integration['id'])
    assert integration['provider'] == 'hubspot'

    sync_res = client.post(
        f'/api/v1/market-intelligence/integrations/external/{integration_id}/sync',
        params={
            'entity_type': 'lead',
            'entity_id': 321,
            'sync_direction': 'outbound',
            'status': 'synced',
            'external_id': 'hs-321',
        },
    )
    assert sync_res.status_code == 200, sync_res.text
    sync_payload = sync_res.json()
    assert sync_payload['integration_id'] == integration_id
    assert sync_payload['status'] == 'synced'

    list_res = client.get('/api/v1/market-intelligence/integrations/external', params={'provider': 'hubspot'})
    assert list_res.status_code == 200, list_res.text
    assert any(row['id'] == integration_id for row in list_res.json())

    record_res = client.get('/api/v1/market-intelligence/integrations/sync-records', params={'integration_id': integration_id})
    assert record_res.status_code == 200, record_res.text
    assert any(row['integration_id'] == integration_id for row in record_res.json())


def test_phase3_escalation_playbook_endpoints():
    create_res = client.post(
        '/api/v1/market-intelligence/escalation-playbook/rules',
        json={
            'rule_code': 'phase3_campaign_failure',
            'rule_type': 'automatic',
            'entity_type': 'campaign',
            'conditions': [
                {'field': 'failure_rate', 'operator': 'gte', 'value': 0.5},
            ],
            'actions': [
                {'action_type': 'notify', 'target': 'ops-manager', 'message': 'Failure threshold exceeded'},
            ],
            'priority': 8,
            'notify_roles': ['ops', 'legal'],
            'sla_hours': 6,
            'rule_metadata': {'phase': 3},
        },
    )
    assert create_res.status_code == 200, create_res.text
    rule_payload = create_res.json()
    rule_id = int(rule_payload['id'])
    assert rule_payload['rule_code'] == 'phase3_campaign_failure'

    trigger_res = client.post(
        '/api/v1/market-intelligence/escalation-playbook/trigger',
        params={
            'rule_id': rule_id,
            'entity_type': 'campaign',
            'entity_id': 404,
            'trigger_reason': 'Compliance incident detected',
            'severity': 'critical',
        },
    )
    assert trigger_res.status_code == 200, trigger_res.text
    trigger_payload = trigger_res.json()
    assert trigger_payload['rule_id'] == rule_id
    assert trigger_payload['status'] == 'open'

    rules_res = client.get('/api/v1/market-intelligence/escalation-playbook/rules', params={'entity_type': 'campaign'})
    assert rules_res.status_code == 200, rules_res.text
    assert any(row['id'] == rule_id for row in rules_res.json())

    records_res = client.get('/api/v1/market-intelligence/escalation-playbook/records', params={'rule_id': rule_id})
    assert records_res.status_code == 200, records_res.text
    assert any(row['rule_id'] == rule_id for row in records_res.json())


def test_phase3_ai_model_governance_records_endpoints():
    create_res = client.post(
        '/api/v1/market-intelligence/ai-governance/models',
        json={
            'model_name': 'market-opportunity-ranker',
            'model_type': 'opportunity',
            'model_version': '3.1.0',
            'approval_required': True,
            'evaluation_metrics': {'precision': 0.91, 'recall': 0.87},
            'governance_metadata': {'phase': 3},
            'created_by': 'mlops',
        },
    )
    assert create_res.status_code == 200, create_res.text
    created = create_res.json()
    record_id = int(created['id'])
    assert created['status'] == 'draft'

    review_res = client.post(
        f'/api/v1/market-intelligence/ai-governance/models/{record_id}/review',
        json={'decision': 'approved', 'reviewed_by': 'governance-board', 'note': 'Meets phase3 standards'},
    )
    assert review_res.status_code == 200, review_res.text
    reviewed = review_res.json()
    assert reviewed['status'] == 'approved'

    rollback_res = client.post(
        '/api/v1/market-intelligence/ai-governance/models/rollback',
        json={
            'model_name': 'market-opportunity-ranker',
            'from_version': '3.1.0',
            'to_version': '3.0.2',
            'reason': 'Rollback for calibration fix',
            'performed_by': 'mlops',
        },
    )
    assert rollback_res.status_code == 200, rollback_res.text
    rollback_payload = rollback_res.json()
    assert rollback_payload['status'] == 'rolled_back'
    assert rollback_payload['rollback_to_version'] == '3.0.2'

    list_res = client.get('/api/v1/market-intelligence/ai-governance/models', params={'model_name': 'market-opportunity-ranker'})
    assert list_res.status_code == 200, list_res.text
    assert any(row['model_name'] == 'market-opportunity-ranker' for row in list_res.json())


def test_phase3_governance_compliance_records_endpoint():
    # Ensure at least one auditable action exists.
    ingest = client.post(
        '/api/v1/market-intelligence/signals/ingest',
        json={
            'performed_by': 'compliance-check',
            'events': [
                {
                    'source_name': 'compliance-source',
                    'signal_type': 'trend',
                    'product_name': 'Compliance Probe Product',
                    'region': 'GLOBAL',
                    'raw_score': 70.0,
                    'sentiment': 'neutral',
                    'price_drop_pct': 5.0,
                    'demand_spike_pct': 20.0,
                }
            ],
        },
    )
    assert ingest.status_code == 200, ingest.text

    report_res = client.get('/api/v1/market-intelligence/governance-compliance/records', params={'window_minutes': 1440})
    assert report_res.status_code == 200, report_res.text
    report = report_res.json()
    assert report['total_entries'] >= 1
    assert isinstance(report['entity_counts'], dict)
    assert isinstance(report['action_counts'], dict)
    assert isinstance(report['recent_entries'], list)


def test_phase3_competitive_campaign_tracking_endpoints():
    lead_id = _create_lead('Competitive Lead', 'competitive-lead@example.com')

    create_res = client.post(
        '/api/v1/market-intelligence/competitive-campaigns',
        json={
            'entity_type': 'rfq',
            'entity_id': 8801,
            'outcome': 'lost',
            'reason_code': 'competitor_won',
            'reason_detail': 'Competitor launched aggressive bundle campaign',
            'competitor': 'RivalCo',
            'deal_value': 25000.0,
            'currency': 'USD',
            'lead_id': lead_id,
            'outcome_metadata': {'campaign_channel': 'email'},
            'recorded_by': 'sales-ops',
        },
    )
    assert create_res.status_code == 200, create_res.text
    created = create_res.json()
    assert created['competitor'] == 'RivalCo'
    assert created['reason_code'] == 'competitor_won'

    list_res = client.get('/api/v1/market-intelligence/competitive-campaigns', params={'reason_code': 'competitor_won'})
    assert list_res.status_code == 200, list_res.text
    assert any(row['id'] == created['id'] for row in list_res.json())

    analytics_res = client.get('/api/v1/market-intelligence/competitive-campaigns/analytics', params={'window_days': 90})
    assert analytics_res.status_code == 200, analytics_res.text
    analytics = analytics_res.json()
    assert analytics['total_deals'] >= 1
    assert 'competitor_won' in analytics['by_reason_code']


def test_phase3_automated_marketing_segmentation_endpoints():
    _create_lead('Segment SMB', 'segment-smb@example.com')
    _create_lead('Segment Mid', 'segment-mid@example.com')
    _create_lead('Segment Enterprise', 'segment-enterprise@example.com')

    run_res = client.post('/api/v1/market-intelligence/marketing-segmentation/run', params={'limit': 500})
    assert run_res.status_code == 200, run_res.text
    run_payload = run_res.json()
    assert run_payload['total_leads'] >= 3
    assert isinstance(run_payload['leads_by_segment'], dict)

    summary_res = client.get('/api/v1/market-intelligence/marketing-segmentation/summary')
    assert summary_res.status_code == 200, summary_res.text
    summary = summary_res.json()
    assert summary['total_leads'] >= 3
    assert isinstance(summary['leads_by_segment'], dict)
    assert any(count >= 1 for count in summary['leads_by_segment'].values())


def test_phase3_ad_platform_integration_endpoints():
    lead_id = _create_lead('Ad Platform Lead', 'ad-platform-lead@example.com')

    pref = client.patch(f'/api/v1/leads/{lead_id}/preferences', json={'marketing_consent': 'yes'})
    assert pref.status_code == 200, pref.text

    intent = client.post(
        '/api/v1/marketing/intent/event',
        json={
            'lead_id': lead_id,
            'source': 'paid-search',
            'signal_type': 'product_page_view',
            'strength': 15,
            'metadata': {'campaign': 'phase3-ad-sync'},
            'performed_by': 'marketing',
        },
    )
    assert intent.status_code == 200, intent.text

    dispatch = client.post(
        '/api/v1/market-intelligence/ad-platforms/dispatch',
        params={'platform': 'google_ads', 'campaign_type': 'nurture', 'limit': 50},
    )
    assert dispatch.status_code == 200, dispatch.text
    dispatch_payload = dispatch.json()
    assert dispatch_payload['platform'] == 'google_ads'
    assert dispatch_payload['dispatched'] >= 1

    listed = client.get('/api/v1/market-intelligence/ad-platforms/dispatches', params={'platform': 'google_ads'})
    assert listed.status_code == 200, listed.text
    assert any(row['provider'] == 'google_ads' for row in listed.json())


def test_phase3_b2c_product_trend_analytics_endpoint():
    create_a = client.post(
        '/api/v1/orders/b2c',
        json={
            'currency': 'USD',
            'total_amount': 240.0,
            'source_channel': 'web',
            'order_items': [
                {'sku': 'SKU-TREND-1', 'name': 'Wireless Earbuds', 'quantity': 2, 'unit_price': 60.0},
                {'sku': 'SKU-TREND-2', 'name': 'Smart Watch', 'quantity': 1, 'unit_price': 120.0},
            ],
            'shipping_address': {'country': 'US'},
        },
    )
    assert create_a.status_code == 200, create_a.text

    create_b = client.post(
        '/api/v1/orders/b2c',
        json={
            'currency': 'USD',
            'total_amount': 180.0,
            'source_channel': 'mobile_app',
            'order_items': [
                {'sku': 'SKU-TREND-1', 'name': 'Wireless Earbuds', 'quantity': 1, 'unit_price': 60.0},
                {'sku': 'SKU-TREND-3', 'name': 'Portable Charger', 'quantity': 2, 'unit_price': 60.0},
            ],
            'shipping_address': {'country': 'US'},
        },
    )
    assert create_b.status_code == 200, create_b.text

    trends = client.get('/api/v1/market-intelligence/b2c-product-trends', params={'window_days': 30, 'limit': 5})
    assert trends.status_code == 200, trends.text
    payload = trends.json()
    assert payload['orders_analyzed'] >= 2
    assert len(payload['trending_products']) >= 2
    assert any(item['product'] == 'Wireless Earbuds' for item in payload['trending_products'])


def test_phase3_personalized_marketing_b2c_endpoint():
    lead_id = _create_lead('Personalized Lead', 'personalized-lead@example.com')

    create_order = client.post(
        '/api/v1/orders/b2c',
        json={
            'lead_id': lead_id,
            'currency': 'USD',
            'total_amount': 220.0,
            'source_channel': 'web',
            'order_items': [
                {'sku': 'SKU-PERS-1', 'name': 'Fitness Band', 'quantity': 2, 'unit_price': 55.0},
                {'sku': 'SKU-PERS-2', 'name': 'Yoga Mat', 'quantity': 1, 'unit_price': 110.0},
            ],
            'shipping_address': {'country': 'US'},
        },
    )
    assert create_order.status_code == 200, create_order.text

    recs = client.get(
        '/api/v1/market-intelligence/b2c-personalization/recommendations',
        params={'lead_id': lead_id, 'top_k': 3},
    )
    assert recs.status_code == 200, recs.text
    payload = recs.json()
    assert payload['lead_id'] == lead_id
    assert len(payload['recommendations']) >= 1
    assert 'recommended_channel' in payload


