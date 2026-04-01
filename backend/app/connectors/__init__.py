from .linkedin import LinkedInConnector
from .indiamart import IndiaMartConnector
from .google_maps import GoogleMapsConnector
from .supplier_feed import SupplierFeedConnector

connectors = [
    LinkedInConnector(),
    IndiaMartConnector(),
    GoogleMapsConnector(),
    SupplierFeedConnector(),
]
