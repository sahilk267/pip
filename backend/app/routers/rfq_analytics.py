"""RFQ Analytics — response rates, quote prices, vendor win rates per broadcast."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter()


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


# ── helpers ───────────────────────────────────────────────────────────────────

def _broadcast_stats(db: Session, window_days: int) -> list[dict[str, Any]]:
    cutoff = _utcnow() - timedelta(days=window_days)
    broadcasts = (
        db.query(models.RFQBroadcast)
        .filter(models.RFQBroadcast.created_at >= cutoff)
        .order_by(models.RFQBroadcast.created_at.desc())
        .limit(50)
        .all()
    )

    result = []
    for bc in broadcasts:
        attempts = (
            db.query(models.RFQDeliveryAttempt)
            .filter(models.RFQDeliveryAttempt.broadcast_id == bc.id)
            .all()
        )
        attempt_ids = [a.id for a in attempts]
        vendor_count = len(attempts)

        responses = []
        if attempt_ids:
            responses = (
                db.query(models.RFQVendorResponse)
                .filter(models.RFQVendorResponse.attempt_id.in_(attempt_ids))
                .all()
            )

        response_count = len(responses)
        response_rate = round(response_count / vendor_count * 100, 1) if vendor_count else 0.0

        quotes = []
        if attempt_ids:
            quotes = (
                db.query(models.RFQParsedQuote)
                .filter(models.RFQParsedQuote.attempt_id.in_(attempt_ids))
                .all()
            )

        prices = [q.unit_price for q in quotes if q.unit_price is not None]
        avg_price = round(sum(prices) / len(prices), 2) if prices else None
        best_price = min(prices) if prices else None
        lead_times = [q.lead_time_days for q in quotes if q.lead_time_days is not None]
        avg_lead_time = round(sum(lead_times) / len(lead_times), 1) if lead_times else None

        # Find winning vendor (lowest unit price)
        winning_vendor_name = None
        if quotes:
            winning_quote = min(
                (q for q in quotes if q.unit_price is not None),
                key=lambda q: q.unit_price,
                default=None,
            )
            if winning_quote:
                vendor = db.query(models.Vendor).filter(
                    models.Vendor.id == winning_quote.vendor_id
                ).first()
                winning_vendor_name = vendor.name if vendor else None

        result.append({
            "broadcast_id": bc.id,
            "message": bc.message or f"RFQ-{bc.id:04d}",
            "status": bc.status,
            "channel": bc.channel,
            "created_at": bc.created_at.isoformat() if bc.created_at else None,
            "vendor_count": vendor_count,
            "response_count": response_count,
            "response_rate": response_rate,
            "avg_unit_price": avg_price,
            "best_unit_price": best_price,
            "avg_lead_time_days": avg_lead_time,
            "winning_vendor": winning_vendor_name,
            "quote_count": len(quotes),
        })

    return result


def _vendor_win_rates(db: Session, window_days: int) -> list[dict[str, Any]]:
    """Return each vendor's quote count, win count, avg quote price, response rate."""
    cutoff = _utcnow() - timedelta(days=window_days)

    # All attempts in window
    attempt_rows = (
        db.query(models.RFQDeliveryAttempt)
        .join(models.RFQBroadcast,
              models.RFQDeliveryAttempt.broadcast_id == models.RFQBroadcast.id)
        .filter(models.RFQBroadcast.created_at >= cutoff)
        .all()
    )

    # Group by vendor
    vendor_attempts: dict[int, int] = {}
    for a in attempt_rows:
        vendor_attempts[a.vendor_id] = vendor_attempts.get(a.vendor_id, 0) + 1

    # All responses in window
    response_rows = (
        db.query(models.RFQVendorResponse)
        .join(models.RFQDeliveryAttempt,
              models.RFQVendorResponse.attempt_id == models.RFQDeliveryAttempt.id)
        .join(models.RFQBroadcast,
              models.RFQDeliveryAttempt.broadcast_id == models.RFQBroadcast.id)
        .filter(models.RFQBroadcast.created_at >= cutoff)
        .all()
    )
    vendor_responses: dict[int, int] = {}
    for r in response_rows:
        vid = r.vendor_id
        vendor_responses[vid] = vendor_responses.get(vid, 0) + 1

    # All parsed quotes in window — to find wins
    quote_rows = (
        db.query(models.RFQParsedQuote)
        .join(models.RFQDeliveryAttempt,
              models.RFQParsedQuote.attempt_id == models.RFQDeliveryAttempt.id)
        .join(models.RFQBroadcast,
              models.RFQDeliveryAttempt.broadcast_id == models.RFQBroadcast.id)
        .filter(models.RFQBroadcast.created_at >= cutoff)
        .all()
    )

    # Group quotes by broadcast to determine winner per broadcast
    broadcast_quotes: dict[int, list[models.RFQParsedQuote]] = {}
    for q in quote_rows:
        attempt = next((a for a in attempt_rows if a.id == q.attempt_id), None)
        if attempt:
            bid = attempt.broadcast_id
            broadcast_quotes.setdefault(bid, []).append(q)

    vendor_wins: dict[int, int] = {}
    vendor_prices: dict[int, list[float]] = {}
    for quotes in broadcast_quotes.values():
        priced = [q for q in quotes if q.unit_price is not None]
        if priced:
            winner = min(priced, key=lambda q: q.unit_price)
            vendor_wins[winner.vendor_id] = vendor_wins.get(winner.vendor_id, 0) + 1
        for q in priced:
            vendor_prices.setdefault(q.vendor_id, []).append(q.unit_price)

    # Build result for vendors that have at least one attempt
    vendor_ids = list(vendor_attempts.keys())
    vendors = (
        db.query(models.Vendor)
        .filter(models.Vendor.id.in_(vendor_ids))
        .all()
    )

    rows = []
    for v in vendors:
        attempts = vendor_attempts.get(v.id, 0)
        responses = vendor_responses.get(v.id, 0)
        wins = vendor_wins.get(v.id, 0)
        prices = vendor_prices.get(v.id, [])
        rows.append({
            "vendor_id": v.id,
            "vendor_name": v.name,
            "category": v.category or v.industry or "Unknown",
            "attempts": attempts,
            "responses": responses,
            "response_rate": round(responses / attempts * 100, 1) if attempts else 0.0,
            "quote_count": len(prices),
            "wins": wins,
            "win_rate": round(wins / len(prices) * 100, 1) if prices else 0.0,
            "avg_quote_price": round(sum(prices) / len(prices), 2) if prices else None,
        })

    rows.sort(key=lambda r: (-r["wins"], -r["response_rate"]))
    return rows[:15]


