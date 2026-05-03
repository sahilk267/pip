"""Email Service — SMTP + SendGrid compatible with console fallback."""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

logger = logging.getLogger(__name__)

# ─── Configuration (set via environment variables) ────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "noreply@procurement-platform.com")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Procurement Intelligence Platform")

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "auto")  # auto | smtp | sendgrid | console


def _is_configured() -> bool:
    return bool(SENDGRID_API_KEY or (SMTP_HOST and SMTP_USER and SMTP_PASSWORD))


def _send_via_sendgrid(to: str, subject: str, html_body: str, text_body: str) -> bool:
    try:
        import urllib.request, urllib.error, json
        payload = json.dumps({
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": SMTP_FROM, "name": SMTP_FROM_NAME},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": text_body},
                {"type": "text/html", "value": html_body},
            ],
        }).encode()
        req = urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=payload,
            headers={
                "Authorization": f"Bearer {SENDGRID_API_KEY}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 202)
    except Exception as exc:
        logger.error("SendGrid error: %s", exc)
        return False


def _send_via_smtp(to: str, subject: str, html_body: str, text_body: str) -> bool:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM}>"
        msg["To"] = to
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, to, msg.as_string())
        return True
    except Exception as exc:
        logger.error("SMTP error: %s", exc)
        return False


def _log_email(to: str, subject: str, text_body: str) -> bool:
    """Console fallback — logs email content when no provider is configured."""
    separator = "=" * 60
    logger.info(
        "\n%s\n📧 EMAIL (console mode)\nTo:      %s\nSubject: %s\nTime:    %s\n%s\n%s\n%s",
        separator, to, subject,
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        separator, text_body, separator,
    )
    print(f"\n{'='*60}\n📧 EMAIL → {to}\nSubject: {subject}\n{text_body}\n{'='*60}\n")
    return True


