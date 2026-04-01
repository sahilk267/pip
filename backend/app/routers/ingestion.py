from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..services.discovery import run_discovery
from ..services.vendor_opt_out import list_vendor_opt_out_rules, upsert_vendor_opt_out_rule
from ..database import get_db

router = APIRouter()


@router.post('/api/v1/vendors', response_model=schemas.VendorResponse)
def ingest_vendor(vendor: schemas.VendorCreate, db: Session = Depends(get_db)) -> schemas.VendorResponse:
    entity, created = crud.create_vendor(db, vendor)
    if not created:
        raise HTTPException(status_code=409, detail='Vendor already exists (deduplicated).')
    return entity


@router.post('/api/v1/products', response_model=schemas.ProductResponse)
def ingest_product(product: schemas.ProductCreate, db: Session = Depends(get_db)) -> schemas.ProductResponse:
    entity, created = crud.create_product(db, product)
    if not created:
        raise HTTPException(status_code=409, detail='Product already exists (deduplicated).')
    return entity


@router.get('/api/v1/vendors', response_model=list[schemas.VendorResponse])
def list_vendors(db: Session = Depends(get_db)) -> list[schemas.VendorResponse]:
    vendors = db.query(models.Vendor).order_by(models.Vendor.created_at.desc()).limit(50).all()
    return vendors


@router.get('/api/v1/products', response_model=list[schemas.ProductResponse])
def list_products(db: Session = Depends(get_db)) -> list[schemas.ProductResponse]:
    products = db.query(models.Product).order_by(models.Product.created_at.desc()).limit(50).all()
    return products


@router.post('/api/v1/vendors/{vendor_id}/opt-out', response_model=schemas.VendorOptOutRuleResponse)
def upsert_vendor_opt_out(
    vendor_id: int,
    payload: schemas.VendorOptOutRuleCreate,
    db: Session = Depends(get_db),
) -> schemas.VendorOptOutRuleResponse:
    try:
        row = upsert_vendor_opt_out_rule(
            db,
            vendor_id=vendor_id,
            channel=payload.channel,
            is_opted_out=payload.is_opted_out,
            rule_type=payload.rule_type,
            reason=payload.reason,
            created_by=payload.created_by,
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if detail == 'Vendor not found' else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return schemas.VendorOptOutRuleResponse.model_validate(row)


@router.get('/api/v1/vendors/opt-out', response_model=list[schemas.VendorOptOutRuleResponse])
def get_vendor_opt_out_rules(
    vendor_id: int | None = None,
    only_active: bool = True,
    limit: int = 200,
    db: Session = Depends(get_db),
) -> list[schemas.VendorOptOutRuleResponse]:
    rows = list_vendor_opt_out_rules(
        db,
        vendor_id=vendor_id,
        only_active=only_active,
        limit=limit,
    )
    return [schemas.VendorOptOutRuleResponse.model_validate(row) for row in rows]


@router.post('/api/v1/ingestion/discovery')
def run_discovery_job(db: Session = Depends(get_db)) -> dict:
    summary = run_discovery(db)
    return {
        'source_count': len(summary),
        'summary': summary,
    }
