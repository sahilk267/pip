from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from sqlalchemy.orm import Session

from .. import models

_RULES_DIR = Path(__file__).resolve().parents[3] / 'ai_engines'
_RULES_FILE = _RULES_DIR / 'categorization_rules.json'


@dataclass(frozen=True)
class Rule:
    keywords: tuple[str, ...]
    category: str
    confidence: float


def _load_rules() -> tuple[list[Rule], list[Rule]]:
    vendor_rules: list[Rule] = []
    product_rules: list[Rule] = []
    if _RULES_FILE.exists():
        data = json.loads(_RULES_FILE.read_text(encoding='utf-8'))
        for row in data.get('vendor_rules', []):
            vendor_rules.append(
                Rule(
                    keywords=tuple(k.lower() for k in row['keywords']),
                    category=row['category'],
                    confidence=float(row['confidence']),
                )
            )
        for row in data.get('product_rules', []):
            product_rules.append(
                Rule(
                    keywords=tuple(k.lower() for k in row['keywords']),
                    category=row['category'],
                    confidence=float(row['confidence']),
                )
            )
    if not vendor_rules:
        vendor_rules = [
            Rule(('supply', 'trading', 'components'), 'general_supply', 0.55),
        ]
    if not product_rules:
        product_rules = [
            Rule(('module', 'kit', 'assembly'), 'assemblies', 0.55),
        ]
    return vendor_rules, product_rules


def _apply_rules(text: str, rules: Iterable[Rule]) -> tuple[str, float] | None:
    haystack = text.lower()
    best: tuple[str, float] | None = None
    for rule in rules:
        if any(k in haystack for k in rule.keywords):
            if best is None or rule.confidence > best[1]:
                best = (rule.category, rule.confidence)
    return best


def _should_recategorize_vendor(v: models.Vendor) -> bool:
    return v.category == 'uncategorized' or (v.category_confidence or 0) < 0.5


def _should_recategorize_product(p: models.Product) -> bool:
    return p.category == 'uncategorized' or (p.category_confidence or 0) < 0.5


def categorize_pending_vendors_and_products(db: Session, limit: int = 50) -> dict[str, int]:
    vendor_rules, product_rules = _load_rules()
    now = datetime.now(timezone.utc)
    vendors_updated = 0
    products_updated = 0

    vendors = (
        db.query(models.Vendor)
        .order_by(models.Vendor.updated_at.asc())
        .limit(limit * 2)
        .all()
    )
    for vendor in vendors:
        if not _should_recategorize_vendor(vendor):
            continue
        blob = f'{vendor.name} {vendor.industry or ""}'
        match = _apply_rules(blob, vendor_rules)
        if not match:
            continue
        category, confidence = match
        vendor.category = category
        vendor.category_confidence = confidence
        vendor.categorization_source = 'rule-engine'
        vendor.last_categorized_at = now
        db.add(vendor)
        vendors_updated += 1
        if vendors_updated >= limit:
            break

    products = (
        db.query(models.Product)
        .order_by(models.Product.created_at.asc())
        .limit(limit * 2)
        .all()
    )
    for product in products:
        if not _should_recategorize_product(product):
            continue
        attr_blob = ' '.join(
            str(v) for v in (product.attributes or {}).values() if isinstance(v, str)
        )
        blob = f'{product.name} {attr_blob}'
        match = _apply_rules(blob, product_rules)
        if not match:
            continue
        category, confidence = match
        product.category = category
        product.category_confidence = confidence
        product.categorization_source = 'rule-engine'
        product.last_categorized_at = now
        db.add(product)
        products_updated += 1
        if products_updated >= limit:
            break

    db.commit()
    return {'vendors_updated': vendors_updated, 'products_updated': products_updated}
