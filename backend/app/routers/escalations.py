"""Escalation rules and records router - automated escalation workflows."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models
from ..schemas import (
    EscalationRuleCreate,
    EscalationRuleResponse,
    EscalationRecordResponse,
)
from ..services.escalation_rules import (
    create_escalation_rule,
    get_escalation_rule,
    list_escalation_rules,
    update_escalation_rule,
    trigger_escalation,
    resolve_escalation,
    list_escalation_records,
)

router = APIRouter()


@router.post('/api/v1/escalations/rules', response_model=EscalationRuleResponse)
def create_rule(
    payload: EscalationRuleCreate,
    db: Session = Depends(get_db),
) -> EscalationRuleResponse:
    try:
        row = create_escalation_rule(
            db,
            rule_code=payload.rule_code,
            rule_type=payload.rule_type,
            entity_type=payload.entity_type,
            conditions=[c.model_dump() for c in payload.conditions],
            actions=[a.model_dump() for a in payload.actions],
            priority=payload.priority,
            notify_roles=payload.notify_roles,
            sla_hours=payload.sla_hours,
            rule_metadata=payload.rule_metadata,
            created_by='system',
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return EscalationRuleResponse.model_validate(row)


@router.get('/api/v1/escalations/rules/{rule_id}', response_model=EscalationRuleResponse)
def get_rule(
    rule_id: int,
    db: Session = Depends(get_db),
) -> EscalationRuleResponse:
    row = get_escalation_rule(db, rule_id=rule_id)
    if not row:
        raise HTTPException(status_code=404, detail='Rule not found')
    return EscalationRuleResponse.model_validate(row)


@router.get('/api/v1/escalations/rules', response_model=list[EscalationRuleResponse])
def list_rules(
    entity_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    rule_type: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[EscalationRuleResponse]:
    rows = list_escalation_rules(
        db,
        entity_type=entity_type,
        status=status,
        rule_type=rule_type,
        limit=limit,
    )
    return [EscalationRuleResponse.model_validate(row) for row in rows]


@router.patch('/api/v1/escalations/rules/{rule_id}', response_model=EscalationRuleResponse)
def update_rule(
    rule_id: int,
    payload: dict,
    db: Session = Depends(get_db),
) -> EscalationRuleResponse:
    try:
        row = update_escalation_rule(
            db,
            rule_id=rule_id,
            status=payload.get('status'),
            priority=payload.get('priority'),
            conditions=payload.get('conditions'),
            actions=payload.get('actions'),
            notify_roles=payload.get('notify_roles'),
            performed_by='system',
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return EscalationRuleResponse.model_validate(row)


# ---------- Escalation Records ----------

@router.post('/api/v1/escalations/trigger', response_model=EscalationRecordResponse)
def trigger_escalation_manually(
    rule_id: int = Query(...),
    entity_type: str = Query(...),
    entity_id: int = Query(...),
    trigger_reason: str = Query(default='manual'),
    severity: str = Query(default='warning'),
    db: Session = Depends(get_db),
) -> EscalationRecordResponse:
    try:
        row = trigger_escalation(
            db,
            rule_id=rule_id,
            entity_type=entity_type,
            entity_id=entity_id,
            trigger_reason=trigger_reason,
            severity=severity,
            triggered_by='system',
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return EscalationRecordResponse.model_validate(row)


@router.get('/api/v1/escalations/records/{escalation_id}', response_model=EscalationRecordResponse)
def get_escalation_record(
    escalation_id: int,
    db: Session = Depends(get_db),
) -> EscalationRecordResponse:
    row = db.query(models.EscalationRecord).filter(
        models.EscalationRecord.id == escalation_id
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail='Record not found')
    return EscalationRecordResponse.model_validate(row)


@router.get('/api/v1/escalations/records', response_model=list[EscalationRecordResponse])
def list_records(
    rule_id: int | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[EscalationRecordResponse]:
    rows = list_escalation_records(
        db,
        rule_id=rule_id,
        entity_type=entity_type,
        status=status,
        severity=severity,
        limit=limit,
    )
    return [EscalationRecordResponse.model_validate(row) for row in rows]


@router.patch('/api/v1/escalations/records/{escalation_id}/resolve')
def resolve_escalation_record(
    escalation_id: int,
    resolution_notes: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> EscalationRecordResponse:
    try:
        row = resolve_escalation(
            db,
            escalation_id=escalation_id,
            resolution_notes=resolution_notes,
            performed_by='system',
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return EscalationRecordResponse.model_validate(row)
