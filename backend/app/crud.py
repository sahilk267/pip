from datetime import datetime
import re

from sqlalchemy.orm import Session

from . import models, schemas
from . import crm_models


def _normalize_name(value: str) -> str:
    lowercase = value.strip().lower()
    normalized = re.sub(r'[^a-z0-9]+', '_', lowercase)
    return normalized[:128]


def log_audit(db: Session, entity_type: str, entity_id: int | None, action: str, detail: str, performed_by: str = 'system') -> None:
    log = models.AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        detail=detail,
        performed_by=performed_by,
    )
    db.add(log)
    db.commit()


def create_vendor(db: Session, vendor_in: schemas.VendorCreate):
    normalized = _normalize_name(vendor_in.name)
    existing = (
        db.query(models.Vendor)
        .filter(models.Vendor.normalized_name == normalized)
        .first()
    )
    if existing:
        return existing, False

    vendor = models.Vendor(
        name=vendor_in.name,
        normalized_name=normalized,
        source=vendor_in.source,
        contact_email=vendor_in.contact_email,
        phone=vendor_in.phone,
        industry=vendor_in.industry,
        vendor_metadata=vendor_in.vendor_metadata or {},
    )
    db.add(vendor)
    db.commit()
    db.refresh(vendor)

    log_audit(db, 'vendor', vendor.id, 'ingest', 'Vendor ingested and deduplicated')
    return vendor, True


def create_product(db: Session, product_in: schemas.ProductCreate):
    normalized = _normalize_name(product_in.name)
    existing = (
        db.query(models.Product)
        .filter(models.Product.normalized_name == normalized, models.Product.sku == product_in.sku)
        .first()
    )
    if existing:
        return existing, False

    product = models.Product(
        name=product_in.name,
        normalized_name=normalized,
        vendor_id=product_in.vendor_id,
        sku=product_in.sku,
        price=product_in.price,
        attributes=product_in.attributes or {},
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    log_audit(db, 'product', product.id, 'ingest', 'Product ingested and normalized')
    return product, True
