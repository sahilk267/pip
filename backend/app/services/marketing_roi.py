from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .. import models

_PROVIDER_RE = re.compile(r'^(?P<provider>[^:]+):(?P<event>[^\s]+)')
_CHANNEL_RE = re.compile(r'channel=(?P<channel>[^\s]+)')
_NUM_RE = re.compile(r'(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>[kmb]?)', re.IGNORECASE)

_PROVIDER_EVENT_COST = {
    'hubspot': 2.6,
    'mailchimp': 1.8,
    'marketo': 3.1,
    'unknown': 2.0,
}


def _parse_revenue_estimate(raw: str | None) -> float:
    if not raw:
        return 0.0
    text = str(raw).strip().lower().replace(',', '')
    m = _NUM_RE.search(text)
    if not m:
        return 0.0
    value = float(m.group('num'))
    unit = (m.group('unit') or '').lower()
    multiplier = {'k': 1_000.0, 'm': 1_000_000.0, 'b': 1_000_000_000.0}.get(unit, 1.0)
    return value * multiplier


def _lead_revenue(lead: models.Lead) -> float:
    explicit = _parse_revenue_estimate(lead.revenue_estimate)
    if explicit > 0:
        return explicit
    # Conservative proxy when revenue enrichment is absent.
    return float(max(0, int(lead.lead_score or 0)) * 150.0)


def compute_campaign_roi(db: Session, window_days: int = 30) -> dict:
    now = datetime.now(timezone.utc)
    window_days = max(1, int(window_days))
    cutoff = now - timedelta(days=window_days)

    logs = (
        db.query(models.AuditLog)
        .filter(
            models.AuditLog.entity_type == 'marketing',
            models.AuditLog.action == 'automation_event',
            models.AuditLog.created_at >= cutoff,
        )
        .all()
    )

    spend_by_provider: dict[str, float] = defaultdict(float)
    events_by_provider: dict[str, int] = defaultdict(int)
    spend_by_channel: dict[str, float] = defaultdict(float)
    events_by_channel: dict[str, int] = defaultdict(int)

    for row in logs:
        detail = row.detail or ''
        pm = _PROVIDER_RE.search(detail)
        provider = (pm.group('provider') if pm else 'unknown').strip().lower() or 'unknown'
        cost = float(_PROVIDER_EVENT_COST.get(provider, _PROVIDER_EVENT_COST['unknown']))
        spend_by_provider[provider] += cost
        events_by_provider[provider] += 1

        cm = _CHANNEL_RE.search(detail)
        channel = (cm.group('channel') if cm else 'unknown').strip().lower() or 'unknown'
        spend_by_channel[channel] += cost
        events_by_channel[channel] += 1

    converted_leads = (
        db.query(models.Lead)
        .filter(models.Lead.stage == 'converted', models.Lead.created_at >= cutoff)
        .all()
    )

    revenue_by_channel: dict[str, float] = defaultdict(float)
    converted_by_channel: dict[str, int] = defaultdict(int)
    for lead in converted_leads:
        channel = str(lead.attribution_channel or 'unknown').strip().lower() or 'unknown'
        revenue_by_channel[channel] += _lead_revenue(lead)
        converted_by_channel[channel] += 1

    channels = sorted(set(spend_by_channel.keys()) | set(revenue_by_channel.keys()))
    channel_roi = []
    for channel in channels:
        spend = round(float(spend_by_channel.get(channel, 0.0)), 2)
        revenue = round(float(revenue_by_channel.get(channel, 0.0)), 2)
        roi = None if spend <= 0 else round((revenue - spend) / spend, 4)
        channel_roi.append(
            {
                'channel': channel,
                'automation_events': int(events_by_channel.get(channel, 0)),
                'converted_leads': int(converted_by_channel.get(channel, 0)),
                'estimated_spend': spend,
                'estimated_revenue': revenue,
                'roi': roi,
            }
        )

    total_spend = round(sum(spend_by_provider.values()), 2)
    total_revenue = round(sum(revenue_by_channel.values()), 2)
    overall_roi = None if total_spend <= 0 else round((total_revenue - total_spend) / total_spend, 4)

    return {
        'generated_at': now,
        'window_days': window_days,
        'total_automation_events': len(logs),
        'total_converted_leads': len(converted_leads),
        'estimated_spend': total_spend,
        'estimated_revenue': total_revenue,
        'overall_roi': overall_roi,
        'spend_by_provider': {k: round(v, 2) for k, v in sorted(spend_by_provider.items())},
        'events_by_provider': dict(sorted(events_by_provider.items())),
        'roi_by_channel': channel_roi,
    }
