from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RawProduct:
    retailer: str
    name: str
    price_str: str      # e.g. "$12.99" — raw, unparsed
    unit_desc: str      # e.g. "8 double rolls = 160 sheets" or "64 fl oz"
    url: str
    in_stock: bool = True


class BaseScraper(ABC):
    def __init__(self, config: dict):
        self.name = config["name"]
        self.base_url = config["base_url"]
        self.config = config

    @abstractmethod
    async def get_store_id(self, zip_code: str, page) -> Optional[str]:
        """Resolve ZIP code to internal store ID. Return None if lookup fails."""
        ...

    @abstractmethod
    async def search_products(
        self,
        query: str,
        zip_code: str,
        page,
        max_results: int = 3,
    ) -> list[RawProduct]:
        """
        Search for products at this retailer near the given ZIP code.
        Returns [] on any failure — never raises.
        """
        ...

    def _check_blocked_title(self, title: str) -> bool:
        """Return True if the page title suggests bot detection."""
        blocked = ["access denied", "robot", "captcha", "automated", "blocked", "verify"]
        return any(phrase in title.lower() for phrase in blocked)
