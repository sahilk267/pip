from .base import DiscoveryConnector, DiscoveryPayload


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
