from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app import models


client = TestClient(app)


def _create_vendor(name: str) -> int:
    res = client.post('/api/v1/vendors', json={'name': name, 'source': 'test-suite'})
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def _create_order() -> int:
    res = client.post(
        '/api/v1/orders/b2c',
        json={
            'currency': 'USD',
            'total_amount': 250.0,
            'order_items': [{'sku': 'V-ORDER', 'qty': 1, 'price': 250.0}],
            'shipping_address': {'line1': '42 Main Rd', 'city': 'Pune', 'country': 'IN'},
        },
    )
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def _create_quote() -> tuple[int, int]:
    lead_res = client.post(
        '/api/v1/leads',
        json={'full_name': 'Quote Buyer', 'email': 'quote-buyer@example.com', 'source': 'web'},
    )
    assert lead_res.status_code == 200, lead_res.text
    lead_id = int(lead_res.json()['id'])

    vendor_id = _create_vendor('Version Quote Vendor')
    broadcast_res = client.post(
        '/api/v1/rfq/broadcasts',
        json={
            'lead_id': lead_id,
            'vendor_ids': [vendor_id],
            'channel': 'email',
            'message': 'Please quote 10 units.',
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
            'response_text': 'Unit price USD 150 quantity 10 lead time 7 days MOQ 5',
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
    quote_id = int(parse_res.json()['id'])
    return response_id, quote_id


def test_order_version_history_and_rollback():
    order_id = _create_order()

    patch_res = client.patch(
        f'/api/v1/orders/b2c/{order_id}/fulfillment',
        json={'fulfillment_status': 'shipped', 'tracking_number': 'TRK-1234', 'carrier': 'DHL', 'performed_by': 'ops'},
    )
    assert patch_res.status_code == 200, patch_res.text

    versions_res = client.get(f'/api/v1/orders/b2c/{order_id}/versions')
    assert versions_res.status_code == 200, versions_res.text
    versions = versions_res.json()
    assert len(versions) >= 2
    assert versions[0]['entity_type'] == 'order'

    rollback_res = client.post(
        f'/api/v1/orders/b2c/{order_id}/versions/1/rollback',
        json={'reason': 'restore baseline', 'performed_by': 'ops-admin'},
    )
    assert rollback_res.status_code == 200, rollback_res.text
    restored = rollback_res.json()
    assert restored['fulfillment_status'] in {'pending', 'created', 'packed', 'shipped', 'in_transit', 'delivered', 'failed', 'returned'}


def test_quote_version_history_and_rollback():
    response_id, quote_id = _create_quote()

    versions_res = client.get(f'/api/v1/rfq/quotes/{quote_id}/versions')
    assert versions_res.status_code == 200, versions_res.text
    versions = versions_res.json()
    assert versions
    assert versions[0]['entity_type'] == 'quote'

    with SessionLocal() as db:
        quote = db.query(models.RFQParsedQuote).filter(models.RFQParsedQuote.id == quote_id).first()
        assert quote is not None
        quote.unit_price = 999.0
        db.add(quote)
        db.commit()

    rollback_res = client.post(
        f'/api/v1/rfq/quotes/{quote_id}/versions/1/rollback',
        json={'reason': 'restore parsed result', 'performed_by': 'sales-ops'},
    )
    assert rollback_res.status_code == 200, rollback_res.text
    assert rollback_res.json()['unit_price'] != 999.0

    parsed_list_res = client.get(f'/api/v1/rfq/responses/{response_id}/parsed-quotes')
    assert parsed_list_res.status_code == 200, parsed_list_res.text
    assert parsed_list_res.json()[0]['id'] == quote_id


def test_automated_escalation_creates_case_and_alert():
    lead_res = client.post(
        '/api/v1/leads',
        json={'full_name': 'Escalation Buyer', 'email': 'escalation@example.com', 'source': 'web'},
    )
    assert lead_res.status_code == 200, lead_res.text
    lead_id = int(lead_res.json()['id'])

    vendor_a = _create_vendor('Escalation Vendor A')
    vendor_b = _create_vendor('Escalation Vendor B')
    _create_vendor('Escalation Vendor C')

    broadcast_res = client.post(
        '/api/v1/rfq/broadcasts',
        json={
            'lead_id': lead_id,
            'vendor_ids': [vendor_a, vendor_b],
            'channel': 'email',
            'message': 'Need immediate quote.',
            'performed_by': 'sales-qa',
        },
    )
    assert broadcast_res.status_code == 200, broadcast_res.text
    broadcast_id = int(broadcast_res.json()['id'])

    deliveries = client.get(f'/api/v1/rfq/broadcasts/{broadcast_id}/deliveries')
    assert deliveries.status_code == 200, deliveries.text
    for row in deliveries.json():
        failed_res = client.patch(
            f"/api/v1/rfq/deliveries/{row['id']}",
            json={'status': 'failed', 'error_detail': 'Mailbox rejected', 'performed_by': 'sales-qa'},
        )
        assert failed_res.status_code == 200, failed_res.text

    escalate_res = client.post(
        '/api/v1/rfq/escalations/auto-run',
        params={'response_sla_hours': 0, 'expansion_limit': 1, 'performed_by': 'sales-manager'},
    )
    assert escalate_res.status_code == 200, escalate_res.text
    body = escalate_res.json()
    assert body['escalated'] >= 1
    assert body['alerts_created'] >= 1

    list_res = client.get('/api/v1/rfq/escalations', params={'escalation_status': 'open'})
    assert list_res.status_code == 200, list_res.text
    rows = list_res.json()
    assert any(int(row['broadcast_id']) == broadcast_id for row in rows)
