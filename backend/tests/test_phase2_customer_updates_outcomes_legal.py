from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def _create_lead(full_name: str, email: str) -> int:
    res = client.post('/api/v1/leads', json={'full_name': full_name, 'email': email, 'source': 'web'})
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def _create_vendor(name: str) -> int:
    res = client.post('/api/v1/vendors', json={'name': name, 'source': 'test-suite'})
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def _create_order(lead_id: int) -> int:
    res = client.post(
        '/api/v1/orders/b2c',
        json={
            'lead_id': lead_id,
            'currency': 'USD',
            'total_amount': 500.0,
            'order_items': [{'sku': 'ITEM-500', 'qty': 1, 'price': 500.0}],
            'shipping_address': {'line1': '1 Commerce St', 'city': 'Delhi', 'country': 'IN'},
        },
    )
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def _create_quote(lead_id: int) -> int:
    vendor_id = _create_vendor('Customer Update Vendor')
    br = client.post('/api/v1/rfq/broadcasts', json={
        'lead_id': lead_id, 'vendor_ids': [vendor_id], 'channel': 'email',
        'message': 'Please quote 5 units', 'performed_by': 'test',
    })
    assert br.status_code == 200, br.text
    bid = int(br.json()['id'])
    deliveries = client.get(f'/api/v1/rfq/broadcasts/{bid}/deliveries')
    assert deliveries.status_code == 200, deliveries.text
    attempt_id = int(deliveries.json()[0]['id'])
    client.patch(f'/api/v1/rfq/deliveries/{attempt_id}', json={'status': 'delivered', 'performed_by': 'test'})
    resp = client.post(f'/api/v1/rfq/deliveries/{attempt_id}/response', json={
        'response_status': 'replied',
        'response_text': 'Unit price USD 80 quantity 5 lead time 3 days MOQ 2',
        'recorded_by': 'test',
    })
    assert resp.status_code == 200, resp.text
    parse = client.post(f'/api/v1/rfq/responses/{resp.json()["id"]}/parse',
                        json={'parser_version': 'rule-v1', 'performed_by': 'test'})
    assert parse.status_code == 200, parse.text
    return int(parse.json()['id'])


def test_automated_customer_updates_on_order_create_and_fulfillment():
    lead_id = _create_lead('Customer Notify User', 'customer-notify@example.com')
    order_id = _create_order(lead_id)

    updates_res = client.get(f'/api/v1/automation/customer-updates', params={'order_id': order_id})
    assert updates_res.status_code == 200, updates_res.text
    updates = updates_res.json()
    assert any(u['event_type'] == 'order_created' and int(u['order_id']) == order_id for u in updates), \
        f'Expected order_created update, got: {[u["event_type"] for u in updates]}'

    patch_res = client.patch(
        f'/api/v1/orders/b2c/{order_id}/fulfillment',
        json={'fulfillment_status': 'shipped', 'tracking_number': 'TRK-TEST-1', 'carrier': 'FedEx', 'performed_by': 'ops'},
    )
    assert patch_res.status_code == 200, patch_res.text

    updates_res2 = client.get('/api/v1/automation/customer-updates', params={'order_id': order_id})
    assert updates_res2.status_code == 200, updates_res2.text
    updates2 = updates_res2.json()
    assert any(u['event_type'] == 'order_shipped' for u in updates2), \
        f'Expected order_shipped update, got: {[u["event_type"] for u in updates2]}'


def test_automated_customer_update_on_shipment_delivered():
    lead_id = _create_lead('Shipment Notify User', 'shipment-notify@example.com')
    order_id = _create_order(lead_id)

    shipment_res = client.post(
        f'/api/v1/orders/b2c/{order_id}/shipping/shipments',
        json={'provider': 'BlueDart', 'service_level': 'express', 'shipping_cost': 15.0,
              'estimated_delivery_days': 2, 'shipment_metadata': {}, 'performed_by': 'ops'},
    )
    assert shipment_res.status_code == 200, shipment_res.text
    shipment_id = int(shipment_res.json()['id'])

    sync_res = client.patch(
        f'/api/v1/orders/b2c/shipping/shipments/{shipment_id}',
        json={'status': 'delivered', 'current_location': 'Delhi Hub', 'performed_by': 'shipping-sync'},
    )
    assert sync_res.status_code == 200, sync_res.text

    updates_res = client.get('/api/v1/automation/customer-updates', params={'order_id': order_id})
    assert updates_res.status_code == 200, updates_res.text
    updates = updates_res.json()
    assert any(u['event_type'] == 'shipment_delivered' for u in updates), \
        f'Expected shipment_delivered, got: {[u["event_type"] for u in updates]}'


