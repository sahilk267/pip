from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit


_ALLOWED_STATUSES = {'draft', 'approved', 'rejected', 'rolled_back', 'deprecated'}


def register_model_record(
    db: Session,
    *,
    model_name: str,
    model_type: str,
    model_version: str,
    approval_required: bool = True,
    evaluation_metrics: dict | None = None,
    governance_metadata: dict | None = None,
    created_by: str = 'mlops',
) -> models.AIModelGovernanceRecord:
    name = str(model_name or '').strip().lower()[:128]
    version = str(model_version or '').strip()[:64]
    if not name or not version:
        raise ValueError('model_name and model_version are required')

    existing = (
        db.query(models.AIModelGovernanceRecord)
        .filter(
            models.AIModelGovernanceRecord.model_name == name,
            models.AIModelGovernanceRecord.model_version == version,
        )
        .first()
    )
    if existing is not None:
        raise ValueError('Model version already registered')

    row = models.AIModelGovernanceRecord(
        model_name=name,
        model_type=str(model_type or 'negotiation').strip().lower()[:64] or 'negotiation',
        model_version=version,
        status='draft',
        approval_required=bool(approval_required),
        evaluation_metrics=evaluation_metrics or {},
        governance_metadata=governance_metadata or {},
        created_by=str(created_by or 'mlops').strip()[:128] or 'mlops',
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit(
        db,
        'ai_model',
        row.id,
        'ai_model_version_registered',
        f'model={row.model_name} version={row.model_version}',
        performed_by=row.created_by,
    )
    return row


def review_model_record(
    db: Session,
    *,
    record_id: int,
    decision: str,
    reviewed_by: str,
    note: str | None = None,
) -> models.AIModelGovernanceRecord:
    row = (
        db.query(models.AIModelGovernanceRecord)
        .filter(models.AIModelGovernanceRecord.id == int(record_id))
        .first()
    )
    if row is None:
        raise ValueError('AI model governance record not found')

    normalized = str(decision or '').strip().lower()
    if normalized not in {'approved', 'rejected'}:
        raise ValueError('decision must be approved or rejected')

    row.status = normalized
    row.approved_by = str(reviewed_by or 'mlops-review').strip()[:128] or 'mlops-review'
    row.approved_at = datetime.now(timezone.utc)

    metadata = dict(row.governance_metadata or {})
    if note:
        metadata['review_note'] = str(note)[:2000]
    row.governance_metadata = metadata

    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit(
        db,
        'ai_model',
        row.id,
        'ai_model_version_reviewed',
        f'decision={normalized}',
        performed_by=row.approved_by,
    )
    return row


def rollback_model_record(
    db: Session,
    *,
    model_name: str,
    from_version: str,
    to_version: str,
    reason: str,
    performed_by: str,
) -> models.AIModelGovernanceRecord:
    name = str(model_name or '').strip().lower()[:128]
    row = (
        db.query(models.AIModelGovernanceRecord)
        .filter(
            models.AIModelGovernanceRecord.model_name == name,
            models.AIModelGovernanceRecord.model_version == str(from_version or '').strip()[:64],
        )
        .first()
    )
    if row is None:
        raise ValueError('Source AI model version not found')

    row.status = 'rolled_back'
    row.rollback_to_version = str(to_version or '').strip()[:64] or None
    row.rollback_reason = str(reason or '').strip()[:4000] or 'manual rollback'
    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit(
        db,
        'ai_model',
        row.id,
        'ai_model_version_rolled_back',
        f'from={from_version} to={to_version} reason={row.rollback_reason}',
        performed_by=str(performed_by or 'mlops').strip()[:128] or 'mlops',
    )
    return row


def list_model_records(
    db: Session,
    *,
    model_name: str | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[models.AIModelGovernanceRecord]:
    query = db.query(models.AIModelGovernanceRecord)

    if model_name:
        query = query.filter(models.AIModelGovernanceRecord.model_name == str(model_name).strip().lower())
    if status:
        normalized = str(status).strip().lower()
        if normalized in _ALLOWED_STATUSES:
            query = query.filter(models.AIModelGovernanceRecord.status == normalized)

    return (
        query.order_by(
            models.AIModelGovernanceRecord.created_at.desc(),
            models.AIModelGovernanceRecord.id.desc(),
        )
        .limit(max(1, min(int(limit), 500)))
        .all()
    )
