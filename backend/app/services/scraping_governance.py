"""Operational guardrails for outbound data collection (rate limits, retries, audit hooks).

Production scrapers must still complete regional legal review; this module encodes
technical controls referenced by the compliance API.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

from .i18n_preview import tr

_CONNECTOR_LOCK = threading.Lock()
_LAST_END: dict[str, float] = {}
_FAIL_STREAK: dict[str, int] = {}

DEFAULT_USER_AGENTS = (
    'PIP-Phase1-Collector/1.0 (+https://example.invalid/bot-policy)',
    'PIP-Phase1-Collector/1.0 (compliance@example.invalid)',
)

MIN_INTERVAL_SEC = float(os.getenv('CONNECTOR_MIN_INTERVAL_SEC', '0'))
MAX_RETRIES = int(os.getenv('CONNECTOR_MAX_RETRIES', '3'))
BACKOFF_BASE = float(os.getenv('CONNECTOR_BACKOFF_BASE_SEC', '1.5'))
MAX_DYNAMIC_MULTIPLIER = int(os.getenv('CONNECTOR_DYNAMIC_MAX_MULTIPLIER', '4'))


def _approved_connectors_set() -> set[str]:
    raw = os.getenv('SCRAPING_APPROVED_CONNECTORS', '').strip()
    if not raw:
        return set()
    return {x.strip().lower() for x in raw.split(',') if x.strip()}


def is_connector_approved(connector_name: str) -> bool:
    """If SCRAPING_APPROVED_CONNECTORS is set, only listed connectors are allowed."""
    allowed = _approved_connectors_set()
    if not allowed:
        return True
    return connector_name.strip().lower() in allowed


def connector_policy(locale: str = 'en') -> dict[str, Any]:
    return {
        'min_interval_seconds': MIN_INTERVAL_SEC,
        'max_retries': MAX_RETRIES,
        'backoff_base_seconds': BACKOFF_BASE,
        'dynamic_backoff_multiplier_max': MAX_DYNAMIC_MULTIPLIER,
        'user_agent_pool_size': len(DEFAULT_USER_AGENTS),
        'robots_txt': os.getenv('SCRAPING_ROBOTS_MODE', 'advisory'),
        'approved_connectors': sorted(_approved_connectors_set()),
        'legal_review_required': True,
        'notes': [
            tr(locale, 'compliance.policy.note.1', default='Advisory robots mode: log-only unless SCRAPING_ROBOTS_MODE=enforced (future).'),
            tr(locale, 'compliance.policy.note.2', default='Rotate credentials and respect site ToS before production scraping.'),
        ],
    }


def compliance_checklist(locale: str = 'en') -> list[dict[str, str]]:
    return [
        {
            'id': 'rate-limit',
            'status': 'implemented',
            'detail': tr(
                locale,
                'compliance.check.rate_limit',
                default='Per-connector spacing via CONNECTOR_MIN_INTERVAL_SEC (current {min_interval}).',
                min_interval=MIN_INTERVAL_SEC,
            ),
        },
        {
            'id': 'retry-backoff',
            'status': 'implemented',
            'detail': tr(
                locale,
                'compliance.check.retry_backoff',
                default='CONNECTOR_MAX_RETRIES={max_retries}, exponential base {backoff}s.',
                max_retries=MAX_RETRIES,
                backoff=BACKOFF_BASE,
            ),
        },
        {
            'id': 'audit-trail',
            'status': 'implemented',
            'detail': tr(
                locale,
                'compliance.check.audit_trail',
                default='Connector fetch outcomes can be logged via AuditLog from execution wrapper.',
            ),
        },
        {
            'id': 'captcha-anti-bot',
            'status': 'implemented',
            'detail': tr(
                locale,
                'compliance.check.anti_bot',
                default='Connector failures with anti-bot signals raise critical alerts for manual escalation.',
            ),
        },
        {
            'id': 'regional-legal',
            'status': 'implemented',
            'detail': tr(
                locale,
                'compliance.check.regional_legal',
                default='Optional SCRAPING_APPROVED_CONNECTORS gate blocks non-approved connectors.',
            ),
        },
        {
            'id': 'adaptive-throttling',
            'status': 'implemented',
            'detail': tr(
                locale,
                'compliance.check.adaptive',
                default='Per-connector dynamic delay increases with failure streak and decays on success.',
            ),
        },
    ]


def _effective_interval(connector_name: str) -> float:
    base = max(0.0, MIN_INTERVAL_SEC)
    if base <= 0:
        return 0.0
    streak = _FAIL_STREAK.get(connector_name, 0)
    multiplier = min(MAX_DYNAMIC_MULTIPLIER, 1 + streak)
    return base * multiplier


def wait_for_rate_limit(connector_name: str) -> None:
    with _CONNECTOR_LOCK:
        interval = _effective_interval(connector_name)
        if interval <= 0:
            return
        now = time.monotonic()
        last = _LAST_END.get(connector_name, 0.0)
        wait = interval - (now - last)
        if wait > 0:
            time.sleep(wait)


def mark_connector_idle(connector_name: str) -> None:
    with _CONNECTOR_LOCK:
        _LAST_END[connector_name] = time.monotonic()


def backoff_sleep(attempt: int) -> None:
    delay = BACKOFF_BASE * (2**attempt)
    time.sleep(delay)


def register_fetch_result(connector_name: str, success: bool) -> None:
    with _CONNECTOR_LOCK:
        if success:
            _FAIL_STREAK[connector_name] = max(0, _FAIL_STREAK.get(connector_name, 0) - 1)
        else:
            _FAIL_STREAK[connector_name] = _FAIL_STREAK.get(connector_name, 0) + 1
