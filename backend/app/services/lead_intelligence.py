from __future__ import annotations

from sqlalchemy.orm import Session

from .. import models
from .enrichment_sources import fetch_vendor_enrichment


def normalize_attribution_channel(source: str | None) -> str:
    if not source:
        return 'unknown'
    s = source.lower()
    if any(x in s for x in ('web', 'site', 'organic')):
        return 'web'
    if any(x in s for x in ('ad', 'ppc', 'paid')):
        return 'paid'
    if any(x in s for x in ('event', 'conference', 'trade')):
        return 'event'
    if 'referral' in s:
        return 'referral'
    return 'other'


def _segment_for_lead(lead: models.Lead) -> str:
    company = (lead.company or '').strip()
    if len(company) >= 24:
        return 'enterprise'
    if len(company) >= 8:
        return 'mid_market'
    return 'smb'


def apply_metrics_to_lead(lead: models.Lead) -> None:
    lead.attribution_channel = normalize_attribution_channel(lead.source)
    lead.segment = _segment_for_lead(lead)
    lead.lead_score = _score_lead(lead)


def _score_lead(lead: models.Lead) -> int:
    score = 0
    stage_weights = {'lead': 5, 'qualified': 15, 'engaged': 25, 'converted': 40}
    score += stage_weights.get((lead.stage or 'lead').lower(), 5)
    if (lead.consented or '').lower() in ('yes', 'true', 'opt_in'):
        score += 10
    if (lead.marketing_consent or '').lower() in ('yes', 'true'):
        score += 8
    score += min(20, int(lead.marketing_intent_score or 0) // 4)
    # B2B enrichment boosts prioritization (Phase 1: CSV-backed intelligence)
    if lead.revenue_estimate:
        score += 12
    if lead.decision_maker:
        score += 6
    if lead.b2b_score:
        letter = str(lead.b2b_score).strip().upper()[:1]
        score += {'A': 10, 'B': 7, 'C': 4, 'D': 1}.get(letter, 0)
    if lead.email:
        score += 3
    if lead.phone:
        score += 2
    if lead.unsubscribed_at is not None:
        score = max(0, score - 30)
    return min(100, score)


def apply_lead_segmentation(db: Session, limit: int = 200) -> dict[str, int]:
    """Derive segment, attribution, score, and default marketing flags for leads."""
    updated = 0
    leads = db.query(models.Lead).order_by(models.Lead.id.asc()).limit(limit).all()

    for lead in leads:
        before = (lead.segment, lead.attribution_channel, lead.lead_score)
        apply_metrics_to_lead(lead)
        after = (lead.segment, lead.attribution_channel, lead.lead_score)
        if before != after:
            updated += 1
        db.add(lead)
    db.commit()
    return {'leads_scored': updated}


def enrich_b2b_leads(db: Session, limit: int = 200) -> dict[str, int]:
    """Populate revenue_estimate / decision_maker / b2b_score from B2B enrichment sources."""
    leads = db.query(models.Lead).order_by(models.Lead.id.asc()).limit(limit).all()
    enriched = 0
    scanned = 0
    for lead in leads:
        if lead.revenue_estimate and lead.decision_maker:
            continue
        scanned += 1
        target_name = lead.company or lead.full_name or ''
        payload = fetch_vendor_enrichment(target_name)
        if not payload:
            continue
        lead.revenue_estimate = payload.get('revenue_estimate')
        lead.decision_maker = payload.get('decision_maker')
        lead.b2b_score = payload.get('score')
        # Recompute score after enrichment.
        apply_metrics_to_lead(lead)
        db.add(lead)
        enriched += 1

    db.commit()
    return {'leads_enriched': enriched, 'scanned': scanned}
