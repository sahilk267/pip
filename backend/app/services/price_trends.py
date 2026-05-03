"""Price trend analysis and benchmarking service."""
from datetime import datetime, timedelta, timezone
from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from .. import models
from ..models_extended import PriceHistory, PriceBenchmark


def record_price(
    db: Session,
    vendor_id: int,
    product_name: str,
    unit_price: float,
    category: str = "uncategorized",
    quantity: int | None = None,
    source: str = "quote",
) -> dict[str, Any]:
    """Record a price data point."""
    record = PriceHistory(
        vendor_id=vendor_id,
        product_name=product_name,
        unit_price=unit_price,
        category=category,
        quantity=quantity,
        source=source,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {
        "id": record.id,
        "vendor_id": vendor_id,
        "product": product_name,
        "price": unit_price,
        "recorded_at": record.recorded_at.isoformat() if record.recorded_at else None,
    }


def get_price_history(
    db: Session,
    category: str,
    days: int = 90,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Get price history for a category over time."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    records = db.query(PriceHistory).filter(
        PriceHistory.category == category,
        PriceHistory.recorded_at >= cutoff,
    ).order_by(PriceHistory.recorded_at.desc()).limit(limit).all()

    return [
        {
            "vendor_id": r.vendor_id,
            "product": r.product_name,
            "price": r.unit_price,
            "date": r.recorded_at.isoformat() if r.recorded_at else None,
        }
        for r in records
    ]


def calculate_benchmark(db: Session, category: str) -> dict[str, Any]:
    """Calculate price benchmark for a category."""
    # Get prices from last 180 days
    cutoff = datetime.now(timezone.utc) - timedelta(days=180)
    prices = db.query(PriceHistory.unit_price).filter(
        PriceHistory.category == category,
        PriceHistory.recorded_at >= cutoff,
        PriceHistory.unit_price > 0,
    ).all()

    if not prices:
        return {"category": category, "sample_count": 0, "status": "insufficient_data"}

    prices = sorted([p[0] for p in prices])
    count = len(prices)
    avg = sum(prices) / count
    median = prices[count // 2]
    min_price = min(prices)
    max_price = max(prices)
    variance = sum((p - avg) ** 2 for p in prices) / count
    std_dev = variance ** 0.5

    # Find best vendor
    best = db.query(PriceHistory).filter(
        PriceHistory.category == category,
        PriceHistory.unit_price == min_price,
        PriceHistory.recorded_at >= cutoff,
    ).first()

    # Save or update benchmark
    bench = db.query(PriceBenchmark).filter(PriceBenchmark.category == category).first()
    if not bench:
        bench = PriceBenchmark(category=category)

    bench.avg_price = avg
    bench.min_price = min_price
    bench.max_price = max_price
    bench.median_price = median
    bench.std_dev = std_dev
    bench.sample_count = count
    bench.best_vendor_id = best.vendor_id if best else None

    db.add(bench)
    db.commit()
    db.refresh(bench)

    return {
        "category": category,
        "avg_price": avg,
        "min_price": min_price,
        "max_price": max_price,
        "median_price": median,
        "std_dev": std_dev,
        "sample_count": count,
        "best_vendor_id": bench.best_vendor_id,
    }


def get_price_trend(db: Session, vendor_id: int, category: str, days: int = 90) -> dict[str, Any]:
    """Get price trend for vendor in a category."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    records = db.query(PriceHistory).filter(
        PriceHistory.vendor_id == vendor_id,
        PriceHistory.category == category,
        PriceHistory.recorded_at >= cutoff,
    ).order_by(PriceHistory.recorded_at).all()

    if not records:
        return {"vendor_id": vendor_id, "category": category, "trend": "no_data"}

    prices = [r.unit_price for r in records]
    dates = [r.recorded_at.isoformat() if r.recorded_at else None for r in records]

    trend = "stable"
    if len(prices) > 1:
        if prices[-1] < prices[0]:
            trend = "decreasing"
        elif prices[-1] > prices[0]:
            trend = "increasing"

    return {
        "vendor_id": vendor_id,
        "category": category,
        "prices": prices,
        "dates": dates,
        "trend": trend,
        "current_price": prices[-1] if prices else None,
        "avg_price": sum(prices) / len(prices) if prices else None,
    }
