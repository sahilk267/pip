from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit
from .sales_notifications import create_sales_notification
from .versioning import capture_quote_version

_CURRENCY_PATTERNS = {
    'USD': re.compile(r'\b(?:usd|us\$|\$)\s*(\d+(?:\.\d+)?)', re.IGNORECASE),
    'INR': re.compile(r'\b(?:inr|rs\.?|₹)\s*(\d+(?:\.\d+)?)', re.IGNORECASE),
    'EUR': re.compile(r'\b(?:eur|€)\s*(\d+(?:\.\d+)?)', re.IGNORECASE),
}
_UNIT_PRICE_LABEL_PATTERN = re.compile(r'(?:unit price|price per unit|per unit)\D{0,12}(\d+(?:\.\d+)?)', re.IGNORECASE)
_UNIT_PRICE_TRAILING_PATTERN = re.compile(r'(\d+(?:\.\d+)?)\s*(?:each|/unit)', re.IGNORECASE)
_TOTAL_PRICE_PATTERN = re.compile(r'(?:total|total price|quote total|amount)\D{0,12}(\d+(?:\.\d+)?)', re.IGNORECASE)
_QUANTITY_PATTERN = re.compile(r'(?:for|qty|quantity|units?)\D{0,12}(\d{1,7})', re.IGNORECASE)
_LEAD_TIME_PATTERN = re.compile(r'(?:lead time|delivery|ships? in|dispatch in)\D{0,12}(\d{1,4})\s*(?:days?|d)', re.IGNORECASE)
_MOQ_PATTERN = re.compile(r'(?:moq|min(?:imum)? order quantity)\D{0,12}(\d{1,7})', re.IGNORECASE)


def parse_quote_response(
    db: Session,
    *,
    response_id: int,
    parser_version: str,
    performed_by: str,
) -> models.RFQParsedQuote:
    response = (
        db.query(models.RFQVendorResponse)
        .filter(models.RFQVendorResponse.id == int(response_id))
        .first()
    )
    if response is None:
        raise ValueError('RFQ vendor response not found')

    raw_text = str(response.response_text or '').strip()
    if not raw_text and response.quoted_price is None:
        raise ValueError('RFQ vendor response has no quote text or quoted_price to parse')

    parsed = _extract_quote_fields(raw_text, fallback_quoted_price=response.quoted_price)

    existing = (
        db.query(models.RFQParsedQuote)
        .filter(
            models.RFQParsedQuote.response_id == int(response_id),
            models.RFQParsedQuote.parser_version == str(parser_version),
        )
        .first()
    )
    if existing is None:
        row = models.RFQParsedQuote(
            response_id=int(response.id),
            attempt_id=int(response.attempt_id),
            vendor_id=int(response.vendor_id),
            parser_version=str(parser_version or 'rule-v1').strip()[:32] or 'rule-v1',
        )
        db.add(row)
    else:
        row = existing

    row.currency = parsed['currency']
    row.unit_price = parsed['unit_price']
    row.total_price = parsed['total_price']
    row.quantity = parsed['quantity']
    row.lead_time_days = parsed['lead_time_days']
    row.minimum_order_quantity = parsed['minimum_order_quantity']
    row.confidence = parsed['confidence']
    row.raw_excerpt = raw_text[:1000] or None
    row.parse_metadata = parsed['parse_metadata']

    db.commit()
    db.refresh(row)

    capture_quote_version(
        db,
        quote=row,
        reason=f'quote_parsed:{row.parser_version}',
        performed_by=performed_by,
    )

    log_audit(
        db,
        'rfq',
        response.attempt_id,
        'rfq_quote_parsed',
        f'response_id={response_id} confidence={row.confidence} parser={row.parser_version}',
        performed_by=performed_by,
    )
    attempt = (
        db.query(models.RFQDeliveryAttempt)
        .filter(models.RFQDeliveryAttempt.id == int(response.attempt_id))
        .first()
    )
    broadcast = None if attempt is None else (
        db.query(models.RFQBroadcast)
        .filter(models.RFQBroadcast.id == int(attempt.broadcast_id))
        .first()
    )
    create_sales_notification(
        db,
        entity_type='quote',
        entity_id=int(row.id),
        notification_type='quote_parsed',
        message=f'Parsed quote {row.id} with confidence {row.confidence}',
        priority='high' if float(row.confidence or 0.0) >= 0.7 else 'medium',
        lead_id=None if broadcast is None or broadcast.lead_id is None else int(broadcast.lead_id),
        recipient='sales-ops',
        metadata={'response_id': int(response.id), 'attempt_id': int(response.attempt_id)},
        performed_by=performed_by,
    )
    return row


