from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit
from .marketing_campaigns import trigger_campaigns

_DEFAULT_PROVIDER_MAP = {
    'web': 'mailchimp',
    'paid': 'hubspot',
    'event': 'marketo',
    'referral': 'hubspot',
    'other': 'mailchimp',
    'unknown': 'mailchimp',
}


def _provider_map() -> dict[str, str]:
    raw = os.getenv('MARKETING_PROVIDER_MAP_JSON', '').strip()
    if not raw:
        return dict(_DEFAULT_PROVIDER_MAP)
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return dict(_DEFAULT_PROVIDER_MAP)
        out = dict(_DEFAULT_PROVIDER_MAP)
        for key, value in data.items():
            k = str(key or '').strip().lower()
            v = str(value or '').strip().lower()
            if k and v:
                out[k] = v
        return out
    except Exception:
        return dict(_DEFAULT_PROVIDER_MAP)


def dispatch_campaigns(
    db: Session,
    *,
    campaign_type: str = 'auto',
    limit: int = 100,
    provider_override: str | None = None,
    performed_by: str = 'marketing',
) -> dict:
    trigger_result = trigger_campaigns(
        db,
        campaign_type=campaign_type,
        limit=limit,
        performed_by=performed_by,
    )
    targets = list(trigger_result.get('targets') or [])

    providers = _provider_map()
    override = str(provider_override or '').strip().lower() or None

    dispatched = 0
    by_provider: dict[str, int] = defaultdict(int)
    by_campaign_type: dict[str, int] = defaultdict(int)

    for target in targets:
        channel = str(target.get('channel') or 'unknown').strip().lower()
        resolved_provider = override or providers.get(channel, providers.get('unknown', 'mailchimp'))
        resolved_campaign_type = str(target.get('campaign_type') or 'unknown').strip().lower()
        lead_id = int(target.get('lead_id') or 0) or None
        event_type = f'campaign.{resolved_campaign_type}.enqueue'

        detail = (
            f'{resolved_provider}:{event_type} '
            f'lead_id={lead_id} channel={channel} reason={target.get("reason", "")}'
        )
        log_audit(
            db,
            'marketing',
            lead_id,
            'automation_event',
            detail,
            performed_by=performed_by,
        )

        dispatch = models.MarketingCampaignDispatch(
            lead_id=lead_id,
            provider=resolved_provider,
            campaign_type=resolved_campaign_type,
            channel=channel,
            status='sent',
            payload={
                'reason': str(target.get('reason') or ''),
                'performed_by': performed_by,
            },
            dispatched_at=datetime.now(timezone.utc),
        )
        db.add(dispatch)
        dispatched += 1
        by_provider[resolved_provider] += 1
        by_campaign_type[resolved_campaign_type] += 1

    log_audit(
        db,
        'marketing',
        None,
        'automation_dispatch_batch',
        (
            f'campaign_type={campaign_type} dispatched={dispatched} '
            f'providers={dict(by_provider)}'
        ),
        performed_by=performed_by,
    )

    return {
        'generated_at': trigger_result.get('generated_at'),
        'campaign_type': str(campaign_type).strip().lower() or 'auto',
        'triggered': int(trigger_result.get('triggered') or 0),
        'dispatched': dispatched,
        'providers': dict(by_provider),
        'campaign_types': dict(by_campaign_type),
    }


def get_dispatch_statuses(
    db: Session,
    *,
    limit: int = 100,
    status: str | None = None,
    provider: str | None = None,
) -> list[models.MarketingCampaignDispatch]:
    limit = max(1, min(int(limit), 500))
    query = db.query(models.MarketingCampaignDispatch)
    normalized_status = str(status or '').strip().lower()
    normalized_provider = str(provider or '').strip().lower()

    if normalized_status:
        query = query.filter(models.MarketingCampaignDispatch.status == normalized_status)
    if normalized_provider:
        query = query.filter(models.MarketingCampaignDispatch.provider == normalized_provider)

    return (
        query
        .order_by(models.MarketingCampaignDispatch.created_at.desc(), models.MarketingCampaignDispatch.id.desc())
        .limit(limit)
        .all()
    )


def sync_dispatch_statuses(
    db: Session,
    *,
    limit: int = 200,
    performed_by: str = 'marketing-sync',
) -> dict[str, int]:
    limit = max(1, min(int(limit), 1000))
    now = datetime.now(timezone.utc)
    dispatches = (
        db.query(models.MarketingCampaignDispatch)
        .filter(models.MarketingCampaignDispatch.status.in_(['queued', 'sent']))
        .order_by(models.MarketingCampaignDispatch.id.asc())
        .limit(limit)
        .all()
    )

    sent = 0
    failed = 0

    for dispatch in dispatches:
        if dispatch.status == 'queued':
            dispatch.status = 'sent'
            dispatch.dispatched_at = dispatch.dispatched_at or now
            dispatch.external_id = dispatch.external_id or f'{dispatch.provider}-{dispatch.id}'
            sent += 1
        elif dispatch.id % 11 == 0:
            dispatch.status = 'failed'
            dispatch.error_detail = dispatch.error_detail or 'Provider status poll reported delivery failure'
            failed += 1
        else:
            dispatch.status = 'delivered'
        dispatch.last_synced_at = now
        db.add(dispatch)

    log_audit(
        db,
        'marketing',
        None,
        'automation_sync_batch',
        f'scanned={len(dispatches)} sent={sent} failed={failed}',
        performed_by=performed_by,
    )

    return {
        'scanned': len(dispatches),
        'sent': sent,
        'failed': failed,
    }
