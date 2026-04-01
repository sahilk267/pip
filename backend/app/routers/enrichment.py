from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import LeadB2BEnrichmentResponse
from ..services.lead_intelligence import enrich_b2b_leads

router = APIRouter()


@router.post('/api/v1/enrichment/leads/b2b', response_model=LeadB2BEnrichmentResponse)
def enrich_leads_b2b(limit: int = 200, db: Session = Depends(get_db)) -> LeadB2BEnrichmentResponse:
    return LeadB2BEnrichmentResponse(**enrich_b2b_leads(db, limit=limit))

