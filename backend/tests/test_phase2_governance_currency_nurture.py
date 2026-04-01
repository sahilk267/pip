from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def _create_lead(full_name: str, email: str) -> int:
    res = client.post('/api/v1/leads', json={'full_name': full_name, 'email': email, 'source': 'web'})
    assert res.status_code == 200, res.text
    lead_id = int(res.json()['id'])
    pref = client.patch(f'/api/v1/leads/{lead_id}/preferences', json={'marketing_consent': 'yes', 'unsubscribe': False})
    assert pref.status_code == 200, pref.text
    return lead_id


def _create_order(lead_id: int, amount: float = 300.0, currency: str = 'USD') -> int:
    res = client.post(
        '/api/v1/orders/b2c',
        json={
            'lead_id': lead_id,
            'currency': currency,
            'total_amount': amount,
            'order_items': [{'sku': 'SKU-1', 'qty': 1, 'price': amount}],
            'shipping_address': {'line1': '1 Main', 'city': 'Mumbai', 'country': 'IN'},
        },
    )
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def _create_quote(lead_id: int) -> int:
    vendor = client.post('/api/v1/vendors', json={'name': 'Gov Vendor', 'source': 'test'})
    assert vendor.status_code == 200, vendor.text
    vendor_id = int(vendor.json()['id'])

    br = client.post('/api/v1/rfq/broadcasts', json={
        'lead_id': lead_id,
        'vendor_ids': [vendor_id],
        'channel': 'email',
        'message': 'Need quote',
        'performed_by': 'test',
    })
    assert br.status_code == 200, br.text
    bid = int(br.json()['id'])

    deliveries = client.get(f'/api/v1/rfq/broadcasts/{bid}/deliveries')
    assert deliveries.status_code == 200, deliveries.text
    attempt_id = int(deliveries.json()[0]['id'])

    patch = client.patch(f'/api/v1/rfq/deliveries/{attempt_id}', json={'status': 'delivered', 'performed_by': 'test'})
    assert patch.status_code == 200, patch.text

    response = client.post(f'/api/v1/rfq/deliveries/{attempt_id}/response', json={
        'response_status': 'replied',
        'response_text': 'Unit price USD 70 quantity 4 lead time 2 days MOQ 1',
        'recorded_by': 'test',
    })
    assert response.status_code == 200, response.text

    parsed = client.post(
        f"/api/v1/rfq/responses/{response.json()['id']}/parse",
        json={'parser_version': 'rule-v1', 'performed_by': 'test'},
    )
    assert parsed.status_code == 200, parsed.text
    return int(parsed.json()['id'])


def test_ai_model_governance_lifecycle():
    create_res = client.post('/api/v1/automation/ai-governance/models', json={
        'model_name': 'negotiation-engine',
        'model_type': 'negotiation',
        'model_version': 'v2.3.1',
        'approval_required': True,
        'evaluation_metrics': {'accuracy': 0.92, 'latency_ms': 140},
        'created_by': 'mlops-ci',
    })
    assert create_res.status_code == 200, create_res.text
    record_id = int(create_res.json()['id'])
    assert create_res.json()['status'] == 'draft'

    review_res = client.post(f'/api/v1/automation/ai-governance/models/{record_id}/review', json={
        'decision': 'approved',
        'reviewed_by': 'mlops-lead',
        'note': 'Passed offline evaluation and canary checks',
    })
    assert review_res.status_code == 200, review_res.text
    assert review_res.json()['status'] == 'approved'

    rollback_res = client.post('/api/v1/automation/ai-governance/models/rollback', json={
        'model_name': 'negotiation-engine',
        'from_version': 'v2.3.1',
        'to_version': 'v2.2.9',
        'reason': 'Observed pricing drift in production',
        'performed_by': 'mlops-oncall',
    })
    assert rollback_res.status_code == 200, rollback_res.text
    assert rollback_res.json()['status'] == 'rolled_back'

    list_res = client.get('/api/v1/automation/ai-governance/models', params={'model_name': 'negotiation-engine'})
    assert list_res.status_code == 200, list_res.text
    assert any(r['model_version'] == 'v2.3.1' for r in list_res.json())


