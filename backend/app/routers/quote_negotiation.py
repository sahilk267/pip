"""Quote negotiation and PO generation endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..services import quote_negotiation

router = APIRouter()


@router.post('/api/v1/rfq/quotes/{quote_id}/counter-offer')
def make_counter_offer(
    quote_id: int,
    counter_price: float,
    lead_time_days: int | None = None,
    notes: str = "",
    offered_by: str = "buyer",
    db: Session = Depends(get_db),
) -> dict:
    """Make a counter-offer on a quote."""
    try:
        result = quote_negotiation.make_counter_offer(
            db, quote_id, counter_price, lead_time_days, notes, offered_by
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post('/api/v1/rfq/quotes/{quote_id}/accept')
def accept_quote(
    quote_id: int,
    accepted_by: str = "buyer",
    db: Session = Depends(get_db),
) -> dict:
    """Accept a quote."""
    try:
        result = quote_negotiation.accept_quote(db, quote_id, accepted_by)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post('/api/v1/rfq/quotes/{quote_id}/reject')
def reject_quote(
    quote_id: int,
    reason: str = "Selected another vendor",
    rejected_by: str = "buyer",
    db: Session = Depends(get_db),
) -> dict:
    """Reject a quote."""
    try:
        result = quote_negotiation.reject_quote(db, quote_id, reason, rejected_by)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post('/api/v1/rfq/quotes/{quote_id}/generate-po')
def generate_po(
    quote_id: int,
    po_number: str | None = None,
    payment_terms: str = "Net 30",
    delivery_address: dict | None = None,
    generated_by: str = "system",
    db: Session = Depends(get_db),
) -> dict:
    """Generate a purchase order from an accepted quote."""
    try:
        result = quote_negotiation.generate_purchase_order(
            db, quote_id, po_number, payment_terms, delivery_address, generated_by
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
