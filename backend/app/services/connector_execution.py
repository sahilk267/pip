from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from ..connectors.base import DiscoveryConnector, DiscoveryPayload
from . import scraping_governance as gov
from .alerting import create_alert

AuditFn = Callable[..., Any]


def fetch_with_resilience(
    connector: DiscoveryConnector,
    *,
    db: Session | None = None,
    log_audit: AuditFn | None = None,
    audit_success: bool = True,
) -> DiscoveryPayload:
    """Run connector.fetch with spacing, retries, and optional audit entries."""
    from .. import crud as _crud

    logger: AuditFn = log_audit or _crud.log_audit
    if not gov.is_connector_approved(connector.name):
        detail = (
            f'{connector.name} blocked by SCRAPING_APPROVED_CONNECTORS policy. '
            'Add the connector to approved list after legal review.'
        )
        if db is not None:
            create_alert(
                db,
                title=f'Connector blocked: {connector.name}',
                detail=detail,
                severity='critical',
                category='compliance',
                entity_type='connector',
            )
            logger(db, 'connector', None, 'policy_block', detail)
        raise RuntimeError(detail)

    gov.wait_for_rate_limit(connector.name)
    last_exc: Exception | None = None
    for attempt in range(gov.MAX_RETRIES + 1):
        try:
            payload = connector.fetch()
            gov.register_fetch_result(connector.name, success=True)
            gov.mark_connector_idle(connector.name)
            if db is not None and audit_success:
                logger(
                    db,
                    'connector',
                    None,
                    'fetch',
                    f'{connector.name} ok (attempt {attempt + 1})',
                )
            return payload
        except Exception as exc:
            last_exc = exc
            gov.register_fetch_result(connector.name, success=False)
            if db is not None:
                logger(
                    db,
                    'connector',
                    None,
                    'fetch_retry',
                    f'{connector.name} attempt {attempt + 1} failed: {exc}',
                )
                msg = str(exc).lower()
                if any(token in msg for token in ('captcha', 'forbidden', 'blocked', '429', 'too many requests')):
                    create_alert(
                        db,
                        title=f'Anti-bot signal: {connector.name}',
                        detail=f'Connector reported anti-bot/ratelimit signal: {exc}',
                        severity='critical',
                        category='compliance',
                        entity_type='connector',
                    )
            if attempt >= gov.MAX_RETRIES:
                break
            gov.backoff_sleep(attempt)
    gov.mark_connector_idle(connector.name)
    assert last_exc is not None
    raise last_exc
