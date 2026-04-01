from backend.app.services.discovery import connectors
from backend.app.services.enrichment_sources import fetch_product_attributes, fetch_vendor_enrichment


def test_connectors_yield_payloads():
    for connector in connectors:
        payload = connector.fetch()
        assert payload.vendors or payload.products


def test_b2b_enrichment_csv():
    enrichment = fetch_vendor_enrichment('Aurora Supply Partners')
    assert enrichment.get('revenue_estimate') == '$12M'
    assert enrichment.get('decision_maker') == 'Ravi Patel'


def test_b2c_attribute_feed_csv():
    attrs = fetch_product_attributes('NTM-300')
    assert attrs.get('category') == 'Thermal Module'
    assert 'efficiency' in attrs
