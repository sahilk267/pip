from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import (
    AIModelGovernanceCreate,
    AIModelGovernanceResponse,
    AIModelGovernanceReviewRequest,
    AIModelGovernanceRollbackRequest,
    CurrencyExchangeRateResponse,
    CurrencyExchangeRateUpsertRequest,
    CustomerUpdateNotificationResponse,
    DealOutcomeAnalytics,
    DealOutcomeRecordCreate,
    DealOutcomeRecordResponse,
    MultiCurrencyTaxPreviewRequest,
    MultiCurrencyTaxPreviewResponse,
    PricingApprovalRequestCreate,
    PricingApprovalRequestResponse,
    PricingApprovalReviewRequest,
    QuoteToCashRecordAdvanceRequest,
    QuoteToCashRecordCreate,
    QuoteToCashRecordResponse,
    SalesRepNotificationCreate,
    SalesRepNotificationResponse,
    SalesRepNotificationStatusPatch,
    TaxComplianceRuleResponse,
    TaxComplianceRuleUpsertRequest,
)
from ..services.ai_model_governance import (
    list_model_records,
    register_model_record,
    review_model_record,
    rollback_model_record,
)
from ..services.currency_tax import (
    pricing_preview,
    upsert_exchange_rate,
    upsert_tax_rule,
)
from ..services.customer_updates import list_customer_updates
from ..services.deal_outcomes import (
    deal_outcome_analytics,
    list_deal_outcomes,
    record_deal_outcome,
)
from ..services.pricing_approvals import (
    create_pricing_approval_request,
    list_pricing_approval_requests,
    review_pricing_approval_request,
)
from ..services.quote_to_cash import (
    advance_quote_to_cash_record,
    create_quote_to_cash_record,
    list_quote_to_cash_records,
)
from ..services.sales_notifications import (
    create_sales_notification,
    list_sales_notifications,
    update_sales_notification_status,
)

router = APIRouter()


