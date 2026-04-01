from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit
from .alerting import create_alert
from .rfq_delivery import list_delivery_attempts
from .vendor_opt_out import get_blocked_vendor_ids_for_channel


def run_automated_escalation(
    db: Session,
    *,
    response_sla_hours: int = 24,
    expansion_limit: int = 3,
    performed_by: str = 'rfq-escalation',
) -> dict:
    response_sla_hours = max(0, min(int(response_sla_hours), 720))
    expansion_limit = max(0, min(int(expansion_limit), 20))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=response_sla_hours)

    candidates = (
        db.query(models.RFQBroadcast)
        .filter(models.RFQBroadcast.created_at <= cutoff)
        .order_by(models.RFQBroadcast.created_at.asc(), models.RFQBroadcast.id.asc())
        .all()
    )

    escalated_cases: list[models.RFQEscalationCase] = []
    alerts_created = 0
    expansion_attempts = 0

    for broadcast in candidates:
        if _has_response(db, broadcast.id):
            continue
        if _has_open_case(db, broadcast.id):
            continue

        attempts = list_delivery_attempts(db, broadcast_id=broadcast.id)
        if not attempts:
            continue

        attempted_vendor_ids = {int(a.vendor_id) for a in attempts}
        additional_vendor_ids = _expand_vendor_pool(
            db,
            attempted_vendor_ids=attempted_vendor_ids,
            channel=broadcast.channel,
            limit=expansion_limit,
        )

        for vendor_id in additional_vendor_ids:
            db.add(
                models.RFQDeliveryAttempt(
                    broadcast_id=broadcast.id,
                    vendor_id=vendor_id,
                    status='queued',
                )
            )
            expansion_attempts += 1

        if additional_vendor_ids:
            broadcast.status = 'in_progress'
        else:
            broadcast.status = 'escalated'
        db.add(broadcast)
        db.commit()
        db.refresh(broadcast)

        row = models.RFQEscalationCase(
            broadcast_id=broadcast.id,
            lead_id=broadcast.lead_id,
            escalation_reason='no_vendor_response_within_sla',
            severity='high' if not additional_vendor_ids else 'warning',
            status='open',
            escalated_by=performed_by,
            escalation_metadata={
                'response_sla_hours': response_sla_hours,
                'attempted_vendor_ids': sorted(attempted_vendor_ids),
                'added_vendor_ids': sorted(additional_vendor_ids),
            },
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        escalated_cases.append(row)

        create_alert(
            db,
            title='RFQ escalation: no vendor response',
            detail=(
                f'broadcast_id={broadcast.id} channel={broadcast.channel} '
                f'added_vendors={len(additional_vendor_ids)}'
            ),
            severity='warning' if additional_vendor_ids else 'critical',
            category='rfq-escalation',
            entity_type='rfq',
            entity_id=broadcast.id,
        )
        alerts_created += 1

        log_audit(
            db,
            'rfq',
            broadcast.id,
            'rfq_auto_escalated',
            (
                f'case_id={row.id} reason=no_vendor_response_within_sla '
                f'added_vendors={len(additional_vendor_ids)}'
            ),
            performed_by=performed_by,
        )

    return {
        'scanned': len(candidates),
        'escalated': len(escalated_cases),
        'alerts_created': alerts_created,
        'expansion_attempts': expansion_attempts,
        'cases': escalated_cases,
    }


def list_escalation_cases(
    db: Session,
    *,
    status: str | None = None,
    limit: int = 200,
) -> list[models.RFQEscalationCase]:
    limit = max(1, min(int(limit), 500))
    query = db.query(models.RFQEscalationCase)
    if status is not None:
        query = query.filter(models.RFQEscalationCase.status == str(status).strip().lower())
    return query.order_by(models.RFQEscalationCase.created_at.desc(), models.RFQEscalationCase.id.desc()).limit(limit).all()


def _has_response(db: Session, broadcast_id: int) -> bool:
    response = (
        db.query(models.RFQVendorResponse.id)
        .join(models.RFQDeliveryAttempt, models.RFQDeliveryAttempt.id == models.RFQVendorResponse.attempt_id)
        .filter(models.RFQDeliveryAttempt.broadcast_id == int(broadcast_id))
        .first()
    )
    return response is not None


def _has_open_case(db: Session, broadcast_id: int) -> bool:
    existing = (
        db.query(models.RFQEscalationCase.id)
        .filter(
            models.RFQEscalationCase.broadcast_id == int(broadcast_id),
            models.RFQEscalationCase.status == 'open',
        )
        .first()
    )
    return existing is not None


def _expand_vendor_pool(
    db: Session,
    *,
    attempted_vendor_ids: set[int],
    channel: str,
    limit: int,
) -> list[int]:
    if limit <= 0:
        return []
    rows = (
        db.query(models.Vendor.id)
        .filter(~models.Vendor.id.in_(sorted(attempted_vendor_ids)))
        .order_by(models.Vendor.updated_at.desc(), models.Vendor.id.asc())
        .limit(limit * 3)
        .all()
    )
    candidate_ids = [int(row.id) for row in rows]
    blocked = set(
        get_blocked_vendor_ids_for_channel(
            db,
            vendor_ids=candidate_ids,
            channel=str(channel or 'email').strip().lower() or 'email',
        )
    )
    selected = [vendor_id for vendor_id in candidate_ids if vendor_id not in blocked]
    return selected[:limit]
