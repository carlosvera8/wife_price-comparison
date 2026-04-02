import asyncio
import random
from typing import Optional
from urllib.parse import quote_plus

from .base import BaseScraper, RawProduct

# Target's internal search API key (public, embedded in their frontend)
_TARGET_API_KEY = "ff457966e64d5e877fdbad070f276d18ecec4a01"


class TargetScraper(BaseScraper):
    """
    Scrapes Target by hitting their internal fulfillment/search API endpoints.
    These are the same endpoints the Target website calls, discovered via devtools.
    """

    async def get_store_id(self, zip_code: str, page) -> Optional[str]:
        try:
            url = (
                f"https://api.target.com/fulfillment/v1/stores"
                f"?zip={zip_code}&limit=1&key={_TARGET_API_KEY}"
            )
            response = await page.goto(url, wait_until="networkidle", timeout=20000)
            if response and response.status == 200:
                data = await response.json()
                stores = data.get("stores", [])
                if stores:
                    return str(stores[0].get("location_id", ""))
        except Exception:
            pass
        return None

    async def search_products(
        self,
        query: str,
        zip_code: str,
        page,
        max_results: int = 3,
    ) -> list[RawProduct]:
        store_id = await self.get_store_id(zip_code, page)
        if not store_id:
            return []

        delay_ms = self.config.get("request_delay_ms", 1500)
        jitter = random.randint(-300, 300)
        await page.wait_for_timeout(max(500, delay_ms + jitter))

        captured: list[RawProduct] = []

        try:
            search_url = (
                f"https://api.target.com/v3/plp/search"
                f"?key={_TARGET_API_KEY}"
                f"&keyword={quote_plus(query)}"
                f"&store_id={store_id}"
                f"&pricing_store_id={store_id}"
                f"&count={max_results}"
                f"&offset=0"
                f"&include_sponsored_search_v2=true"
            )
            response = await page.goto(search_url, wait_until="networkidle", timeout=30000)
            if not response or response.status != 200:
                return []

            data = await response.json()
            products = (
                data.get("data", {})
                .get("search", {})
                .get("products", [])
            )

            for item in products[:max_results]:
                price_info = item.get("price", {})
                current_price = price_info.get("current_retail")
                if current_price is None:
                    continue

                unit_price_info = price_info.get("unit_price", {})
                unit_desc = ""
                if unit_price_info:
                    unit_desc = (
                        f"{unit_price_info.get('price', '')} "
                        f"per {unit_price_info.get('unit_of_measure', '')}"
                    ).strip()

                item_attrs = item.get("item", {})
                desc = item_attrs.get("product_description", {}).get("soft_bullets", {})
                bullets = desc.get("bullets", [])
                if not unit_desc and bullets:
                    unit_desc = " | ".join(bullets[:2])

                tcin = item_attrs.get("tcin", "")
                captured.append(
                    RawProduct(
                        retailer="Target",
                        name=item_attrs.get("product_description", {}).get("title", ""),
                        price_str=f"${current_price}",
                        unit_desc=unit_desc,
                        url=f"https://www.target.com/p/-/A-{tcin}" if tcin else "https://www.target.com",
                    )
                )
        except Exception:
            pass

        if self._check_blocked_title(await page.title()):
            return []

        return captured
