from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit


def send_due_follow_up_reminders(db: Session, limit: int = 200) -> dict[str, int]:
    """Mark due follow-ups as reminded and write audit entries for traceability."""
    now = datetime.now(timezone.utc)
    rows = (
        db.query(models.CRMCommunication)
        .filter(models.CRMCommunication.follow_up_at.isnot(None))
        .filter(models.CRMCommunication.follow_up_at <= now)
        .filter(models.CRMCommunication.reminder_sent_at.is_(None))
        .order_by(models.CRMCommunication.follow_up_at.asc())
        .limit(limit)
        .all()
    )

    reminded = 0
    for row in rows:
        row.reminder_sent_at = now
        if row.status in ('logged', 'sent', 'delivered'):
            row.status = 'follow_up_due'
        db.add(row)

        if row.lead_id is not None:
            log_audit(
                db,
                'lead',
                row.lead_id,
                'follow_up_reminder',
                f'Follow-up reminder generated for CRM communication {row.id}',
            )
        elif row.customer_id is not None:
            log_audit(
                db,
                'customer',
                row.customer_id,
                'follow_up_reminder',
                f'Follow-up reminder generated for CRM communication {row.id}',
            )
        reminded += 1

    db.commit()
    return {'reminders_sent': reminded, 'scanned': len(rows)}
