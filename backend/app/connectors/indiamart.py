from __future__ import annotations

import os
from .base import DiscoveryConnector, DiscoveryPayload

INDIAMART_API_KEY = os.getenv("INDIAMART_API_KEY", "")

_MOCK_VENDORS = [
    {"name": "Taj Metals Traders", "source": "IndiaMART", "contact_email": "export@tajmetals.com", "phone": "+91-22-5550-1234", "industry": "Construction Materials", "metadata": {"region": "Mumbai, IN", "tier": "Gold", "gst": "27AAAAA0000A1Z5"}},
    {"name": "Bharat Precision Engineering", "source": "IndiaMART", "contact_email": "info@bharatprecision.in", "phone": "+91-20-5550-2345", "industry": "Precision Engineering", "metadata": {"region": "Pune, IN", "tier": "Platinum", "gst": "27BBBBB0000B2Z6"}},
    {"name": "Krishna Agro Commodities", "source": "IndiaMART", "contact_email": "trade@krishnaagro.in", "phone": "+91-40-5550-3456", "industry": "Agriculture", "metadata": {"region": "Hyderabad, IN", "tier": "Gold", "gst": "36CCCCC0000C3Z7"}},
    {"name": "Delhi Auto Parts Hub", "source": "IndiaMART", "contact_email": "sales@delhiautoparts.in", "phone": "+91-11-5550-4567", "industry": "Automotive Parts", "metadata": {"region": "Delhi, IN", "tier": "Silver", "gst": "07DDDDD0000D4Z8"}},
    {"name": "Surat Textiles Export House", "source": "IndiaMART", "contact_email": "export@surattextiles.in", "phone": "+91-261-555-5678", "industry": "Textiles", "metadata": {"region": "Surat, IN", "tier": "Platinum", "gst": "24EEEEE0000E5Z9"}},
    {"name": "Chennai Electronics Wholesale", "source": "IndiaMART", "contact_email": "bulk@chennaielec.in", "phone": "+91-44-5550-6789", "industry": "Electronics", "metadata": {"region": "Chennai, IN", "tier": "Gold", "gst": "33FFFFF0000F6Z0"}},
]


class IndiaMartConnector(DiscoveryConnector):
    name = "IndiaMART"

    def fetch(self) -> DiscoveryPayload:
        return DiscoveryPayload(vendors=_MOCK_VENDORS)
