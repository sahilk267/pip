"""Analytics endpoints for price trends, supplier scoring, cost optimization."""
import random
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..services import price_trends, supplier_scoring, cost_optimization
from .. import models
from ..models_extended import PriceHistory, DiscountTier, CostOpportunity

router = APIRouter()

# ─── PRICE TREND ANALYTICS ───────────────────────────────────────────────

@router.post('/api/v1/analytics/price-trends/seed')
def seed_price_data(db: Session = Depends(get_db)) -> dict:
    """Seed realistic historical price data using vendors in the DB."""
    vendors = db.query(models.Vendor).limit(15).all()
    if not vendors:
        return {"status": "no_vendors", "records_created": 0}

    category_price_ranges = {
        'Electronics':    (50.0,  800.0),
        'Manufacturing':  (200.0, 5000.0),
        'Raw Materials':  (10.0,  500.0),
        'Logistics':      (50.0,  2000.0),
        'Software':       (100.0, 10000.0),
        'Services':       (50.0,  5000.0),
        'Chemicals':      (20.0,  1000.0),
        'Packaging':      (5.0,   200.0),
        'uncategorized':  (30.0,  1000.0),
    }

    category_products = {
        'Electronics':   ['Microcontrollers', 'OLED Displays', 'Power Modules', 'Sensor Arrays', 'PCB Boards'],
        'Manufacturing': ['CNC Parts', 'Steel Castings', 'Aluminum Extrusions', 'Tooling Sets', 'Precision Gears'],
        'Raw Materials': ['Copper Wire', 'Polymer Resin', 'Steel Sheets', 'Aluminum Alloy', 'Carbon Fiber'],
        'Logistics':     ['Air Freight (kg)', 'Sea Shipping (CBM)', 'Last-Mile Delivery', 'Warehousing (sq ft)'],
        'Software':      ['Enterprise License', 'SaaS Subscription', 'Support Plan', 'API Access'],
        'Services':      ['Engineering Consulting', 'QC Inspection', 'Installation Services', 'Training'],
        'Chemicals':     ['Industrial Solvents', 'Adhesives', 'Lubricants', 'Coatings'],
        'Packaging':     ['Cardboard Boxes', 'Bubble Wrap', 'Foam Inserts', 'Pallets'],
        'uncategorized': ['General Supply', 'Mixed Goods', 'Standard Parts'],
    }

    records_created = 0
    categories = list(category_price_ranges.keys())
    now = datetime.now(timezone.utc)

    for vendor in vendors:
        # Each vendor covers their primary category heavily + 2-3 others lightly
        primary_cat = vendor.category if vendor.category in categories else 'uncategorized'
        secondary_cats = random.sample([c for c in categories if c != primary_cat], min(3, len(categories) - 1))

        vendor_categories = [(primary_cat, 8)] + [(c, 3) for c in secondary_cats]

        for cat, num_records in vendor_categories:
            lo, hi = category_price_ranges[cat]
            base_price = random.uniform(lo, hi)
            products = category_products.get(cat, ['Product'])

            for _ in range(num_records):
                # Add slight trend variation over 90 days
                days_ago = random.randint(1, 90)
                # Simulate gentle price drift
                drift = random.uniform(-0.08, 0.08)
                price = round(base_price * (1 + drift), 2)

                record = PriceHistory(
                    vendor_id=vendor.id,
                    product_name=random.choice(products),
                    unit_price=price,
                    category=cat,
                    quantity=random.choice([10, 25, 50, 100, 250, 500]),
                    source='historical',
                    recorded_at=now - timedelta(days=days_ago),
                )
                db.add(record)
                records_created += 1

    db.commit()

    # Refresh benchmarks for all categories
    benchmarks_updated = []
    for cat in categories:
        try:
            price_trends.calculate_benchmark(db, cat)
            benchmarks_updated.append(cat)
        except Exception:
            pass

    return {
        "status": "ok",
        "records_created": records_created,
        "vendors_used": len(vendors),
        "benchmarks_updated": benchmarks_updated,
    }


