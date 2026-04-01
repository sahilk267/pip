from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app import models
from backend.app.database import SessionLocal
from backend.app.services.categorization import categorize_pending_vendors_and_products


def test_rule_engine_categories_software_vendor():
    with SessionLocal() as db:
        v = models.Vendor(
            name='Acme Cloud Software Ltd',
            normalized_name='acme_cloud_software_ltd',
            industry='software',
            source='test',
        )
        db.add(v)
        db.commit()
        stats = categorize_pending_vendors_and_products(db, limit=10)
        db.refresh(v)
    assert stats['vendors_updated'] >= 1
    assert v.category == 'technology'
    assert v.categorization_source == 'rule-engine'


def test_admin_vendor_category_override():
    client = TestClient(app)
    r = client.post(
        '/api/v1/vendors',
        json={
            'name': 'Manual Override Co',
            'source': 'test',
        },
    )
    assert r.status_code == 200, r.text
    vid = r.json()['id']
    r2 = client.patch(
        f'/api/v1/admin/vendors/{vid}/category',
        json={'category': 'custom_vertical', 'notes': 'approved', 'performed_by': 'qa'},
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body['category'] == 'custom_vertical'
    assert body['categorization_source'] == 'admin'
    assert body['category_confidence'] == 1.0
