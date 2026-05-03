from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..schemas import (
    RFQBroadcastCreate,
    RFQBroadcastResponse,
    RFQDeliveryAttemptPatch,
    RFQDeliveryAttemptResponse,
    RFQParsedQuoteResponse,
    RFQDeliverySummary,
    RFQDeliverySyncResponse,
    RFQQuoteParseRequest,
    RFQQuoteParsingSummary,
    RFQVendorResponseCreate,
    RFQVendorResponseResponse,
    RFQVendorResponseAnalytics,
    RFQQuoteAuthenticityRequest,
    RFQQuoteAuthenticityCheckResponse,
    RFQQuoteAuthenticityCheckSummary,
    EntityVersionRecordResponse,
    EntityVersionRollbackRequest,
    RFQEscalationCaseResponse,
    RFQEscalationRunResponse,
)
from ..schemas import (
    RFQRateLimitRuleCreate,
    RFQRateLimitRuleResponse,
    RFQRateLimitUsageSummary,
)
from ..schemas import (
    RFQNegotiationStrategyCreate,
    RFQNegotiationStrategyResponse,
    RFQCounterOfferRequest,
    RFQNegotiationRoundResponse,
    RFQNegotiationFeedbackCreate,
    RFQNegotiationFeedbackResponse,
    RFQNegotiationAnalytics,
    RFQHumanReviewRequestCreate,
    RFQHumanReviewDecision,
    RFQHumanReviewRequestResponse,
)
from ..services.rfq_delivery import (
    create_rfq_broadcast,
    delivery_summary,
    list_delivery_attempts,
    list_rfq_broadcasts,
    sync_delivery_attempts,
    update_delivery_attempt,
)
from ..services.rfq_vendor_response import (
    list_responses_for_attempt,
    record_vendor_response,
    vendor_response_analytics,
)
from ..services.rfq_quote_parsing import (
    list_parsed_quotes_for_response,
    parse_quote_response,
    quote_parsing_summary,
)
from ..services.rfq_rate_limiting import (
    check_rfq_rate_limit,
    get_rate_limit_usage_summary,
    list_rate_limit_rules,
    upsert_rate_limit_rule,
)
from ..services.rfq_negotiations import (
    create_or_update_negotiation_strategy,
    list_negotiation_strategies,
    generate_counter_offer,
    list_negotiation_rounds,
    record_negotiation_feedback,
    list_negotiation_feedback,
    create_human_review_request,
    list_human_review_requests,
    review_human_review_request,
    negotiation_analytics,
)
from ..services.rfq_quote_authenticity import (
    validate_quote_authenticity,
    list_authenticity_checks,
    authenticity_check_summary,
)
from ..services.rfq_escalation import list_escalation_cases, run_automated_escalation
from ..services.versioning import list_entity_versions, rollback_quote_version
from ..services.vendor_matching import rank_vendors_for_rfq

router = APIRouter()


