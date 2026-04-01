from backend.app.services import scraping_governance as gov


def test_connector_approval_gate_when_env_set(monkeypatch):
    monkeypatch.setenv('SCRAPING_APPROVED_CONNECTORS', 'linkedin,googlemaps')
    assert gov.is_connector_approved('LinkedIn')
    assert not gov.is_connector_approved('IndiaMart')


def test_compliance_checklist_has_adaptive_and_legal_entries():
    items = gov.compliance_checklist()
    ids = {row['id'] for row in items}
    assert 'adaptive-throttling' in ids
    assert 'regional-legal' in ids

