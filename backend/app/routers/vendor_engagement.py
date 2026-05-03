"""Vendor engagement and bot automation endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..services import vendor_bot

router = APIRouter()


@router.post('/api/v1/rfq/vendor-engagement/send-reply/{rfq_id}/{vendor_id}')
def send_vendor_reply(
    rfq_id: int,
    vendor_id: int,
    reply_type: str = 'rfq_received',
    db: Session = Depends(get_db),
) -> dict:
    """Send templated auto-reply to a vendor."""
    try:
        result = vendor_bot.send_auto_reply(db, rfq_id, vendor_id, reply_type)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post('/api/v1/rfq/{rfq_id}/check-escalations')
def check_escalations(
    rfq_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Check and apply escalation rules for an RFQ."""
    try:
        escalations = vendor_bot.check_escalations(db, rfq_id)
        return {
            'rfq_id': rfq_id,
            'escalations': escalations,
            'total': len(escalations),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post('/api/v1/rfq/{rfq_id}/record-interaction')
def record_interaction(
    rfq_id: int,
    vendor_id: int,
    interaction_type: str,
    details: dict | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """Record vendor interaction for engagement tracking."""
    try:
        result = vendor_bot.record_vendor_interaction(
            db, rfq_id, vendor_id, interaction_type, details
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
