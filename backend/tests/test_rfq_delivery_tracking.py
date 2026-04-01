from fastapi.testclient import TestClient

from backend.app.main import app


def _create_vendor(client: TestClient, name: str) -> int:
    res = client.post(
        '/api/v1/vendors',
        json={
            'name': name,
            'source': 'test-suite',
        },
    )
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def test_rfq_delivery_tracking_flow():
    client = TestClient(app)

    lead = client.post(
        '/api/v1/leads',
        json={
            'full_name': 'RFQ Buyer',
            'email': 'rfq-buyer@example.com',
            'source': 'web',
        },
    )
    assert lead.status_code == 200, lead.text
    lead_id = int(lead.json()['id'])

    vendor_1 = _create_vendor(client, 'RFQ Vendor One')
    vendor_2 = _create_vendor(client, 'RFQ Vendor Two')

    broadcast = client.post(
        '/api/v1/rfq/broadcasts',
        json={
            'lead_id': lead_id,
            'vendor_ids': [vendor_1, vendor_2],
            'channel': 'email',
            'message': 'Please share quote for 500 units.',
            'performed_by': 'sales-qa',
        },
    )
    assert broadcast.status_code == 200, broadcast.text
    broadcast_body = broadcast.json()
    broadcast_id = int(broadcast_body['id'])
    assert broadcast_body['status'] == 'in_progress'

    deliveries = client.get(f'/api/v1/rfq/broadcasts/{broadcast_id}/deliveries')
    assert deliveries.status_code == 200, deliveries.text
    rows = deliveries.json()
    assert len(rows) == 2
    assert all(row['status'] == 'queued' for row in rows)

    delivered = client.patch(
        f"/api/v1/rfq/deliveries/{rows[0]['id']}",
        json={
            'status': 'delivered',
            'external_ref': 'msg-1001',
            'performed_by': 'sales-qa',
        },
    )
    assert delivered.status_code == 200, delivered.text
    assert delivered.json()['status'] == 'delivered'

    failed = client.patch(
        f"/api/v1/rfq/deliveries/{rows[1]['id']}",
        json={
            'status': 'failed',
            'error_detail': 'Mailbox bounced',
            'performed_by': 'sales-qa',
        },
    )
    assert failed.status_code == 200, failed.text
    assert failed.json()['status'] == 'failed'

    broadcasts = client.get('/api/v1/rfq/broadcasts')
    assert broadcasts.status_code == 200, broadcasts.text
    broadcast_map = {int(row['id']): row for row in broadcasts.json()}
    assert broadcast_map[broadcast_id]['status'] == 'partial_failed'

    summary = client.get('/api/v1/rfq/delivery-summary', params={'window_days': 30})
    assert summary.status_code == 200, summary.text
    stats = summary.json()
    assert stats['total_attempts'] == 2
    assert stats['delivered'] == 1
    assert stats['failed'] == 1
    assert stats['by_channel']['email']['total'] == 2


def test_rfq_delivery_sync_updates_queued_attempts():
    client = TestClient(app)

    _create_vendor(client, 'Auto Match Vendor A')
    _create_vendor(client, 'Auto Match Vendor B')
    _create_vendor(client, 'Auto Match Vendor C')

    broadcast = client.post(
        '/api/v1/rfq/broadcasts',
        json={
            'auto_match_limit': 3,
            'channel': 'email',
            'message': 'Automated RFQ broadcast',
            'performed_by': 'sales-qa',
        },
    )
    assert broadcast.status_code == 200, broadcast.text
    broadcast_id = int(broadcast.json()['id'])

    sync = client.post('/api/v1/rfq/deliveries/sync', params={'limit': 100, 'performed_by': 'sync-test'})
    assert sync.status_code == 200, sync.text
    sync_body = sync.json()
    assert sync_body['scanned'] >= 3
    assert sync_body['delivered'] + sync_body['failed'] == sync_body['scanned']

    deliveries = client.get(f'/api/v1/rfq/broadcasts/{broadcast_id}/deliveries')
    assert deliveries.status_code == 200, deliveries.text
    rows = deliveries.json()
    assert rows
    assert all(row['status'] in {'delivered', 'failed'} for row in rows)
