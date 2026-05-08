"""RFQ Digest API — configure recipients, send now, view history, unsubscribe."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import rfq_digest as digest_svc

router = APIRouter()


# ─── Config ───────────────────────────────────────────────────────────────────

@router.get("/api/v1/rfq/digest/config")
def get_config(db: Session = Depends(get_db)) -> dict:
    cfg = digest_svc.get_or_create_config(db)
    return _cfg_response(cfg)


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
    return _cfg_response(cfg)


# ─── Send / Preview ───────────────────────────────────────────────────────────

@router.post("/api/v1/rfq/digest/send-now")
def send_now(db: Session = Depends(get_db)) -> dict:
    return digest_svc.send_digest(db, triggered_by="manual")


@router.get("/api/v1/rfq/digest/preview")
def preview_digest(
    window_days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
) -> dict:
    """Return the stats that would be included in the next digest email."""
    stats = digest_svc._compute_stats(db, window_days)
    return {"window_days": window_days, "stats": stats}


# ─── History ──────────────────────────────────────────────────────────────────

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


# ─── Unsubscribe ──────────────────────────────────────────────────────────────

@router.get("/api/v1/rfq/digest/unsubscribe", response_class=HTMLResponse)
def unsubscribe(token: str, db: Session = Depends(get_db)) -> HTMLResponse:
    """
    Public one-click unsubscribe endpoint.
    Embedded as a link in every digest email. No auth required.
    """
    result = digest_svc.unsubscribe_by_token(db, token)

    if not result["success"]:
        return HTMLResponse(_unsub_page(
            icon="⚠️",
            title="Invalid Link",
            message="This unsubscribe link is invalid or has expired.",
            color="#f59e0b",
        ), status_code=400)

    if result.get("already_used"):
        return HTMLResponse(_unsub_page(
            icon="✓",
            title="Already Unsubscribed",
            message=f"{result['email']} was already removed from the digest.",
            color="#4a5c6a",
        ))

    return HTMLResponse(_unsub_page(
        icon="✓",
        title="Unsubscribed Successfully",
        message=f"{result['email']} has been removed from the RFQ digest mailing list.",
        color="#4bca7a",
    ))


@router.get("/api/v1/rfq/digest/unsubscribe-tokens")
def list_unsub_tokens(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Admin view of all generated unsubscribe tokens."""
    tokens = digest_svc.list_unsubscribe_tokens(db, limit=limit)
    return [
        {
            "id": t.id,
            "email": t.email,
            "token": t.token,
            "log_id": t.log_id,
            "used": t.used,
            "used_at": t.used_at.isoformat() if t.used_at else None,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tokens
    ]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _cfg_response(cfg) -> dict:
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return {
        "id": cfg.id,
        "recipient_emails": cfg.recipient_emails or [],
        "schedule_day": cfg.schedule_day,
        "schedule_hour": cfg.schedule_hour,
        "window_days": cfg.window_days,
        "is_active": cfg.is_active,
        "last_run_at": cfg.last_run_at.isoformat() if cfg.last_run_at else None,
        "schedule_label": f"Every {days[cfg.schedule_day]} at {cfg.schedule_hour:02d}:00 UTC",
    }


def _unsub_page(icon: str, title: str, message: str, color: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#0f1419;font-family:system-ui,sans-serif;
             display:flex;align-items:center;justify-content:center;min-height:100vh;">
  <div style="text-align:center;max-width:420px;padding:40px 24px;">
    <div style="font-size:48px;margin-bottom:16px;">{icon}</div>
    <h1 style="color:{color};font-size:22px;font-weight:700;margin:0 0 12px;">{title}</h1>
    <p style="color:#9aacbc;font-size:15px;line-height:1.6;margin:0 0 24px;">{message}</p>
    <p style="color:#4a5c6a;font-size:12px;margin:0;">
      Procurement Intelligence Platform &middot; RFQ Digest
    </p>
  </div>
</body>
</html>"""
