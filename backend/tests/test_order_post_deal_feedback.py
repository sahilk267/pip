from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def _create_order() -> int:
    res = client.post(
        '/api/v1/orders/b2c',
        json={
            'currency': 'usd',
            'total_amount': 399.0,
            'order_items': [{'sku': 'FDBK-1', 'qty': 1, 'price': 399.0}],
            'shipping_address': {'city': 'Pune', 'country': 'IN'},
        },
    )
    assert res.status_code == 200, res.text
    return int(res.json()['id'])


def test_collect_and_list_post_deal_feedback():
    order_id = _create_order()

    fb1 = client.post(
        f'/api/v1/orders/b2c/{order_id}/feedback',
        json={
            'actor_type': 'customer',
            'actor_id': 11,
            'sentiment': 'positive',
            'rating': 5,
            'feedback_text': 'Delivery experience was smooth and timely.',
            'feedback_metadata': {'channel': 'email'},
            'created_by': 'support.agent',
        },
    )
    assert fb1.status_code == 200, fb1.text
    body1 = fb1.json()
    assert body1['order_id'] == order_id
    assert body1['sentiment'] == 'positive'
    assert body1['rating'] == 5

    fb2 = client.post(
        f'/api/v1/orders/b2c/{order_id}/feedback',
        json={
            'actor_type': 'vendor',
            'actor_id': 22,
            'sentiment': 'neutral',
            'rating': 3,
            'feedback_text': 'Packaging requirements could be clearer.',
            'created_by': 'ops.manager',
        },
    )
    assert fb2.status_code == 200, fb2.text

    listed = client.get(f'/api/v1/orders/b2c/{order_id}/feedback')
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert len(rows) >= 2
    sentiments = {row['sentiment'] for row in rows}
    assert 'positive' in sentiments
    assert 'neutral' in sentiments


def test_post_deal_feedback_summary_endpoint():
    order_a = _create_order()
    order_b = _create_order()

    create_a = client.post(
        f'/api/v1/orders/b2c/{order_a}/feedback',
        json={
            'actor_type': 'customer',
            'sentiment': 'positive',
            'rating': 4,
            'feedback_text': 'Good support',
            'created_by': 'support.agent',
        },
    )
    assert create_a.status_code == 200, create_a.text

    create_b = client.post(
        f'/api/v1/orders/b2c/{order_b}/feedback',
        json={
            'actor_type': 'client',
            'sentiment': 'negative',
            'rating': 2,
            'feedback_text': 'Shipment was delayed.',
            'created_by': 'account.manager',
        },
    )
    assert create_b.status_code == 200, create_b.text

    summary_res = client.get('/api/v1/orders/b2c/feedback/summary', params={'window_days': 30})
    assert summary_res.status_code == 200, summary_res.text
    summary = summary_res.json()
    assert summary['total_feedback'] >= 2
    assert summary['average_rating'] >= 0.0
    assert summary['sentiment_counts']['positive'] >= 1
    assert summary['sentiment_counts']['negative'] >= 1
    assert summary['by_actor_type']['customer'] >= 1
