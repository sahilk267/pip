from __future__ import annotations

import csv
import os
from pathlib import Path
from .base import DiscoveryConnector, DiscoveryPayload

SUPPLIER_FEED_CSV = os.getenv("SUPPLIER_FEED_CSV", "")

_MOCK_VENDORS = [
    {"name": "Nova Components", "source": "Supplier Feed", "contact_email": "sales@nova-components.com", "phone": "+1-512-555-0199", "industry": "Electronics", "metadata": {"feed": "Supplier CSV", "products": 32}},
    {"name": "Apex Industrial Group", "source": "Supplier Feed", "contact_email": "procurement@apexind.com", "phone": "+1-404-555-0287", "industry": "Industrial Equipment", "metadata": {"feed": "Supplier CSV", "products": 54}},
    {"name": "NorthStar Safety Systems", "source": "Supplier Feed", "contact_email": "sales@northstarsafety.com", "phone": "+1-651-555-0366", "industry": "Safety Equipment", "metadata": {"feed": "Supplier CSV", "products": 28}},
    {"name": "FusionTech Semiconductors", "source": "Supplier Feed", "contact_email": "b2b@fusiontech.io", "phone": "+1-503-555-0443", "industry": "Semiconductors", "metadata": {"feed": "Supplier CSV", "products": 89}},
]

_MOCK_PRODUCTS = [
    {"name": "Nova Thermal Module", "sku": "NTM-300", "price": "129.99", "vendor": "Nova Components", "attributes": {"rating": "IDA", "warranty": "2 years", "efficiency": "92%"}},
    {"name": "Nova Power Drive", "sku": "PDO-120", "price": "89.50", "vendor": "Nova Components", "attributes": {"rating": "IDB", "warranty": "1 year", "efficiency": "88%"}},
    {"name": "Apex Industrial Press", "sku": "AIP-500", "price": "2499.00", "vendor": "Apex Industrial Group", "attributes": {"capacity": "500T", "warranty": "3 years"}},
    {"name": "NorthStar Hard Hat XL", "sku": "NSH-XL", "price": "34.99", "vendor": "NorthStar Safety Systems", "attributes": {"standard": "ANSI Z89.1", "rating": "Type I Class E"}},
    {"name": "FusionTech MCU Chip FT32", "sku": "FT32-MCU", "price": "4.75", "vendor": "FusionTech Semiconductors", "attributes": {"cores": "32-bit", "flash": "512KB", "voltage": "3.3V"}},
]


def _load_csv_feed(path: str) -> tuple[list[dict], list[dict]]:
    p = Path(path)
    if not p.exists():
        return [], []
    with p.open() as f:
        rows = list(csv.DictReader(f))
    vendors = [r for r in rows if r.get("type") == "vendor"]
    products = [r for r in rows if r.get("type") == "product"]
    return vendors, products


class SupplierFeedConnector(DiscoveryConnector):
    name = "Supplier Feed"

    def fetch(self) -> DiscoveryPayload:
        if SUPPLIER_FEED_CSV:
            vendors, products = _load_csv_feed(SUPPLIER_FEED_CSV)
            if vendors or products:
                return DiscoveryPayload(vendors=vendors, products=products)
        return DiscoveryPayload(vendors=_MOCK_VENDORS, products=_MOCK_PRODUCTS)