def list_parsed_quotes_for_response(db: Session, *, response_id: int) -> list[models.RFQParsedQuote]:
    return (
        db.query(models.RFQParsedQuote)
        .filter(models.RFQParsedQuote.response_id == int(response_id))
        .order_by(models.RFQParsedQuote.created_at.desc(), models.RFQParsedQuote.id.desc())
        .all()
    )


def quote_parsing_summary(db: Session, *, window_days: int = 30) -> dict:
    window_days = max(1, int(window_days))
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    rows = (
        db.query(models.RFQParsedQuote)
        .filter(models.RFQParsedQuote.created_at >= cutoff)
        .all()
    )
    total_quotes = len(rows)
    average_confidence = round(sum(float(row.confidence or 0.0) for row in rows) / total_quotes, 4) if total_quotes else 0.0
    return {
        'generated_at': datetime.now(timezone.utc),
        'total_quotes': total_quotes,
        'parsed_with_unit_price': sum(1 for row in rows if row.unit_price is not None),
        'parsed_with_lead_time': sum(1 for row in rows if row.lead_time_days is not None),
        'parsed_with_quantity': sum(1 for row in rows if row.quantity is not None),
        'average_confidence': average_confidence,
    }


def _extract_quote_fields(raw_text: str, *, fallback_quoted_price: float | None) -> dict:
    text = str(raw_text or '')
    metadata: dict[str, str | float | int | bool] = {'used_fallback_quoted_price': False}
    currency = 'USD'
    unit_price = None
    total_price = None
    quantity = None
    lead_time_days = None
    minimum_order_quantity = None
    matches = 0

    for code, pattern in _CURRENCY_PATTERNS.items():
        match = pattern.search(text)
        if match:
            currency = code
            if unit_price is None:
                unit_price = float(match.group(1))
                metadata['currency_source'] = code
                matches += 1
            break

    unit_match = _UNIT_PRICE_LABEL_PATTERN.search(text)
    if unit_match:
        unit_price = float(unit_match.group(1))
        matches += 1
    elif unit_price is None:
        trailing_unit_match = _UNIT_PRICE_TRAILING_PATTERN.search(text)
        if trailing_unit_match:
            unit_price = float(trailing_unit_match.group(1))
            matches += 1

    total_match = _TOTAL_PRICE_PATTERN.search(text)
    if total_match:
        total_price = float(total_match.group(1))
        matches += 1

    quantity_match = _QUANTITY_PATTERN.search(text)
    if quantity_match:
        quantity = int(quantity_match.group(1))
        matches += 1

    lead_time_match = _LEAD_TIME_PATTERN.search(text)
    if lead_time_match:
        lead_time_days = int(lead_time_match.group(1))
        matches += 1

    moq_match = _MOQ_PATTERN.search(text)
    if moq_match:
        minimum_order_quantity = int(moq_match.group(1))
        matches += 1

    if unit_price is None and fallback_quoted_price is not None:
        unit_price = float(fallback_quoted_price)
        metadata['used_fallback_quoted_price'] = True
        matches += 1

    if total_price is None and unit_price is not None and quantity is not None:
        total_price = round(unit_price * quantity, 2)
        metadata['derived_total_price'] = True

    confidence = min(0.99, round(matches / 5.0, 4)) if matches else 0.0
    metadata['match_count'] = matches

    return {
        'currency': currency,
        'unit_price': unit_price,
        'total_price': total_price,
        'quantity': quantity,
        'lead_time_days': lead_time_days,
        'minimum_order_quantity': minimum_order_quantity,
        'confidence': confidence,
        'parse_metadata': metadata,
    }
