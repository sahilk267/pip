"""Invoice management endpoints."""
import random
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..services import invoice_management
from .. import models
from ..models_extended import Invoice, InvoiceItem

router = APIRouter()


@router.post('/api/v1/invoices/seed')
def seed_invoices(db: Session = Depends(get_db)) -> dict:
    """Seed sample invoices using vendors in the DB."""
    vendors = db.query(models.Vendor).limit(10).all()
    if not vendors:
        return {"status": "no_vendors", "created": 0}

    existing_count = db.query(Invoice).count()
    if existing_count >= 8:
        return {"status": "already_seeded", "existing": existing_count}

    statuses = ['paid', 'paid', 'sent', 'sent', 'draft', 'draft', 'paid', 'sent', 'draft', 'paid']
    payment_terms_options = ['Net 15', 'Net 30', 'Net 30', 'Net 60']
    line_items_catalog = [
        ("Bulk Electronics Supply Q2", 200, 45.50),
        ("Manufacturing Parts Order", 50, 320.00),
        ("Raw Materials Delivery", 1000, 8.75),
        ("Logistics Services - April", 30, 250.00),
        ("Software Licenses Annual", 5, 1200.00),
        ("Packaging Materials Bulk", 5000, 0.85),
        ("Engineering Consulting Hours", 40, 180.00),
        ("Chemical Compounds Batch", 100, 55.00),
        ("PCB Assembly Run", 500, 12.40),
        ("QC Inspection Service", 1, 3500.00),
    ]

    now = datetime.now(timezone.utc)
    created = 0

    for i, vendor in enumerate(vendors):
        status = statuses[i % len(statuses)]
        terms = random.choice(payment_terms_options)
        days_map = {"Net 15": 15, "Net 30": 30, "Net 60": 60}
        due_days = days_map[terms]

        invoice_date = now - timedelta(days=random.randint(5, 60))
        due_date = invoice_date + timedelta(days=due_days)

        desc, qty, unit_price = line_items_catalog[i % len(line_items_catalog)]
        total = round(qty * unit_price, 2)

        count = db.query(Invoice).count()
        inv_num = f"INV-{invoice_date.strftime('%Y%m%d')}-{count + 1:04d}"

        invoice = Invoice(
            invoice_number=inv_num,
            vendor_id=vendor.id,
            po_number=f"PO-{2025000 + i + 1}",
            total_amount=total,
            currency="USD",
            status=status,
            invoice_date=invoice_date,
            due_date=due_date,
            paid_date=invoice_date + timedelta(days=random.randint(3, due_days - 1)) if status == 'paid' else None,
            payment_terms=terms,
            notes=f"Auto-generated sample invoice for {vendor.name}",
            created_by="seed",
        )
        db.add(invoice)
        db.flush()

        item = InvoiceItem(
            invoice_id=invoice.id,
            description=desc,
            quantity=qty,
            unit_price=unit_price,
            total_price=total,
        )
        db.add(item)
        created += 1

    db.commit()
    return {"status": "ok", "created": created}


@router.post('/api/v1/invoices/create')
def create_invoice(
    vendor_id: int,
    description: str,
    quantity: float,
    unit_price: float,
    payment_terms: str = "Net 30",
    po_number: str = "",
    notes: str = "",
    db: Session = Depends(get_db),
) -> dict:
    """Manually create an invoice."""
    vendor = db.query(models.Vendor).filter(models.Vendor.id == vendor_id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    total = round(quantity * unit_price, 2)
    days_map = {"Net 15": 15, "Net 30": 30, "Net 60": 60}
    due_days = days_map.get(payment_terms, 30)
    now = datetime.now(timezone.utc)
    due_date = now + timedelta(days=due_days)

    count = db.query(Invoice).count()
    inv_num = f"INV-{now.strftime('%Y%m%d')}-{count + 1:04d}"

    invoice = Invoice(
        invoice_number=inv_num,
        vendor_id=vendor_id,
        po_number=po_number or f"PO-{2025000 + count + 1}",
        total_amount=total,
        currency="USD",
        status="draft",
        invoice_date=now,
        due_date=due_date,
        payment_terms=payment_terms,
        notes=notes,
        created_by="user",
    )
    db.add(invoice)
    db.flush()

    item = InvoiceItem(
        invoice_id=invoice.id,
        description=description,
        quantity=quantity,
        unit_price=unit_price,
        total_price=total,
    )
    db.add(item)
    db.commit()
    db.refresh(invoice)

    return {
        "invoice_id": invoice.id,
        "invoice_number": inv_num,
        "vendor_id": vendor_id,
        "vendor_name": vendor.name,
        "total_amount": total,
        "status": "draft",
        "due_date": due_date.isoformat(),
        "payment_terms": payment_terms,
    }


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
    """List invoices with vendor names."""
    invoices = invoice_management.get_invoices(db, vendor_id, status, limit)
    # Enrich with vendor names
    vendor_map: dict[int, str] = {}
    for inv in invoices:
        vid = inv["vendor_id"]
        if vid not in vendor_map:
            v = db.query(models.Vendor).filter(models.Vendor.id == vid).first()
            vendor_map[vid] = v.name if v else f"Vendor {vid}"
        inv["vendor_name"] = vendor_map[vid]
    return {"invoices": invoices}
