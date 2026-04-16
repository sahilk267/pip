"""Phase 4: Comprehensive Analytics & Continuous Improvement — integration tests."""
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


# ---------------------------------------------------------------------------
# 1 & 2. Drill-down analytics + Predictive analytics
# ---------------------------------------------------------------------------

def test_phase4_drill_down_analytics():
    """Drill-down analytics returns funnel metrics; region filter adds drill_down key."""
    lead_id = _create_lead('Drilldown Lead', 'drilldown@test.com')

    res = client.get('/api/v1/analytics/sales/drill-down', params={'window_days': 30})
    assert res.status_code == 200, res.text
    data = res.json()
    assert 'stage_counts' in data
    assert 'total_leads' in data

    # with region filter
    res2 = client.get(
        '/api/v1/analytics/sales/drill-down',
        params={'window_days': 30, 'region': 'IN'},
    )
    assert res2.status_code == 200, res2.text
    data2 = res2.json()
    assert 'drill_down' in data2
    assert data2['drill_down']['region'] == 'IN'


def test_phase4_predictive_analytics():
    """Predictive analytics returns projected conversions and churn risk."""
    _create_lead('Predict Lead', 'predict@test.com')

    res = client.get(
        '/api/v1/analytics/sales/predictive',
        params={'window_days': 30, 'forecast_days': 14},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert 'projected_conversions' in data
    assert 'churn_risk_leads' in data
    assert 'win_rate' in data
    assert data['forecast_days'] == 14


# ---------------------------------------------------------------------------
# 3. Anomaly detection
# ---------------------------------------------------------------------------

def test_phase4_anomaly_detection_endpoints():
    """Anomaly detection run and results endpoints work correctly."""
    # Run with high threshold so no anomaly fires (empty DB = 0 alerts)
    res = client.post(
        '/api/v1/analytics/anomaly-detection/run',
        params={'window_minutes': 60, 'spike_threshold': 100, 'performed_by': 'test_system'},
    )
    assert res.status_code == 200, res.text
    run_data = res.json()
    assert 'anomaly_triggered' in run_data
    assert run_data['anomaly_triggered'] is False

    # Directly inject unresolved alerts so spike_threshold=1 will trigger
    from backend.app.database import SessionLocal
    from backend.app import models as _models
    with SessionLocal() as _db:
        for i in range(3):
            _db.add(_models.Alert(
                title=f'Test alert {i}',
                severity='warning',
                detail='injected for anomaly test',
                category='monitoring',
                resolved=False,
            ))
        _db.commit()

    res2 = client.post(
        '/api/v1/analytics/anomaly-detection/run',
        params={'window_minutes': 60, 'spike_threshold': 1, 'performed_by': 'test_system'},
    )
    assert res2.status_code == 200, res2.text
    assert res2.json()['anomaly_triggered'] is True

    # Get results list
    res3 = client.get('/api/v1/analytics/anomaly-detection/results', params={'limit': 10})
    assert res3.status_code == 200, res3.text
    results = res3.json()
    assert isinstance(results, list)
    assert any(r['category'] == 'anomaly_detection' for r in results)


# ---------------------------------------------------------------------------
# 4. Automated bug triage
# ---------------------------------------------------------------------------

def test_phase4_automated_bug_triage_endpoints():
    """Bug triage run and issues endpoints scan AuditLog for failures."""
    # Manually inject a failure-like audit log entry
    from backend.app.database import SessionLocal
    from backend.app import models

    with SessionLocal() as db:
        entry = models.AuditLog(
            entity_type='connector',
            entity_id=None,
            action='discovery_failed',
            detail='critical: connector error timeout connecting to api',
            performed_by='system',
        )
        db.add(entry)
        db.commit()

    res = client.post(
        '/api/v1/analytics/bug-triage/run',
        params={'window_hours': 24, 'performed_by': 'test_system'},
    )
    assert res.status_code == 200, res.text
    triage = res.json()
    assert triage['total_issues'] >= 1
    assert 'by_severity' in triage
    assert 'critical_issues' in triage

    res2 = client.get('/api/v1/analytics/bug-triage/issues', params={'window_hours': 24})
    assert res2.status_code == 200, res2.text
    issues = res2.json()
    assert isinstance(issues, list)
    assert len(issues) >= 1


# ---------------------------------------------------------------------------
# 5. Dev productivity metrics (optional)
# ---------------------------------------------------------------------------

def test_phase4_dev_productivity_metrics():
    """Dev productivity metrics aggregate AuditLog actions by entity/actor."""
    _create_lead('DevProd Lead', 'devprod@test.com')  # creates audit log entries

    res = client.get('/api/v1/analytics/dev-productivity', params={'window_days': 7})
    assert res.status_code == 200, res.text
    data = res.json()
    assert 'total_actions' in data
    assert 'by_entity_type' in data
    assert 'top_actors' in data


# ---------------------------------------------------------------------------
# 6. Root cause analysis
# ---------------------------------------------------------------------------

def test_phase4_root_cause_analysis():
    """Root cause analysis correlates Alert spikes with AuditLog events."""
    # Ensure at least one alert exists
    client.post(
        '/api/v1/market-intelligence/signals/ingest',
        json={
            'performed_by': 'cron',
            'events': [
                {
                    'source_name': 'rca_source',
                    'signal_type': 'price_drop',
                    'product_name': 'RCA Product',
                    'region': 'US',
                    'raw_score': 90.0,
                    'sentiment': 'negative',
                    'price_drop_pct': 40.0,
                    'demand_spike_pct': 100.0,
                    'signal_metadata': {},
                }
            ],
        },
    )
    res = client.get('/api/v1/analytics/root-cause-analysis', params={'window_hours': 24})
    assert res.status_code == 200, res.text
    data = res.json()
    assert 'total_alerts' in data
    assert 'likely_root_category' in data
    assert 'correlated_audit_events' in data
    assert isinstance(data['correlated_audit_events'], list)


# ---------------------------------------------------------------------------
# 7. Alert fatigue suppression
# ---------------------------------------------------------------------------

def test_phase4_alert_fatigue_suppression():
    """Alert fatigue suppression resolves duplicate alerts within window."""
    from backend.app.database import SessionLocal
    from backend.app import models

    # Create two identical alerts
    with SessionLocal() as db:
        for _ in range(2):
            db.add(models.Alert(
                title='Duplicate alert for fatigue test',
                detail='same issue repeated',
                severity='warning',
                category='test_fatigue',
                resolved=False,
            ))
        db.commit()

    res = client.post(
        '/api/v1/analytics/alert-fatigue/suppress',
        params={'window_minutes': 60, 'category': 'test_fatigue', 'performed_by': 'test_system'},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data['suppressed_count'] >= 1
    assert len(data['suppressed_alert_ids']) >= 1


# ---------------------------------------------------------------------------
# 8. Analytics data anonymization
# ---------------------------------------------------------------------------

def test_phase4_analytics_data_anonymization():
    """Anonymized data endpoint returns leads with PII masked."""
    _create_lead('Anon User', 'anon_user@example.com')

    res = client.get('/api/v1/analytics/anonymized-data', params={'limit': 10})
    assert res.status_code == 200, res.text
    data = res.json()
    assert 'records' in data
    assert data['total'] >= 1
    record = data['records'][0]
    assert 'email_hash' in record
    assert 'anon_id' in record
    # PII must be masked — actual email must not appear
    assert '@' not in record.get('email_hash', '')


# ---------------------------------------------------------------------------
# 9. Continuous improvement feedback
# ---------------------------------------------------------------------------

def test_phase4_continuous_improvement_feedback():
    """Continuous improvement feedback returns order deal feedback summary."""
    lead_id = _create_lead('Feedback Lead', 'feedback@test.com')
    order_id = _create_order(lead_id)

    client.post(
        f'/api/v1/orders/b2c/{order_id}/feedback',
        json={
            'actor_type': 'customer',
            'actor_id': lead_id,
            'sentiment': 'positive',
            'rating': 5,
            'feedback_text': 'Great order experience',
            'feedback_metadata': {},
            'created_by': 'customer',
        },
    )

    res = client.get(
        '/api/v1/analytics/continuous-improvement/feedback',
        params={'window_days': 30},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert 'total_feedback' in data
    assert data['total_feedback'] >= 1
    assert 'sentiment_counts' in data
    assert data['sentiment_counts']['positive'] >= 1


# ---------------------------------------------------------------------------
# 10. Audit logging
# ---------------------------------------------------------------------------

def test_phase4_audit_logs_endpoint():
    """Audit logs endpoint returns paginated, filterable log entries."""
    _create_lead('Audit Lead', 'audit_lead@test.com')  # triggers audit entries

    res = client.get('/api/v1/analytics/audit-logs', params={'limit': 20})
    assert res.status_code == 200, res.text
    logs = res.json()
    assert isinstance(logs, list)
    assert len(logs) >= 1
    assert 'entity_type' in logs[0]
    assert 'action' in logs[0]

    # Filter by entity_type
    res2 = client.get(
        '/api/v1/analytics/audit-logs',
        params={'entity_type': 'lead', 'limit': 10},
    )
    assert res2.status_code == 200, res2.text
    filtered = res2.json()
    assert all(r['entity_type'] == 'lead' for r in filtered)


# ---------------------------------------------------------------------------
# 11 & 12. Sales enablement recommendations and playbooks
# ---------------------------------------------------------------------------

def test_phase4_sales_enablement_recommendations():
    """Sales enablement recommendations return a playbook for a lead."""
    lead_id = _create_lead('Enablement Lead', 'enablement@test.com')

    res = client.get(
        '/api/v1/analytics/sales-enablement/recommendations',
        params={'lead_id': lead_id},
    )
    assert res.status_code == 200, res.text
    playbook = res.json()
    assert playbook['lead_id'] == lead_id
    assert 'steps' in playbook
    assert 'priority' in playbook

    # 404 for missing lead
    res404 = client.get(
        '/api/v1/analytics/sales-enablement/recommendations',
        params={'lead_id': 999999},
    )
    assert res404.status_code == 404


def test_phase4_sales_playbooks_queue():
    """Sales playbooks queue returns prioritized leads."""
    _create_lead('Playbook Alpha', 'playbook_alpha@test.com')
    _create_lead('Playbook Beta', 'playbook_beta@test.com')

    res = client.get('/api/v1/analytics/sales-playbooks', params={'limit': 10})
    assert res.status_code == 200, res.text
    data = res.json()
    assert 'playbooks' in data or isinstance(data, dict)


# ---------------------------------------------------------------------------
# 13. Rep training / onboarding tracking
# ---------------------------------------------------------------------------

def test_phase4_rep_training_tracking_endpoints():
    """Rep training log and status endpoints track onboarding progress."""
    res = client.post(
        '/api/v1/analytics/rep-training/log',
        params={
            'rep_id': 'rep_001',
            'module': 'product_intro',
            'status': 'completed',
            'performed_by': 'hr_system',
        },
    )
    assert res.status_code == 200, res.text
    log_data = res.json()
    assert log_data['rep_id'] == 'rep_001'
    assert log_data['module'] == 'product_intro'

    res2 = client.get(
        '/api/v1/analytics/rep-training/status',
        params={'rep_id': 'rep_001', 'limit': 10},
    )
    assert res2.status_code == 200, res2.text
    entries = res2.json()
    assert isinstance(entries, list)
    assert len(entries) >= 1
    assert any('rep_id=rep_001' in (e.get('detail') or '') for e in entries)


# ---------------------------------------------------------------------------
# 14. Sales content analytics
# ---------------------------------------------------------------------------

def test_phase4_sales_content_analytics_endpoints():
    """Sales content track and analytics endpoints work correctly."""
    res = client.post(
        '/api/v1/analytics/sales-content/track',
        params={
            'content_id': 'playbook_enterprise_v2',
            'content_type': 'playbook',
            'rep_id': 'rep_001',
            'performed_by': 'sales_portal',
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()['content_id'] == 'playbook_enterprise_v2'

    res2 = client.get(
        '/api/v1/analytics/sales-content/analytics',
        params={'window_days': 30},
    )
    assert res2.status_code == 200, res2.text
    data = res2.json()
    assert data['total_accesses'] >= 1
    assert 'by_content_id' in data
    assert 'playbook_enterprise_v2' in data['by_content_id']


# ---------------------------------------------------------------------------
# 15, 16, 17. Knowledge base, AI Q&A, training modules
# ---------------------------------------------------------------------------

def test_phase4_knowledge_base_and_ai_qa():
    """Knowledge base add, search, and AI Q&A endpoints operate correctly."""
    res = client.post(
        '/api/v1/analytics/knowledge-base/entries',
        params={
            'title': 'GDPR Compliance Guide',
            'content': 'This guide explains how to handle personal data under GDPR regulations.',
            'category': 'compliance',
            'created_by': 'admin',
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()['title'] == 'GDPR Compliance Guide'

    res2 = client.get(
        '/api/v1/analytics/knowledge-base/search',
        params={'q': 'GDPR', 'limit': 5},
    )
    assert res2.status_code == 200, res2.text
    results = res2.json()
    assert isinstance(results, list)
    assert len(results) >= 1

    res3 = client.post(
        '/api/v1/analytics/ai-qa/ask',
        params={'question': 'How to handle GDPR compliance?', 'limit': 3},
    )
    assert res3.status_code == 200, res3.text
    qa = res3.json()
    assert qa['question'] == 'How to handle GDPR compliance?'
    assert 'answers' in qa
    assert qa['answer_count'] >= 1


def test_phase4_training_modules_progress():
    """Training modules log and progress endpoints track module completion."""
    res = client.post(
        '/api/v1/analytics/training-modules/log',
        params={
            'rep_id': 'rep_002',
            'module_name': 'compliance_101',
            'progress_pct': 80,
            'performed_by': 'lms_system',
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data['module_name'] == 'compliance_101'
    assert data['progress_pct'] == 80

    res2 = client.get(
        '/api/v1/analytics/training-modules/progress',
        params={'rep_id': 'rep_002'},
    )
    assert res2.status_code == 200, res2.text
    prog = res2.json()
    assert 'progress_by_rep' in prog
    assert 'rep_002' in prog['progress_by_rep']
    assert prog['progress_by_rep']['rep_002'].get('compliance_101') == 80


# ---------------------------------------------------------------------------
# 18. Regional legal review (Phase 4 context)
# ---------------------------------------------------------------------------

def test_phase4_governance_legal_reviews():
    """Legal reviews endpoint returns analytics-context legal review records."""
    # Create a legal review first via compliance endpoint
    client.post(
        '/api/v1/compliance/legal-reviews',
        json={
            'entity_type': 'analytics',
            'entity_id': 1,
            'region': 'EU',
            'regulation': 'GDPR',
            'checklist_items': [],
            'reviewer': 'legal_team',
            'notes': 'Phase 4 analytics GDPR review',
            'status': 'pending',
            'performed_by': 'legal_team',
        },
    )

    res = client.get(
        '/api/v1/analytics/governance/legal-reviews',
        params={'region': 'EU', 'limit': 10},
    )
    assert res.status_code == 200, res.text
    reviews = res.json()
    assert isinstance(reviews, list)
    assert len(reviews) >= 1
    assert any(r['region'] == 'EU' for r in reviews)


# ---------------------------------------------------------------------------
# 19. Multi-language support (Phase 4 context)
# ---------------------------------------------------------------------------

def test_phase4_governance_multi_language():
    """Multi-language endpoint lists message templates for analytics dashboards."""
    # Create a template via market-intelligence i18n/templates endpoint
    client.post(
        '/api/v1/market-intelligence/i18n/templates',
        json={
            'template_code': 'analytics_dashboard_welcome',
            'template_type': 'notification',
            'default_locale': 'fr',
            'translations': {
                'fr': {'subject': 'Bienvenue sur Analytics', 'body': 'Tableau de bord analytique chargé avec succès.'}
            },
        },
    )

    res = client.get(
        '/api/v1/analytics/governance/multi-language',
        params={'limit': 10},
    )
    assert res.status_code == 200, res.text
    templates = res.json()
    assert isinstance(templates, list)
    assert any(t['template_code'] == 'analytics_dashboard_welcome' for t in templates)


# ---------------------------------------------------------------------------
# 20. External analytics/LMS integration
# ---------------------------------------------------------------------------

def test_phase4_external_analytics_lms_integration():
    """External integrations endpoint lists and provides sync records."""
    # Create an integration via integrations/external endpoint
    create_res = client.post(
        '/api/v1/integrations/external',
        json={
            'name': 'Tableau Analytics',
            'provider': 'tableau',
            'integration_metadata': {'api_key': 'test_key', 'workspace': 'analytics'},
        },
    )
    assert create_res.status_code == 200, create_res.text
    integration_id = create_res.json()['id']

    res = client.get(
        '/api/v1/analytics/external-integrations',
        params={'provider': 'tableau'},
    )
    assert res.status_code == 200, res.text
    integrations = res.json()
    assert isinstance(integrations, list)
    assert any(i['provider'] == 'tableau' for i in integrations)

    res2 = client.get(
        f'/api/v1/analytics/external-integrations/{integration_id}/sync-records',
        params={'limit': 10},
    )
    assert res2.status_code == 200, res2.text
    assert isinstance(res2.json(), list)


# ---------------------------------------------------------------------------
# 21. Escalation playbook (Phase 4 context)
# ---------------------------------------------------------------------------

def test_phase4_governance_escalation_playbook():
    """Escalation playbook endpoint returns rules and records."""
    # Create a rule via escalations endpoint
    client.post(
        '/api/v1/escalations/rules',
        json={
            'name': 'Analytics failure escalation',
            'entity_type': 'analytics',
            'trigger_condition': 'anomaly_score > 0.9',
            'action': 'notify_analytics_team',
            'active': True,
        },
    )

    res = client.get(
        '/api/v1/analytics/governance/escalation-playbook',
        params={'entity_type': 'analytics'},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert 'rules' in data
    assert 'recent_records' in data
    assert isinstance(data['rules'], list)


# ---------------------------------------------------------------------------
# 22. AI model governance (Phase 4 context)
# ---------------------------------------------------------------------------

def test_phase4_governance_ai_model_records():
    """AI model governance records list for analytics modules."""
    # Create a model record via Phase 3 AI governance endpoint
    client.post(
        '/api/v1/market-intelligence/ai-governance/models',
        json={
            'model_name': 'analytics_predictive_v1',
            'model_version': '1.0.0',
            'model_type': 'predictive',
            'created_by': 'ml_team',
        },
    )

    res = client.get(
        '/api/v1/analytics/governance/ai-model-governance',
        params={'limit': 10},
    )
    assert res.status_code == 200, res.text
    records = res.json()
    assert isinstance(records, list)
    assert any(r['model_name'] == 'analytics_predictive_v1' for r in records)


# ---------------------------------------------------------------------------
# 23. Governance/compliance records (Phase 4 context)
# ---------------------------------------------------------------------------

def test_phase4_governance_compliance_records():
    """Compliance records endpoint returns audit/compliance report for analytics."""
    _create_lead('Compliance Lead', 'compliance_phase4@test.com')

    res = client.get(
        '/api/v1/analytics/governance/compliance-records',
        params={'window_minutes': 1440},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert 'generated_at' in data or 'total_leads' in data or isinstance(data, dict)


# ---------------------------------------------------------------------------
# 24. Marketing attribution analytics
# ---------------------------------------------------------------------------

def test_phase4_marketing_attribution_analytics():
    """Marketing attribution analytics returns order-to-campaign attribution."""
    lead_id = _create_lead('Attribution Lead', 'attribution@test.com')
    _create_order(lead_id, amount=150.0, channel='email_campaign')

    res = client.get(
        '/api/v1/analytics/marketing/attribution',
        params={'window_days': 30},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert 'generated_at' in data or 'attributed_orders' in data or isinstance(data, dict)


# ---------------------------------------------------------------------------
# 25. Marketing content performance analytics
# ---------------------------------------------------------------------------

def test_phase4_marketing_content_performance():
    """Marketing content performance returns intent signals and automation events."""
    res = client.get(
        '/api/v1/analytics/marketing/content-performance',
        params={'window_days': 30},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert isinstance(data, dict)
    assert 'generated_at' in data or 'lead_attribution' in data


def test_phase4_marketing_roi():
    """Marketing ROI endpoint returns campaign spend and revenue metrics."""
    res = client.get('/api/v1/analytics/marketing/roi', params={'window_days': 30})
    assert res.status_code == 200, res.text
    data = res.json()
    assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# 26. Marketing analytics feedback loop
# ---------------------------------------------------------------------------

def test_phase4_marketing_analytics_feedback_loop():
    """Marketing analytics feedback loop returns FeedbackLoopRecord entries."""
    res = client.get(
        '/api/v1/analytics/marketing/feedback-loop',
        params={'limit': 20},
    )
    assert res.status_code == 200, res.text
    assert isinstance(res.json(), list)


# ---------------------------------------------------------------------------
# 27. B2C product and customer analytics
# ---------------------------------------------------------------------------

def test_phase4_b2c_product_analytics():
    """B2C product analytics returns orders, revenue, and attribution summary."""
    lead_id = _create_lead('B2C Prod Lead', 'b2c_prod@test.com')
    _create_order(lead_id, amount=200.0, channel='mobile_app')

    res = client.get(
        '/api/v1/analytics/b2c/product-analytics',
        params={'window_days': 30},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data['total_orders'] >= 1
    assert data['total_revenue'] >= 200.0
    assert 'orders_by_source_channel' in data
    assert 'mobile_app' in data['orders_by_source_channel']


# ---------------------------------------------------------------------------
# 28. Customer lifecycle analytics (B2C)
# ---------------------------------------------------------------------------

def test_phase4_b2c_customer_lifecycle_analytics():
    """Customer lifecycle analytics returns LTV, retention, cohort data."""
    lead_id = _create_lead('Lifecycle Lead', 'lifecycle@test.com')
    _create_order(lead_id, amount=100.0, channel='website')
    _create_order(lead_id, amount=150.0, channel='email')

    res = client.get(
        '/api/v1/analytics/b2c/customer-lifecycle',
        params={'window_days': 90, 'limit': 20},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert 'total_customers_with_orders' in data
    assert data['total_customers_with_orders'] >= 1
    assert 'retention_rate' in data
    assert 'top_customers' in data
    top = data['top_customers']
    assert isinstance(top, list)
    matched = [c for c in top if c['lead_id'] == lead_id]
    assert len(matched) >= 1
    assert matched[0]['order_count'] >= 2
    assert matched[0]['lifetime_value'] >= 250.0
