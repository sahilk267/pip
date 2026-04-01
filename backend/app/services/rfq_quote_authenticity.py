"""Quote authenticity validation service.

Detects fake or duplicate quotes by running a set of checks on a parsed quote:
  - low_confidence      : parse confidence < 0.3
  - missing_unit_price  : unit_price is None
  - duplicate_same_vendor : same vendor already has a quote in this broadcast with the same
                            unit_price + quantity (exact copy submitted more than once)
  - duplicate_cross_vendor: another vendor's quote in the same broadcast shares an identical
                            raw_excerpt (possible colluded/copy-paste quote)
  - price_outlier_low   : unit_price is below Q1 - 1.5*IQR across the broadcast (needs >= 3
                          other quotes with unit_price for statistical significance)
  - price_outlier_high  : unit_price is above Q3 + 1.5*IQR (same guard)

Verdicts:
  - authentic  : no flags
  - suspicious : only soft flags (low_confidence, missing_unit_price)
  - rejected   : any hard flag (duplicate_*, price_outlier_*)
"""
from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit

_SOFT_FLAGS = frozenset({'low_confidence', 'missing_unit_price'})
_HARD_FLAGS = frozenset({'duplicate_same_vendor', 'duplicate_cross_vendor', 'price_outlier_low', 'price_outlier_high'})
_LOW_CONFIDENCE_THRESHOLD = 0.3


