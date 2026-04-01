from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db

router = APIRouter()


@router.patch('/api/v1/admin/vendors/{vendor_id}/category', response_model=schemas.VendorResponse)
def admin_set_vendor_category(
    vendor_id: int,
    payload: schemas.AdminCategoryPatch,
    db: Session = Depends(get_db),
) -> schemas.VendorResponse:
    vendor = db.query(models.Vendor).filter(models.Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail='Vendor not found')
    vendor.category = payload.category.strip()
    vendor.category_confidence = 1.0
    vendor.categorization_source = 'admin'
    vendor.category_notes = payload.notes
    vendor.last_categorized_at = datetime.now(timezone.utc)
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    crud.log_audit(
        db,
        'vendor',
        vendor.id,
        'categorization_override',
        f"Admin set category={payload.category} (by {payload.performed_by})",
        performed_by=payload.performed_by,
    )
    return vendor


@router.patch('/api/v1/admin/products/{product_id}/category', response_model=schemas.ProductResponse)
def admin_set_product_category(
    product_id: int,
    payload: schemas.AdminCategoryPatch,
    db: Session = Depends(get_db),
) -> schemas.ProductResponse:
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail='Product not found')
    product.category = payload.category.strip()
    product.category_confidence = 1.0
    product.categorization_source = 'admin'
    product.category_notes = payload.notes
    product.last_categorized_at = datetime.now(timezone.utc)
    db.add(product)
    db.commit()
    db.refresh(product)
    crud.log_audit(
        db,
        'product',
        product.id,
        'categorization_override',
        f"Admin set category={payload.category} (by {payload.performed_by})",
        performed_by=payload.performed_by,
    )
    return product
