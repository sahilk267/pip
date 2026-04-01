from backend.app import models
from backend.app.database import SessionLocal
from backend.app.services import alerting
from backend.app.services.monitoring import check_connectors, watch_schema_changes


def test_check_connectors_creates_data_source_entries():
    with SessionLocal() as db:
        statuses = check_connectors(db)
        assert statuses
        data_sources = db.query(models.DataSource).all()
        assert len(data_sources) >= len(statuses)


def test_watch_schema_changes_reports_nothing_for_stable_schema():
    with SessionLocal() as db:
        warnings = watch_schema_changes(db)
        assert warnings == []


def test_alerting_can_create_and_persist():
    with SessionLocal() as db:
        alert = alerting.create_alert(db, title='test', detail='detail', severity='info')
        assert alert.id
        assert alert.category == 'monitoring'
