from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def _create_vendor(name: str) -> int:
    res = client.post('/api/v1/vendors', json={'name': name, 'source': 'test-suite'})
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def _create_lead(full_name: str, email: str) -> int:
    res = client.post('/api/v1/leads', json={'full_name': full_name, 'email': email, 'source': 'web'})
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def _create_order(lead_id: int) -> int:
    res = client.post(
        '/api/v1/orders/b2c',
        json={
            'lead_id': lead_id,
            'currency': 'USD',
            'total_amount': 400.0,
            'order_items': [{'sku': 'SKU-400', 'qty': 2, 'price': 200.0}],
            'shipping_address': {'line1': '1 Market St', 'city': 'Mumbai', 'country': 'IN'},
        },
    )
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def _create_quote(lead_id: int) -> int:
    vendor_id = _create_vendor('Phase2 Quote Vendor')
    broadcast_res = client.post(
        '/api/v1/rfq/broadcasts',
        json={
            'lead_id': lead_id,
            'vendor_ids': [vendor_id],
            'channel': 'email',
            'message': 'Please quote 20 units',
            'performed_by': 'sales-qa',
        },
    )
    assert broadcast_res.status_code == 200, broadcast_res.text
    broadcast_id = int(broadcast_res.json()['id'])

    deliveries_res = client.get(f'/api/v1/rfq/broadcasts/{broadcast_id}/deliveries')
    assert deliveries_res.status_code == 200, deliveries_res.text
    attempt_id = int(deliveries_res.json()[0]['id'])

    patch_res = client.patch(
        f'/api/v1/rfq/deliveries/{attempt_id}',
        json={'status': 'delivered', 'performed_by': 'sales-qa'},
    )
    assert patch_res.status_code == 200, patch_res.text

    response_res = client.post(
        f'/api/v1/rfq/deliveries/{attempt_id}/response',
        json={
            'response_status': 'replied',
            'response_text': 'Unit price USD 50 quantity 20 lead time 5 days MOQ 10',
            'recorded_by': 'sales-qa',
        },
    )
    assert response_res.status_code == 200, response_res.text
    response_id = int(response_res.json()['id'])

    parse_res = client.post(
        f'/api/v1/rfq/responses/{response_id}/parse',
        json={'parser_version': 'rule-v1', 'performed_by': 'sales-qa'},
    )
    assert parse_res.status_code == 200, parse_res.text
    return int(parse_res.json()['id'])


def test_sales_notifications_capture_manual_and_rfq_events():
    lead_id = _create_lead('Sales Notify', 'sales-notify@example.com')
    quote_id = _create_quote(lead_id)

    list_res = client.get('/api/v1/automation/sales-notifications')
    assert list_res.status_code == 200, list_res.text
    rows = list_res.json()
    assert any(row['notification_type'] == 'vendor_response_received' for row in rows)
    assert any(row['notification_type'] == 'quote_parsed' and int(row['entity_id']) == quote_id for row in rows)

    create_res = client.post(
        '/api/v1/automation/sales-notifications',
        json={
            'entity_type': 'quote',
            'entity_id': quote_id,
            'notification_type': 'manual_follow_up',
            'message': 'Call vendor to confirm revised lead time',
            'priority': 'high',
            'lead_id': lead_id,
            'recipient': 'sales',
            'performed_by': 'sales-manager',
        },
    )
    assert create_res.status_code == 200, create_res.text
    notification_id = int(create_res.json()['id'])

    patch_res = client.patch(
        f'/api/v1/automation/sales-notifications/{notification_id}',
        json={'status': 'sent', 'performed_by': 'sales-manager'},
    )
    assert patch_res.status_code == 200, patch_res.text
    assert patch_res.json()['status'] == 'sent'
    assert patch_res.json()['sent_at'] is not None


def test_discount_approval_workflow_updates_order_and_quote():
    lead_id = _create_lead('Pricing Review', 'pricing-review@example.com')
    order_id = _create_order(lead_id)
    quote_id = _create_quote(lead_id)

    order_req = client.post(
        '/api/v1/automation/pricing-approvals',
        json={
            'entity_type': 'order',
            'entity_id': order_id,
            'requested_discount_pct': 10.0,
            'reason': 'Strategic account expansion',
            'requested_by': 'sales-rep',
        },
    )
    assert order_req.status_code == 200, order_req.text
    order_request_id = int(order_req.json()['id'])

    order_review = client.post(
        f'/api/v1/automation/pricing-approvals/{order_request_id}/review',
        json={'decision': 'approved', 'approved_discount_pct': 10.0, 'reviewed_by': 'sales-director'},
    )
    assert order_review.status_code == 200, order_review.text
    assert order_review.json()['status'] == 'approved'

    orders_res = client.get('/api/v1/orders/b2c')
    assert orders_res.status_code == 200, orders_res.text
    order = next(row for row in orders_res.json() if int(row['id']) == order_id)
    assert float(order['total_amount']) == 360.0

    quote_req = client.post(
        '/api/v1/automation/pricing-approvals',
        json={
            'entity_type': 'quote',
            'entity_id': quote_id,
            'requested_discount_amount': 5.0,
            'reason': 'Close competitive deal',
            'requested_by': 'sales-rep',
        },
    )
    assert quote_req.status_code == 200, quote_req.text
    quote_request_id = int(quote_req.json()['id'])

    quote_review = client.post(
        f'/api/v1/automation/pricing-approvals/{quote_request_id}/review',
        json={'decision': 'approved', 'approved_discount_amount': 5.0, 'reviewed_by': 'sales-director'},
    )
    assert quote_review.status_code == 200, quote_review.text

    parsed_res = client.get(f'/api/v1/rfq/quotes/{quote_id}/versions')
    assert parsed_res.status_code == 200, parsed_res.text
    assert len(parsed_res.json()) >= 2


def test_quote_to_cash_flow_creates_invoice_and_marks_paid():
    lead_id = _create_lead('Finance Flow', 'finance-flow@example.com')
    order_id = _create_order(lead_id)
    quote_id = _create_quote(lead_id)

    create_res = client.post(
        '/api/v1/automation/quote-to-cash',
        json={
            'quote_id': quote_id,
            'order_id': order_id,
            'external_system': 'erp-sandbox',
            'created_by': 'finance-ops',
        },
    )
    assert create_res.status_code == 200, create_res.text
    record_id = int(create_res.json()['id'])
    assert create_res.json()['status'] == 'quoted'

    invoice_res = client.post(
        f'/api/v1/automation/quote-to-cash/{record_id}/advance',
        json={'status': 'invoiced', 'external_reference': 'ERP-1001', 'performed_by': 'finance-ops'},
    )
    assert invoice_res.status_code == 200, invoice_res.text
    assert invoice_res.json()['invoice_number'].startswith('INV-')
    assert invoice_res.json()['invoiced_at'] is not None

    paid_res = client.post(
        f'/api/v1/automation/quote-to-cash/{record_id}/advance',
        json={'status': 'paid', 'performed_by': 'finance-ops'},
    )
    assert paid_res.status_code == 200, paid_res.text
    assert paid_res.json()['status'] == 'paid'
    assert paid_res.json()['payment_status'] == 'paid'
    assert paid_res.json()['paid_at'] is not None

    list_res = client.get('/api/v1/automation/quote-to-cash', params={'qtc_status': 'paid'})
    assert list_res.status_code == 200, list_res.text
    assert any(int(row['id']) == record_id for row in list_res.json())
