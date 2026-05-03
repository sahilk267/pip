"""Cost optimization opportunities and volume discount management."""
from typing import Any
from sqlalchemy.orm import Session
from ..models_extended import CostOpportunity, DiscountTier, PriceHistory, SupplierScore
from .. import models
from datetime import datetime, timezone


def identify_bulk_discount_opportunity(
    db: Session,
    category: str,
    current_spend: float,
    current_quantity: float,
) -> dict[str, Any]:
    """Identify bulk discount opportunities."""
    # Get discount tiers for vendors in category
    tiers = (
        db.query(DiscountTier)
        .filter(DiscountTier.product_category == category)
        .order_by(DiscountTier.min_quantity)
        .all()
    )

    if not tiers:
        return {"status": "no_opportunities"}

    # Calculate potential savings with higher volumes
    best_opportunity = None
    max_savings = 0

    for tier in tiers:
        if tier.min_quantity > current_quantity:
            new_total = tier.unit_price * tier.min_quantity
            savings = current_spend - new_total
            if savings > max_savings:
                max_savings = savings
                best_opportunity = {
                    "vendor_id": tier.vendor_id,
                    "min_quantity": tier.min_quantity,
                    "unit_price": tier.unit_price,
                    "new_total": new_total,
                    "savings": savings,
                    "savings_percentage": (savings / current_spend * 100) if current_spend else 0,
                }

    if best_opportunity:
        # Create cost opportunity record
        opp = CostOpportunity(
            title=f"Bulk discount opportunity: {category}",
            category=category,
            opportunity_type="bulk_discount",
            current_cost=current_spend,
            potential_savings=best_opportunity["savings"],
            savings_percentage=best_opportunity["savings_percentage"],
            recommended_action=f"Order {int(best_opportunity['min_quantity'])} units from vendor {best_opportunity['vendor_id']} at ${best_opportunity['unit_price']:.2f}/unit",
            affected_vendors=[best_opportunity["vendor_id"]],
        )
        db.add(opp)
        db.commit()

        return {
            "opportunity_id": opp.id,
            "type": "bulk_discount",
            "savings": best_opportunity["savings"],
            "details": best_opportunity,
        }

    return {"status": "no_opportunities"}


def identify_alternative_vendor_opportunity(
    db: Session,
    category: str,
    current_spend: float,
) -> dict[str, Any]:
    """Find cheaper alternative vendor."""
    # Get avg price in category
    avg_price = (
        db.query(func.avg(PriceHistory.unit_price))
        .filter(PriceHistory.category == category)
        .scalar()
    )

    if not avg_price:
        return {"status": "no_data"}

    # Find vendor below average with good score
    best_vendor = None
    best_savings = 0

    vendors = db.query(models.Vendor).all()
    for vendor in vendors:
        score = db.query(SupplierScore).filter(SupplierScore.vendor_id == vendor.id).first()
        if not score or score.total_score < 70:
            continue

        vendor_avg = (
            db.query(func.avg(PriceHistory.unit_price))
            .filter(PriceHistory.vendor_id == vendor.id, PriceHistory.category == category)
            .scalar()
        )

        if vendor_avg and vendor_avg < avg_price:
            savings = current_spend * ((avg_price - vendor_avg) / avg_price)
            if savings > best_savings:
                best_savings = savings
                best_vendor = {
                    "vendor_id": vendor.id,
                    "vendor_name": vendor.name,
                    "price": vendor_avg,
                    "savings": savings,
                }

    if best_vendor:
        opp = CostOpportunity(
            title=f"Switch to {best_vendor['vendor_name']} for {category}",
            category=category,
            opportunity_type="alternative_vendor",
            current_cost=current_spend,
            potential_savings=best_vendor["savings"],
            savings_percentage=(best_vendor["savings"] / current_spend * 100) if current_spend else 0,
            recommended_action=f"Switch supplier to {best_vendor['vendor_name']} at ${best_vendor['price']:.2f}/unit",
            affected_vendors=[best_vendor["vendor_id"]],
        )
        db.add(opp)
        db.commit()

        return {
            "opportunity_id": opp.id,
            "type": "alternative_vendor",
            "savings": best_vendor["savings"],
            "vendor": best_vendor["vendor_name"],
        }

    return {"status": "no_opportunities"}


def add_discount_tier(
    db: Session,
    vendor_id: int,
    category: str,
    min_quantity: float,
    unit_price: float,
    max_quantity: float | None = None,
    notes: str = "",
) -> dict[str, Any]:
    """Add volume discount tier for vendor."""
    tier = DiscountTier(
        vendor_id=vendor_id,
        product_category=category,
        min_quantity=min_quantity,
        max_quantity=max_quantity,
        unit_price=unit_price,
        notes=notes,
    )
    db.add(tier)
    db.commit()
    db.refresh(tier)

    return {
        "tier_id": tier.id,
        "vendor_id": vendor_id,
        "min_quantity": min_quantity,
        "unit_price": unit_price,
    }


def get_cost_opportunities(
    db: Session,
    category: str | None = None,
    status: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Get identified cost opportunities."""
    query = db.query(CostOpportunity)
    if category:
        query = query.filter(CostOpportunity.category == category)
    if status:
        query = query.filter(CostOpportunity.status == status)

    opportunities = query.order_by(CostOpportunity.potential_savings.desc()).limit(limit).all()

    return [
        {
            "opportunity_id": o.id,
            "title": o.title,
            "type": o.opportunity_type,
            "current_cost": o.current_cost,
            "savings": o.potential_savings,
            "savings_pct": o.savings_percentage,
            "status": o.status,
        }
        for o in opportunities
    ]
