from .base import DiscoveryConnector, DiscoveryPayload


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