def _category_breakdown(db: Session, window_days: int) -> list[dict[str, Any]]:
    """Response rate and avg price broken down by vendor category."""
    cutoff = _utcnow() - timedelta(days=window_days)

    attempt_rows = (
        db.query(models.RFQDeliveryAttempt, models.Vendor.category, models.Vendor.industry)
        .join(models.Vendor, models.RFQDeliveryAttempt.vendor_id == models.Vendor.id)
        .join(models.RFQBroadcast,
              models.RFQDeliveryAttempt.broadcast_id == models.RFQBroadcast.id)
        .filter(models.RFQBroadcast.created_at >= cutoff)
        .all()
    )

    response_attempt_ids = set(
        r.attempt_id for r in
        db.query(models.RFQVendorResponse)
        .join(models.RFQDeliveryAttempt,
              models.RFQVendorResponse.attempt_id == models.RFQDeliveryAttempt.id)
        .join(models.RFQBroadcast,
              models.RFQDeliveryAttempt.broadcast_id == models.RFQBroadcast.id)
        .filter(models.RFQBroadcast.created_at >= cutoff)
        .all()
    )

    cat_data: dict[str, dict] = {}
    for attempt, cat, industry in attempt_rows:
        label = cat or industry or "Unknown"
        if label not in cat_data:
            cat_data[label] = {"attempts": 0, "responses": 0}
        cat_data[label]["attempts"] += 1
        if attempt.id in response_attempt_ids:
            cat_data[label]["responses"] += 1

    result = []
    for cat, d in sorted(cat_data.items()):
        result.append({
            "category": cat,
            "attempts": d["attempts"],
            "responses": d["responses"],
            "response_rate": round(d["responses"] / d["attempts"] * 100, 1) if d["attempts"] else 0.0,
        })
    return result


def _overall_kpis(broadcast_stats: list[dict], vendor_stats: list[dict]) -> dict[str, Any]:
    total_broadcasts = len(broadcast_stats)
    total_responses = sum(b["response_count"] for b in broadcast_stats)
    total_vendors_reached = sum(b["vendor_count"] for b in broadcast_stats)
    rates = [b["response_rate"] for b in broadcast_stats if b["vendor_count"] > 0]
    avg_response_rate = round(sum(rates) / len(rates), 1) if rates else 0.0
    all_prices = [b["avg_unit_price"] for b in broadcast_stats if b["avg_unit_price"] is not None]
    avg_quote_price = round(sum(all_prices) / len(all_prices), 2) if all_prices else None
    lead_times = [b["avg_lead_time_days"] for b in broadcast_stats if b["avg_lead_time_days"] is not None]
    avg_lead_time = round(sum(lead_times) / len(lead_times), 1) if lead_times else None
    top_vendor = vendor_stats[0]["vendor_name"] if vendor_stats else None
    total_quotes = sum(b["quote_count"] for b in broadcast_stats)

    return {
        "total_broadcasts": total_broadcasts,
        "total_vendors_reached": total_vendors_reached,
        "total_responses": total_responses,
        "total_quotes": total_quotes,
        "avg_response_rate_pct": avg_response_rate,
        "avg_quote_price_usd": avg_quote_price,
        "avg_lead_time_days": avg_lead_time,
        "top_winning_vendor": top_vendor,
    }


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/api/v1/rfq/analytics")
def rfq_analytics(
    window_days: int = Query(default=90, ge=1, le=365),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Full RFQ analytics: KPIs, per-broadcast stats, vendor win rates, category breakdown."""
    broadcast_stats = _broadcast_stats(db, window_days)
    vendor_stats = _vendor_win_rates(db, window_days)
    category_breakdown = _category_breakdown(db, window_days)
    kpis = _overall_kpis(broadcast_stats, vendor_stats)

    return {
        "window_days": window_days,
        "kpis": kpis,
        "broadcasts": broadcast_stats,
        "vendor_win_rates": vendor_stats,
        "category_breakdown": category_breakdown,
    }
