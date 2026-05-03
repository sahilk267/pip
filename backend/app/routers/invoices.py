"""Invoice management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..services import invoice_management

router = APIRouter()


@router.post('/api/v1/invoices/generate-from-quote/{quote_id}')
def generate_invoice(
    quote_id: int,
    po_number: str,
    payment_terms: str = "Net 30",
    db: Session = Depends(get_db),
) -> dict:
    """Generate invoice from quote."""
    try:
        return invoice_management.generate_invoice_from_quote(db, quote_id, po_number, payment_terms)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/api/v1/invoices/{invoice_id}/send')
def send_invoice(invoice_id: int, db: Session = Depends(get_db)) -> dict:
    """Send invoice to vendor."""
    try:
        return invoice_management.send_invoice(db, invoice_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/api/v1/invoices/{invoice_id}/record-payment')
def record_payment(
    invoice_id: int,
    amount_paid: float | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """Record payment for invoice."""
    try:
        return invoice_management.record_payment(db, invoice_id, amount_paid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/api/v1/invoices')
def list_invoices(
    vendor_id: int | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict:
    """List invoices."""
    invoices = invoice_management.get_invoices(db, vendor_id, status, limit)
    return {"invoices": invoices}
