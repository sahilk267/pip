"""RFQ Email Digest — weekly summary of RFQ performance stats."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..models_extended import RFQDigestConfig, RFQDigestLog
from .. import models
from . import email_service

logger = logging.getLogger(__name__)

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ─── Stats computation ────────────────────────────────────────────────────────

def _compute_stats(db: Session, window_days: int) -> dict[str, Any]:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=window_days)

    broadcasts = (
        db.query(models.RFQBroadcast)
        .filter(models.RFQBroadcast.created_at >= cutoff)
        .all()
    )
    total_broadcasts = len(broadcasts)
    broadcast_ids = [b.id for b in broadcasts]

    attempt_rows = (
        db.query(models.RFQDeliveryAttempt)
        .filter(models.RFQDeliveryAttempt.broadcast_id.in_(broadcast_ids))
        .all()
    ) if broadcast_ids else []
    attempt_ids = [a.id for a in attempt_rows]
    vendors_reached = len(attempt_rows)

    responses = (
        db.query(models.RFQVendorResponse)
        .filter(models.RFQVendorResponse.attempt_id.in_(attempt_ids))
        .all()
    ) if attempt_ids else []
    total_responses = len(responses)
    response_rate = round(total_responses / vendors_reached * 100, 1) if vendors_reached else 0.0

    quotes = (
        db.query(models.RFQParsedQuote)
        .filter(models.RFQParsedQuote.attempt_id.in_(attempt_ids))
        .all()
    ) if attempt_ids else []
    prices = [q.unit_price for q in quotes if q.unit_price is not None]
    avg_price = round(sum(prices) / len(prices), 2) if prices else None
    lead_times = [q.lead_time_days for q in quotes if q.lead_time_days is not None]
    avg_lead = round(sum(lead_times) / len(lead_times), 1) if lead_times else None

    # Top broadcast by response rate
    top_broadcast = None
    best_rate = -1.0
    for bc in broadcasts:
        bc_attempts = [a for a in attempt_rows if a.broadcast_id == bc.id]
        bc_responses = [r for r in responses if any(a.id == r.attempt_id for a in bc_attempts)]
        if bc_attempts:
            rate = len(bc_responses) / len(bc_attempts) * 100
            if rate > best_rate:
                best_rate = rate
                top_broadcast = {"message": bc.message or f"RFQ-{bc.id:04d}", "rate": round(rate, 1)}

    # Winning vendor (most quote wins)
    broadcast_quotes: dict[int, list] = {}
    for q in quotes:
        attempt = next((a for a in attempt_rows if a.id == q.attempt_id), None)
        if attempt:
            broadcast_quotes.setdefault(attempt.broadcast_id, []).append(q)

    vendor_wins: dict[int, int] = {}
    for bquotes in broadcast_quotes.values():
        priced = [q for q in bquotes if q.unit_price is not None]
        if priced:
            winner = min(priced, key=lambda q: q.unit_price)
            vendor_wins[winner.vendor_id] = vendor_wins.get(winner.vendor_id, 0) + 1

    top_vendor_name = None
    if vendor_wins:
        top_vid = max(vendor_wins, key=lambda v: vendor_wins[v])
        vendor = db.query(models.Vendor).filter(models.Vendor.id == top_vid).first()
        top_vendor_name = vendor.name if vendor else None

    return {
        "window_days": window_days,
        "total_broadcasts": total_broadcasts,
        "vendors_reached": vendors_reached,
        "total_responses": total_responses,
        "response_rate_pct": response_rate,
        "total_quotes": len(quotes),
        "avg_unit_price_usd": avg_price,
        "avg_lead_time_days": avg_lead,
        "top_broadcast": top_broadcast,
        "top_winning_vendor": top_vendor_name,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }


# ─── Email rendering ──────────────────────────────────────────────────────────

def _html_email(stats: dict[str, Any], period_label: str) -> str:
    def kpi(label: str, value: str, color: str = "#4b9fff") -> str:
        return f"""
        <td style="text-align:center;padding:16px 12px;background:#1a232e;border-radius:8px;border:1px solid #2a3540;">
          <div style="font-size:22px;font-weight:700;color:{color};">{value}</div>
          <div style="font-size:11px;color:#9aacbc;margin-top:4px;text-transform:uppercase;letter-spacing:.05em;">{label}</div>
        </td>"""

    avg_price = f"${stats['avg_unit_price_usd']:,.2f}" if stats["avg_unit_price_usd"] else "—"
    avg_lead = f"{stats['avg_lead_time_days']}d" if stats["avg_lead_time_days"] else "—"
    top_bc = stats.get("top_broadcast")
    top_bc_html = (
        f'<tr><td style="padding:10px 0;border-bottom:1px solid #1e2a34;">'
        f'<span style="color:#e7ecf1;font-size:13px;">{top_bc["message"]}</span>'
        f'<span style="float:right;color:#4bca7a;font-weight:700;">{top_bc["rate"]}% response rate</span>'
        f'</td></tr>'
    ) if top_bc else ""
    top_vendor = stats.get("top_winning_vendor") or "—"

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/></head>
<body style="margin:0;padding:0;background:#0f1419;font-family:system-ui,sans-serif;color:#e7ecf1;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;margin:32px auto;">
  <tr><td>

    <!-- Header -->
    <table width="100%" style="background:#121a24;border-radius:12px 12px 0 0;border:1px solid #2a3540;border-bottom:none;">
      <tr>
        <td style="padding:24px 28px;">
          <div style="display:inline-block;background:#1e3a5f;color:#4b9fff;font-size:11px;font-weight:700;
                      letter-spacing:.08em;text-transform:uppercase;padding:4px 10px;border-radius:4px;margin-bottom:12px;">
            Weekly RFQ Digest
          </div>
          <h1 style="margin:0 0 4px;font-size:22px;font-weight:700;color:#fff;">
            RFQ Performance Summary
          </h1>
          <p style="margin:0;font-size:13px;color:#9aacbc;">{period_label}</p>
        </td>
      </tr>
    </table>

    <!-- KPI grid -->
    <table width="100%" style="background:#0f1419;border:1px solid #2a3540;border-top:none;border-bottom:none;padding:20px 28px;">
      <tr><td style="padding:0 0 16px;font-size:11px;color:#4a5c6a;text-transform:uppercase;letter-spacing:.08em;">Key Metrics</td></tr>
      <tr>
        <table width="100%" cellpadding="8" cellspacing="0">
          <tr>
            {kpi("Broadcasts", str(stats["total_broadcasts"]), "#4b9fff")}
            <td width="12"></td>
            {kpi("Response Rate", f"{stats['response_rate_pct']}%", "#4bca7a")}
            <td width="12"></td>
            {kpi("Avg Quote Price", avg_price, "#f59e0b")}
            <td width="12"></td>
            {kpi("Avg Lead Time", avg_lead, "#a78bfa")}
          </tr>
        </table>
      </tr>
      <tr><td style="padding:12px 0 0;font-size:12px;color:#4a5c6a;">
        {stats['vendors_reached']} vendors reached · {stats['total_responses']} responses · {stats['total_quotes']} quotes
      </td></tr>
    </table>

    <!-- Highlights -->
    <table width="100%" style="background:#121a24;border:1px solid #2a3540;border-top:none;border-bottom:none;padding:20px 28px;">
      <tr><td style="padding:0 0 12px;font-size:11px;color:#4a5c6a;text-transform:uppercase;letter-spacing:.08em;">Highlights</td></tr>
      {"<tr><td><table width='100%'>" + top_bc_html + "</table></td></tr>" if top_bc_html else ""}
      <tr>
        <td style="padding:10px 0;border-bottom:1px solid #1e2a34;">
          <span style="color:#9aacbc;font-size:13px;">Top winning vendor</span>
          <span style="float:right;color:#f59e0b;font-weight:700;font-size:13px;">🏆 {top_vendor}</span>
        </td>
      </tr>
    </table>

    <!-- Footer -->
    <table width="100%" style="background:#0f1419;border-radius:0 0 12px 12px;border:1px solid #2a3540;border-top:none;">
      <tr>
        <td style="padding:16px 28px;font-size:11px;color:#4a5c6a;text-align:center;">
          Procurement Intelligence Platform · Weekly Digest<br/>
          Generated {datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
        </td>
      </tr>
    </table>

  </td></tr>
</table>
</body></html>"""


