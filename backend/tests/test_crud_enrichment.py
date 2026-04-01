from backend.app import crud, schemas, models
from backend.app.database import SessionLocal
from backend.app.services.enrichment import run_enrichment, enrich_product_attributes


def create_sample_vendor(db, name):
    vendor_in = schemas.VendorCreate(name=name, source='test', vendor_metadata={})
    vendor, created = crud.create_vendor(db, vendor_in)
    return vendor


def test_vendor_deduplication():
    with SessionLocal() as db:
        vendor = schemas.VendorCreate(name='Test Solutions', source='test')
        first, created1 = crud.create_vendor(db, vendor)
        assert created1
        second, created2 = crud.create_vendor(db, vendor)
        assert not created2
        assert first.id == second.id
        assert first.normalized_name == second.normalized_name


def test_product_deduplication_uses_sku():
    with SessionLocal() as db:
        vendor = create_sample_vendor(db, 'Vendor Dedup')
        product_in = schemas.ProductCreate(name='Cooling Module', vendor_id=vendor.id, sku='CM-01')
        first, created1 = crud.create_product(db, product_in)
        assert created1
        second, created2 = crud.create_product(db, product_in)
        assert not created2
        assert first.id == second.id


def test_run_enrichment_applies_stub_data():
    with SessionLocal() as db:
        vendor = create_sample_vendor(db, 'Aurora Supply Partners')
        stats = run_enrichment(db, limit=5)
        assert stats['enriched'] == 1
        refreshed = db.query(models.Vendor).filter(models.Vendor.id == vendor.id).one()
        assert 'revenue_estimate' in refreshed.vendor_metadata



def test_enrich_product_attributes_updates_feed():
    with SessionLocal() as db:
        vendor = create_sample_vendor(db, 'Nova Components')
        product_in = schemas.ProductCreate(name='Nova Thermal Module', vendor_id=vendor.id, sku='NTM-300')
        product, _ = crud.create_product(db, product_in)
        stats = enrich_product_attributes(db, limit=10)
        assert stats['annotated'] >= 1
        refreshed = db.query(models.Product).filter(models.Product.id == product.id).one()
        assert refreshed.attributes.get('category') == 'Thermal Module'
        assert refreshed.category == 'Thermal Module'
        assert refreshed.category_confidence >= 0.6
