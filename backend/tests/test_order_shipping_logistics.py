from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def _create_order() -> int:
    create_res = client.post(
        '/api/v1/orders/b2c',
        json={
            'currency': 'usd',
            'total_amount': 299.5,
            'order_items': [
                {'sku': 'SHIP-100', 'qty': 2, 'price': 149.75},
            ],
            'shipping_address': {'line1': 'A-12 Market Street', 'city': 'Pune', 'country': 'IN'},
        },
    )
    assert create_res.status_code == 200, create_res.text
    return int(create_res.json()['id'])


def test_create_shipping_shipment_and_list_for_order():
    order_id = _create_order()

    create_ship_res = client.post(
        f'/api/v1/orders/b2c/{order_id}/shipping/shipments',
        json={
            'provider': 'BlueDart',
            'service_level': 'express',
            'shipping_cost': 49.0,
            'estimated_delivery_days': 3,
            'shipment_metadata': {'priority': 'high'},
            'performed_by': 'ops-logistics',
        },
    )
    assert create_ship_res.status_code == 200, create_ship_res.text
    shipment = create_ship_res.json()
    assert shipment['order_id'] == order_id
    assert shipment['provider'] == 'BlueDart'
    assert shipment['status'] == 'booked'
    assert shipment['tracking_number'].startswith('TRK-')

    list_res = client.get(f'/api/v1/orders/b2c/{order_id}/shipping/shipments')
    assert list_res.status_code == 200, list_res.text
    rows = list_res.json()
    assert len(rows) >= 1
    assert rows[0]['order_id'] == order_id

    tracking_res = client.get(f'/api/v1/orders/b2c/{order_id}/tracking')
    assert tracking_res.status_code == 200, tracking_res.text
    tracking = tracking_res.json()
    assert tracking['tracking_number'] == shipment['tracking_number']
    assert tracking['carrier'] == 'BlueDart'
    assert tracking['fulfillment_status'] == 'shipped'


def test_shipping_status_sync_updates_order_tracking_timeline():
    order_id = _create_order()

    shipment_res = client.post(
        f'/api/v1/orders/b2c/{order_id}/shipping/shipments',
        json={
            'provider': 'Delhivery',
            'service_level': 'standard',
            'shipping_cost': 29.0,
            'estimated_delivery_days': 5,
            'performed_by': 'ops-logistics',
        },
    )
    assert shipment_res.status_code == 200, shipment_res.text
    shipment = shipment_res.json()
    shipment_id = int(shipment['id'])

    transit_res = client.patch(
        f'/api/v1/orders/b2c/shipping/shipments/{shipment_id}',
        json={
            'status': 'in_transit',
            'current_location': 'Mumbai Hub',
            'note': 'Departed origin hub',
            'performed_by': 'carrier-sync',
        },
    )
    assert transit_res.status_code == 200, transit_res.text
    assert transit_res.json()['status'] == 'in_transit'

    delivered_res = client.patch(
        f'/api/v1/orders/b2c/shipping/shipments/{shipment_id}',
        json={
            'status': 'delivered',
            'current_location': 'Customer Doorstep',
            'note': 'Delivered by courier',
            'performed_by': 'carrier-sync',
        },
    )
    assert delivered_res.status_code == 200, delivered_res.text
    assert delivered_res.json()['status'] == 'delivered'
    assert delivered_res.json()['delivered_at'] is not None

    tracking_res = client.get(f'/api/v1/orders/b2c/{order_id}/tracking')
    assert tracking_res.status_code == 200, tracking_res.text
    tracking = tracking_res.json()
    assert tracking['fulfillment_status'] == 'delivered'
    assert tracking['status'] == 'fulfilled'
    statuses = [event['status'] for event in tracking['events']]
    assert statuses[0] == 'created'
    assert 'shipped' in statuses
    assert 'in_transit' in statuses
    assert statuses[-1] == 'delivered'
