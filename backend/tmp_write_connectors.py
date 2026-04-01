from pathlib import Path
content_linkedin = '''from .base import DiscoveryConnector, DiscoveryPayload


class LinkedInConnector(DiscoveryConnector):
    name = 'LinkedIn'

    def fetch(self) -> DiscoveryPayload:
        return DiscoveryPayload(vendors=[
            {
                'name': 'Aurora Supply Partners',
                'source': 'LinkedIn',
                'contact_email': 'contact@aurora.io',
                'phone': '+1-202-555-0104',
                'industry': 'Renewable Energy',
                'metadata': {'location': 'US', 'signal': 'High'},
            },
        ])
'''
content_indiamart = '''from .base import DiscoveryConnector, DiscoveryPayload


class IndiaMartConnector(DiscoveryConnector):
    name = 'IndiaMART'

    def fetch(self) -> DiscoveryPayload:
        return DiscoveryPayload(vendors=[
            {
                'name': 'Taj Metals Traders',
                'source': 'IndiaMART',
                'contact_email': 'export@tajmetals.com',
                'phone': '+91-22-5550-1234',
                'industry': 'Construction Materials',
                'metadata': {'region': 'IN', 'tier': 'Gold'},
            },
        ])
'''
content_google = '''from .base import DiscoveryConnector, DiscoveryPayload


class GoogleMapsConnector(DiscoveryConnector):
    name = 'Google Maps'

    def fetch(self) -> DiscoveryPayload:
        return DiscoveryPayload(vendors=[
            {
                'name': 'Springfield Industrial Supplies',
                'source': 'Google Maps',
                'contact_email': 'info@springfieldind.com',
                'phone': '+1-415-555-0188',
                'industry': 'Industrial Equipment',
                'metadata': {'location': 'US', 'rating': 4.8},
            },
        ])
'''
content_supplier = '''from .base import DiscoveryConnector, DiscoveryPayload


class SupplierFeedConnector(DiscoveryConnector):
    name = 'Supplier Feed'

    def fetch(self) -> DiscoveryPayload:
        return DiscoveryPayload(
            vendors=[
                {
                    'name': 'Nova Components',
                    'source': 'Supplier Feed',
                    'contact_email': 'sales@nova-components.com',
                    'phone': '+1-512-555-0199',
                    'industry': 'Electronics',
                    'metadata': {'feed': 'Supplier CSV', 'products': 32},
                },
            ],
            products=[
                {
                    'name': 'Nova Thermal Module',
                    'sku': 'NTM-300',
                    'price': '129.99',
                    'vendor': 'Nova Components',
                    'attributes': {'rating': 'IDA', 'warranty': '2 years'},
                },
            ],
        )
'''
for name, content in [
    ('backend/app/connectors/linkedin.py', content_linkedin),
    ('backend/app/connectors/indiamart.py', content_indiamart),
    ('backend/app/connectors/google_maps.py', content_google),
    ('backend/app/connectors/supplier_feed.py', content_supplier),
]:
    path = Path(name)
    path.write_text(content, encoding='utf-8')
init_content = '''from .linkedin import LinkedInConnector
from .indiamart import IndiaMartConnector
from .google_maps import GoogleMapsConnector
from .supplier_feed import SupplierFeedConnector

connectors = [
    LinkedInConnector(),
    IndiaMartConnector(),
    GoogleMapsConnector(),
    SupplierFeedConnector(),
]
'''
Path('backend/app/connectors/__init__.py').write_text(init_content, encoding='utf-8')
