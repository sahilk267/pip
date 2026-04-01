from __future__ import annotations

from typing import Dict

from sqlalchemy.orm import Session

from .. import models
from .enrichment_sources import fetch_product_attributes, fetch_vendor_enrichment


def run_enrichment(db: Session, limit: int = 10) -> Dict[str, int]:
    vendors = (
        db.query(models.Vendor)
        .order_by(models.Vendor.updated_at.asc())
        .limit(limit)
        .all()
    )

    enriched = 0
    for vendor in vendors:
        enrichment = fetch_vendor_enrichment(vendor.name)
        if not enrichment:
            continue
        metadata = vendor.vendor_metadata or {}
        metadata.update(enrichment)
        vendor.vendor_metadata = metadata
        db.add(vendor)
        enriched += 1

    db.commit()
    return {'enriched': enriched, 'scanned': len(vendors)}


def enrich_product_attributes(db: Session, limit: int = 20) -> Dict[str, int]:
    products = db.query(models.Product).limit(limit).all()
    annotated = 0
    for product in products:
        attrs = fetch_product_attributes(product.sku or '')
        if not attrs:
            continue
        attributes = product.attributes or {}
        attributes.update(attrs)
        product.attributes = attributes
        # If the B2C feed provides a direct category label, bootstrap product
        # category/confidence before rule-based categorization runs.
        feed_category = attrs.get('category')
        if feed_category:
            if not product.category or product.category == 'uncategorized' or (product.category_confidence or 0.0) < 0.6:
                product.category = str(feed_category)
                product.category_confidence = 0.6
                product.categorization_source = 'b2c-feed'
                product.category_notes = 'Set from B2C attribute feed'
        db.add(product)
        annotated += 1

    db.commit()
    return {'annotated': annotated, 'scanned': len(products)}
