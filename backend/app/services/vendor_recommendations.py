"""Smart vendor recommendations based on category and scores."""
from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..models_extended import VendorRanking, SupplierScore
from .. import models


def rank_vendors_for_category(
    db: Session,
    category: str,
) -> dict[str, Any]:
    """Rank vendors for a specific category."""
    # Get all vendors with scores
    vendors = db.query(models.Vendor).all()
    rankings = []

    for i, vendor in enumerate(vendors, 1):
        # Get supplier score
        score_obj = db.query(SupplierScore).filter(SupplierScore.vendor_id == vendor.id).first()
        base_score = score_obj.total_score if score_obj else 50.0

        # TODO: Calculate category-specific adjustments based on:
        # - Price competitiveness in category
        # - Past performance in category
        # - Specialization in category

        score = base_score * 0.8  # Conservative default

        rankings.append({
            "vendor_id": vendor.id,
            "vendor_name": vendor.name,
            "rank": i,
            "score": score,
            "breakdown": {
                "base_score": base_score,
                "category_fit": 20.0,
                "price_competitiveness": 20.0,
                "reliability": 20.0,
            },
        })

    # Sort by score descending
    rankings.sort(key=lambda x: x["score"], reverse=True)

    # Update ranks
    for i, r in enumerate(rankings, 1):
        r["rank"] = i
        existing = db.query(VendorRanking).filter(
            VendorRanking.vendor_id == r["vendor_id"],
            VendorRanking.product_category == category,
        ).first()

        if not existing:
            existing = VendorRanking(
                product_category=category,
                vendor_id=r["vendor_id"],
            )

        existing.rank = i
        existing.score = r["score"]
        existing.score_breakdown = r["breakdown"]
        db.add(existing)

    db.commit()

    return {
        "category": category,
        "recommendations": rankings[:10],  # Top 10
    }


def get_recommended_vendors(
    db: Session,
    category: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Get top recommended vendors for a category."""
    rankings = (
        db.query(VendorRanking)
        .filter(VendorRanking.product_category == category)
        .order_by(VendorRanking.rank)
        .limit(limit)
        .all()
    )

    return [
        {
            "vendor_id": r.vendor_id,
            "rank": r.rank,
            "score": r.score,
            "reason": r.recommendation_reason,
        }
        for r in rankings
    ]


def update_recommendations(db: Session) -> dict[str, int]:
    """Update recommendations for all categories."""
    from datetime import datetime, timezone

    categories = set()

    # Get all product categories
    vendors = db.query(models.Vendor).all()
    for vendor in vendors:
        vendor_cat = getattr(vendor, "category", "uncategorized")
        if vendor_cat:
            categories.add(vendor_cat)

    updated = 0
    for category in categories:
        try:
            rank_vendors_for_category(db, category)
            updated += 1
        except Exception:
            pass

    return {
        "categories_updated": updated,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
