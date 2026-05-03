from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models


# ---------------------------------------------------------------------------
# Keyword extraction helpers
# ---------------------------------------------------------------------------

_STOP_WORDS = {
    'a', 'an', 'the', 'and', 'or', 'of', 'in', 'for', 'to', 'with',
    'by', 'on', 'at', 'is', 'are', 'from', 'this', 'that', 'unit',
    'units', 'items', 'item', 'product', 'products', 'part', 'parts',
    'panel', 'panels', 'system', 'systems', 'kit', 'kits',
}

# Category/industry keyword banks — map common product words → categories
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    'electronics': ['electronic', 'circuit', 'sensor', 'chip', 'battery', 'led', 'display',
                    'lighting', 'light', 'cable', 'wire', 'connector', 'pcb', 'semiconductor',
                    'power', 'charger', 'adapter', 'module', 'microcontroller', 'arduino'],
    'mechanical': ['bearing', 'gear', 'shaft', 'motor', 'pump', 'valve', 'seal', 'gasket',
                   'bolt', 'nut', 'screw', 'fastener', 'bracket', 'frame', 'housing',
                   'hydraulic', 'pneumatic', 'actuator', 'coupling', 'flange'],
    'chemical': ['chemical', 'solvent', 'acid', 'resin', 'polymer', 'adhesive', 'coating',
                 'paint', 'lubricant', 'grease', 'oil', 'cleaner', 'reagent', 'compound'],
    'packaging': ['box', 'carton', 'bag', 'wrap', 'label', 'tape', 'pallet', 'container',
                  'bottle', 'jar', 'tube', 'pouch', 'film', 'foil', 'packaging'],
    'textile': ['fabric', 'cloth', 'textile', 'yarn', 'thread', 'fiber', 'cotton', 'polyester',
                'nylon', 'wool', 'silk', 'leather', 'garment', 'uniform', 'apparel'],
    'food': ['food', 'grain', 'flour', 'sugar', 'salt', 'spice', 'oil', 'dairy', 'beverage',
             'drink', 'juice', 'snack', 'ingredient', 'additive', 'preservative'],
    'medical': ['medical', 'surgical', 'diagnostic', 'pharmaceutical', 'drug', 'medicine',
                'glove', 'syringe', 'mask', 'bandage', 'implant', 'device', 'probe'],
    'construction': ['concrete', 'steel', 'cement', 'brick', 'timber', 'lumber', 'pipe', 'duct',
                     'insulation', 'roofing', 'flooring', 'tile', 'glass', 'window', 'door'],
    'it': ['server', 'laptop', 'computer', 'software', 'hardware', 'network', 'router',
           'switch', 'storage', 'ssd', 'ram', 'cpu', 'gpu', 'printer', 'scanner'],
    'office': ['paper', 'stationery', 'pen', 'ink', 'toner', 'furniture', 'desk', 'chair',
               'shelf', 'cabinet', 'whiteboard', 'projector', 'phone'],
}


def _tokenize(text: str) -> set[str]:
    tokens = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower()).split()
    return {t for t in tokens if t not in _STOP_WORDS and len(t) > 1}


def _infer_categories_from_product(product_name: str) -> list[str]:
    tokens = _tokenize(product_name)
    matched: list[tuple[str, int]] = []
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in tokens or any(kw in t for t in tokens))
        if hits:
            matched.append((cat, hits))
    matched.sort(key=lambda x: -x[1])
    return [cat for cat, _ in matched]


# ---------------------------------------------------------------------------
# Score components
# ---------------------------------------------------------------------------

def _category_fit_score(vendor: models.Vendor, product_tokens: set[str], inferred_categories: list[str]) -> float:
    score = 0.0
    vendor_category = (vendor.category or 'uncategorized').lower()
    vendor_industry = (vendor.industry or '').lower()
    combined = vendor_category + ' ' + vendor_industry

    # Direct category match (inferred vs vendor category)
    for cat in inferred_categories:
        if cat in combined:
            score += 35.0
            break
        if any(kw in combined for kw in _CATEGORY_KEYWORDS.get(cat, [])):
            score += 20.0
            break

    # Product keyword overlap with vendor industry/category text
    vendor_tokens = _tokenize(combined)
    overlap = len(product_tokens & vendor_tokens)
    score += min(overlap * 8.0, 15.0)

    return min(score, 50.0)


