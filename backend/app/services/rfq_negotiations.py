"""
RFQ negotiation strategies and dynamic counter-offer generation.

This module handles:
- Creating and managing vendor-specific negotiation strategies
- Generating counter-offers based on vendor history and strategy rules
- Recording negotiation rounds and tracking outcomes
- Aggregating negotiation analytics and success metrics
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..crud import log_audit
from ..models import (
    RFQNegotiationStrategy,
    RFQNegotiationRound,
    RFQNegotiationFeedback,
    RFQHumanReviewRequest,
    RFQParsedQuote,
    Vendor,
)


_ALLOWED_FEEDBACK_OUTCOMES = {'accepted', 'rejected', 'counter_offered', 'expired'}


def create_or_update_negotiation_strategy(
    db: Session,
    vendor_id: int,
    target_unit_price_reduction_pct: float = 10.0,
    target_moq_reduction_pct: float = 15.0,
    max_acceptable_lead_time_days: int = 30,
    negotiation_rounds_limit: int = 3,
    prior_success_rate: float = 0.0,
    require_human_review_for_high_value: bool = False,
    high_value_threshold: float = 50000.0,
    is_active: bool = True,
    strategy_metadata: dict = None,
) -> RFQNegotiationStrategy:
    """
    Create or update a negotiation strategy for a vendor.
    
    Args:
        db: Database session
        vendor_id: Vendor ID
        target_unit_price_reduction_pct: Target price reduction percentage
        target_moq_reduction_pct: Target MOQ reduction percentage
        max_acceptable_lead_time_days: Maximum acceptable lead time
        negotiation_rounds_limit: Maximum negotiation rounds before escalation
        prior_success_rate: Historical success rate (0.0-1.0)
        is_active: Whether strategy is active
        strategy_metadata: Additional metadata (dict)
    
    Returns:
        RFQNegotiationStrategy instance
    """
    if strategy_metadata is None:
        strategy_metadata = {}
    
    # Check if vendor exists
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        raise ValueError(f"Vendor {vendor_id} not found")
    
    # Upsert strategy
    strategy = db.query(RFQNegotiationStrategy).filter(
        RFQNegotiationStrategy.vendor_id == vendor_id
    ).first()
    
    if strategy:
        strategy.target_unit_price_reduction_pct = target_unit_price_reduction_pct
        strategy.target_moq_reduction_pct = target_moq_reduction_pct
        strategy.max_acceptable_lead_time_days = max_acceptable_lead_time_days
        strategy.negotiation_rounds_limit = negotiation_rounds_limit
        strategy.prior_success_rate = prior_success_rate
        strategy.require_human_review_for_high_value = bool(require_human_review_for_high_value)
        strategy.high_value_threshold = float(high_value_threshold)
        strategy.is_active = is_active
        strategy.strategy_metadata = strategy_metadata
    else:
        strategy = RFQNegotiationStrategy(
            vendor_id=vendor_id,
            target_unit_price_reduction_pct=target_unit_price_reduction_pct,
            target_moq_reduction_pct=target_moq_reduction_pct,
            max_acceptable_lead_time_days=max_acceptable_lead_time_days,
            negotiation_rounds_limit=negotiation_rounds_limit,
            prior_success_rate=prior_success_rate,
            require_human_review_for_high_value=bool(require_human_review_for_high_value),
            high_value_threshold=float(high_value_threshold),
            is_active=is_active,
            strategy_metadata=strategy_metadata,
        )
        db.add(strategy)
    
    db.commit()
    db.refresh(strategy)
    log_audit(
        db,
        'rfq',
        vendor_id,
        'rfq_negotiation_strategy_upsert',
        (
            f'vendor_id={vendor_id} rounds_limit={strategy.negotiation_rounds_limit} '
            f'high_value_review={bool(strategy.require_human_review_for_high_value)}'
        ),
        performed_by='sales-ops',
    )
    return strategy


def create_human_review_request(
    db: Session,
    *,
    quote_id: int,
    request_reason: str,
    requested_by: str,
) -> RFQHumanReviewRequest:
    quote = db.query(RFQParsedQuote).filter(RFQParsedQuote.id == int(quote_id)).first()
    if quote is None:
        raise ValueError('RFQ parsed quote not found')

    strategy = get_negotiation_strategy(db, quote.vendor_id)
    if strategy is None:
        raise ValueError('No active negotiation strategy for vendor')

    estimated_total_value = float(quote.total_price or 0.0)
    if estimated_total_value <= 0 and quote.unit_price is not None and quote.quantity is not None:
        estimated_total_value = float(quote.unit_price) * int(quote.quantity)

    existing_pending = (
        db.query(RFQHumanReviewRequest)
        .filter(
            RFQHumanReviewRequest.quote_id == int(quote_id),
            RFQHumanReviewRequest.status == 'pending',
        )
        .first()
    )
    if existing_pending is not None:
        return existing_pending

    row = RFQHumanReviewRequest(
        quote_id=int(quote.id),
        attempt_id=int(quote.attempt_id),
        vendor_id=int(quote.vendor_id),
        estimated_total_value=float(estimated_total_value),
        high_value_threshold=float(strategy.high_value_threshold or 50000.0),
        status='pending',
        request_reason=str(request_reason or '').strip()[:2000] or None,
        requested_by=str(requested_by or 'system').strip()[:128] or 'system',
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit(
        db,
        'rfq',
        row.attempt_id,
        'rfq_human_review_requested',
        f'quote_id={row.quote_id} value={row.estimated_total_value} threshold={row.high_value_threshold}',
        performed_by=row.requested_by,
    )
    return row


def list_human_review_requests(
    db: Session,
    *,
    status: str | None = None,
    vendor_id: int | None = None,
    quote_id: int | None = None,
) -> list[RFQHumanReviewRequest]:
    query = db.query(RFQHumanReviewRequest)
    if status is not None:
        query = query.filter(RFQHumanReviewRequest.status == str(status).strip().lower())
    if vendor_id is not None:
        query = query.filter(RFQHumanReviewRequest.vendor_id == int(vendor_id))
    if quote_id is not None:
        query = query.filter(RFQHumanReviewRequest.quote_id == int(quote_id))
    return query.order_by(RFQHumanReviewRequest.created_at.desc(), RFQHumanReviewRequest.id.desc()).all()


def review_human_review_request(
    db: Session,
    *,
    request_id: int,
    status: str,
    review_note: str | None,
    reviewed_by: str,
) -> RFQHumanReviewRequest:
    normalized = str(status or '').strip().lower()
    if normalized not in {'approved', 'rejected'}:
        raise ValueError("status must be 'approved' or 'rejected'")

    row = db.query(RFQHumanReviewRequest).filter(RFQHumanReviewRequest.id == int(request_id)).first()
    if row is None:
        raise ValueError('Human review request not found')

    row.status = normalized
    row.review_note = str(review_note or '').strip()[:2000] or None
    row.reviewed_by = str(reviewed_by or 'reviewer').strip()[:128] or 'reviewer'
    row.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(row)

    log_audit(
        db,
        'rfq',
        row.attempt_id,
        'rfq_human_review_decision',
        f'request_id={row.id} quote_id={row.quote_id} status={row.status}',
        performed_by=row.reviewed_by,
    )
    return row


def _has_approved_human_review(db: Session, *, quote_id: int) -> bool:
    approved = (
        db.query(RFQHumanReviewRequest)
        .filter(
            RFQHumanReviewRequest.quote_id == int(quote_id),
            RFQHumanReviewRequest.status == 'approved',
        )
        .first()
    )
    return approved is not None


def list_negotiation_strategies(db: Session) -> list[RFQNegotiationStrategy]:
    """
    List all negotiation strategies.
    
    Args:
        db: Database session
    
    Returns:
        List of RFQNegotiationStrategy instances
    """
    return db.query(RFQNegotiationStrategy).order_by(
        RFQNegotiationStrategy.vendor_id
    ).all()


def get_negotiation_strategy(db: Session, vendor_id: int) -> RFQNegotiationStrategy:
    """
    Get negotiation strategy for a vendor.
    
    Args:
        db: Database session
        vendor_id: Vendor ID
    
    Returns:
        RFQNegotiationStrategy instance or None
    """
    return db.query(RFQNegotiationStrategy).filter(
        RFQNegotiationStrategy.vendor_id == vendor_id,
        RFQNegotiationStrategy.is_active == True,
    ).first()


def generate_counter_offer(
    db: Session,
    quote_id: int,
    reason: str = "Optimizing terms based on budget and timeline requirements",
) -> RFQNegotiationRound:
    """
    Generate a counter-offer for a parsed quote based on vendor's negotiation strategy.
    
    Strategy:
    1. Get parsed quote and check vendor's negotiation strategy
    2. Calculate target unit price (apply reduction target)
    3. Calculate target MOQ (apply reduction target)
    4. Use lead time from parsed quote if within acceptable limits
    5. Record the counter-offer and return it
    
    Args:
        db: Database session
        quote_id: RFQParsedQuote ID
        reason: Justification for counter-offer
    
    Returns:
        RFQNegotiationRound instance
    
    Raises:
        ValueError: If quote not found or no strategy for vendor
    """
    # Fetch the parsed quote
    quote = db.query(RFQParsedQuote).filter(
        RFQParsedQuote.id == quote_id
    ).first()
    
    if not quote:
        raise ValueError(f"Quote {quote_id} not found")
    
    # Get vendor's negotiation strategy
    strategy = get_negotiation_strategy(db, quote.vendor_id)
    if not strategy:
        raise ValueError(
            f"No active negotiation strategy for vendor {quote.vendor_id}"
        )

    estimated_total_value = float(quote.total_price or 0.0)
    if estimated_total_value <= 0 and quote.unit_price is not None and quote.quantity is not None:
        estimated_total_value = float(quote.unit_price) * int(quote.quantity)

    if (
        bool(strategy.require_human_review_for_high_value)
        and estimated_total_value >= float(strategy.high_value_threshold or 50000.0)
        and not _has_approved_human_review(db, quote_id=quote_id)
    ):
        raise ValueError('Human review approval required for high-value deal before counter-offer generation')
    
    # Check if we've exceeded max rounds for this quote
    existing_rounds = db.query(RFQNegotiationRound).filter(
        RFQNegotiationRound.quote_id == quote_id
    ).count()
    
    round_number = existing_rounds + 1
    if round_number > strategy.negotiation_rounds_limit:
        raise ValueError(
            f"Negotiation limit ({strategy.negotiation_rounds_limit} rounds) "
            f"exceeded for quote {quote_id}"
        )
    
    # Calculate counter-offer terms
    counter_unit_price = None
    if quote.unit_price:
        # Apply target price reduction
        reduction_factor = 1.0 - (strategy.target_unit_price_reduction_pct / 100.0)
        counter_unit_price = quote.unit_price * reduction_factor
    
    counter_moq = None
    if quote.minimum_order_quantity:
        # Apply target MOQ reduction
        reduction_factor = 1.0 - (strategy.target_moq_reduction_pct / 100.0)
        counter_moq = max(1, int(quote.minimum_order_quantity * reduction_factor))
    
    # Use lead time from quote if acceptable
    counter_lead_time = None
    if quote.lead_time_days and quote.lead_time_days <= strategy.max_acceptable_lead_time_days:
        counter_lead_time = quote.lead_time_days
    elif quote.lead_time_days:
        counter_lead_time = strategy.max_acceptable_lead_time_days
    
    # Create negotiation round record
    round_record = RFQNegotiationRound(
        quote_id=quote_id,
        attempt_id=quote.attempt_id,
        vendor_id=quote.vendor_id,
        round_number=round_number,
        counter_offer_unit_price=counter_unit_price,
        counter_offer_moq=counter_moq,
        counter_offer_lead_time_days=counter_lead_time,
        justification=reason,
        status='pending',
        generated_by='system',
    )
    
    db.add(round_record)
    db.commit()
    db.refresh(round_record)

    log_audit(
        db,
        'rfq',
        round_record.attempt_id,
        'rfq_counter_offer_generated',
        (
            f'quote_id={quote_id} round={round_record.round_number} '
            f'counter_unit_price={round_record.counter_offer_unit_price}'
        ),
        performed_by='negotiation-ai',
    )
    
    return round_record


def record_negotiation_round_response(
    db: Session,
    round_id: int,
    vendor_response: str,
    status: str = 'counter_offered',  # counter_offered/accepted/rejected
) -> RFQNegotiationRound:
    """
    Record vendor's response to a counter-offer.
    
    Args:
        db: Database session
        round_id: RFQNegotiationRound ID
        vendor_response: Text of vendor's response
        status: 'counter_offered', 'accepted', or 'rejected'
    
    Returns:
        Updated RFQNegotiationRound instance
    
    Raises:
        ValueError: If round not found
    """
    round_record = db.query(RFQNegotiationRound).filter(
        RFQNegotiationRound.id == round_id
    ).first()
    
    if not round_record:
        raise ValueError(f"Negotiation round {round_id} not found")
    
    round_record.vendor_response = vendor_response
    round_record.status = status
    
    db.commit()
    db.refresh(round_record)
    
    return round_record


def list_negotiation_rounds(
    db: Session,
    quote_id: int = None,
    attempt_id: int = None,
    vendor_id: int = None,
) -> list[RFQNegotiationRound]:
    """
    List negotiation rounds with optional filters.
    
    Args:
        db: Database session
        quote_id: Filter by quote ID
        attempt_id: Filter by attempt ID
        vendor_id: Filter by vendor ID
    
    Returns:
        List of RFQNegotiationRound instances
    """
    query = db.query(RFQNegotiationRound)
    
    if quote_id:
        query = query.filter(RFQNegotiationRound.quote_id == quote_id)
    if attempt_id:
        query = query.filter(RFQNegotiationRound.attempt_id == attempt_id)
    if vendor_id:
        query = query.filter(RFQNegotiationRound.vendor_id == vendor_id)
    
    return query.order_by(RFQNegotiationRound.created_at.desc()).all()


def record_negotiation_feedback(
    db: Session,
    *,
    round_id: int,
    outcome: str,
    realized_unit_price: float | None,
    realized_moq: int | None,
    realized_lead_time_days: int | None,
    feedback_note: str | None,
    feedback_metadata: dict | None,
    recorded_by: str,
) -> RFQNegotiationFeedback:
    round_record = db.query(RFQNegotiationRound).filter(RFQNegotiationRound.id == int(round_id)).first()
    if round_record is None:
        raise ValueError('Negotiation round not found')

    normalized_outcome = str(outcome or '').strip().lower()
    if normalized_outcome not in _ALLOWED_FEEDBACK_OUTCOMES:
        raise ValueError(f'Unsupported outcome; allowed: {sorted(_ALLOWED_FEEDBACK_OUTCOMES)}')

    row = (
        db.query(RFQNegotiationFeedback)
        .filter(RFQNegotiationFeedback.round_id == int(round_id))
        .first()
    )
    if row is None:
        row = RFQNegotiationFeedback(
            round_id=int(round_record.id),
            quote_id=int(round_record.quote_id),
            attempt_id=int(round_record.attempt_id),
            vendor_id=int(round_record.vendor_id),
        )
        db.add(row)

    row.outcome = normalized_outcome
    row.realized_unit_price = float(realized_unit_price) if realized_unit_price is not None else None
    row.realized_moq = int(realized_moq) if realized_moq is not None else None
    row.realized_lead_time_days = int(realized_lead_time_days) if realized_lead_time_days is not None else None
    row.feedback_note = str(feedback_note or '').strip()[:3000] or None
    row.feedback_metadata = feedback_metadata or {}
    row.recorded_by = str(recorded_by or 'system').strip()[:128] or 'system'

    if normalized_outcome in {'accepted', 'rejected', 'counter_offered'}:
        round_record.status = normalized_outcome
    db.add(round_record)
    db.flush()

    _refresh_strategy_success_rate_from_feedback(db, vendor_id=int(round_record.vendor_id))

    db.commit()
    db.refresh(row)

    log_audit(
        db,
        'rfq',
        int(round_record.attempt_id),
        'rfq_negotiation_feedback_recorded',
        f'round_id={round_id} outcome={normalized_outcome}',
        performed_by=row.recorded_by,
    )
    return row


def list_negotiation_feedback(
    db: Session,
    *,
    vendor_id: int | None = None,
    quote_id: int | None = None,
    outcome: str | None = None,
    limit: int = 200,
) -> list[RFQNegotiationFeedback]:
    limit = max(1, min(int(limit), 500))
    query = db.query(RFQNegotiationFeedback)
    if vendor_id is not None:
        query = query.filter(RFQNegotiationFeedback.vendor_id == int(vendor_id))
    if quote_id is not None:
        query = query.filter(RFQNegotiationFeedback.quote_id == int(quote_id))
    if outcome is not None:
        query = query.filter(RFQNegotiationFeedback.outcome == str(outcome).strip().lower())
    return query.order_by(RFQNegotiationFeedback.created_at.desc(), RFQNegotiationFeedback.id.desc()).limit(limit).all()


def _refresh_strategy_success_rate_from_feedback(db: Session, *, vendor_id: int) -> None:
    strategy = db.query(RFQNegotiationStrategy).filter(RFQNegotiationStrategy.vendor_id == int(vendor_id)).first()
    if strategy is None:
        return

    rows = (
        db.query(RFQNegotiationFeedback.outcome)
        .filter(RFQNegotiationFeedback.vendor_id == int(vendor_id))
        .all()
    )
    outcomes = [str(row.outcome or '').strip().lower() for row in rows]
    decided = [x for x in outcomes if x in {'accepted', 'rejected'}]
    if not decided:
        return

    accepted = sum(1 for x in decided if x == 'accepted')
    rejected = sum(1 for x in decided if x == 'rejected')
    success_rate = accepted / len(decided)

    strategy.prior_success_rate = round(success_rate, 4)
    metadata = strategy.strategy_metadata or {}
    metadata['feedback_samples'] = len(decided)
    metadata['feedback_accepted'] = accepted
    metadata['feedback_rejected'] = rejected
    metadata['feedback_loop_enabled'] = True
    metadata['feedback_last_updated_at'] = datetime.utcnow().isoformat()
    strategy.strategy_metadata = metadata
    db.add(strategy)


def negotiation_analytics(
    db: Session,
    window_days: int = 30,
) -> dict:
    """
    Get negotiation analytics and outcomes summary.
    
    Computes:
    - Total negotiation rounds in window
    - Distribution by status (accepted/rejected/pending)
    - Acceptance rate
    - Average price/MOQ reductions achieved
    - Per-vendor breakdown
    
    Args:
        db: Database session
        window_days: Number of days to look back (default 30)
    
    Returns:
        Dictionary with analytics summary
    """
    cutoff_date = datetime.utcnow() - timedelta(days=window_days)
    
    # Get all negotiation rounds in window
    rounds = db.query(RFQNegotiationRound).filter(
        RFQNegotiationRound.created_at >= cutoff_date
    ).all()
    
    total_rounds = len(rounds)
    accepted = sum(1 for r in rounds if r.status == 'accepted')
    rejected = sum(1 for r in rounds if r.status == 'rejected')
    pending = sum(1 for r in rounds if r.status == 'pending')
    counter_offered = sum(1 for r in rounds if r.status == 'counter_offered')
    
    accepted_rate = (accepted / total_rounds) if total_rounds > 0 else 0.0
    
    # Calculate average price reductions achieved
    # (for rounds with counter_offer_unit_price, compare to original quote price)
    price_reduction_rates = []
    moq_reduction_rates = []
    
    for round_record in rounds:
        if round_record.counter_offer_unit_price and round_record.status == 'accepted':
            quote = db.query(RFQParsedQuote).filter(
                RFQParsedQuote.id == round_record.quote_id
            ).first()
            if quote and quote.unit_price:
                reduction_rate = (
                    (quote.unit_price - round_record.counter_offer_unit_price)
                    / quote.unit_price
                ) * 100.0
                price_reduction_rates.append(reduction_rate)
        
        if round_record.counter_offer_moq and round_record.status == 'accepted':
            quote = db.query(RFQParsedQuote).filter(
                RFQParsedQuote.id == round_record.quote_id
            ).first()
            if quote and quote.minimum_order_quantity:
                reduction_rate = (
                    (quote.minimum_order_quantity - round_record.counter_offer_moq)
                    / quote.minimum_order_quantity
                ) * 100.0
                moq_reduction_rates.append(reduction_rate)
    
    avg_price_reduction = (
        sum(price_reduction_rates) / len(price_reduction_rates)
        if price_reduction_rates
        else 0.0
    )
    avg_moq_reduction = (
        sum(moq_reduction_rates) / len(moq_reduction_rates)
        if moq_reduction_rates
        else 0.0
    )
    
    # Per-vendor breakdown
    by_vendor = {}
    for round_record in rounds:
        vendor_id = str(round_record.vendor_id)
        if vendor_id not in by_vendor:
            by_vendor[vendor_id] = {
                'total_rounds': 0,
                'accepted': 0,
                'rejected': 0,
                'pending': 0,
                'counter_offered': 0,
            }
        
        by_vendor[vendor_id]['total_rounds'] += 1
        if round_record.status == 'accepted':
            by_vendor[vendor_id]['accepted'] += 1
        elif round_record.status == 'rejected':
            by_vendor[vendor_id]['rejected'] += 1
        elif round_record.status == 'pending':
            by_vendor[vendor_id]['pending'] += 1
        elif round_record.status == 'counter_offered':
            by_vendor[vendor_id]['counter_offered'] += 1
    
    return {
        'generated_at': datetime.utcnow(),
        'window_days': window_days,
        'total_negotiation_rounds': total_rounds,
        'rounds_accepted': accepted,
        'rounds_rejected': rejected,
        'rounds_pending': pending,
        'rounds_counter_offered': counter_offered,
        'accepted_rate': round(accepted_rate, 4),
        'average_price_reduction_achieved': round(avg_price_reduction, 2),
        'average_moq_reduction_achieved': round(avg_moq_reduction, 2),
        'by_vendor': by_vendor,
    }