@router.get('/api/v1/rfq/vendor-suggestions')
def vendor_suggestions(
    product_name: str = Query(..., min_length=2, max_length=200),
    target_price: Optional[float] = Query(default=None, ge=0),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> list[dict]:
    matches = rank_vendors_for_rfq(
        db,
        product_name=product_name,
        target_price=target_price,
        limit=limit,
    )
    return [
        {
            'vendor_id': m.vendor_id,
            'name': m.name,
            'email': m.email,
            'industry': m.industry,
            'category': m.category,
            'category_confidence': m.category_confidence,
            'score': m.score,
            'confidence': m.confidence,
            'score_breakdown': m.score_breakdown,
            'quote_stats': m.quote_stats,
        }
        for m in matches
    ]


@router.post('/api/v1/rfq/broadcasts', response_model=RFQBroadcastResponse)
def create_broadcast(payload: RFQBroadcastCreate, db: Session = Depends(get_db)) -> RFQBroadcastResponse:
    try:
        check_rfq_rate_limit(db, lead_id=payload.lead_id, performed_by=payload.performed_by)
        broadcast, _ = create_rfq_broadcast(
            db,
            lead_id=payload.lead_id,
            vendor_ids=payload.vendor_ids,
            channel=payload.channel,
            message=payload.message,
            auto_match_limit=payload.auto_match_limit,
            performed_by=payload.performed_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = status.HTTP_429_TOO_MANY_REQUESTS if 'rate limit exceeded' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return RFQBroadcastResponse.model_validate(broadcast)


@router.get('/api/v1/rfq/broadcasts', response_model=list[RFQBroadcastResponse])
def list_broadcasts(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[RFQBroadcastResponse]:
    rows = list_rfq_broadcasts(db, limit=limit)
    return [RFQBroadcastResponse.model_validate(row) for row in rows]


@router.get('/api/v1/rfq/broadcasts/{broadcast_id}/deliveries', response_model=list[RFQDeliveryAttemptResponse])
def list_broadcast_deliveries(broadcast_id: int, db: Session = Depends(get_db)) -> list[RFQDeliveryAttemptResponse]:
    rows = list_delivery_attempts(db, broadcast_id=broadcast_id)
    return [RFQDeliveryAttemptResponse.model_validate(row) for row in rows]


@router.patch('/api/v1/rfq/deliveries/{attempt_id}', response_model=RFQDeliveryAttemptResponse)
def patch_delivery_attempt(
    attempt_id: int,
    payload: RFQDeliveryAttemptPatch,
    db: Session = Depends(get_db),
) -> RFQDeliveryAttemptResponse:
    try:
        row = update_delivery_attempt(
            db,
            attempt_id=attempt_id,
            status=payload.status,
            external_ref=payload.external_ref,
            error_detail=payload.error_detail,
            performed_by=payload.performed_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if detail == 'RFQ delivery attempt not found' else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return RFQDeliveryAttemptResponse.model_validate(row)


@router.post('/api/v1/rfq/deliveries/sync', response_model=RFQDeliverySyncResponse)
def sync_deliveries(
    limit: int = Query(default=300, ge=1, le=1000),
    performed_by: str = Query(default='rfq-sync'),
    db: Session = Depends(get_db),
) -> RFQDeliverySyncResponse:
    payload = sync_delivery_attempts(db, limit=limit, performed_by=performed_by)
    return RFQDeliverySyncResponse(**payload)


@router.post('/api/v1/rfq/escalations/auto-run', response_model=RFQEscalationRunResponse)
def run_rfq_escalation(
    response_sla_hours: int = Query(default=24, ge=0, le=720),
    expansion_limit: int = Query(default=3, ge=0, le=20),
    performed_by: str = Query(default='rfq-escalation'),
    db: Session = Depends(get_db),
) -> RFQEscalationRunResponse:
    payload = run_automated_escalation(
        db,
        response_sla_hours=response_sla_hours,
        expansion_limit=expansion_limit,
        performed_by=performed_by,
    )
    return RFQEscalationRunResponse(
        scanned=payload['scanned'],
        escalated=payload['escalated'],
        alerts_created=payload['alerts_created'],
        expansion_attempts=payload['expansion_attempts'],
        cases=[RFQEscalationCaseResponse.model_validate(row) for row in payload['cases']],
    )


@router.get('/api/v1/rfq/escalations', response_model=list[RFQEscalationCaseResponse])
def get_rfq_escalations(
    escalation_status: str | None = Query(default='open'),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[RFQEscalationCaseResponse]:
    rows = list_escalation_cases(db, status=escalation_status, limit=limit)
    return [RFQEscalationCaseResponse.model_validate(row) for row in rows]


@router.get('/api/v1/rfq/delivery-summary', response_model=RFQDeliverySummary)
def rfq_delivery_summary(
    window_days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> RFQDeliverySummary:
    payload = delivery_summary(db, window_days=window_days)
    return RFQDeliverySummary(**payload)


@router.post('/api/v1/rfq/deliveries/{attempt_id}/response', response_model=RFQVendorResponseResponse)
def create_vendor_response(
    attempt_id: int,
    payload: RFQVendorResponseCreate,
    db: Session = Depends(get_db),
) -> RFQVendorResponseResponse:
    try:
        row = record_vendor_response(
            db,
            attempt_id=attempt_id,
            response_status=payload.response_status,
            response_text=payload.response_text,
            quoted_price=payload.quoted_price,
            recorded_by=payload.recorded_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return RFQVendorResponseResponse.model_validate(row)


@router.get('/api/v1/rfq/deliveries/{attempt_id}/responses', response_model=list[RFQVendorResponseResponse])
def list_attempt_responses(
    attempt_id: int,
    db: Session = Depends(get_db),
) -> list[RFQVendorResponseResponse]:
    rows = list_responses_for_attempt(db, attempt_id=attempt_id)
    return [RFQVendorResponseResponse.model_validate(r) for r in rows]


@router.post('/api/v1/rfq/responses/{response_id}/parse', response_model=RFQParsedQuoteResponse)
def parse_response_quote(
    response_id: int,
    payload: RFQQuoteParseRequest,
    db: Session = Depends(get_db),
) -> RFQParsedQuoteResponse:
    try:
        row = parse_quote_response(
            db,
            response_id=response_id,
            parser_version=payload.parser_version,
            performed_by=payload.performed_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return RFQParsedQuoteResponse.model_validate(row)


@router.get('/api/v1/rfq/responses/{response_id}/parsed-quotes', response_model=list[RFQParsedQuoteResponse])
def get_parsed_quotes_for_response(
    response_id: int,
    db: Session = Depends(get_db),
) -> list[RFQParsedQuoteResponse]:
    rows = list_parsed_quotes_for_response(db, response_id=response_id)
    return [RFQParsedQuoteResponse.model_validate(row) for row in rows]


@router.get('/api/v1/rfq/quotes/{quote_id}/versions', response_model=list[EntityVersionRecordResponse])
def get_quote_versions(
    quote_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[EntityVersionRecordResponse]:
    rows = list_entity_versions(db, entity_type='quote', entity_id=quote_id, limit=limit)
    return [EntityVersionRecordResponse.model_validate(row) for row in rows]


@router.post('/api/v1/rfq/quotes/{quote_id}/versions/{version_number}/rollback', response_model=RFQParsedQuoteResponse)
def rollback_quote(
    quote_id: int,
    version_number: int,
    payload: EntityVersionRollbackRequest,
    db: Session = Depends(get_db),
) -> RFQParsedQuoteResponse:
    try:
        row = rollback_quote_version(
            db,
            quote_id=quote_id,
            version_number=version_number,
            reason=payload.reason,
            performed_by=payload.performed_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if detail in {'RFQ parsed quote not found', 'Version not found'} else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return RFQParsedQuoteResponse.model_validate(row)


@router.get('/api/v1/rfq/vendor-response-analytics', response_model=RFQVendorResponseAnalytics)
def rfq_vendor_response_analytics(
    window_days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> RFQVendorResponseAnalytics:
    payload = vendor_response_analytics(db, window_days=window_days)
    return RFQVendorResponseAnalytics(**payload)


@router.get('/api/v1/rfq/quote-parsing-summary', response_model=RFQQuoteParsingSummary)
def rfq_quote_summary(
    window_days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> RFQQuoteParsingSummary:
    payload = quote_parsing_summary(db, window_days=window_days)
    return RFQQuoteParsingSummary(**payload)


@router.post('/api/v1/rfq/rate-limit/rules', response_model=RFQRateLimitRuleResponse)
def create_or_update_rate_limit_rule(
    payload: RFQRateLimitRuleCreate,
    performed_by: str = Query(default='admin'),
    db: Session = Depends(get_db),
) -> RFQRateLimitRuleResponse:
    try:
        rule = upsert_rate_limit_rule(
            db,
            entity_type=payload.entity_type,
            entity_key=payload.entity_key,
            max_per_window=payload.max_per_window,
            window_hours=payload.window_hours,
            is_active=payload.is_active,
            performed_by=performed_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RFQRateLimitRuleResponse.model_validate(rule)


@router.get('/api/v1/security/rate-limit/rules', response_model=list[RFQRateLimitRuleResponse])
@router.get('/api/v1/rfq/rate-limit/rules', response_model=list[RFQRateLimitRuleResponse])
def get_rate_limit_rules(db: Session = Depends(get_db)) -> list[RFQRateLimitRuleResponse]:
    rows = list_rate_limit_rules(db)
    return [RFQRateLimitRuleResponse.model_validate(r) for r in rows]


@router.get('/api/v1/rfq/rate-limit/usage', response_model=RFQRateLimitUsageSummary)
def get_rate_limit_usage(
    window_hours: int = Query(default=24, ge=1, le=720),
    db: Session = Depends(get_db),
) -> RFQRateLimitUsageSummary:
    payload = get_rate_limit_usage_summary(db, window_hours=window_hours)
    return RFQRateLimitUsageSummary(**payload)


@router.post('/api/v1/rfq/negotiation-strategies', response_model=RFQNegotiationStrategyResponse)
def create_negotiation_strategy(
    payload: RFQNegotiationStrategyCreate,
    db: Session = Depends(get_db),
) -> RFQNegotiationStrategyResponse:
    try:
        strategy = create_or_update_negotiation_strategy(
            db,
            vendor_id=payload.vendor_id,
            target_unit_price_reduction_pct=payload.target_unit_price_reduction_pct,
            target_moq_reduction_pct=payload.target_moq_reduction_pct,
            max_acceptable_lead_time_days=payload.max_acceptable_lead_time_days,
            negotiation_rounds_limit=payload.negotiation_rounds_limit,
            prior_success_rate=payload.prior_success_rate,
            require_human_review_for_high_value=payload.require_human_review_for_high_value,
            high_value_threshold=payload.high_value_threshold,
            is_active=payload.is_active,
            strategy_metadata=payload.strategy_metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RFQNegotiationStrategyResponse.model_validate(strategy)


@router.get('/api/v1/rfq/negotiation-strategies', response_model=list[RFQNegotiationStrategyResponse])
def get_negotiation_strategies(db: Session = Depends(get_db)) -> list[RFQNegotiationStrategyResponse]:
    strategies = list_negotiation_strategies(db)
    return [RFQNegotiationStrategyResponse.model_validate(s) for s in strategies]


@router.post('/api/v1/rfq/human-reviews', response_model=RFQHumanReviewRequestResponse)
def request_human_review(
    payload: RFQHumanReviewRequestCreate,
    db: Session = Depends(get_db),
) -> RFQHumanReviewRequestResponse:
    try:
        row = create_human_review_request(
            db,
            quote_id=payload.quote_id,
            request_reason=payload.request_reason,
            requested_by=payload.requested_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return RFQHumanReviewRequestResponse.model_validate(row)


@router.get('/api/v1/rfq/human-reviews', response_model=list[RFQHumanReviewRequestResponse])
def get_human_review_requests(
    review_status: str | None = Query(default=None),
    vendor_id: int | None = Query(default=None),
    quote_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[RFQHumanReviewRequestResponse]:
    rows = list_human_review_requests(
        db,
        status=review_status,
        vendor_id=vendor_id,
        quote_id=quote_id,
    )
    return [RFQHumanReviewRequestResponse.model_validate(r) for r in rows]


@router.post('/api/v1/rfq/human-reviews/{request_id}/decision', response_model=RFQHumanReviewRequestResponse)
def decide_human_review_request(
    request_id: int,
    payload: RFQHumanReviewDecision,
    db: Session = Depends(get_db),
) -> RFQHumanReviewRequestResponse:
    try:
        row = review_human_review_request(
            db,
            request_id=request_id,
            status=payload.status,
            review_note=payload.review_note,
            reviewed_by=payload.reviewed_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return RFQHumanReviewRequestResponse.model_validate(row)


@router.post('/api/v1/rfq/quotes/{quote_id}/counter-offer', response_model=RFQNegotiationRoundResponse)
def generate_counter_offer_for_quote(
    quote_id: int,
    payload: RFQCounterOfferRequest,
    db: Session = Depends(get_db),
) -> RFQNegotiationRoundResponse:
    try:
        round_record = generate_counter_offer(
            db,
            quote_id=quote_id,
            reason=payload.reason,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return RFQNegotiationRoundResponse.model_validate(round_record)


@router.get('/api/v1/rfq/negotiation-rounds', response_model=list[RFQNegotiationRoundResponse])
def get_negotiation_rounds(
    quote_id: int = Query(default=None),
    attempt_id: int = Query(default=None),
    vendor_id: int = Query(default=None),
    db: Session = Depends(get_db),
) -> list[RFQNegotiationRoundResponse]:
    rounds = list_negotiation_rounds(
        db,
        quote_id=quote_id,
        attempt_id=attempt_id,
        vendor_id=vendor_id,
    )
    return [RFQNegotiationRoundResponse.model_validate(r) for r in rounds]


@router.post('/api/v1/rfq/negotiation-rounds/{round_id}/feedback', response_model=RFQNegotiationFeedbackResponse)
def create_negotiation_feedback(
    round_id: int,
    payload: RFQNegotiationFeedbackCreate,
    db: Session = Depends(get_db),
) -> RFQNegotiationFeedbackResponse:
    try:
        row = record_negotiation_feedback(
            db,
            round_id=round_id,
            outcome=payload.outcome,
            realized_unit_price=payload.realized_unit_price,
            realized_moq=payload.realized_moq,
            realized_lead_time_days=payload.realized_lead_time_days,
            feedback_note=payload.feedback_note,
            feedback_metadata=payload.feedback_metadata,
            recorded_by=payload.recorded_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return RFQNegotiationFeedbackResponse.model_validate(row)


@router.get('/api/v1/rfq/negotiation-feedback', response_model=list[RFQNegotiationFeedbackResponse])
def get_negotiation_feedback(
    vendor_id: int | None = Query(default=None),
    quote_id: int | None = Query(default=None),
    outcome: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[RFQNegotiationFeedbackResponse]:
    rows = list_negotiation_feedback(
        db,
        vendor_id=vendor_id,
        quote_id=quote_id,
        outcome=outcome,
        limit=limit,
    )
    return [RFQNegotiationFeedbackResponse.model_validate(r) for r in rows]


@router.get('/api/v1/rfq/negotiation-analytics', response_model=RFQNegotiationAnalytics)
def get_negotiation_analytics(
    window_days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> RFQNegotiationAnalytics:
    payload = negotiation_analytics(db, window_days=window_days)
    return RFQNegotiationAnalytics(**payload)


@router.post('/api/v1/rfq/quotes/{quote_id}/validate-authenticity', response_model=RFQQuoteAuthenticityCheckResponse)
def validate_quote(
    quote_id: int,
    payload: RFQQuoteAuthenticityRequest,
    db: Session = Depends(get_db),
) -> RFQQuoteAuthenticityCheckResponse:
    try:
        row = validate_quote_authenticity(db, quote_id=quote_id, performed_by=payload.performed_by)
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return RFQQuoteAuthenticityCheckResponse.model_validate(row)


@router.get('/api/v1/rfq/quotes/authenticity-checks', response_model=list[RFQQuoteAuthenticityCheckResponse])
def get_authenticity_checks(
    broadcast_id: Optional[int] = Query(default=None),
    verdict: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[RFQQuoteAuthenticityCheckResponse]:
    rows = list_authenticity_checks(db, broadcast_id=broadcast_id, verdict=verdict, limit=limit)
    return [RFQQuoteAuthenticityCheckResponse.model_validate(r) for r in rows]


@router.get('/api/v1/rfq/quotes/authenticity-summary', response_model=RFQQuoteAuthenticityCheckSummary)
def get_authenticity_summary(
    window_days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> RFQQuoteAuthenticityCheckSummary:
    payload = authenticity_check_summary(db, window_days=window_days)
    return RFQQuoteAuthenticityCheckSummary(**payload)
