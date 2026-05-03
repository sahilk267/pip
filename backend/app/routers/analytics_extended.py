"""Analytics endpoints for price trends, supplier scoring, cost optimization."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..services import price_trends, supplier_scoring, cost_optimization

router = APIRouter()

# ─── PRICE TREND ANALYTICS ───────────────────────────────────────────────

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
