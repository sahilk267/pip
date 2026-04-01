from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence, Mapping

from pydantic import BaseModel


class DiscoveryPayload(BaseModel):
    vendors: Sequence[Mapping[str, object]] = []
    products: Sequence[Mapping[str, object]] = []


class DiscoveryConnector(ABC):
    """Connector that returns vendor/product data from an external feed."""

    name: str

    @abstractmethod
    def fetch(self) -> DiscoveryPayload:
        ...
