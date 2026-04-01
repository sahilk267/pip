from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app import schemas


def test_scraping_compliance_bundle():
    client = TestClient(app)
    r = client.get('/api/v1/compliance/scraping-controls')
    assert r.status_code == 200
    body = r.json()
    assert 'policy' in body and 'checklist' in body
    assert any(x['id'] == 'rate-limit' for x in body['checklist'])


def test_scraping_compliance_bundle_hi_localized():
    client = TestClient(app)
    r = client.get('/api/v1/compliance/scraping-controls', params={'locale': 'hi'})
    assert r.status_code == 200
    body = r.json()
    assert body['checklist']
    assert any('वर्तमान' in row['detail'] or 'कनेक्टर' in row['detail'] for row in body['checklist'])


def test_escalation_playbook():
    client = TestClient(app)
    r = client.get('/api/v1/operations/escalation-playbook')
    assert r.status_code == 200
    steps = r.json()['steps']
    assert len(steps) >= 3
    assert steps[0]['step'] == 1


def test_escalation_playbook_hi_localized():
    client = TestClient(app)
    r = client.get('/api/v1/operations/escalation-playbook', params={'locale': 'hi'})
    assert r.status_code == 200
    steps = r.json()['steps']
    assert steps
    assert any('अलर्ट' in row['title'] or 'कनेक्टर' in row['action'] for row in steps)


def test_i18n_strings_hi():
    client = TestClient(app)
    r = client.get('/api/v1/i18n/strings?locale=hi')
    assert r.status_code == 200
    assert r.json()['locale'] == 'hi'
    assert 'app.title' in r.json()['strings']
    assert 'operations.escalation.1.title' in r.json()['strings']


def test_external_crm_stub_audit():
    client = TestClient(app)
    r = client.post(
        '/api/v1/integrations/external-crm/event',
        params={'locale': 'hi'},
        json={'provider': 'hubspot', 'event_type': 'contact.updated', 'payload': {'id': 1}},
    )
    assert r.status_code == 200
    assert r.json()['status'] == 'accepted'
    assert 'ऑडिट' in r.json()['detail']


def test_crm_dashboard_aggregates():
    client = TestClient(app)
    r = client.get('/api/v1/crm/dashboard')
    assert r.status_code == 200
    b = r.json()
    assert 'totals' in b and 'leads_by_stage' in b
    assert 'vendors' in b['totals']


def test_product_create_normalizes_sku():
    p = schemas.ProductCreate(name='Test Product', sku='  abc-12  ', price='  12.00 ')
    assert p.sku == 'ABC-12'
    assert p.price == '12.00'