@router.post('/api/v1/automation/sales-notifications', response_model=SalesRepNotificationResponse)
def create_notification(
    payload: SalesRepNotificationCreate,
    db: Session = Depends(get_db),
) -> SalesRepNotificationResponse:
    try:
        row = create_sales_notification(
            db,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            notification_type=payload.notification_type,
            message=payload.message,
            priority=payload.priority,
            lead_id=payload.lead_id,
            recipient=payload.recipient,
            channel=payload.channel,
            metadata=payload.metadata,
            performed_by=payload.performed_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SalesRepNotificationResponse.model_validate(row)


@router.get('/api/v1/automation/sales-notifications', response_model=list[SalesRepNotificationResponse])
def get_notifications(
    notification_status: str | None = Query(default=None),
    recipient: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[SalesRepNotificationResponse]:
    rows = list_sales_notifications(db, status=notification_status, recipient=recipient, limit=limit)
    return [SalesRepNotificationResponse.model_validate(row) for row in rows]


@router.patch('/api/v1/automation/sales-notifications/{notification_id}', response_model=SalesRepNotificationResponse)
def patch_notification_status(
    notification_id: int,
    payload: SalesRepNotificationStatusPatch,
    db: Session = Depends(get_db),
) -> SalesRepNotificationResponse:
    try:
        row = update_sales_notification_status(
            db,
            notification_id=notification_id,
            status=payload.status,
            performed_by=payload.performed_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if detail == 'Sales notification not found' else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return SalesRepNotificationResponse.model_validate(row)


@router.post('/api/v1/automation/pricing-approvals', response_model=PricingApprovalRequestResponse)
def create_approval_request(
    payload: PricingApprovalRequestCreate,
    db: Session = Depends(get_db),
) -> PricingApprovalRequestResponse:
    try:
        row = create_pricing_approval_request(
            db,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            requested_discount_pct=payload.requested_discount_pct,
            requested_discount_amount=payload.requested_discount_amount,
            reason=payload.reason,
            requested_by=payload.requested_by,
            metadata=payload.metadata,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return PricingApprovalRequestResponse.model_validate(row)


@router.get('/api/v1/automation/pricing-approvals', response_model=list[PricingApprovalRequestResponse])
def get_approval_requests(
    entity_type: str | None = Query(default=None),
    approval_status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[PricingApprovalRequestResponse]:
    rows = list_pricing_approval_requests(db, entity_type=entity_type, status=approval_status, limit=limit)
    return [PricingApprovalRequestResponse.model_validate(row) for row in rows]


@router.post('/api/v1/automation/pricing-approvals/{request_id}/review', response_model=PricingApprovalRequestResponse)
def review_approval_request(
    request_id: int,
    payload: PricingApprovalReviewRequest,
    db: Session = Depends(get_db),
) -> PricingApprovalRequestResponse:
    try:
        row = review_pricing_approval_request(
            db,
            request_id=request_id,
            decision=payload.decision,
            approved_discount_pct=payload.approved_discount_pct,
            approved_discount_amount=payload.approved_discount_amount,
            review_note=payload.review_note,
            reviewed_by=payload.reviewed_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return PricingApprovalRequestResponse.model_validate(row)


@router.post('/api/v1/automation/quote-to-cash', response_model=QuoteToCashRecordResponse)
def create_qtc_record(
    payload: QuoteToCashRecordCreate,
    db: Session = Depends(get_db),
) -> QuoteToCashRecordResponse:
    try:
        row = create_quote_to_cash_record(
            db,
            quote_id=payload.quote_id,
            order_id=payload.order_id,
            customer_id=payload.customer_id,
            external_system=payload.external_system,
            created_by=payload.created_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return QuoteToCashRecordResponse.model_validate(row)


@router.get('/api/v1/automation/quote-to-cash', response_model=list[QuoteToCashRecordResponse])
def get_qtc_records(
    qtc_status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[QuoteToCashRecordResponse]:
    rows = list_quote_to_cash_records(db, status=qtc_status, limit=limit)
    return [QuoteToCashRecordResponse.model_validate(row) for row in rows]


@router.post('/api/v1/automation/quote-to-cash/{record_id}/advance', response_model=QuoteToCashRecordResponse)
def advance_qtc_record(
    record_id: int,
    payload: QuoteToCashRecordAdvanceRequest,
    db: Session = Depends(get_db),
) -> QuoteToCashRecordResponse:
    try:
        row = advance_quote_to_cash_record(
            db,
            record_id=record_id,
            status=payload.status,
            payment_status=payload.payment_status,
            external_reference=payload.external_reference,
            performed_by=payload.performed_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return QuoteToCashRecordResponse.model_validate(row)


# ---------- Customer update notifications ----------

@router.get('/api/v1/automation/customer-updates', response_model=list[CustomerUpdateNotificationResponse])
def get_customer_updates(
    order_id: int | None = Query(default=None),
    lead_id: int | None = Query(default=None),
    update_status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[CustomerUpdateNotificationResponse]:
    rows = list_customer_updates(db, order_id=order_id, lead_id=lead_id, status=update_status, limit=limit)
    return [CustomerUpdateNotificationResponse.model_validate(row) for row in rows]


# ---------- Win/loss reason capture ----------

@router.post('/api/v1/automation/deal-outcomes', response_model=DealOutcomeRecordResponse)
def create_deal_outcome(
    payload: DealOutcomeRecordCreate,
    db: Session = Depends(get_db),
) -> DealOutcomeRecordResponse:
    try:
        row = record_deal_outcome(
            db,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            outcome=payload.outcome,
            reason_code=payload.reason_code,
            reason_detail=payload.reason_detail,
            competitor=payload.competitor,
            deal_value=payload.deal_value,
            currency=payload.currency,
            lead_id=payload.lead_id,
            customer_id=payload.customer_id,
            outcome_metadata=payload.outcome_metadata,
            recorded_by=payload.recorded_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DealOutcomeRecordResponse.model_validate(row)


@router.get('/api/v1/automation/deal-outcomes', response_model=list[DealOutcomeRecordResponse])
def get_deal_outcomes(
    entity_type: str | None = Query(default=None),
    deal_outcome: str | None = Query(default=None),
    reason_code: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[DealOutcomeRecordResponse]:
    rows = list_deal_outcomes(db, entity_type=entity_type, outcome=deal_outcome, reason_code=reason_code, limit=limit)
    return [DealOutcomeRecordResponse.model_validate(row) for row in rows]


@router.get('/api/v1/automation/deal-outcomes/analytics', response_model=DealOutcomeAnalytics)
def get_deal_outcome_analytics(
    window_days: int = Query(default=90, ge=1, le=365),
    db: Session = Depends(get_db),
) -> DealOutcomeAnalytics:
    payload = deal_outcome_analytics(db, window_days=window_days)
    return DealOutcomeAnalytics(**payload)


# ---------- AI model governance ----------

@router.post('/api/v1/automation/ai-governance/models', response_model=AIModelGovernanceResponse)
def create_ai_model_record(
    payload: AIModelGovernanceCreate,
    db: Session = Depends(get_db),
) -> AIModelGovernanceResponse:
    try:
        row = register_model_record(
            db,
            model_name=payload.model_name,
            model_type=payload.model_type,
            model_version=payload.model_version,
            approval_required=payload.approval_required,
            evaluation_metrics=payload.evaluation_metrics,
            governance_metadata=payload.governance_metadata,
            created_by=payload.created_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AIModelGovernanceResponse.model_validate(row)


@router.post('/api/v1/automation/ai-governance/models/{record_id}/review', response_model=AIModelGovernanceResponse)
def review_ai_model_record(
    record_id: int,
    payload: AIModelGovernanceReviewRequest,
    db: Session = Depends(get_db),
) -> AIModelGovernanceResponse:
    try:
        row = review_model_record(
            db,
            record_id=record_id,
            decision=payload.decision,
            reviewed_by=payload.reviewed_by,
            note=payload.note,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return AIModelGovernanceResponse.model_validate(row)


@router.post('/api/v1/automation/ai-governance/models/rollback', response_model=AIModelGovernanceResponse)
def rollback_ai_model_record(
    payload: AIModelGovernanceRollbackRequest,
    db: Session = Depends(get_db),
) -> AIModelGovernanceResponse:
    try:
        row = rollback_model_record(
            db,
            model_name=payload.model_name,
            from_version=payload.from_version,
            to_version=payload.to_version,
            reason=payload.reason,
            performed_by=payload.performed_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return AIModelGovernanceResponse.model_validate(row)


@router.get('/api/v1/automation/ai-governance/models', response_model=list[AIModelGovernanceResponse])
def get_ai_model_records(
    model_name: str | None = Query(default=None),
    governance_status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[AIModelGovernanceResponse]:
    rows = list_model_records(db, model_name=model_name, status=governance_status, limit=limit)
    return [AIModelGovernanceResponse.model_validate(row) for row in rows]


# ---------- Multi-currency & tax compliance ----------

@router.post('/api/v1/automation/currency-rates', response_model=CurrencyExchangeRateResponse)
def create_currency_rate(
    payload: CurrencyExchangeRateUpsertRequest,
    db: Session = Depends(get_db),
) -> CurrencyExchangeRateResponse:
    try:
        row = upsert_exchange_rate(
            db,
            base_currency=payload.base_currency,
            quote_currency=payload.quote_currency,
            rate=payload.rate,
            source=payload.source,
            rate_metadata=payload.rate_metadata,
            created_by=payload.created_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CurrencyExchangeRateResponse.model_validate(row)


@router.post('/api/v1/automation/tax-rules', response_model=TaxComplianceRuleResponse)
def create_tax_rule(
    payload: TaxComplianceRuleUpsertRequest,
    db: Session = Depends(get_db),
) -> TaxComplianceRuleResponse:
    try:
        row = upsert_tax_rule(
            db,
            region=payload.region,
            country_code=payload.country_code,
            tax_name=payload.tax_name,
            tax_type=payload.tax_type,
            tax_rate=payload.tax_rate,
            applies_to=payload.applies_to,
            rule_metadata=payload.rule_metadata,
            created_by=payload.created_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TaxComplianceRuleResponse.model_validate(row)


@router.post('/api/v1/automation/pricing/preview', response_model=MultiCurrencyTaxPreviewResponse)
def get_pricing_preview(
    payload: MultiCurrencyTaxPreviewRequest,
    db: Session = Depends(get_db),
) -> MultiCurrencyTaxPreviewResponse:
    try:
        result = pricing_preview(
            db,
            amount=payload.amount,
            from_currency=payload.from_currency,
            to_currency=payload.to_currency,
            country_code=payload.country_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MultiCurrencyTaxPreviewResponse(**result)

