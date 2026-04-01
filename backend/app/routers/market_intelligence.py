from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import (
    MarketIntelligenceSummaryResponse,
    MarketOpportunityResponse,
    MarketOpportunityValidateRequest,
    MarketOpportunityValidationMetricsResponse,
    MarketOpportunityValidationResponse,
    MarketSignalIngestRequest,
    MarketSignalIngestResponse,
    MarketSourceReliabilityResponse,
)
from ..services.market_intelligence import (
    ingest_market_signals,
    list_market_opportunities,
    list_market_opportunity_validations,
    list_source_reliability,
    market_intelligence_summary,
    market_opportunity_validation_metrics,
    validate_market_opportunity,
)

router = APIRouter()


@router.post('/api/v1/market-intelligence/signals/ingest', response_model=MarketSignalIngestResponse)
def ingest_signals(payload: MarketSignalIngestRequest, db: Session = Depends(get_db)) -> MarketSignalIngestResponse:
    result = ingest_market_signals(
        db,
        events=[row.model_dump() for row in payload.events],
        performed_by=payload.performed_by,
    )
    return MarketSignalIngestResponse(**result)


@router.get('/api/v1/market-intelligence/opportunities', response_model=list[MarketOpportunityResponse])
def get_opportunities(
    region: str | None = Query(default=None),
    min_score: float = Query(default=0.0, ge=0.0, le=100.0),
    opportunity_status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[MarketOpportunityResponse]:
    rows = list_market_opportunities(
        db,
        region=region,
        min_score=min_score,
        status=opportunity_status,
        limit=limit,
    )
    return [MarketOpportunityResponse.model_validate(row) for row in rows]


@router.get('/api/v1/market-intelligence/sources/reliability', response_model=list[MarketSourceReliabilityResponse])
def get_source_reliability(
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[MarketSourceReliabilityResponse]:
    rows = list_source_reliability(db, limit=limit)
    return [MarketSourceReliabilityResponse.model_validate(row) for row in rows]


@router.get('/api/v1/market-intelligence/summary', response_model=MarketIntelligenceSummaryResponse)
def get_market_summary(
    region: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> MarketIntelligenceSummaryResponse:
    payload = market_intelligence_summary(db, region=region)
    return MarketIntelligenceSummaryResponse(**payload)


@router.get('/api/v1/market-intelligence/opportunities/validation/metrics', response_model=MarketOpportunityValidationMetricsResponse)
def get_validation_metrics(
    lookback_days: int = Query(default=30, ge=1, le=365),
    region: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> MarketOpportunityValidationMetricsResponse:
    payload = market_opportunity_validation_metrics(
        db,
        lookback_days=lookback_days,
        region=region,
    )
    return MarketOpportunityValidationMetricsResponse(**payload)


@router.patch('/api/v1/market-intelligence/opportunities/{opportunity_id}/validate', response_model=MarketOpportunityValidationResponse)
def validate_opportunity(
    opportunity_id: int,
    payload: MarketOpportunityValidateRequest,
    db: Session = Depends(get_db),
) -> MarketOpportunityValidationResponse:
    try:
        row = validate_market_opportunity(
            db,
            opportunity_id=opportunity_id,
            decision=payload.decision,
            validator_type=payload.validator_type,
            validation_score=payload.validation_score,
            rejection_reason=payload.rejection_reason,
            validation_notes=payload.validation_notes,
            validated_by=payload.validated_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return MarketOpportunityValidationResponse.model_validate(row)


@router.get('/api/v1/market-intelligence/opportunities/{opportunity_id}/validations', response_model=list[MarketOpportunityValidationResponse])
def get_opportunity_validations(
    opportunity_id: int,
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[MarketOpportunityValidationResponse]:
    rows = list_market_opportunity_validations(db, opportunity_id=opportunity_id, limit=limit)
    return [MarketOpportunityValidationResponse.model_validate(row) for row in rows]
