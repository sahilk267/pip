from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Alert


def create_alert(
    db: Session,
    title: str,
    detail: str,
    severity: str = "warning",
    category: str = "monitoring",
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
) -> Alert:
    alert = Alert(
        title=title,
        detail=detail,
        severity=severity,
        category=category,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def resolve_alert(db: Session, alert_id: int) -> None:
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        return
    alert.resolved = True
    alert.resolved_at = func.now()
    db.add(alert)
    db.commit()
