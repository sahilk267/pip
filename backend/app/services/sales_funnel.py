from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models

_LOSS_STAGES = {'lost', 'disqualified', 'dropped'}


def compute_sales_funnel_metrics(db: Session, window_days: int = 30) -> dict:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(1, window_days))

    total_leads = db.query(models.Lead).count()
    stage_counts_rows = (
        db.query(models.Lead.stage, func.count(models.Lead.id))
        .group_by(models.Lead.stage)
        .all()
    )
    stage_counts = {str(stage or 'unknown'): int(count) for stage, count in stage_counts_rows}

    transitions = (
        db.query(models.LeadStageTransition)
        .filter(models.LeadStageTransition.changed_at >= cutoff)
        .order_by(models.LeadStageTransition.lead_id.asc(), models.LeadStageTransition.changed_at.asc())
        .all()
    )

    base_counts: dict[str, int] = defaultdict(int)
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    for row in transitions:
        if row.from_stage:
            base_counts[row.from_stage] += 1
            pair_counts[(row.from_stage, row.to_stage)] += 1

    conversion_rates = []
    for (from_stage, to_stage), transitions_count in sorted(pair_counts.items()):
        base = max(1, base_counts.get(from_stage, 0))
        conversion_rates.append(
            {
                'from_stage': from_stage,
                'to_stage': to_stage,
                'transitions': transitions_count,
                'base': base,
                'conversion_rate': round(transitions_count / base, 4),
            }
        )

    durations: dict[str, list[float]] = defaultdict(list)
    per_lead: dict[int, list[models.LeadStageTransition]] = defaultdict(list)
    for row in transitions:
        per_lead[row.lead_id].append(row)

    for rows in per_lead.values():
        for idx, current in enumerate(rows[:-1]):
            nxt = rows[idx + 1]
            delta_hours = (nxt.changed_at - current.changed_at).total_seconds() / 3600.0
            if delta_hours >= 0:
                durations[current.to_stage].append(delta_hours)

    median_time_in_stage_hours = {
        stage: round(float(median(values)), 2)
        for stage, values in durations.items()
        if values
    }

    drop_off_reasons: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in transitions:
        if row.to_stage in _LOSS_STAGES:
            reason = (row.reason or 'unspecified').strip() or 'unspecified'
            drop_off_reasons[row.to_stage][reason] += 1

    normalized_drop_off = {
        stage: dict(reasons)
        for stage, reasons in drop_off_reasons.items()
    }

    return {
        'generated_at': now,
        'window_days': max(1, window_days),
        'total_leads': total_leads,
        'stage_counts': stage_counts,
        'conversion_rates': conversion_rates,
        'median_time_in_stage_hours': median_time_in_stage_hours,
        'drop_off_reasons': normalized_drop_off,
    }
