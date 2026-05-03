from __future__ import annotations

import os
from .base import DiscoveryConnector, DiscoveryPayload

LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")

_MOCK_VENDORS = [
    {"name": "Aurora Supply Partners", "source": "LinkedIn", "contact_email": "contact@aurora.io", "phone": "+1-202-555-0104", "industry": "Renewable Energy", "metadata": {"location": "Washington DC, US", "signal": "High", "connections": 1240}},
    {"name": "Vertex Manufacturing Group", "source": "LinkedIn", "contact_email": "bd@vertexmfg.com", "phone": "+1-408-555-0223", "industry": "Electronics Manufacturing", "metadata": {"location": "San Jose, US", "signal": "Medium", "connections": 876}},
    {"name": "BlueOcean Procurement Solutions", "source": "LinkedIn", "contact_email": "hello@blueoceanproc.com", "phone": "+1-617-555-0341", "industry": "Procurement Services", "metadata": {"location": "Boston, US", "signal": "High", "connections": 2150}},
    {"name": "Meridian Chemicals International", "source": "LinkedIn", "contact_email": "sales@meridianchem.com", "phone": "+1-281-555-0456", "industry": "Chemicals", "metadata": {"location": "Houston, US", "signal": "Medium", "connections": 543}},
    {"name": "TechBridge Distribution", "source": "LinkedIn", "contact_email": "dist@techbridge.io", "phone": "+1-512-555-0567", "industry": "Technology Distribution", "metadata": {"location": "Austin, US", "signal": "High", "connections": 1890}},
]


class LinkedInConnector(DiscoveryConnector):
    name = "LinkedIn"

    def fetch(self) -> DiscoveryPayload:
        return DiscoveryPayload(vendors=_MOCK_VENDORS)
