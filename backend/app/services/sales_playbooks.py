from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .. import models


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _last_communication(db: Session, lead_id: int) -> models.CRMCommunication | None:
    return (
        db.query(models.CRMCommunication)
        .filter(models.CRMCommunication.lead_id == lead_id)
        .order_by(models.CRMCommunication.created_at.desc())
        .first()
    )


def _priority_for_lead(lead: models.Lead, communication: models.CRMCommunication | None) -> str:
    now = datetime.now(timezone.utc)
    if lead.unsubscribed_at is not None:
        return 'blocked'
    follow_up_at = _as_utc(communication.follow_up_at) if communication else None
    if communication and follow_up_at and communication.reminder_sent_at is None and follow_up_at <= now:
        return 'urgent'
    if (lead.lead_score or 0) >= 35:
        return 'high'
    if (lead.lead_score or 0) >= 18:
        return 'medium'
    return 'low'


def _recommended_channel(lead: models.Lead, communication: models.CRMCommunication | None) -> str:
    if lead.unsubscribed_at is not None:
        return 'none'
    if communication and communication.channel:
        return communication.channel
    if lead.phone:
        return 'phone'
    return 'email'


def build_sales_playbook(db: Session, lead: models.Lead) -> dict:
    communication = _last_communication(db, lead.id)
    priority = _priority_for_lead(lead, communication)
    channel = _recommended_channel(lead, communication)
    steps: list[dict[str, str | int]] = []

    if lead.unsubscribed_at is not None:
        steps.append(
            {
                'step': 1,
                'title': 'Respect unsubscribe',
                'action': 'Do not send sales outreach. Limit actions to compliance-safe account maintenance.',
                'reason': 'Lead has unsubscribed and should not receive further direct outreach.',
            }
        )
        return {
            'lead_id': lead.id,
            'full_name': lead.full_name,
            'stage': lead.stage,
            'lead_score': int(lead.lead_score or 0),
            'priority': priority,
            'recommended_channel': channel,
            'summary': 'Outreach blocked by unsubscribe status.',
            'steps': steps,
        }

    if lead.stage == 'lead':
        steps.append(
            {
                'step': 1,
                'title': 'Send introduction',
                'action': f'Send a first-touch intro via {channel} with a concise value proposition and qualification question.',
                'reason': 'Lead is new and needs initial contact to begin qualification.',
            }
        )
        steps.append(
            {
                'step': 2,
                'title': 'Qualify source and need',
                'action': 'Confirm budget, timeline, and product interest. Update lead stage to qualified if signals are positive.',
                'reason': 'Qualification is the next funnel gate after initial outreach.',
            }
        )
    elif lead.stage == 'qualified':
        steps.append(
            {
                'step': 1,
                'title': 'Book discovery call',
                'action': 'Schedule a discovery call or demo and capture primary business need and buying role.',
                'reason': 'Qualified leads should move to a direct conversation to prevent stall-out.',
            }
        )
        steps.append(
            {
                'step': 2,
                'title': 'Tailor proposal path',
                'action': 'Prepare product/vendor shortlist and define the proof points needed to move into engaged stage.',
                'reason': 'The lead has enough intent to justify personalized follow-up.',
            }
        )
    elif lead.stage == 'engaged':
        steps.append(
            {
                'step': 1,
                'title': 'Advance active deal',
                'action': 'Send proposal recap, address open objections, and confirm next decision milestone.',
                'reason': 'Engaged leads need momentum and explicit next steps to avoid drop-off.',
            }
        )
        steps.append(
            {
                'step': 2,
                'title': 'Use communication history',
                'action': 'Review recent CRM communications and follow up on unanswered items before escalating pricing or commercial detail.',
                'reason': 'Communication context reduces duplicate outreach and improves close probability.',
            }
        )
    elif lead.stage == 'converted':
        steps.append(
            {
                'step': 1,
                'title': 'Handoff to account management',
                'action': 'Record win notes, transfer context to customer success/account owner, and open onboarding workflow.',
                'reason': 'Converted leads should transition from pursuit to retention/expansion motions.',
            }
        )
    else:
        steps.append(
            {
                'step': 1,
                'title': 'Review re-engagement eligibility',
                'action': 'If consent still allows outreach, move the lead into a nurture path with a lighter-touch sequence.',
                'reason': 'Non-active leads may still be recoverable through targeted re-engagement.',
            }
        )

    follow_up_at = _as_utc(communication.follow_up_at) if communication else None
    if communication and follow_up_at:
        overdue = follow_up_at <= datetime.now(timezone.utc)
        steps.append(
            {
                'step': len(steps) + 1,
                'title': 'Follow-up checkpoint',
                'action': 'Review the latest scheduled follow-up and act on it immediately.' if overdue else 'Keep the next scheduled follow-up on calendar and update after contact.',
                'reason': 'A CRM follow-up already exists for this lead.',
            }
        )

    summary = f"{lead.stage.title()} lead with score {int(lead.lead_score or 0)}; prioritize via {channel}."
    return {
        'lead_id': lead.id,
        'full_name': lead.full_name,
        'stage': lead.stage,
        'lead_score': int(lead.lead_score or 0),
        'priority': priority,
        'recommended_channel': channel,
        'summary': summary,
        'steps': steps,
    }


def build_sales_playbook_queue(db: Session, limit: int = 20) -> dict:
    leads = db.query(models.Lead).order_by(models.Lead.lead_score.desc(), models.Lead.id.asc()).limit(limit).all()
    playbooks = [build_sales_playbook(db, lead) for lead in leads]
    rank = {'urgent': 0, 'high': 1, 'medium': 2, 'low': 3, 'blocked': 4}
    playbooks.sort(key=lambda row: (rank.get(str(row['priority']), 9), -(row['lead_score'] or 0), row['lead_id']))
    return {
        'generated_at': datetime.now(timezone.utc),
        'leads': playbooks,
    }
