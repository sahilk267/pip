"""Operator escalation steps for data-quality and ingestion incidents (API-backed playbook)."""

from __future__ import annotations

from typing import Any

from .i18n_preview import tr

PLAYBOOK: list[dict[str, Any]] = [
    {
        'step': 1,
        'severity': 'warning',
        'title': 'Acknowledge alert',
        'action': 'Open monitoring dashboard; note connector name, timestamp, and error text.',
    },
    {
        'step': 2,
        'severity': 'warning',
        'title': 'Triage connector',
        'action': 'Re-run `/api/v1/ingestion/discovery` manually after verifying credentials and target availability.',
    },
    {
        'step': 3,
        'severity': 'critical',
        'title': 'Schema drift',
        'action': 'If alert references schema drift, review Alembic migrations vs live DB; deploy migration or revert problematic deploy.',
    },
    {
        'step': 4,
        'severity': 'critical',
        'title': 'Categorization backlog',
        'action': 'For repeated miscategorization, adjust `ai_engines/categorization_rules.json` and use admin override endpoints.',
    },
    {
        'step': 5,
        'severity': 'info',
        'title': 'Close loop',
        'action': 'Resolve `Alert` records once verified; attach compliance note via audit if customer-impacting.',
    },
]


def get_playbook(locale: str = 'en') -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in PLAYBOOK:
        step = int(row.get('step') or 0)
        localized = dict(row)
        localized['title'] = tr(locale, f'operations.escalation.{step}.title', default=str(row.get('title', '')))
        localized['action'] = tr(locale, f'operations.escalation.{step}.action', default=str(row.get('action', '')))
        rows.append(localized)
    return rows
