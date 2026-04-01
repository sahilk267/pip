from datetime import datetime, timedelta, timezone
from typing import Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import AuditLog


def generate_compliance_report(db: Session, window_minutes: int = 1440) -> Dict[str, object]:
    """Summarize audit log activity for governance reporting."""
    window = timedelta(minutes=window_minutes)
    cutoff = datetime.now(timezone.utc) - window

    entity_counts = db.query(
        AuditLog.entity_type,
        func.count(AuditLog.id),
    ).group_by(AuditLog.entity_type).all()

    action_counts = db.query(
        AuditLog.action,
        func.count(AuditLog.id),
    ).group_by(AuditLog.action).all()

    recent_entries = (
        db.query(AuditLog)
        .filter(AuditLog.created_at >= cutoff)
        .order_by(AuditLog.created_at.desc())
        .limit(20)
        .all()
    )

    total = db.query(func.count(AuditLog.id)).scalar() or 0

    return {
        'total_entries': total,
        'entity_counts': {entity: count for entity, count in entity_counts},
        'action_counts': {action: count for action, count in action_counts},
        'recent_entries': recent_entries,
        'window_minutes': window_minutes,
    }
