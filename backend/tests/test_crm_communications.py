from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app import models
from backend.app.database import SessionLocal
from backend.app.services.crm_communications import send_due_follow_up_reminders


def test_create_and_list_crm_communication_for_lead():
    client = TestClient(app)

    lead_resp = client.post(
        '/api/v1/leads',
        json={'full_name': 'Comms Lead', 'source': 'web'},
    )
    assert lead_resp.status_code == 200, lead_resp.text
    lead_id = lead_resp.json()['id']

    follow_up_at = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    comm_resp = client.post(
        '/api/v1/crm/communications',
        json={
            'lead_id': lead_id,
            'channel': 'email',
            'direction': 'outbound',
            'subject': 'Intro',
            'message': 'Thanks for connecting',
            'follow_up_at': follow_up_at,
            'performed_by': 'qa',
        },
    )
    assert comm_resp.status_code == 200, comm_resp.text
    body = comm_resp.json()
    assert body['lead_id'] == lead_id
    assert body['channel'] == 'email'

    list_resp = client.get(f'/api/v1/crm/communications?lead_id={lead_id}')
    assert list_resp.status_code == 200, list_resp.text
    rows = list_resp.json()
    assert len(rows) == 1
    assert rows[0]['message'] == 'Thanks for connecting'


def test_due_follow_up_reminder_marks_row_and_writes_audit():
    with SessionLocal() as db:
        lead = models.Lead(full_name='Reminder Lead', stage='lead')
        db.add(lead)
        db.commit()
        db.refresh(lead)

        comm = models.CRMCommunication(
            lead_id=lead.id,
            channel='email',
            direction='outbound',
            message='Follow up next day',
            status='logged',
            follow_up_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            performed_by='tester',
        )
        db.add(comm)
        db.commit()
        db.refresh(comm)

        stats = send_due_follow_up_reminders(db, limit=20)
        assert stats['reminders_sent'] == 1

        refreshed = db.query(models.CRMCommunication).filter(models.CRMCommunication.id == comm.id).one()
        assert refreshed.reminder_sent_at is not None
        assert refreshed.status == 'follow_up_due'

        audit = (
            db.query(models.AuditLog)
            .filter(models.AuditLog.action == 'follow_up_reminder', models.AuditLog.entity_id == lead.id)
            .all()
        )
        assert audit
