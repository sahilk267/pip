"""RFQ template management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..services import rfq_templates

router = APIRouter()


@router.post('/api/v1/rfq/templates')
def create_template(
    name: str,
    category: str,
    description: str = "",
    is_public: bool = False,
    db: Session = Depends(get_db),
) -> dict:
    """Create RFQ template."""
    return rfq_templates.create_rfq_template(db, name, category, description, "system", is_public)


@router.post('/api/v1/rfq/templates/{template_id}/items')
def add_item(
    template_id: int,
    product_name: str,
    quantity: float,
    target_price: float | None = None,
    lead_time_days: int | None = None,
    notes: str = "",
    db: Session = Depends(get_db),
) -> dict:
    """Add item to template."""
    try:
        return rfq_templates.add_template_item(db, template_id, product_name, quantity, target_price, lead_time_days, notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/api/v1/rfq/templates/{template_id}')
def get_template(template_id: int, db: Session = Depends(get_db)) -> dict:
    """Get template with items."""
    try:
        return rfq_templates.get_template(db, template_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/api/v1/rfq/templates')
def list_templates(
    category: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict:
    """List RFQ templates."""
    templates = rfq_templates.list_templates(db, category, limit)
    return {"templates": templates}


@router.post('/api/v1/rfq/templates/{template_id}/use')
def use_template(
    template_id: int,
    new_rfq_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Record template usage."""
    try:
        return rfq_templates.use_template(db, template_id, new_rfq_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
