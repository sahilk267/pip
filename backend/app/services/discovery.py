from typing import Dict

from sqlalchemy.orm import Session

from ..connectors import connectors
from .. import crud, schemas
from .connector_execution import fetch_with_resilience


def run_discovery(db: Session) -> Dict[str, int]:
    summary = {'vendors': 0, 'products': 0}
    for connector in connectors:
        payload = fetch_with_resilience(connector, db=db)
        for vendor_payload in payload.vendors:
            vendor_schema = schemas.VendorCreate(**vendor_payload)
            _, created = crud.create_vendor(db, vendor_schema)
            if created:
                summary['vendors'] += 1
        for product_payload in payload.products:
            vendor_name = product_payload.pop('vendor', None)
            if vendor_name:
                vendor = (
                    db.query(crud.models.Vendor)
                    .filter(crud.models.Vendor.name == vendor_name)
                    .first()
                )
                if vendor:
                    product_payload['vendor_id'] = vendor.id
            product_schema = schemas.ProductCreate(**product_payload)
            _, created = crud.create_product(db, product_schema)
            if created:
                summary['products'] += 1
    return summary
