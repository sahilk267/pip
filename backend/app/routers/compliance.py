from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..schemas import (
    ComplianceReport,
    ScrapingComplianceResponse,
    RegionalLegalReviewCreate,
    RegionalLegalReviewResponse,
    RegionalLegalReviewUpdateRequest,
)
from ..services.compliance import generate_compliance_report
from ..services import scraping_governance
from ..services.legal_review import (
    get_checklist_template,
    get_region_regulations,
    list_legal_reviews,
    record_legal_review,
    update_legal_review,
)

router = APIRouter()


@router.get('/api/v1/compliance/report', response_model=ComplianceReport)
def get_compliance_report(db: Session = Depends(get_db)) -> ComplianceReport:
    return generate_compliance_report(db)


@router.get('/api/v1/compliance/scraping-controls', response_model=ScrapingComplianceResponse)
def scraping_compliance_bundle(locale: str = 'en') -> ScrapingComplianceResponse:
    return ScrapingComplianceResponse(
        policy=scraping_governance.connector_policy(locale=locale),
        checklist=scraping_governance.compliance_checklist(locale=locale),
    )


@router.get('/api/v1/compliance/legal-review/template')
def get_legal_review_template(
    regulation: str = Query(..., min_length=4, max_length=32),
    entity_type: Optional[str] = Query(default=None),
) -> dict:
    try:
        items = get_checklist_template(regulation=regulation, entity_type=entity_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {'regulation': regulation.upper(), 'items': items}


@router.get('/api/v1/compliance/legal-review/region-regulations')
def get_regulations_for_region(region: str = Query(default='GLOBAL')) -> dict:
    return {'region': region.upper(), 'regulations': get_region_regulations(region)}


@router.post('/api/v1/compliance/legal-reviews', response_model=RegionalLegalReviewResponse)
def create_legal_review(
    payload: RegionalLegalReviewCreate,
    db: Session = Depends(get_db),
) -> RegionalLegalReviewResponse:
    try:
        row = record_legal_review(
            db,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            region=payload.region,
            regulation=payload.regulation,
            checklist_items=[item.model_dump() for item in payload.checklist_items],
            reviewer=payload.reviewer,
            notes=payload.notes,
            status=payload.status,
            performed_by=payload.performed_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RegionalLegalReviewResponse.model_validate(row)


@router.get('/api/v1/compliance/legal-reviews', response_model=list[RegionalLegalReviewResponse])
def list_legal_reviews_endpoint(
    entity_type: Optional[str] = Query(default=None),
    region: Optional[str] = Query(default=None),
    regulation: Optional[str] = Query(default=None),
    review_status: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[RegionalLegalReviewResponse]:
    rows = list_legal_reviews(db, entity_type=entity_type, region=region, regulation=regulation, status=review_status, limit=limit)
    return [RegionalLegalReviewResponse.model_validate(row) for row in rows]


@router.patch('/api/v1/compliance/legal-reviews/{review_id}', response_model=RegionalLegalReviewResponse)
def update_legal_review_endpoint(
    review_id: int,
    payload: RegionalLegalReviewUpdateRequest,
    db: Session = Depends(get_db),
) -> RegionalLegalReviewResponse:
    try:
        row = update_legal_review(
            db,
            review_id=review_id,
            status=payload.status,
            checklist_items=[item.model_dump() for item in payload.checklist_items] if payload.checklist_items else None,
            notes=payload.notes,
            reviewer=payload.reviewer,
            performed_by=payload.performed_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return RegionalLegalReviewResponse.model_validate(row)
