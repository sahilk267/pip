from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from ..connectors import connectors
from .. import models
from .alerting import create_alert
from .connector_execution import fetch_with_resilience


def _expected_columns() -> Dict[str, set[str]]:
    return {
        table.__tablename__: {col.name for col in table.__table__.columns}
        for table in (models.Vendor, models.Product, models.Alert)
    }


def check_connectors(db: Session) -> Dict[str, Dict[str, str | int]]:
    statuses: Dict[str, Dict[str, str | int]] = {}
    for connector in connectors:
        try:
            payload = fetch_with_resilience(connector, db=db, audit_success=False)
        except Exception as exc:
            detail = f"{connector.name} failed to fetch payload: {exc}"
            create_alert(
                db,
                title=f"Connector failure: {connector.name}",
                detail=detail,
                severity="critical",
                category="ingestion",
            )
            statuses[connector.name] = {"items": 0, "error": str(exc)}
            continue

        count = len(payload.vendors) + len(payload.products)
        statuses[connector.name] = {"items": count}

        source = (
            db.query(models.DataSource)
            .filter(models.DataSource.name == connector.name)
            .first()
        )
        if not source:
            source = models.DataSource(name=connector.name)
        source.last_synced = datetime.now(timezone.utc)
        db.add(source)

        if count == 0:
            detail = f"{connector.name} returned no items during discovery run."
            create_alert(
                db,
                title=f"Connector alert: {connector.name}",
                detail=detail,
                severity="warning",
                category="ingestion",
                entity_type="connector",
            )
        else:
            log_entry = models.AuditLog(
                entity_type="connector",
                entity_id=None,
                action="discovery",
                detail=f"{connector.name} returned {count} items",
            )
            db.add(log_entry)

    db.commit()
    return statuses


def watch_schema_changes(db: Session) -> List[str]:
    expected = _expected_columns()
    inspector = inspect(db.bind)
    warnings: List[str] = []
    for table_name, columns in expected.items():
        actual = {col["name"] for col in inspector.get_columns(table_name)}
        missing = columns - actual
        extra = actual - columns
        if missing or extra:
            detail = (
                f"{table_name} schema drift (missing={sorted(missing)}, extra={sorted(extra)})"
            )
            create_alert(
                db,
                title=f"Schema drift detected: {table_name}",
                detail=detail,
                severity="warning",
                category="schema",
                entity_type="table",
            )
            warnings.append(detail)
    return warnings
