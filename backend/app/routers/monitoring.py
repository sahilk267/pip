from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..services.monitoring import watch_schema_changes

router = APIRouter()


@router.get('/api/v1/monitoring/dashboard', response_model=schemas.MonitoringDashboard)
def monitoring_dashboard(db: Session = Depends(get_db)) -> schemas.MonitoringDashboard:
    sources = (
        db.query(models.DataSource)
        .order_by(models.DataSource.last_synced.desc().nullslast())
        .all()
    )
    alerts = (
        db.query(models.Alert)
        .order_by(models.Alert.created_at.desc())
        .limit(20)
        .all()
    )
    audit_entries = (
        db.query(models.AuditLog)
        .order_by(models.AuditLog.created_at.desc())
        .limit(20)
        .all()
    )
    schema_warnings = watch_schema_changes(db)

    return schemas.MonitoringDashboard(
        data_sources=[
            schemas.DataSourceStatus(
                name=source.name,
                last_synced=source.last_synced,
            )
            for source in sources
        ],
        alerts=[schemas.AlertResponse.model_validate(alert) for alert in alerts],
        audit_log=[schemas.ComplianceLogEntry.model_validate(entry) for entry in audit_entries],
        schema_warnings=schema_warnings,
    )
