"""Escalation rules service - define and execute escalation workflows."""

from sqlalchemy.orm import Session
from datetime import datetime, timezone
from .. import models
from ..crud import log_audit


def create_escalation_rule(
    db: Session,
    *,
    rule_code: str,
    rule_type: str,
    entity_type: str,
    conditions: list[dict],
    actions: list[dict],
    priority: int = 5,
    notify_roles: list[str] | None = None,
    sla_hours: int | None = None,
    rule_metadata: dict | None = None,
    created_by: str = 'system',
) -> models.EscalationRule:
    """Create a new escalation rule."""
    rule_code_norm = str(rule_code or '').strip().lower()
    if not rule_code_norm:
        raise ValueError('rule_code is required')
    
    existing = db.query(models.EscalationRule).filter(
        models.EscalationRule.rule_code == rule_code_norm
    ).first()
    if existing:
        raise ValueError(f'Rule {rule_code} already exists')
    
    rule_type_norm = str(rule_type or '').strip()[:32] or 'manual'
    entity_type_norm = str(entity_type or '').strip()[:32] or 'order'
    
    if not conditions:
        raise ValueError('conditions list cannot be empty')
    if not actions:
        raise ValueError('actions list cannot be empty')
    
    priority_val = max(1, min(int(priority), 10))

    row = models.EscalationRule(
        rule_code=rule_code_norm,
        rule_type=rule_type_norm,
        entity_type=entity_type_norm,
        status='active',
        priority=priority_val,
        conditions=conditions,
        actions=actions,
        notify_roles=notify_roles or [],
        sla_hours=int(sla_hours) if sla_hours else None,
        rule_metadata=rule_metadata or {},
        created_by=str(created_by or 'system').strip()[:128] or 'system',
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit(
        db,
        'escalation_rule',
        row.id,
        'escalation_rule_created',
        f'code={row.rule_code} type={row.rule_type} entity_type={row.entity_type}',
        performed_by=created_by,
    )
    return row


def get_escalation_rule(db: Session, *, rule_id: int) -> models.EscalationRule | None:
    """Fetch a rule by ID."""
    return db.query(models.EscalationRule).filter(
        models.EscalationRule.id == rule_id
    ).first()


def list_escalation_rules(
    db: Session,
    *,
    entity_type: str | None = None,
    status: str | None = None,
    rule_type: str | None = None,
    limit: int = 200,
) -> list[models.EscalationRule]:
    """List escalation rules, optionally filtered."""
    query = db.query(models.EscalationRule)
    
    if entity_type:
        entity_type_norm = str(entity_type or '').strip()[:32]
        query = query.filter(models.EscalationRule.entity_type == entity_type_norm)
    
    if status:
        status_norm = str(status or '').strip()
        query = query.filter(models.EscalationRule.status == status_norm)
    
    if rule_type:
        rule_type_norm = str(rule_type or '').strip()[:32]
        query = query.filter(models.EscalationRule.rule_type == rule_type_norm)
    
    return query.order_by(models.EscalationRule.priority, models.EscalationRule.rule_code).limit(limit).all()


def update_escalation_rule(
    db: Session,
    *,
    rule_id: int,
    status: str | None = None,
    priority: int | None = None,
    conditions: list[dict] | None = None,
    actions: list[dict] | None = None,
    notify_roles: list[str] | None = None,
    performed_by: str = 'system',
) -> models.EscalationRule:
    """Update an escalation rule."""
    rule = get_escalation_rule(db, rule_id=rule_id)
    if not rule:
        raise ValueError(f'Rule {rule_id} not found')
    
    if status:
        status_norm = str(status or '').strip()
        if status_norm not in ['active', 'paused', 'archived']:
            raise ValueError('Status must be active, paused, or archived')
        rule.status = status_norm
    
    if priority is not None:
        rule.priority = max(1, min(int(priority), 10))
    
    if conditions:
        rule.conditions = conditions
    
    if actions:
        rule.actions = actions
    
    if notify_roles is not None:
        rule.notify_roles = notify_roles
    
    db.add(rule)
    db.commit()
    db.refresh(rule)
    
    log_audit(
        db,
        'escalation_rule',
        rule.id,
        'escalation_rule_updated',
        f'code={rule.rule_code} status={rule.status}',
        performed_by=performed_by,
    )
    return rule


def evaluate_condition(condition: dict, context: dict) -> bool:
    """Evaluate a single condition against context."""
    field = str(condition.get('field') or '').strip()
    operator = str(condition.get('operator') or '').strip().lower()
    expected_value = condition.get('value')
    
    actual_value = context.get(field)
    
    if operator == 'eq':
        return actual_value == expected_value
    elif operator == 'ne':
        return actual_value != expected_value
    elif operator == 'gt':
        return (actual_value or 0) > (expected_value or 0)
    elif operator == 'gte':
        return (actual_value or 0) >= (expected_value or 0)
    elif operator == 'lt':
        return (actual_value or 0) < (expected_value or 0)
    elif operator == 'lte':
        return (actual_value or 0) <= (expected_value or 0)
    elif operator == 'in':
        return actual_value in (expected_value or [])
    elif operator == 'contains':
        return str(expected_value or '') in str(actual_value or '')
    else:
        return False


def evaluate_rule(rule: models.EscalationRule, context: dict) -> bool:
    """Evaluate whether a rule applies to given context."""
    conditions = rule.conditions or []
    if not conditions:
        return False
    
    # Simple AND logic - all conditions must be true
    return all(evaluate_condition(c, context) for c in conditions)


def trigger_escalation(
    db: Session,
    *,
    rule_id: int,
    entity_type: str,
    entity_id: int,
    trigger_reason: str,
    severity: str = 'warning',
    context: dict | None = None,
    triggered_by: str = 'system',
) -> models.EscalationRecord:
    """Record and execute an escalation based on a rule."""
    rule = get_escalation_rule(db, rule_id=rule_id)
    if not rule:
        raise ValueError(f'Rule {rule_id} not found')
    
    if rule.status != 'active':
        raise ValueError(f'Rule {rule.rule_code} is not active')
    
    entity_type_norm = str(entity_type or '').strip()[:32] or 'unknown'
    severity_norm = str(severity or 'warning').strip()[:16]

    record = models.EscalationRecord(
        rule_id=rule.id,
        entity_type=entity_type_norm,
        entity_id=int(entity_id),
        trigger_reason=str(trigger_reason or 'manual').strip()[:256],
        severity=severity_norm,
        status='open',
        actions_taken=[],
        triggered_by=str(triggered_by or 'system').strip()[:128] or 'system',
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # Execute actions defined in the rule
    for action in (rule.actions or []):
        action_type = str(action.get('action_type') or 'notify').strip()
        
        action_record = {
            'action': action_type,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'performed_by': triggered_by,
            'status': 'executed',
        }
        
        record.actions_taken.append(action_record)
    
    db.add(record)
    db.commit()
    db.refresh(record)

    log_audit(
        db,
        'escalation',
        record.id,
        'escalation_triggered',
        f'rule_code={rule.rule_code} entity={entity_type_norm}/{entity_id} severity={severity_norm}',
        performed_by=triggered_by,
    )
    return record


def resolve_escalation(
    db: Session,
    *,
    escalation_id: int,
    resolution_notes: str | None = None,
    performed_by: str = 'system',
) -> models.EscalationRecord:
    """Mark an escalation as resolved."""
    escalation = db.query(models.EscalationRecord).filter(
        models.EscalationRecord.id == escalation_id
    ).first()
    if not escalation:
        raise ValueError(f'Escalation {escalation_id} not found')
    
    escalation.status = 'resolved'
    escalation.resolution_notes = str(resolution_notes or '').strip() or None
    escalation.resolved_at = datetime.now(timezone.utc)
    db.add(escalation)
    db.commit()
    db.refresh(escalation)

    log_audit(
        db,
        'escalation',
        escalation.id,
        'escalation_resolved',
        f'notes={escalation.resolution_notes}',
        performed_by=performed_by,
    )
    return escalation


def list_escalation_records(
    db: Session,
    *,
    rule_id: int | None = None,
    entity_type: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    limit: int = 200,
) -> list[models.EscalationRecord]:
    """List escalation records, optionally filtered."""
    query = db.query(models.EscalationRecord)
    
    if rule_id:
        query = query.filter(models.EscalationRecord.rule_id == rule_id)
    
    if entity_type:
        entity_type_norm = str(entity_type or '').strip()[:32]
        query = query.filter(models.EscalationRecord.entity_type == entity_type_norm)
    
    if status:
        status_norm = str(status or '').strip()
        query = query.filter(models.EscalationRecord.status == status_norm)
    
    if severity:
        severity_norm = str(severity or '').strip()
        query = query.filter(models.EscalationRecord.severity == severity_norm)
    
    return query.order_by(models.EscalationRecord.created_at.desc()).limit(limit).all()
