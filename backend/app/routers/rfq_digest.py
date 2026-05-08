"""RFQ Digest API — configure recipients, send now, view history."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import rfq_digest as digest_svc

router = APIRouter()


@router.get("/api/v1/rfq/digest/config")
def get_config(db: Session = Depends(get_db)) -> dict:
    cfg = digest_svc.get_or_create_config(db)
    return {
        "id": cfg.id,
        "recipient_emails": cfg.recipient_emails or [],
        "schedule_day": cfg.schedule_day,
        "schedule_hour": cfg.schedule_hour,
        "window_days": cfg.window_days,
        "is_active": cfg.is_active,
        "last_run_at": cfg.last_run_at.isoformat() if cfg.last_run_at else None,
        "schedule_label": _schedule_label(cfg.schedule_day, cfg.schedule_hour),
    }


@router.post("/api/v1/rfq/digest/config")
def save_config(
    recipient_emails: list[str] | None = None,
    schedule_day: int | None = Query(default=None, ge=0, le=6),
    schedule_hour: int | None = Query(default=None, ge=0, le=23),
    window_days: int | None = Query(default=None, ge=1, le=90),
    is_active: bool | None = None,
    db: Session = Depends(get_db),
) -> dict:
    cfg = digest_svc.update_config(
        db,
        recipient_emails=recipient_emails,
        schedule_day=schedule_day,
        schedule_hour=schedule_hour,
        window_days=window_days,
        is_active=is_active,
    )
    return {
        "id": cfg.id,
        "recipient_emails": cfg.recipient_emails or [],
        "schedule_day": cfg.schedule_day,
        "schedule_hour": cfg.schedule_hour,
        "window_days": cfg.window_days,
        "is_active": cfg.is_active,
        "last_run_at": cfg.last_run_at.isoformat() if cfg.last_run_at else None,
        "schedule_label": _schedule_label(cfg.schedule_day, cfg.schedule_hour),
    }


@router.post("/api/v1/rfq/digest/send-now")
def send_now(db: Session = Depends(get_db)) -> dict:
    return digest_svc.send_digest(db, triggered_by="manual")


@router.get("/api/v1/rfq/digest/history")
def digest_history(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[dict]:
    logs = digest_svc.list_logs(db, limit=limit)
    return [
        {
            "id": log.id,
            "triggered_by": log.triggered_by,
            "recipients": log.recipients or [],
            "status": log.status,
            "sent_count": log.sent_count,
            "failed_count": log.failed_count,
            "error_message": log.error_message,
            "stats_snapshot": log.stats_snapshot or {},
            "sent_at": log.sent_at.isoformat() if log.sent_at else None,
        }
        for log in logs
    ]


@router.get("/api/v1/rfq/digest/preview")
def preview_digest(
    window_days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
) -> dict:
    """Return the stats that would be included in the next digest email."""
    from ..services.rfq_digest import _compute_stats
    stats = _compute_stats(db, window_days)
    return {"window_days": window_days, "stats": stats}


def _schedule_label(day: int, hour: int) -> str:
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return f"Every {days[day]} at {hour:02d}:00 UTC"