def _text_email(stats: dict[str, Any], period_label: str) -> str:
    avg_price = f"${stats['avg_unit_price_usd']:,.2f}" if stats["avg_unit_price_usd"] else "N/A"
    avg_lead = f"{stats['avg_lead_time_days']} days" if stats["avg_lead_time_days"] else "N/A"
    top_bc = stats.get("top_broadcast")
    top_bc_line = f"  Best broadcast: {top_bc['message']} ({top_bc['rate']}%)" if top_bc else ""

    return f"""
WEEKLY RFQ DIGEST — {period_label}
Procurement Intelligence Platform

KEY METRICS
-----------
  Broadcasts sent:   {stats["total_broadcasts"]}
  Vendors reached:   {stats["vendors_reached"]}
  Total responses:   {stats["total_responses"]}
  Response rate:     {stats["response_rate_pct"]}%
  Total quotes:      {stats["total_quotes"]}
  Avg quote price:   {avg_price}
  Avg lead time:     {avg_lead}

HIGHLIGHTS
----------
{top_bc_line}
  Top winning vendor: {stats.get("top_winning_vendor") or "N/A"}

Generated: {datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
""".strip()


# ─── Config helpers ───────────────────────────────────────────────────────────

def get_or_create_config(db: Session) -> RFQDigestConfig:
    cfg = db.query(RFQDigestConfig).first()
    if not cfg:
        cfg = RFQDigestConfig(
            recipient_emails=[],
            schedule_day=0,
            schedule_hour=8,
            window_days=7,
            is_active=True,
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def update_config(
    db: Session,
    recipient_emails: list[str] | None = None,
    schedule_day: int | None = None,
    schedule_hour: int | None = None,
    window_days: int | None = None,
    is_active: bool | None = None,
) -> RFQDigestConfig:
    cfg = get_or_create_config(db)
    if recipient_emails is not None:
        cfg.recipient_emails = [e.strip().lower() for e in recipient_emails if e.strip()]
    if schedule_day is not None:
        cfg.schedule_day = max(0, min(6, schedule_day))
    if schedule_hour is not None:
        cfg.schedule_hour = max(0, min(23, schedule_hour))
    if window_days is not None:
        cfg.window_days = max(1, min(90, window_days))
    if is_active is not None:
        cfg.is_active = is_active
    db.commit()
    db.refresh(cfg)
    return cfg


def list_logs(db: Session, limit: int = 20) -> list[RFQDigestLog]:
    return (
        db.query(RFQDigestLog)
        .order_by(RFQDigestLog.sent_at.desc())
        .limit(limit)
        .all()
    )


# ─── Core send logic ──────────────────────────────────────────────────────────

def send_digest(db: Session, triggered_by: str = "scheduler") -> dict[str, Any]:
    """Compute stats, build email, send to all recipients, log result."""
    cfg = get_or_create_config(db)
    recipients = cfg.recipient_emails or []

    now = datetime.now(tz=timezone.utc)
    window = cfg.window_days
    period_start = (now - timedelta(days=window)).strftime("%b %d")
    period_end = now.strftime("%b %d, %Y")
    period_label = f"{period_start} – {period_end}"

    stats = _compute_stats(db, window)
    subject = f"📊 Weekly RFQ Digest — {period_label}"
    html_body = _html_email(stats, period_label)
    text_body = _text_email(stats, period_label)

    log = RFQDigestLog(
        triggered_by=triggered_by,
        recipients=recipients,
        status="pending",
        stats_snapshot=stats,
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    sent_count = 0
    failed_count = 0
    errors: list[str] = []

    if not recipients:
        log.status = "failed"
        log.error_message = "No recipients configured"
        log.failed_count = 0
        db.commit()
        return {"status": "failed", "reason": "no_recipients", "stats": stats}

    for recipient in recipients:
        try:
            result = email_service.send_email(
                to=recipient,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            )
            if result.get("sent"):
                sent_count += 1
            else:
                failed_count += 1
                errors.append(f"{recipient}: send returned False")
        except Exception as exc:
            failed_count += 1
            errors.append(f"{recipient}: {exc}")

    if sent_count > 0 and failed_count == 0:
        log.status = "success"
    elif sent_count > 0:
        log.status = "partial"
    else:
        log.status = "failed"

    log.sent_count = sent_count
    log.failed_count = failed_count
    log.error_message = "; ".join(errors) if errors else None

    cfg.last_run_at = now
    db.commit()

    logger.info(
        "RFQ digest sent: %s/%s recipients, status=%s",
        sent_count, len(recipients), log.status,
    )
    return {
        "status": log.status,
        "sent_count": sent_count,
        "failed_count": failed_count,
        "recipients": recipients,
        "stats": stats,
        "log_id": log.id,
    }


# ─── Scheduler check ──────────────────────────────────────────────────────────

def maybe_send_scheduled_digest() -> None:
    """Called by the periodic scheduler — sends digest if it's the right day/hour."""
    from ..database import SessionLocal
    now = datetime.now(tz=timezone.utc)

    with SessionLocal() as db:
        cfg = get_or_create_config(db)
        if not cfg.is_active or not cfg.recipient_emails:
            return

        # Check day-of-week (0=Mon) and hour
        if now.weekday() != cfg.schedule_day or now.hour != cfg.schedule_hour:
            return

        # Avoid double-sending within the same hour
        if cfg.last_run_at:
            last = cfg.last_run_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if (now - last).total_seconds() < 3600:
                return

        logger.info("Sending scheduled RFQ digest (day=%d hour=%d)", cfg.schedule_day, cfg.schedule_hour)
        send_digest(db, triggered_by="scheduler")
