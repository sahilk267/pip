"""Vendor recommendation endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..services import vendor_recommendations

router = APIRouter()


@router.post('/api/v1/rfq/recommendations/rank/{category}')
def rank_vendors(category: str, db: Session = Depends(get_db)) -> dict:
    """Rank vendors for category."""
    return vendor_recommendations.rank_vendors_for_category(db, category)


@router.get('/api/v1/rfq/recommendations/{category}')
def get_recommendations(
    category: str,
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
) -> dict:
    """Get recommended vendors for category."""
    vendors = vendor_recommendations.get_recommended_vendors(db, category, limit)
    return {"category": category, "recommendations": vendors}


@router.post('/api/v1/rfq/recommendations/update-all')
def update_all_recommendations(db: Session = Depends(get_db)) -> dict:
    """Update all recommendations."""
    return vendor_recommendations.update_recommendations(db)
