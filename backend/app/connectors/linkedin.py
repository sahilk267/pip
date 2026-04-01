from .base import DiscoveryConnector, DiscoveryPayload


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
