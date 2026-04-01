from .base import DiscoveryConnector, DiscoveryPayload


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
