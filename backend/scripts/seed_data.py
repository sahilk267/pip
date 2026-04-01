import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app import crud, models, schemas
from backend.app.database import init_db, SessionLocal

VENDORS = [
    {
        'name': 'Luminous Tech Distributors',
        'source': 'manual',
        'contact_email': 'ops@luminous.com',
        'phone': '+1-202-555-0177',
        'industry': 'Electronics',
        'metadata': {'region': 'US', 'intent': 'high'},
    },
    {
        'name': 'Luminous Tech Distributors',
        'source': 'supplier-feed',
        'contact_email': 'sales@luminous.com',
        'metadata': {'region': 'US', 'intent': 'medium'},
    },
]

PRODUCTS = [
    {
        'name': 'Smart Lighting Panel 1200x600',
        'sku': 'LTP-1200',
        'price': '499',
        'attributes': {'color': 'White', 'warranty': '5 years'},
    },
    {
        'name': 'Luminous Smart Lighting Panel 1200x600',
        'sku': 'LTP-1200',
        'price': '499',
        'attributes': {'color': 'White', 'warranty': '5 years'},
    },
]


def seed() -> None:
    init_db()
    with SessionLocal() as db:
        for vendor_payload in VENDORS:
            vendor, created = crud.create_vendor(db, schemas.VendorCreate(**vendor_payload))
            print('Vendor', 'created' if created else 'deduplicated', vendor.name, 'id=', vendor.id)

        first_vendor = db.query(models.Vendor).first()
        if not first_vendor:
            print('No vendor found to attach to sample products.')
            return

        for product_payload in PRODUCTS:
            payload = product_payload.copy()
            payload['vendor_id'] = first_vendor.id
            product, created = crud.create_product(db, schemas.ProductCreate(**payload))
            print('Product', 'created' if created else 'deduplicated', product.name, 'id=', product.id)


if __name__ == '__main__':
    seed()