@router.post('/api/v1/analytics/price-trends/record')
def record_price(
    vendor_id: int,
    product_name: str,
    unit_price: float,
    category: str = "uncategorized",
    quantity: int | None = None,
    source: str = "quote",
    db: Session = Depends(get_db),
) -> dict:
    """Record a price data point."""
    return price_trends.record_price(db, vendor_id, product_name, unit_price, category, quantity, source)


@router.get('/api/v1/analytics/price-trends/{category}')
def get_price_history(
    category: str,
    days: int = Query(90, ge=1, le=365),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict:
    """Get price history for a category."""
    history = price_trends.get_price_history(db, category, days, limit)
    return {"category": category, "days": days, "records": history}


@router.get('/api/v1/analytics/price-trends/benchmark/{category}')
def get_benchmark(category: str, db: Session = Depends(get_db)) -> dict:
    """Get price benchmark for category."""
    return price_trends.calculate_benchmark(db, category)


@router.get('/api/v1/analytics/price-trends/vendor/{vendor_id}/{category}')
def get_vendor_trend(
    vendor_id: int,
    category: str,
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
) -> dict:
    """Get price trend for vendor in category."""
    return price_trends.get_price_trend(db, vendor_id, category, days)


# ─── SUPPLIER SCORING ────────────────────────────────────────────────────

@router.post('/api/v1/suppliers/seed-scores')
def seed_supplier_scores(db: Session = Depends(get_db)) -> dict:
    """Calculate and seed scores for all vendors."""
    vendors = db.query(models.Vendor).all()
    if not vendors:
        return {"status": "no_vendors", "scored": 0}

    results = []
    failed = 0
    for vendor in vendors:
        try:
            result = supplier_scoring.calculate_supplier_score(db, vendor.id)
            results.append({
                "vendor_id": vendor.id,
                "vendor_name": vendor.name,
                "score": result["total_score"],
            })
        except Exception:
            failed += 1

    return {
        "status": "ok",
        "scored": len(results),
        "failed": failed,
        "results": results[:10],  # Preview first 10
    }


@router.post('/api/v1/suppliers/{vendor_id}/calculate-score')
def calculate_score(vendor_id: int, db: Session = Depends(get_db)) -> dict:
    """Calculate supplier score."""
    try:
        return supplier_scoring.calculate_supplier_score(db, vendor_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/api/v1/suppliers/{vendor_id}/record-event')
def record_event(
    vendor_id: int,
    event_type: str,
    event_id: int | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """Record rating event for vendor."""
    try:
        return supplier_scoring.record_rating_event(db, vendor_id, event_type, event_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/api/v1/suppliers/{vendor_id}/scorecard')
def get_scorecard(vendor_id: int, db: Session = Depends(get_db)) -> dict:
    """Get supplier scorecard."""
    return supplier_scoring.get_supplier_scorecard(db, vendor_id)


@router.get('/api/v1/suppliers/top-rated')
def get_top_suppliers(
    category: str | None = None,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> dict:
    """Get top-rated suppliers."""
    suppliers = supplier_scoring.get_top_suppliers(db, category, limit)
    return {"suppliers": suppliers}


# ─── COST OPTIMIZATION ───────────────────────────────────────────────────

@router.post('/api/v1/cost-optimization/seed')
def seed_cost_data(db: Session = Depends(get_db)) -> dict:
    """Seed sample discount tiers and cost opportunities."""
    vendors = db.query(models.Vendor).limit(10).all()
    if not vendors:
        return {"status": "no_vendors", "tiers_created": 0, "opportunities_created": 0}

    categories = ['Electronics', 'Manufacturing', 'Raw Materials', 'Logistics', 'Software', 'Packaging']
    category_prices = {
        'Electronics': (45.0, 380.0),
        'Manufacturing': (150.0, 3500.0),
        'Raw Materials': (8.0, 400.0),
        'Logistics': (40.0, 1500.0),
        'Software': (80.0, 8000.0),
        'Packaging': (4.0, 150.0),
    }

    tiers_created = 0
    opps_created = 0

    for i, vendor in enumerate(vendors):
        # Assign 2 categories per vendor
        vendor_cats = [categories[i % len(categories)], categories[(i + 1) % len(categories)]]
        for cat in vendor_cats:
            lo, hi = category_prices.get(cat, (50.0, 500.0))
            base = round(random.uniform(lo, hi), 2)

            # 3-tier volume discount
            tier_defs = [
                (10,  500,  base),
                (500, 2000, round(base * 0.90, 2)),
                (2000, None, round(base * 0.78, 2)),
            ]
            for min_q, max_q, price in tier_defs:
                # Skip if tier already exists
                existing = db.query(DiscountTier).filter(
                    DiscountTier.vendor_id == vendor.id,
                    DiscountTier.product_category == cat,
                    DiscountTier.min_quantity == min_q,
                ).first()
                if not existing:
                    tier = DiscountTier(
                        vendor_id=vendor.id,
                        product_category=cat,
                        min_quantity=min_q,
                        max_quantity=max_q,
                        unit_price=price,
                        discount_percentage=0 if min_q == 10 else (10 if min_q == 500 else 22),
                        notes=f"Volume tier for {cat}",
                    )
                    db.add(tier)
                    tiers_created += 1

    db.commit()

    # Create sample cost opportunities
    opp_templates = [
        ("Consolidate Electronics Orders Q3", "Electronics", "consolidation", 85000, 12750),
        ("Switch to tier-2 Raw Materials supplier", "Raw Materials", "alternative_vendor", 42000, 8400),
        ("Volume discount: Manufacturing Q4", "Manufacturing", "bulk_discount", 220000, 33000),
        ("Logistics network optimization", "Logistics", "consolidation", 65000, 9750),
        ("Software license renegotiation", "Software", "alternative_vendor", 120000, 24000),
        ("Packaging bulk purchase Jan", "Packaging", "bulk_discount", 18000, 2700),
    ]
    for title, cat, opp_type, cost, savings in opp_templates:
        existing = db.query(CostOpportunity).filter(CostOpportunity.title == title).first()
        if not existing:
            opp = CostOpportunity(
                title=title,
                category=cat,
                opportunity_type=opp_type,
                current_cost=cost,
                potential_savings=savings,
                savings_percentage=round(savings / cost * 100, 1),
                recommended_action=f"Review {cat} spend and negotiate with top-ranked vendors",
                affected_vendors=[v.id for v in vendors[:3]],
                status=random.choice(['identified', 'identified', 'approved']),
            )
            db.add(opp)
            opps_created += 1

    db.commit()

    return {
        "status": "ok",
        "tiers_created": tiers_created,
        "opportunities_created": opps_created,
        "vendors_used": len(vendors),
    }


@router.post('/api/v1/cost-optimization/bulk-discount-opportunity')
def check_bulk_discount(
    category: str,
    current_spend: float,
    current_quantity: float,
    db: Session = Depends(get_db),
) -> dict:
    """Identify bulk discount opportunities."""
    return cost_optimization.identify_bulk_discount_opportunity(db, category, current_spend, current_quantity)


@router.post('/api/v1/cost-optimization/alternative-vendor-opportunity')
def check_alternative_vendor(
    category: str,
    current_spend: float,
    db: Session = Depends(get_db),
) -> dict:
    """Find alternative vendor opportunities."""
    return cost_optimization.identify_alternative_vendor_opportunity(db, category, current_spend)


@router.post('/api/v1/cost-optimization/discount-tier')
def add_discount_tier(
    vendor_id: int,
    category: str,
    min_quantity: float,
    unit_price: float,
    max_quantity: float | None = None,
    notes: str = "",
    db: Session = Depends(get_db),
) -> dict:
    """Add volume discount tier."""
    return cost_optimization.add_discount_tier(db, vendor_id, category, min_quantity, unit_price, max_quantity, notes)


@router.get('/api/v1/cost-optimization/opportunities')
def list_opportunities(
    category: str | None = None,
    status: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    """List cost opportunities."""
    opps = cost_optimization.get_cost_opportunities(db, category, status, limit)
    return {"opportunities": opps}
