"""
Tests for RFQ negotiation strategies and dynamic counter-offer generation.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models import Vendor, Lead


client = TestClient(app)


def _create_full_rfq_flow_with_quote(vendor_id: int, lead_id: int) -> int:
    """Helper to create full RFQ flow and return parsed quote ID."""
    # Create broadcast
    broadcast_payload = {
        'lead_id': lead_id,
        'vendor_ids': [vendor_id],
        'channel': 'email',
        'message': 'Test negotiation RFQ',
        'auto_match_limit': 10,
        'performed_by': 'test_user',
    }
    resp = client.post('/api/v1/rfq/broadcasts', json=broadcast_payload)
    broadcast_data = resp.json()
    broadcast_id = broadcast_data['id']
    
    # Get delivery attempts
    resp = client.get(f'/api/v1/rfq/broadcasts/{broadcast_id}/deliveries')
    deliveries = resp.json()
    attempt_id = deliveries[0]['id']
    
    # Record vendor response
    response_payload = {
        'response_status': 'replied',
        'response_text': 'Unit price 100 USD, quantity 500 units, MOQ 500, lead time 30 days',
        'quoted_price': 100.0,
        'recorded_by': 'test_system',
    }
    resp = client.post(f'/api/v1/rfq/deliveries/{attempt_id}/response', json=response_payload)
    response_data = resp.json()
    response_id = response_data['id']
    
    # Parse the quote
    parse_payload = {
        'parser_version': 'rule-v1',
        'performed_by': 'quote-parser',
    }
    resp = client.post(f'/api/v1/rfq/responses/{response_id}/parse', json=parse_payload)
    parsed_data = resp.json()
    quote_id = parsed_data['id']
    
    return quote_id


def test_create_negotiation_strategy_and_generate_counter_offer(reset_database):
    """
    Test creating a negotiation strategy for a vendor and generating a counter-offer.
    """
    db = SessionLocal()
    
    # Create vendor
    vendor = Vendor(
        name='Test Vendor',
        normalized_name='test_vendor',
        contact_email='test@vendor.com',
        phone='+1234567890',
        source='manual',
    )
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    
    # Create lead
    lead = Lead(
        full_name='John Doe',
        email='john@test.com',
        phone='+1234567890',
        company='Test Company',
        stage='qualified',
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    vendor_id = vendor.id
    lead_id = lead.id
    db.close()
    
    # Create RFQ flow and get quote ID
    quote_id = _create_full_rfq_flow_with_quote(vendor_id, lead_id)
    
    # Create negotiation strategy via API
    strategy_payload = {
        'vendor_id': vendor_id,
        'target_unit_price_reduction_pct': 10.0,
        'target_moq_reduction_pct': 20.0,
        'max_acceptable_lead_time_days': 45,
        'negotiation_rounds_limit': 3,
        'prior_success_rate': 0.8,
        'is_active': True,
        'strategy_metadata': {'notes': 'Test vendor'},
    }
    response = client.post('/api/v1/rfq/negotiation-strategies', json=strategy_payload)
    assert response.status_code == 200
    strategy_data = response.json()
    assert strategy_data['vendor_id'] == vendor_id
    assert strategy_data['target_unit_price_reduction_pct'] == 10.0
    
    # Generate counter-offer via API
    counter_offer_payload = {
        'quote_id': quote_id,
        'reason': 'Optimizing terms based on budget requirements',
    }
    response = client.post(
        f'/api/v1/rfq/quotes/{quote_id}/counter-offer',
        json=counter_offer_payload,
    )
    assert response.status_code == 200
    round_data = response.json()
    
    # Verify counter-offer
    assert round_data['quote_id'] == quote_id
    assert round_data['vendor_id'] == vendor_id
    assert round_data['round_number'] == 1
    assert round_data['counter_offer_unit_price'] == pytest.approx(90.0, rel=0.01)
    assert round_data['counter_offer_moq'] == 400
    assert round_data['status'] == 'pending'


def test_negotiation_analytics_and_multi_round(reset_database):
    """
    Test negotiation analytics by creating negotiation rounds.
    """
    db = SessionLocal()
    
    # Create vendor
    vendor = Vendor(
        name='Analytics Vendor',
        normalized_name='analytics_vendor',
        contact_email='analytics@vendor.com',
        phone='+1234567890',
        source='manual',
    )
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    
    # Create lead
    lead = Lead(
        full_name='Jane Doe',
        email='jane@test.com',
        phone='+1234567890',
        company='Analytics Company',
        stage='qualified',
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    vendor_id = vendor.id
    lead_id = lead.id
    db.close()
    
    # Create RFQ flow and get quote ID
    quote_id = _create_full_rfq_flow_with_quote(vendor_id, lead_id)
    
    # Create negotiation strategy via API
    strategy_payload = {
        'vendor_id': vendor_id,
        'target_unit_price_reduction_pct': 15.0,
        'target_moq_reduction_pct': 25.0,
        'max_acceptable_lead_time_days': 30,
        'negotiation_rounds_limit': 5,
        'prior_success_rate': 0.75,
        'is_active': True,
    }
    response = client.post('/api/v1/rfq/negotiation-strategies', json=strategy_payload)
    assert response.status_code == 200
    
    # Generate counter-offer
    counter_offer_payload = {
        'quote_id': quote_id,
        'reason': 'First negotiation round',
    }
    response = client.post(
        f'/api/v1/rfq/quotes/{quote_id}/counter-offer',
        json=counter_offer_payload,
    )
    assert response.status_code == 200
    first_round = response.json()
    assert first_round['round_number'] == 1
    assert first_round['status'] == 'pending'
    
    # Get negotiation rounds
    response = client.get('/api/v1/rfq/negotiation-rounds', params={'quote_id': quote_id})
    assert response.status_code == 200
    rounds = response.json()
    assert len(rounds) >= 1
    assert rounds[0]['quote_id'] == quote_id
    
    # Get negotiation analytics
    response = client.get('/api/v1/rfq/negotiation-analytics', params={'window_days': 30})
    assert response.status_code == 200
    analytics = response.json()
    assert analytics['total_negotiation_rounds'] >= 1
    assert 'by_vendor' in analytics
    assert isinstance(analytics['average_price_reduction_achieved'], float)


def test_human_review_required_for_high_value_deal(reset_database):
    db = SessionLocal()
    vendor = Vendor(
        name='High Value Vendor',
        normalized_name='high_value_vendor',
        contact_email='high@vendor.com',
        phone='+1234567890',
        source='manual',
    )
    lead = Lead(
        full_name='Alex Buyer',
        email='alex@buyer.com',
        phone='+1987654321',
        company='High Value Company',
        stage='qualified',
    )
    db.add(vendor)
    db.add(lead)
    db.commit()
    db.refresh(vendor)
    db.refresh(lead)
    vendor_id = vendor.id
    lead_id = lead.id
    db.close()

    quote_id = _create_full_rfq_flow_with_quote(vendor_id, lead_id)

    strategy_payload = {
        'vendor_id': vendor_id,
        'target_unit_price_reduction_pct': 10.0,
        'target_moq_reduction_pct': 15.0,
        'max_acceptable_lead_time_days': 30,
        'negotiation_rounds_limit': 3,
        'prior_success_rate': 0.4,
        'require_human_review_for_high_value': True,
        'high_value_threshold': 10000.0,
        'is_active': True,
    }
    response = client.post('/api/v1/rfq/negotiation-strategies', json=strategy_payload)
    assert response.status_code == 200

    blocked = client.post(
        f'/api/v1/rfq/quotes/{quote_id}/counter-offer',
        json={'quote_id': quote_id, 'reason': 'Attempt before approval'},
    )
    assert blocked.status_code == 400
    assert 'Human review approval required' in blocked.json()['detail']

    req = client.post(
        '/api/v1/rfq/human-reviews',
        json={
            'quote_id': quote_id,
            'request_reason': 'Deal size above auto-negotiation threshold',
            'requested_by': 'ops.user',
        },
    )
    assert req.status_code == 200
    request_id = req.json()['id']

    approve = client.post(
        f'/api/v1/rfq/human-reviews/{request_id}/decision',
        json={'status': 'approved', 'review_note': 'Approved for automated counter', 'reviewed_by': 'sales.manager'},
    )
    assert approve.status_code == 200
    assert approve.json()['status'] == 'approved'

    allowed = client.post(
        f'/api/v1/rfq/quotes/{quote_id}/counter-offer',
        json={'quote_id': quote_id, 'reason': 'Proceed after approval'},
    )
    assert allowed.status_code == 200
    assert allowed.json()['status'] == 'pending'


def test_human_review_rejection_keeps_gate_closed(reset_database):
    db = SessionLocal()
    vendor = Vendor(
        name='Rejected Review Vendor',
        normalized_name='rejected_review_vendor',
        contact_email='reject@vendor.com',
        phone='+1234567890',
        source='manual',
    )
    lead = Lead(
        full_name='Riley Buyer',
        email='riley@buyer.com',
        phone='+1987654321',
        company='Rejected Review Company',
        stage='qualified',
    )
    db.add(vendor)
    db.add(lead)
    db.commit()
    db.refresh(vendor)
    db.refresh(lead)
    vendor_id = vendor.id
    lead_id = lead.id
    db.close()

    quote_id = _create_full_rfq_flow_with_quote(vendor_id, lead_id)

    response = client.post(
        '/api/v1/rfq/negotiation-strategies',
        json={
            'vendor_id': vendor_id,
            'require_human_review_for_high_value': True,
            'high_value_threshold': 10000.0,
            'is_active': True,
        },
    )
    assert response.status_code == 200

    req = client.post('/api/v1/rfq/human-reviews', json={'quote_id': quote_id, 'requested_by': 'ops.user'})
    assert req.status_code == 200
    request_id = req.json()['id']

    reject = client.post(
        f'/api/v1/rfq/human-reviews/{request_id}/decision',
        json={'status': 'rejected', 'review_note': 'Need manual negotiation', 'reviewed_by': 'sales.manager'},
    )
    assert reject.status_code == 200
    assert reject.json()['status'] == 'rejected'

    blocked = client.post(
        f'/api/v1/rfq/quotes/{quote_id}/counter-offer',
        json={'quote_id': quote_id, 'reason': 'Should remain blocked'},
    )
    assert blocked.status_code == 400
    assert 'Human review approval required' in blocked.json()['detail']


def test_negotiation_feedback_loop_updates_strategy_success_rate(reset_database):
    db = SessionLocal()
    vendor = Vendor(
        name='Feedback Loop Vendor',
        normalized_name='feedback_loop_vendor',
        contact_email='feedback@vendor.com',
        phone='+1234567890',
        source='manual',
    )
    lead_a = Lead(
        full_name='Feedback Buyer A',
        email='feedback-a@buyer.com',
        phone='+1987654321',
        company='Feedback Company A',
        stage='qualified',
    )
    lead_b = Lead(
        full_name='Feedback Buyer B',
        email='feedback-b@buyer.com',
        phone='+1987654322',
        company='Feedback Company B',
        stage='qualified',
    )
    db.add(vendor)
    db.add(lead_a)
    db.add(lead_b)
    db.commit()
    db.refresh(vendor)
    db.refresh(lead_a)
    db.refresh(lead_b)
    vendor_id = vendor.id
    quote_id_a = _create_full_rfq_flow_with_quote(vendor_id, lead_a.id)
    quote_id_b = _create_full_rfq_flow_with_quote(vendor_id, lead_b.id)
    db.close()

    strategy = client.post(
        '/api/v1/rfq/negotiation-strategies',
        json={
            'vendor_id': vendor_id,
            'target_unit_price_reduction_pct': 10.0,
            'target_moq_reduction_pct': 10.0,
            'prior_success_rate': 0.0,
            'is_active': True,
        },
    )
    assert strategy.status_code == 200, strategy.text

    round_a = client.post(
        f'/api/v1/rfq/quotes/{quote_id_a}/counter-offer',
        json={'quote_id': quote_id_a, 'reason': 'Feedback loop A'},
    )
    assert round_a.status_code == 200, round_a.text

    feedback_a = client.post(
        f"/api/v1/rfq/negotiation-rounds/{round_a.json()['id']}/feedback",
        json={
            'outcome': 'accepted',
            'realized_unit_price': 92.0,
            'realized_moq': 450,
            'feedback_note': 'Vendor accepted revised terms',
            'recorded_by': 'sales-ops',
        },
    )
    assert feedback_a.status_code == 200, feedback_a.text
    assert feedback_a.json()['outcome'] == 'accepted'

    round_b = client.post(
        f'/api/v1/rfq/quotes/{quote_id_b}/counter-offer',
        json={'quote_id': quote_id_b, 'reason': 'Feedback loop B'},
    )
    assert round_b.status_code == 200, round_b.text

    feedback_b = client.post(
        f"/api/v1/rfq/negotiation-rounds/{round_b.json()['id']}/feedback",
        json={
            'outcome': 'rejected',
            'feedback_note': 'Vendor rejected reduced price',
            'recorded_by': 'sales-ops',
        },
    )
    assert feedback_b.status_code == 200, feedback_b.text
    assert feedback_b.json()['outcome'] == 'rejected'

    list_feedback = client.get(f'/api/v1/rfq/negotiation-feedback?vendor_id={vendor_id}')
    assert list_feedback.status_code == 200, list_feedback.text
    assert len(list_feedback.json()) >= 2

    strategies = client.get('/api/v1/rfq/negotiation-strategies')
    assert strategies.status_code == 200, strategies.text
    vendor_strategy = next(s for s in strategies.json() if int(s['vendor_id']) == vendor_id)
    assert vendor_strategy['prior_success_rate'] == pytest.approx(0.5, rel=0.001)
    assert vendor_strategy['strategy_metadata'].get('feedback_loop_enabled') is True
