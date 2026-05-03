"""Supplier performance scoring and rating service."""
from datetime import datetime, timedelta, timezone
from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from .. import models
from ..models_extended import SupplierScore, SupplierRatingHistory


def calculate_supplier_score(
    db: Session,
    vendor_id: int,
) -> dict[str, Any]:
    """Calculate composite supplier score (0-100)."""
    vendor = db.query(models.Vendor).filter(models.Vendor.id == vendor_id).first()
    if not vendor:
        raise ValueError(f"Vendor {vendor_id} not found")

    # Metrics (each weighted 0-20 points)
    quality_score = 20.0  # Default: no defects recorded
    reliability_score = 18.0  # Default: slightly below perfect
    price_score = 15.0  # Will calculate from benchmarks
    communication_score = 17.0  # Assume responsive
    compliance_score = 10.0  # Default: no cert data

    # TODO: Calculate from actual data:
    # - quality: defect rate from invoices
    # - reliability: quote accuracy vs actual, response time
    # - price: vs benchmark average
    # - communication: avg response time in hours
    # - compliance: certification count

    total_score = quality_score + reliability_score + price_score + communication_score + compliance_score

    # Save score
    score_obj = db.query(SupplierScore).filter(SupplierScore.vendor_id == vendor_id).first()
    if not score_obj:
        score_obj = SupplierScore(vendor_id=vendor_id)

    score_obj.total_score = total_score
    score_obj.quality_score = quality_score
    score_obj.reliability_score = reliability_score
    score_obj.price_score = price_score
    score_obj.communication_score = communication_score
    score_obj.compliance_score = compliance_score

    db.add(score_obj)
    db.commit()

    return {
        "vendor_id": vendor_id,
        "total_score": total_score,
        "breakdown": {
            "quality": quality_score,
            "reliability": reliability_score,
            "price": price_score,
            "communication": communication_score,
            "compliance": compliance_score,
        },
    }


def record_rating_event(
    db: Session,
    vendor_id: int,
    event_type: str,
    event_id: int | None = None,
) -> dict[str, Any]:
    """Record a rating event (quote, delivery, payment, feedback)."""
    score_data = calculate_supplier_score(db, vendor_id)
    total = score_data["total_score"]

    history = SupplierRatingHistory(
        vendor_id=vendor_id,
        total_score=total,
        event_type=event_type,
        event_id=event_id,
    )
    db.add(history)
    db.commit()

    return {
        "vendor_id": vendor_id,
        "score": total,
        "event": event_type,
        "recorded_at": history.recorded_at.isoformat() if history.recorded_at else None,
    }


def get_supplier_scorecard(db: Session, vendor_id: int) -> dict[str, Any]:
    """Get full supplier scorecard."""
    score = db.query(SupplierScore).filter(SupplierScore.vendor_id == vendor_id).first()
    if not score:
        score_data = calculate_supplier_score(db, vendor_id)
        total = score_data["total_score"]
        breakdown = score_data["breakdown"]
    else:
        total = score.total_score
        breakdown = {
            "quality": score.quality_score,
            "reliability": score.reliability_score,
            "price": score.price_score,
            "communication": score.communication_score,
            "compliance": score.compliance_score,
        }

    vendor = db.query(models.Vendor).filter(models.Vendor.id == vendor_id).first()

    # Get rating history (last 10 events)
    history = (
        db.query(SupplierRatingHistory)
        .filter(SupplierRatingHistory.vendor_id == vendor_id)
        .order_by(SupplierRatingHistory.recorded_at.desc())
        .limit(10)
        .all()
    )

    return {
        "vendor_id": vendor_id,
        "vendor_name": vendor.name if vendor else "Unknown",
        "total_score": total,
        "grade": "A+" if total >= 90 else "A" if total >= 80 else "B+" if total >= 70 else "B" if total >= 60 else "C",
        "breakdown": breakdown,
        "recent_events": [
            {
                "event_type": h.event_type,
                "score": h.total_score,
                "date": h.recorded_at.isoformat() if h.recorded_at else None,
            }
            for h in history
        ],
    }


def get_top_suppliers(db: Session, category: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
    """Get top-rated suppliers."""
    query = db.query(SupplierScore).order_by(SupplierScore.total_score.desc()).limit(limit)
    scores = query.all()

    return [
        {
            "vendor_id": s.vendor_id,
            "score": s.total_score,
            "grade": "A+" if s.total_score >= 90 else "A" if s.total_score >= 80 else "B+",
        }
        for s in scores
    ]