def test_deal_outcome_win_loss_capture_and_analytics():
    lead_id = _create_lead('Deal Outcome User', 'deal-outcome@example.com')
    order_id = _create_order(lead_id)
    quote_id = _create_quote(lead_id)

    win_res = client.post('/api/v1/automation/deal-outcomes', json={
        'entity_type': 'order',
        'entity_id': order_id,
        'outcome': 'won',
        'reason_code': 'best_price',
        'deal_value': 500.0,
        'currency': 'USD',
        'lead_id': lead_id,
        'recorded_by': 'sales-rep',
    })
    assert win_res.status_code == 200, win_res.text
    assert win_res.json()['outcome'] == 'won'

    loss_res = client.post('/api/v1/automation/deal-outcomes', json={
        'entity_type': 'rfq',
        'entity_id': quote_id,
        'outcome': 'lost',
        'reason_code': 'competitor_won',
        'competitor': 'AcmeCorp',
        'deal_value': 400.0,
        'lead_id': lead_id,
        'recorded_by': 'sales-rep',
    })
    assert loss_res.status_code == 200, loss_res.text
    assert loss_res.json()['outcome'] == 'lost'

    list_res = client.get('/api/v1/automation/deal-outcomes', params={'deal_outcome': 'won'})
    assert list_res.status_code == 200, list_res.text
    assert any(int(row['entity_id']) == order_id for row in list_res.json())

    analytics_res = client.get('/api/v1/automation/deal-outcomes/analytics', params={'window_days': 90})
    assert analytics_res.status_code == 200, analytics_res.text
    body = analytics_res.json()
    assert body['total_deals'] >= 2
    assert body['win_rate'] > 0.0
    assert 'won' in body['by_outcome']
    assert 'lost' in body['by_outcome']


def test_regional_legal_review_template_and_crud():
    template_res = client.get('/api/v1/compliance/legal-review/template', params={'regulation': 'GDPR'})
    assert template_res.status_code == 200, template_res.text
    items = template_res.json()['items']
    assert len(items) == 10
    assert all(i['status'] == 'pending' for i in items)

    regs_res = client.get('/api/v1/compliance/legal-review/region-regulations', params={'region': 'IN'})
    assert regs_res.status_code == 200, regs_res.text
    assert 'DPDP' in regs_res.json()['regulations']
    assert 'PCI_DSS' in regs_res.json()['regulations']

    lead_id = _create_lead('Legal Review User', 'legal-review@example.com')
    order_id = _create_order(lead_id)

    checklist = [dict(i, status='approved', notes='Reviewed and confirmed') for i in items[:3]]
    checklist += [dict(i) for i in items[3:]]

    review_res = client.post('/api/v1/compliance/legal-reviews', json={
        'entity_type': 'order',
        'entity_id': order_id,
        'region': 'EU',
        'regulation': 'GDPR',
        'checklist_items': checklist,
        'reviewer': 'legal-team',
        'notes': 'Initial review pass',
        'status': 'pending',
        'performed_by': 'legal-team',
    })
    assert review_res.status_code == 200, review_res.text
    review_id = int(review_res.json()['id'])
    assert review_res.json()['status'] == 'pending'

    patch_res = client.patch(f'/api/v1/compliance/legal-reviews/{review_id}', json={
        'status': 'approved',
        'reviewer': 'chief-legal',
        'notes': 'All GDPR items satisfied',
        'performed_by': 'chief-legal',
    })
    assert patch_res.status_code == 200, patch_res.text
    assert patch_res.json()['status'] == 'approved'
    assert patch_res.json()['reviewed_at'] is not None

    list_res = client.get('/api/v1/compliance/legal-reviews',
                          params={'regulation': 'GDPR', 'review_status': 'approved'})
    assert list_res.status_code == 200, list_res.text
    assert any(int(row['id']) == review_id for row in list_res.json())


def test_legal_review_dpdp_template():
    res = client.get('/api/v1/compliance/legal-review/template', params={'regulation': 'DPDP'})
    assert res.status_code == 200, res.text
    items = res.json()['items']
    assert len(items) == 8
    assert all(i['category'] for i in items)


def test_legal_review_invalid_regulation():
    res = client.get('/api/v1/compliance/legal-review/template', params={'regulation': 'INVALID_REG'})
    assert res.status_code == 400, res.text
