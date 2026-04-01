from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit

_ALLOWED_CONSENT = {'yes', 'true', 'opt_in'}
_REENGAGEMENT_STAGES = {'lost', 'disqualified', 'dropped'}
_UPSELL_MIN_SCORE = 35
_CROSS_SELL_MIN_SCORE = 20


def _is_marketing_allowed(lead: models.Lead) -> bool:
    if lead.unsubscribed_at is not None:
        return False
    return str(lead.marketing_consent or '').strip().lower() in _ALLOWED_CONSENT


def trigger_campaigns(
    db: Session,
    *,
    campaign_type: str = 'auto',
    limit: int = 100,
    performed_by: str = 'marketing',
) -> dict:
    now = datetime.now(timezone.utc)
    limit = max(1, min(int(limit), 500))
    normalized_type = str(campaign_type or 'auto').strip().lower()
    if normalized_type not in {'auto', 'nurture', 'reengagement', 'upsell', 'cross_sell', 'upsell_cross_sell'}:
        raise ValueError('campaign_type must be one of auto|nurture|reengagement|upsell|cross_sell|upsell_cross_sell')

    stale_cutoff = now - timedelta(days=21)
    leads = db.query(models.Lead).order_by(models.Lead.created_at.asc(), models.Lead.id.asc()).all()

    targets: list[dict] = []
    targeted_ids: set[int] = set()

    for lead in leads:
        if len(targets) >= limit:
            break
        if lead.id in targeted_ids or not _is_marketing_allowed(lead):
            continue

        stage = str(lead.stage or '').strip().lower()
        intent_score = int(lead.marketing_intent_score or 0)
        last_intent_at = lead.last_intent_at
        if last_intent_at is not None and last_intent_at.tzinfo is None:
            last_intent_at = last_intent_at.replace(tzinfo=timezone.utc)

        nurture_candidate = (
            stage in {'lead', 'qualified'}
            and intent_score >= 5
            and intent_score < 60
        )
        stale_or_no_intent = last_intent_at is None or last_intent_at <= stale_cutoff
        reengagement_candidate = stage in _REENGAGEMENT_STAGES or (
            stage in {'lead', 'qualified', 'engaged'} and stale_or_no_intent
        )
        upsell_candidate = stage == 'converted' and int(lead.lead_score or 0) >= _UPSELL_MIN_SCORE
        cross_sell_candidate = stage in {'converted', 'engaged'} and int(lead.marketing_intent_score or 0) >= _CROSS_SELL_MIN_SCORE

        if normalized_type == 'nurture' and not nurture_candidate:
            continue
        if normalized_type == 'reengagement' and not reengagement_candidate:
            continue
        if normalized_type == 'upsell' and not upsell_candidate:
            continue
        if normalized_type == 'cross_sell' and not cross_sell_candidate:
            continue
        if normalized_type == 'upsell_cross_sell' and not (upsell_candidate or cross_sell_candidate):
            continue
        if normalized_type == 'auto' and not (nurture_candidate or reengagement_candidate):
            continue

        if normalized_type == 'upsell':
            resolved_type = 'upsell'
        elif normalized_type == 'cross_sell':
            resolved_type = 'cross_sell'
        elif normalized_type == 'upsell_cross_sell':
            resolved_type = 'upsell' if upsell_candidate else 'cross_sell'
        elif normalized_type == 'reengagement':
            resolved_type = 'reengagement'
        else:
            resolved_type = 'nurture' if nurture_candidate else 'reengagement'

        if resolved_type == 'nurture':
            reason = f'stage={stage or "unknown"} score={intent_score}'
        elif resolved_type == 'reengagement':
            reason = f'stage={stage or "unknown"} stale_intent={stale_or_no_intent}'
        elif resolved_type == 'upsell':
            reason = f'stage={stage or "unknown"} lead_score={int(lead.lead_score or 0)}'
        else:
            reason = f'stage={stage or "unknown"} intent_score={int(lead.marketing_intent_score or 0)}'
        channel = str(lead.attribution_channel or 'unknown')

        targets.append(
            {
                'lead_id': lead.id,
                'campaign_type': resolved_type,
                'reason': reason,
                'channel': channel,
            }
        )
        targeted_ids.add(lead.id)

        action_map = {
            'nurture': 'nurture_campaign_trigger',
            'reengagement': 'reengagement_campaign_trigger',
            'upsell': 'upsell_campaign_trigger',
            'cross_sell': 'cross_sell_campaign_trigger',
        }
        action = action_map[resolved_type]
        log_audit(
            db,
            'lead',
            lead.id,
            action,
            f'Triggered {resolved_type} campaign ({reason}) channel={channel}',
            performed_by=performed_by,
        )

    log_audit(
        db,
        'marketing',
        None,
        'campaign_trigger_batch',
        (
            f'campaign_type={normalized_type} triggered={len(targets)} '
            f'limit={limit}'
        ),
        performed_by=performed_by,
    )

    return {
        'generated_at': now,
        'campaign_type': normalized_type,
        'triggered': len(targets),
        'total_candidates': len(leads),
        'targets': targets,
    }
