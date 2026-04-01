from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models

_PROVIDER_RE = re.compile(r'^(?P<provider>[^:]+):(?P<event>[^\s]+)')
_INTENT_RE = re.compile(r'signal=(?P<signal>[^\s]+)\s+source=(?P<source>[^\s]+)')


def _intent_band(score: int) -> str:
    if score >= 60:
        return 'high'
    if score >= 25:
        return 'medium'
    if score > 0:
        return 'low'
    return 'none'


def compute_marketing_analytics(db: Session, window_days: int = 30) -> dict:
    window_days = max(1, int(window_days))
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

    automation_logs = (
        db.query(models.AuditLog)
        .filter(
            models.AuditLog.entity_type == 'marketing',
            models.AuditLog.action == 'automation_event',
            models.AuditLog.created_at >= cutoff,
        )
        .all()
    )
    automation_by_provider: dict[str, int] = defaultdict(int)
    automation_by_type: dict[str, int] = defaultdict(int)
    for row in automation_logs:
        detail = row.detail or ''
        m = _PROVIDER_RE.search(detail)
        provider = (m.group('provider') if m else 'unknown').strip().lower() or 'unknown'
        event_type = (m.group('event') if m else 'unknown').strip().lower() or 'unknown'
        automation_by_provider[provider] += 1
        automation_by_type[event_type] += 1

    intent_logs = (
        db.query(models.AuditLog)
        .filter(
            models.AuditLog.action == 'marketing_intent',
            models.AuditLog.created_at >= cutoff,
        )
        .all()
    )
    intent_signals_by_type: dict[str, int] = defaultdict(int)
    intent_sources: dict[str, int] = defaultdict(int)
    for row in intent_logs:
        detail = row.detail or ''
        m = _INTENT_RE.search(detail)
        signal = (m.group('signal') if m else 'unknown').strip().lower() or 'unknown'
        source = (m.group('source') if m else 'unknown').strip().lower() or 'unknown'
        intent_signals_by_type[signal] += 1
        intent_sources[source] += 1

    lead_attribution_rows = (
        db.query(models.Lead.attribution_channel, func.count(models.Lead.id))
        .group_by(models.Lead.attribution_channel)
        .all()
    )
    lead_attribution = {
        str(channel or 'unknown'): int(count)
        for channel, count in lead_attribution_rows
    }

    leads = db.query(models.Lead).all()
    bands: dict[str, int] = defaultdict(int)
    channel_stats: dict[str, dict[str, int]] = defaultdict(lambda: {'leads': 0, 'converted': 0})
    for lead in leads:
        score = int(lead.marketing_intent_score or 0)
        bands[_intent_band(score)] += 1
        channel = str(lead.attribution_channel or 'unknown')
        channel_stats[channel]['leads'] += 1
        if str(lead.stage or '').lower() == 'converted':
            channel_stats[channel]['converted'] += 1

    conversion_by_channel = []
    for channel in sorted(channel_stats.keys()):
        leads_count = channel_stats[channel]['leads']
        converted = channel_stats[channel]['converted']
        rate = 0.0 if leads_count <= 0 else round(converted / leads_count, 4)
        conversion_by_channel.append(
            {
                'channel': channel,
                'leads': leads_count,
                'converted': converted,
                'conversion_rate': rate,
            }
        )

    return {
        'generated_at': datetime.now(timezone.utc),
        'window_days': window_days,
        'total_automation_events': len(automation_logs),
        'automation_events_by_provider': dict(automation_by_provider),
        'automation_events_by_type': dict(automation_by_type),
        'intent_signals_by_type': dict(intent_signals_by_type),
        'intent_sources': dict(intent_sources),
        'lead_attribution': lead_attribution,
        'intent_score_bands': dict(bands),
        'conversion_by_channel': conversion_by_channel,
    }
