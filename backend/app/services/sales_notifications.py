from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit


_ALLOWED_STATUS = {'pending', 'sent', 'dismissed'}


def create_sales_notification(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    notification_type: str,
    message: str,
    priority: str = 'medium',
    lead_id: int | None = None,
    recipient: str = 'sales',
    channel: str = 'inbox',
    metadata: dict | None = None,
    performed_by: str = 'system',
) -> models.SalesRepNotification:
    row = models.SalesRepNotification(
        lead_id=int(lead_id) if lead_id is not None else None,
        entity_type=str(entity_type or 'rfq').strip()[:32] or 'rfq',
        entity_id=int(entity_id),
        notification_type=str(notification_type or 'rfq_update').strip()[:64] or 'rfq_update',
        priority=str(priority or 'medium').strip()[:16] or 'medium',
        channel=str(channel or 'inbox').strip()[:32] or 'inbox',
        recipient=str(recipient or 'sales').strip()[:128] or 'sales',
        message=str(message or '').strip()[:2000] or 'Sales notification',
        status='pending',
        notification_metadata=metadata or {},
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit(
        db,
        'notification',
        row.id,
        'sales_rep_notification_created',
        f'type={row.notification_type} priority={row.priority} recipient={row.recipient}',
        performed_by=performed_by,
    )
    return row


def list_sales_notifications(
    db: Session,
    *,
    status: str | None = None,
    recipient: str | None = None,
    limit: int = 200,
) -> list[models.SalesRepNotification]:
    limit = max(1, min(int(limit), 500))
    query = db.query(models.SalesRepNotification)
    if status is not None:
        query = query.filter(models.SalesRepNotification.status == str(status).strip().lower())
    if recipient is not None:
        query = query.filter(models.SalesRepNotification.recipient == str(recipient).strip())
    return query.order_by(models.SalesRepNotification.created_at.desc(), models.SalesRepNotification.id.desc()).limit(limit).all()


def update_sales_notification_status(
    db: Session,
    *,
    notification_id: int,
    status: str,
    performed_by: str,
) -> models.SalesRepNotification:
    normalized = str(status or '').strip().lower()
    if normalized not in _ALLOWED_STATUS:
        raise ValueError('Unsupported notification status')

    row = db.query(models.SalesRepNotification).filter(models.SalesRepNotification.id == int(notification_id)).first()
    if row is None:
        raise ValueError('Sales notification not found')

    row.status = normalized
    if normalized == 'sent':
        row.sent_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit(
        db,
        'notification',
        row.id,
        'sales_rep_notification_status_updated',
        f'status={row.status}',
        performed_by=performed_by,
    )
    return row