def send_email(
    to: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> dict[str, Any]:
    """Send an email using the best available backend."""
    if not text_body:
        import re
        text_body = re.sub(r"<[^>]+>", "", html_body).strip()

    backend = EMAIL_BACKEND.lower()
    success = False

    if backend == "sendgrid" or (backend == "auto" and SENDGRID_API_KEY):
        success = _send_via_sendgrid(to, subject, html_body, text_body)
    elif backend == "smtp" or (backend == "auto" and SMTP_HOST and SMTP_USER):
        success = _send_via_smtp(to, subject, html_body, text_body)
    else:
        success = _log_email(to, subject, text_body)

    return {
        "sent": success,
        "to": to,
        "subject": subject,
        "backend": backend if backend != "auto" else ("sendgrid" if SENDGRID_API_KEY else "smtp" if SMTP_HOST else "console"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─── Pre-built email templates ────────────────────────────────────────────────

def send_order_confirmation(to: str, order_id: int, total: float, currency: str = "USD") -> dict[str, Any]:
    subject = f"Order #{order_id} Confirmed — Thank you!"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f9fafb;padding:32px;">
      <div style="background:#1e293b;border-radius:12px;padding:32px;color:#f1f5f9;">
        <h1 style="color:#3b82f6;margin:0 0 8px;">Order Confirmed ✓</h1>
        <p style="color:#94a3b8;margin:0 0 24px;">Your order has been placed successfully.</p>
        <div style="background:#0f172a;border-radius:8px;padding:16px;margin-bottom:24px;">
          <p style="margin:0;font-size:14px;color:#94a3b8;">Order Number</p>
          <p style="margin:4px 0 0;font-size:24px;font-weight:700;color:#3b82f6;">#{order_id}</p>
        </div>
        <div style="background:#0f172a;border-radius:8px;padding:16px;margin-bottom:24px;">
          <p style="margin:0;font-size:14px;color:#94a3b8;">Total Amount</p>
          <p style="margin:4px 0 0;font-size:24px;font-weight:700;color:#10b981;">{currency} {total:,.2f}</p>
        </div>
        <p style="color:#94a3b8;font-size:14px;">We will notify you when your order ships. Thank you for your business!</p>
      </div>
    </div>
    """
    return send_email(to, subject, html)


def send_rfq_vendor_notification(
    to: str, vendor_name: str, rfq_title: str, rfq_id: int, deadline: str | None = None
) -> dict[str, Any]:
    subject = f"New RFQ Request: {rfq_title}"
    deadline_line = f"<p><strong>Deadline:</strong> {deadline}</p>" if deadline else ""
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f9fafb;padding:32px;">
      <div style="background:#1e293b;border-radius:12px;padding:32px;color:#f1f5f9;">
        <h1 style="color:#8b5cf6;margin:0 0 8px;">RFQ Invitation 📋</h1>
        <p style="color:#94a3b8;margin:0 0 24px;">Dear {vendor_name}, you have been selected for an RFQ.</p>
        <div style="background:#0f172a;border-radius:8px;padding:16px;margin-bottom:16px;">
          <p style="margin:0;font-size:14px;color:#94a3b8;">RFQ Title</p>
          <p style="margin:4px 0 0;font-size:18px;font-weight:700;color:#f1f5f9;">{rfq_title}</p>
        </div>
        <div style="background:#0f172a;border-radius:8px;padding:16px;margin-bottom:16px;">
          <p style="margin:0;font-size:14px;color:#94a3b8;">Reference ID</p>
          <p style="margin:4px 0 0;font-size:18px;font-weight:700;color:#8b5cf6;">RFQ-{rfq_id:04d}</p>
        </div>
        {deadline_line}
        <p style="color:#94a3b8;font-size:14px;">Please review and submit your quote at your earliest convenience.</p>
      </div>
    </div>
    """
    return send_email(to, subject, html)


def send_quote_comparison_ready(to: str, rfq_title: str, quote_count: int) -> dict[str, Any]:
    subject = f"Quote Comparison Ready — {rfq_title}"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f9fafb;padding:32px;">
      <div style="background:#1e293b;border-radius:12px;padding:32px;color:#f1f5f9;">
        <h1 style="color:#f59e0b;margin:0 0 8px;">Quotes Ready 📊</h1>
        <p style="color:#94a3b8;margin:0 0 24px;">{quote_count} vendor quote(s) are ready for your review.</p>
        <div style="background:#0f172a;border-radius:8px;padding:16px;margin-bottom:24px;">
          <p style="margin:0;font-size:14px;color:#94a3b8;">RFQ</p>
          <p style="margin:4px 0 0;font-size:18px;font-weight:700;color:#f1f5f9;">{rfq_title}</p>
        </div>
        <p style="color:#94a3b8;font-size:14px;">Log in to the Procurement Platform to compare quotes side-by-side.</p>
      </div>
    </div>
    """
    return send_email(to, subject, html)


def send_lead_follow_up(to: str, lead_name: str, rep_name: str, company: str = "") -> dict[str, Any]:
    subject = f"Following up — {company or 'Your Inquiry'}"
    company_line = f" at {company}" if company else ""
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f9fafb;padding:32px;">
      <div style="background:#1e293b;border-radius:12px;padding:32px;color:#f1f5f9;">
        <h1 style="color:#10b981;margin:0 0 8px;">Following Up 👋</h1>
        <p style="color:#94a3b8;margin:0 0 24px;">Hi {lead_name}{company_line},</p>
        <p style="color:#f1f5f9;">I wanted to follow up on your recent inquiry. We'd love to help you find the right procurement solution.</p>
        <p style="color:#f1f5f9;">Could we schedule a quick 15-minute call this week?</p>
        <p style="color:#94a3b8;margin-top:24px;font-size:14px;">Best regards,<br/><strong>{rep_name}</strong></p>
      </div>
    </div>
    """
    return send_email(to, subject, html)


def send_password_reset(to: str, reset_token: str, username: str = "") -> dict[str, Any]:
    subject = "Reset Your Password"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f9fafb;padding:32px;">
      <div style="background:#1e293b;border-radius:12px;padding:32px;color:#f1f5f9;">
        <h1 style="color:#ef4444;margin:0 0 8px;">Password Reset 🔐</h1>
        {"<p style='color:#94a3b8;margin:0 0 24px;'>Hi " + username + ",</p>" if username else ""}
        <p style="color:#f1f5f9;">Use the token below to reset your password. It expires in 1 hour.</p>
        <div style="background:#0f172a;border-radius:8px;padding:16px;margin:24px 0;text-align:center;">
          <code style="font-size:20px;font-weight:700;color:#ef4444;letter-spacing:2px;">{reset_token}</code>
        </div>
        <p style="color:#94a3b8;font-size:14px;">If you didn't request this, please ignore this email.</p>
      </div>
    </div>
    """
    return send_email(to, subject, html)


def send_welcome_email(to: str, username: str, role: str = "user") -> dict[str, Any]:
    subject = "Welcome to Procurement Intelligence Platform!"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#f9fafb;padding:32px;">
      <div style="background:#1e293b;border-radius:12px;padding:32px;color:#f1f5f9;">
        <h1 style="color:#3b82f6;margin:0 0 8px;">Welcome! 🎉</h1>
        <p style="color:#94a3b8;margin:0 0 24px;">Hi {username}, your account is ready.</p>
        <div style="background:#0f172a;border-radius:8px;padding:16px;margin-bottom:24px;">
          <p style="margin:0;font-size:14px;color:#94a3b8;">Your Role</p>
          <p style="margin:4px 0 0;font-size:18px;font-weight:700;color:#3b82f6;text-transform:capitalize;">{role}</p>
        </div>
        <p style="color:#f1f5f9;">You can now access the Procurement Intelligence Platform to manage vendors, create RFQs, compare quotes, and track orders.</p>
        <p style="color:#94a3b8;font-size:14px;margin-top:24px;">Happy procuring! 🚀</p>
      </div>
    </div>
    """
    return send_email(to, subject, html)