def test_multi_currency_tax_preview():
    rate_res = client.post('/api/v1/automation/currency-rates', json={
        'base_currency': 'USD',
        'quote_currency': 'INR',
        'rate': 83.5,
        'source': 'manual',
        'created_by': 'finance-bot',
    })
    assert rate_res.status_code == 200, rate_res.text

    tax_res = client.post('/api/v1/automation/tax-rules', json={
        'region': 'IN',
        'country_code': 'IN',
        'tax_name': 'GST',
        'tax_type': 'exclusive',
        'tax_rate': 18.0,
        'applies_to': 'order',
        'created_by': 'tax-team',
    })
    assert tax_res.status_code == 200, tax_res.text

    preview_res = client.post('/api/v1/automation/pricing/preview', json={
        'amount': 100.0,
        'from_currency': 'USD',
        'to_currency': 'INR',
        'country_code': 'IN',
    })
    assert preview_res.status_code == 200, preview_res.text
    body = preview_res.json()
    assert body['converted_amount'] == 8350.0
    assert body['tax_name'] == 'GST'
    assert body['tax_amount'] > 0
    assert body['total_amount'] > body['converted_amount']


def test_nurture_trigger_from_deal_outcomes():
    lead_id = _create_lead('Nurture Lead', 'nurture-lead@example.com')
    quote_id = _create_quote(lead_id)

    outcome = client.post('/api/v1/automation/deal-outcomes', json={
        'entity_type': 'rfq',
        'entity_id': quote_id,
        'outcome': 'lost',
        'reason_code': 'price_gap',
        'lead_id': lead_id,
        'recorded_by': 'sales',
    })
    assert outcome.status_code == 200, outcome.text

    trigger_res = client.post('/api/v1/marketing/campaigns/nurture-reengagement/trigger', json={
        'abandoned_after_hours': 24,
        'lookback_days': 30,
        'limit': 200,
        'performed_by': 'marketing-cron',
    })
    assert trigger_res.status_code == 200, trigger_res.text
    assert trigger_res.json()['deal_outcome_triggers'] >= 1

    list_res = client.get('/api/v1/marketing/campaigns/nurture-reengagement/triggers', params={
        'campaign_type': 'nurture',
        'lead_id': lead_id,
    })
    assert list_res.status_code == 200, list_res.text
    assert any(row['source_type'] == 'deal_outcome' for row in list_res.json())


def test_reengagement_trigger_from_abandoned_cart():
    lead_id = _create_lead('Cart Lead', 'cart-lead@example.com')

    cart_add = client.post('/api/v1/cart/items', json={
        'lead_id': lead_id,
        'currency': 'USD',
        'item': {
            'sku': 'SKU-CART',
            'name': 'Cart Item',
            'unit_price': 120.0,
            'quantity': 1,
            'item_metadata': {},
        },
        'performed_by': 'commerce',
    })
    assert cart_add.status_code == 200, cart_add.text
    cart_id = int(cart_add.json()['cart_id'])

    trigger_res = client.post('/api/v1/marketing/campaigns/nurture-reengagement/trigger', json={
        'abandoned_after_hours': 0,
        'lookback_days': 1,
        'limit': 200,
        'performed_by': 'marketing-cron',
    })
    assert trigger_res.status_code == 200, trigger_res.text

    list_res = client.get('/api/v1/marketing/campaigns/nurture-reengagement/triggers', params={
        'campaign_type': 'reengagement',
        'lead_id': lead_id,
    })
    assert list_res.status_code == 200, list_res.text
    assert any(row['source_type'] == 'abandoned_cart' for row in list_res.json())
