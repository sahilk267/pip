from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from .base import DiscoveryConnector, DiscoveryPayload

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

_MOCK_VENDORS = [
    {"name": "Springfield Industrial Supplies", "source": "Google Maps", "contact_email": "info@springfieldind.com", "phone": "+1-415-555-0188", "industry": "Industrial Equipment", "metadata": {"location": "Springfield, US", "rating": 4.8, "reviews": 142}},
    {"name": "Pacific Rim Trading Co.", "source": "Google Maps", "contact_email": "trade@pacificrim.com", "phone": "+1-206-555-0294", "industry": "Import/Export", "metadata": {"location": "Seattle, US", "rating": 4.5, "reviews": 89}},
    {"name": "Great Lakes Fabrication", "source": "Google Maps", "contact_email": "sales@greatlakesfab.com", "phone": "+1-312-555-0371", "industry": "Metal Fabrication", "metadata": {"location": "Chicago, US", "rating": 4.7, "reviews": 203}},
    {"name": "Sunbelt Materials LLC", "source": "Google Maps", "contact_email": "info@sunbeltmat.com", "phone": "+1-713-555-0447", "industry": "Construction Materials", "metadata": {"location": "Houston, US", "rating": 4.3, "reviews": 67}},
    {"name": "Eastern Seaboard Logistics", "source": "Google Maps", "contact_email": "ops@eslogistics.com", "phone": "+1-212-555-0512", "industry": "Logistics", "metadata": {"location": "New York, US", "rating": 4.6, "reviews": 318}},
]


def _fetch_from_api(query: str = "industrial suppliers") -> list[dict]:
    if not GOOGLE_MAPS_API_KEY:
        return []
    try:
        params = urllib.parse.urlencode({"query": query, "key": GOOGLE_MAPS_API_KEY})
        url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?{params}"
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        vendors = []
        for r in data.get("results", [])[:5]:
            vendors.append({"name": r.get("name", "Unknown"), "source": "Google Maps", "contact_email": "", "phone": r.get("formatted_phone_number", ""), "industry": query, "metadata": {"location": r.get("formatted_address", ""), "rating": r.get("rating", 0), "reviews": r.get("user_ratings_total", 0), "place_id": r.get("place_id", "")}})
        return vendors
    except Exception:
        return []


class GoogleMapsConnector(DiscoveryConnector):
    name = "Google Maps"

    def fetch(self) -> DiscoveryPayload:
        live = _fetch_from_api()
        return DiscoveryPayload(vendors=live if live else _MOCK_VENDORS)
