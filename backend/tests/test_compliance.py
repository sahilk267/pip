from backend.app import crud
from backend.app.database import SessionLocal
from backend.app.services.compliance import generate_compliance_report


def test_generate_compliance_report_counts():
    with SessionLocal() as db:
        crud.log_audit(db, 'vendor', 1, 'ingest', 'Compliance coverage test', performed_by='tester')
        report = generate_compliance_report(db, window_minutes=60)
        assert report['total_entries'] >= 1
        assert report['entity_counts'].get('vendor', 0) >= 1
        assert report['action_counts'].get('ingest', 0) >= 1
        assert report['recent_entries']