def validate_quote_authenticity(
    db: Session,
    *,
    quote_id: int,
    performed_by: str,
) -> models.RFQQuoteAuthenticityCheck:
    """Run all authenticity checks on a parsed quote and persist the result."""
    quote = (
        db.query(models.RFQParsedQuote)
        .filter(models.RFQParsedQuote.id == int(quote_id))
        .first()
    )
    if quote is None:
        raise ValueError('RFQ parsed quote not found')

    attempt = (
        db.query(models.RFQDeliveryAttempt)
        .filter(models.RFQDeliveryAttempt.id == int(quote.attempt_id))
        .first()
    )
    if attempt is None:
        raise ValueError('RFQ delivery attempt not found')

    broadcast_id = int(attempt.broadcast_id)
    flags: list[str] = []
    duplicate_of_quote_id: Optional[int] = None

    # --- soft flags ---------------------------------------------------------
    if float(quote.confidence or 0.0) < _LOW_CONFIDENCE_THRESHOLD:
        flags.append('low_confidence')

    if quote.unit_price is None:
        flags.append('missing_unit_price')

    # --- hard flag: duplicate same vendor -----------------------------------
    # Same vendor already has a quote for this broadcast with identical price + qty
    sibling_same_vendor = (
        db.query(models.RFQParsedQuote)
        .join(models.RFQDeliveryAttempt, models.RFQParsedQuote.attempt_id == models.RFQDeliveryAttempt.id)
        .filter(
            models.RFQDeliveryAttempt.broadcast_id == broadcast_id,
            models.RFQParsedQuote.vendor_id == int(quote.vendor_id),
            models.RFQParsedQuote.unit_price == quote.unit_price,
            models.RFQParsedQuote.quantity == quote.quantity,
            models.RFQParsedQuote.id != int(quote_id),
        )
        .first()
    )
    if sibling_same_vendor is not None:
        flags.append('duplicate_same_vendor')
        if duplicate_of_quote_id is None:
            duplicate_of_quote_id = int(sibling_same_vendor.id)

    # --- hard flag: duplicate cross-vendor (identical raw excerpt) ----------
    raw_text = str(quote.raw_excerpt or '').strip()
    if raw_text:
        sibling_cross_vendor = (
            db.query(models.RFQParsedQuote)
            .join(models.RFQDeliveryAttempt, models.RFQParsedQuote.attempt_id == models.RFQDeliveryAttempt.id)
            .filter(
                models.RFQDeliveryAttempt.broadcast_id == broadcast_id,
                models.RFQParsedQuote.raw_excerpt == raw_text,
                models.RFQParsedQuote.vendor_id != int(quote.vendor_id),
                models.RFQParsedQuote.id != int(quote_id),
            )
            .first()
        )
        if sibling_cross_vendor is not None:
            flags.append('duplicate_cross_vendor')
            if duplicate_of_quote_id is None:
                duplicate_of_quote_id = int(sibling_cross_vendor.id)

    # --- hard flags: price outlier ------------------------------------------
    if quote.unit_price is not None:
        peer_prices = [
            float(row.unit_price)
            for row in (
                db.query(models.RFQParsedQuote)
                .join(models.RFQDeliveryAttempt, models.RFQParsedQuote.attempt_id == models.RFQDeliveryAttempt.id)
                .filter(
                    models.RFQDeliveryAttempt.broadcast_id == broadcast_id,
                    models.RFQParsedQuote.unit_price.isnot(None),
                    models.RFQParsedQuote.id != int(quote_id),
                )
                .all()
            )
        ]
        if len(peer_prices) >= 3:
            sorted_prices = sorted(peer_prices)
            n = len(sorted_prices)
            q1 = statistics.median(sorted_prices[: n // 2])
            q3 = statistics.median(sorted_prices[(n + 1) // 2 :])
            iqr = q3 - q1
            lower_fence = q1 - 1.5 * iqr
            upper_fence = q3 + 1.5 * iqr
            unit_price = float(quote.unit_price)
            if unit_price < lower_fence:
                flags.append('price_outlier_low')
            elif unit_price > upper_fence:
                flags.append('price_outlier_high')

    # --- compute verdict ----------------------------------------------------
    flag_set = set(flags)
    if not flag_set:
        verdict = 'authentic'
    elif flag_set & _HARD_FLAGS:
        verdict = 'rejected'
    else:
        verdict = 'suspicious'

    # confidence score: 1.0 minus deductions per flag
    _deductions: dict[str, float] = {
        'low_confidence': 0.2,
        'missing_unit_price': 0.15,
        'duplicate_same_vendor': 0.5,
        'duplicate_cross_vendor': 0.5,
        'price_outlier_low': 0.4,
        'price_outlier_high': 0.4,
    }
    auth_confidence = max(0.0, round(1.0 - sum(_deductions.get(f, 0.1) for f in flags), 4))

    # --- upsert check record ------------------------------------------------
    existing = (
        db.query(models.RFQQuoteAuthenticityCheck)
        .filter(models.RFQQuoteAuthenticityCheck.quote_id == int(quote_id))
        .first()
    )
    if existing is None:
        row = models.RFQQuoteAuthenticityCheck(
            quote_id=int(quote_id),
            attempt_id=int(quote.attempt_id),
            vendor_id=int(quote.vendor_id),
            broadcast_id=broadcast_id,
            performed_by=str(performed_by).strip()[:128] or 'system',
        )
        db.add(row)
    else:
        row = existing

    row.verdict = verdict
    row.flags = flags
    row.duplicate_of_quote_id = duplicate_of_quote_id
    row.confidence_score = auth_confidence
    row.performed_by = str(performed_by).strip()[:128] or 'system'

    db.commit()
    db.refresh(row)

    log_audit(
        db,
        'rfq',
        int(quote.attempt_id),
        'rfq_quote_authenticity_checked',
        f'quote_id={quote_id} verdict={verdict} flags={flags}',
        performed_by=performed_by,
    )
    return row


def list_authenticity_checks(
    db: Session,
    *,
    broadcast_id: Optional[int] = None,
    verdict: Optional[str] = None,
    limit: int = 200,
) -> list[models.RFQQuoteAuthenticityCheck]:
    limit = max(1, min(int(limit), 500))
    q = db.query(models.RFQQuoteAuthenticityCheck)
    if broadcast_id is not None:
        q = q.filter(models.RFQQuoteAuthenticityCheck.broadcast_id == int(broadcast_id))
    if verdict is not None:
        q = q.filter(models.RFQQuoteAuthenticityCheck.verdict == str(verdict).strip())
    return q.order_by(models.RFQQuoteAuthenticityCheck.created_at.desc()).limit(limit).all()


def authenticity_check_summary(db: Session, *, window_days: int = 30) -> dict:
    window_days = max(1, int(window_days))
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    rows = (
        db.query(models.RFQQuoteAuthenticityCheck)
        .filter(models.RFQQuoteAuthenticityCheck.created_at >= cutoff)
        .all()
    )
    total = len(rows)
    by_verdict: dict[str, int] = {}
    flag_counts: dict[str, int] = {}
    for row in rows:
        by_verdict[row.verdict] = by_verdict.get(row.verdict, 0) + 1
        for flag in (row.flags or []):
            flag_counts[flag] = flag_counts.get(flag, 0) + 1
    return {
        'generated_at': datetime.now(timezone.utc),
        'window_days': window_days,
        'total_checks': total,
        'by_verdict': by_verdict,
        'flag_counts': flag_counts,
        'rejection_rate': round(by_verdict.get('rejected', 0) / total, 4) if total else 0.0,
        'suspicion_rate': round(by_verdict.get('suspicious', 0) / total, 4) if total else 0.0,
    }
