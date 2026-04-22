from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from .. import models
from ..crud import log_audit
from ..crm_models import Customer
from ..services.lead_intelligence import apply_metrics_to_lead, normalize_attribution_channel
from ..services.sales_funnel import compute_sales_funnel_metrics
from ..services.sales_playbooks import build_sales_playbook, build_sales_playbook_queue

router = APIRouter()


def _record_lead_transition(
    db: Session,
    *,
    lead_id: int,
    from_stage: str | None,
    to_stage: str,
    performed_by: str = 'system',
    reason: str | None = None,
) -> None:
    transition = models.LeadStageTransition(
        lead_id=lead_id,
        from_stage=from_stage,
        to_stage=to_stage,
        performed_by=performed_by,
        reason=reason,
    )
    db.add(transition)


@router.post('/api/v1/leads', response_model=schemas.LeadResponse)
def create_lead(lead: schemas.LeadCreate, db: Session = Depends(get_db)):
    entity = models.Lead(
        full_name=lead.full_name,
        email=lead.email,
        phone=lead.phone,
        company=lead.company,
        source=lead.source,
        stage='lead',
        attribution_channel=normalize_attribution_channel(lead.source),
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    apply_metrics_to_lead(entity)
    db.add(entity)
    _record_lead_transition(
        db,
        lead_id=entity.id,
        from_stage=None,
        to_stage=entity.stage,
        reason='lead_created',
    )
    db.commit()
    db.refresh(entity)
    log_audit(db, 'lead', entity.id, 'ingest', 'CRM lead created')
    return entity


@router.get('/api/v1/leads', response_model=list[schemas.LeadResponse])
def list_leads(db: Session = Depends(get_db), limit: int = 100):
    rows = db.query(models.Lead).order_by(models.Lead.id.desc()).limit(min(limit, 500)).all()
    return rows


@router.patch('/api/v1/leads/{lead_id}/stage', response_model=schemas.LeadResponse)
def update_lead_stage(lead_id: int, payload: schemas.LeadUpdate, db: Session = Depends(get_db)):
    lead = db.query(models.Lead).filter(models.Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail='Lead not found')
    previous_stage = lead.stage
    lead.stage = payload.stage
    if payload.consented is not None:
        lead.consented = payload.consented
    apply_metrics_to_lead(lead)
    db.add(lead)
    if previous_stage != lead.stage:
        _record_lead_transition(
            db,
            lead_id=lead.id,
            from_stage=previous_stage,
            to_stage=lead.stage,
            reason=f'stage_update:{previous_stage}->{lead.stage}',
        )
    db.commit()
    db.refresh(lead)
    log_audit(db, 'lead', lead.id, 'stage_update', f'Stage updated to {payload.stage}')
    return lead


@router.patch('/api/v1/leads/{lead_id}/preferences', response_model=schemas.LeadResponse)
def update_lead_preferences(lead_id: int, payload: schemas.LeadPreferences, db: Session = Depends(get_db)):
    lead = db.query(models.Lead).filter(models.Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail='Lead not found')
    if payload.marketing_consent is not None:
        lead.marketing_consent = payload.marketing_consent
    if payload.unsubscribe:
        lead.unsubscribed_at = datetime.now(timezone.utc)
        lead.marketing_consent = 'no'
    apply_metrics_to_lead(lead)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    log_audit(db, 'lead', lead.id, 'preferences', 'Lead marketing preferences updated')
    return lead


@router.patch('/api/v1/security/privacy/leads/{lead_id}/preferences', response_model=schemas.LeadResponse)
def update_security_privacy_lead_preferences(lead_id: int, payload: schemas.LeadPreferences, db: Session = Depends(get_db)) -> schemas.LeadResponse:
    return update_lead_preferences(lead_id, payload, db)


@router.post('/api/v1/customers', response_model=schemas.CustomerResponse)
def create_customer(payload: schemas.CustomerCreate, db: Session = Depends(get_db)):
    entity = Customer(
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        vendor_id=payload.vendor_id,
        account_status=payload.account_status,
        consent_status=payload.consent_status,
        engagement_score=payload.engagement_score or 0,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    log_audit(db, 'customer', entity.id, 'ingest', 'Customer created')
    return entity


@router.get('/api/v1/customers', response_model=list[schemas.CustomerResponse])
def list_customers(db: Session = Depends(get_db), limit: int = 100):
    rows = db.query(Customer).order_by(Customer.id.desc()).limit(min(limit, 500)).all()
    return rows


@router.patch('/api/v1/customers/{customer_id}/consent', response_model=schemas.CustomerResponse)
def update_customer_consent(customer_id: int, payload: schemas.ConsentUpdate, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail='Customer not found')
    customer.consent_status = payload.consent_status
    db.add(customer)
    db.commit()
    log_audit(db, 'customer', customer.id, 'consent_update', f'Consent set to {payload.consent_status}')
    return customer


@router.patch('/api/v1/customers/{customer_id}', response_model=schemas.CustomerResponse)
def patch_customer(customer_id: int, payload: schemas.CustomerEngagementPatch, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail='Customer not found')
    if payload.account_status is not None:
        customer.account_status = payload.account_status
    if payload.engagement_score is not None:
        customer.engagement_score = payload.engagement_score
    db.add(customer)
    db.commit()
    log_audit(db, 'customer', customer.id, 'profile_update', 'Customer engagement/profile updated')
    return customer


@router.post('/api/v1/crm/communications', response_model=schemas.CRMCommunicationResponse)
def create_crm_communication(payload: schemas.CRMCommunicationCreate, db: Session = Depends(get_db)):
    lead = None
    customer = None
    if payload.lead_id is not None:
        lead = db.query(models.Lead).filter(models.Lead.id == payload.lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail='Lead not found')
    if payload.customer_id is not None:
        customer = db.query(Customer).filter(Customer.id == payload.customer_id).first()
        if not customer:
            raise HTTPException(status_code=404, detail='Customer not found')

    row = models.CRMCommunication(
        lead_id=payload.lead_id,
        customer_id=payload.customer_id,
        channel=payload.channel.strip().lower(),
        direction=payload.direction.strip().lower(),
        subject=(payload.subject or '').strip() or None,
        message=payload.message.strip(),
        status=payload.status.strip().lower(),
        follow_up_at=payload.follow_up_at,
        performed_by=payload.performed_by,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    entity_type = 'lead' if lead is not None else 'customer'
    entity_id = payload.lead_id if lead is not None else payload.customer_id
    log_audit(
        db,
        entity_type,
        entity_id,
        'communication_logged',
        f'CRM communication logged via {row.channel} ({row.direction})',
        performed_by=payload.performed_by,
    )
    return row


@router.get('/api/v1/crm/communications', response_model=list[schemas.CRMCommunicationResponse])
def list_crm_communications(
    db: Session = Depends(get_db),
    lead_id: int | None = None,
    customer_id: int | None = None,
    limit: int = 100,
):
    q = db.query(models.CRMCommunication)
    if lead_id is not None:
        q = q.filter(models.CRMCommunication.lead_id == lead_id)
    if customer_id is not None:
        q = q.filter(models.CRMCommunication.customer_id == customer_id)
    rows = q.order_by(models.CRMCommunication.created_at.desc()).limit(min(limit, 500)).all()
    return rows


@router.get('/api/v1/leads/{lead_id}/transitions', response_model=list[schemas.LeadStageTransitionResponse])
def list_lead_stage_transitions(lead_id: int, db: Session = Depends(get_db), limit: int = 200):
    lead = db.query(models.Lead).filter(models.Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail='Lead not found')
    rows = (
        db.query(models.LeadStageTransition)
        .filter(models.LeadStageTransition.lead_id == lead_id)
        .order_by(models.LeadStageTransition.changed_at.asc())
        .limit(min(limit, 500))
        .all()
    )
    return rows


@router.get('/api/v1/crm/funnel', response_model=schemas.SalesFunnelMetrics)
def crm_funnel_metrics(window_days: int = 30, db: Session = Depends(get_db)):
    metrics = compute_sales_funnel_metrics(db, window_days=window_days)
    return schemas.SalesFunnelMetrics(**metrics)


@router.get('/api/v1/leads/{lead_id}/playbook', response_model=schemas.LeadSalesPlaybook)
def lead_sales_playbook(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(models.Lead).filter(models.Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail='Lead not found')
    playbook = build_sales_playbook(db, lead)
    return schemas.LeadSalesPlaybook(**playbook)


@router.get('/api/v1/crm/playbook-queue', response_model=schemas.SalesPlaybookQueueResponse)
def sales_playbook_queue(limit: int = 20, db: Session = Depends(get_db)):
    payload = build_sales_playbook_queue(db, limit=min(limit, 100))
    return schemas.SalesPlaybookQueueResponse(**payload)


def _pair_counts(rows: list) -> dict[str, int]:
    return {str(k or ''): int(v) for k, v in rows}


@router.get('/api/v1/crm/dashboard', response_model=schemas.CrmDashboard)
def crm_dashboard(db: Session = Depends(get_db)):
    lead_stages = _pair_counts(
        db.query(models.Lead.stage, func.count(models.Lead.id)).group_by(models.Lead.stage).all()
    )
    lead_segments = _pair_counts(
        db.query(models.Lead.segment, func.count(models.Lead.id)).group_by(models.Lead.segment).all()
    )
    customers_by_consent = _pair_counts(
        db.query(Customer.consent_status, func.count(Customer.id)).group_by(Customer.consent_status).all()
    )
    totals = {
        'vendors': db.query(models.Vendor).count(),
        'products': db.query(models.Product).count(),
        'leads': db.query(models.Lead).count(),
        'customers': db.query(Customer).count(),
    }
    return schemas.CrmDashboard(
        totals=totals,
        leads_by_stage=lead_stages,
        leads_by_segment=lead_segments,
        customers_by_consent=customers_by_consent,
    )


@router.get('/api/v1/security/data-access-control/compliance', response_model=schemas.CrmDashboard)
@router.get('/api/v1/security/zero-trust/access-control/compliance', response_model=schemas.CrmDashboard)
@router.get('/api/v1/security/privacy/compliance', response_model=schemas.CrmDashboard)
def security_privacy_compliance_dashboard(db: Session = Depends(get_db)) -> schemas.CrmDashboard:
    return crm_dashboard(db=db)