def _name_relevance_score(vendor: models.Vendor, product_tokens: set[str]) -> float:
    name_tokens = _tokenize(vendor.name or '')
    meta_tokens: set[str] = set()
    if isinstance(vendor.vendor_metadata, dict):
        meta_tokens = _tokenize(' '.join(str(v) for v in vendor.vendor_metadata.values()))
    all_tokens = name_tokens | meta_tokens
    overlap = len(product_tokens & all_tokens)
    return min(overlap * 6.0, 15.0)


def _quote_history_score(
    vendor: models.Vendor,
    target_price: Optional[float],
    db: Session,
) -> tuple[float, dict]:
    attempts = (
        db.query(models.RFQDeliveryAttempt)
        .filter(models.RFQDeliveryAttempt.vendor_id == vendor.id)
        .count()
    )
    responses = (
        db.query(models.RFQVendorResponse)
        .filter(models.RFQVendorResponse.vendor_id == vendor.id)
        .count()
    )
    quotes = (
        db.query(models.RFQParsedQuote)
        .filter(models.RFQParsedQuote.vendor_id == vendor.id)
        .all()
    )

    response_rate = (responses / attempts) if attempts > 0 else None
    avg_price: Optional[float] = None
    if quotes:
        prices = [q.unit_price for q in quotes if q.unit_price is not None]
        if prices:
            avg_price = sum(prices) / len(prices)

    score = 0.0
    # Response rate bonus (0–20 pts)
    if response_rate is not None:
        score += response_rate * 20.0
    # Price competitiveness vs target (0–15 pts)
    if avg_price is not None and target_price and target_price > 0:
        ratio = avg_price / target_price
        if ratio <= 1.0:
            score += 15.0
        elif ratio <= 1.2:
            score += 10.0
        elif ratio <= 1.5:
            score += 4.0

    stats = {
        'total_rfqs': attempts,
        'total_responses': responses,
        'response_rate': round(response_rate * 100, 1) if response_rate is not None else None,
        'avg_quoted_price': round(avg_price, 2) if avg_price is not None else None,
        'quote_count': len(quotes),
    }
    return min(score, 35.0), stats


def _confidence_label(score: float) -> str:
    if score >= 75:
        return 'excellent'
    if score >= 55:
        return 'good'
    if score >= 35:
        return 'fair'
    return 'low'


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class VendorMatch:
    vendor_id: int
    name: str
    email: Optional[str]
    industry: Optional[str]
    category: str
    category_confidence: float
    score: float
    confidence: str
    score_breakdown: dict = field(default_factory=dict)
    quote_stats: dict = field(default_factory=dict)


def rank_vendors_for_rfq(
    db: Session,
    *,
    product_name: str,
    target_price: Optional[float] = None,
    limit: int = 10,
) -> list[VendorMatch]:
    limit = max(1, min(int(limit), 50))
    vendors = db.query(models.Vendor).all()
    if not vendors:
        return []

    product_tokens = _tokenize(product_name)
    inferred_categories = _infer_categories_from_product(product_name)

    results: list[VendorMatch] = []
    for vendor in vendors:
        cat_score = _category_fit_score(vendor, product_tokens, inferred_categories)
        name_score = _name_relevance_score(vendor, product_tokens)
        hist_score, quote_stats = _quote_history_score(vendor, target_price, db)

        total = cat_score + name_score + hist_score

        results.append(VendorMatch(
            vendor_id=vendor.id,
            name=vendor.name,
            email=vendor.contact_email,
            industry=vendor.industry,
            category=vendor.category or 'uncategorized',
            category_confidence=float(vendor.category_confidence or 0.0),
            score=round(total, 1),
            confidence=_confidence_label(total),
            score_breakdown={
                'category_fit': round(cat_score, 1),
                'name_relevance': round(name_score, 1),
                'quote_history': round(hist_score, 1),
            },
            quote_stats=quote_stats,
        ))

    results.sort(key=lambda m: (-m.score, m.name))
    return results[:limit]
