import random
from typing import Optional
from urllib.parse import quote_plus

from curl_cffi.requests import AsyncSession

from .base import BaseScraper, RawProduct

# Target's internal API key — embedded in their public frontend.
# If this stops working: open target.com in devtools, find any /v3/plp/search
# network request, and copy the key= query param.
_TARGET_API_KEY = "ff457966e64d5e877fdbad070f276d18ecec4a01"

# Chrome 131 UA to match the curl_cffi impersonate profile
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

_HEADERS = {
    "User-Agent": _UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.target.com/",
    "Origin": "https://www.target.com",
    "DNT": "1",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}


class TargetScraper(BaseScraper):
    """
    Scrapes Target by hitting their internal search API directly with curl_cffi,
    which spoofs Chrome's TLS fingerprint at the network level.
    No browser/Playwright required — the 'page' param is accepted but unused.
    """

    async def get_store_id(self, zip_code: str, page) -> Optional[str]:
        url = (
            f"https://api.target.com/fulfillment/v1/stores"
            f"?zip={zip_code}&limit=1&key={_TARGET_API_KEY}"
        )
        try:
            async with AsyncSession(impersonate="chrome131") as session:
                resp = await session.get(url, headers=_HEADERS, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
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

        # Small human-like delay between store lookup and search
        import asyncio
        await asyncio.sleep(max(0.5, (delay_ms + jitter) / 1000))

        url = (
            f"https://api.target.com/v3/plp/search"
            f"?key={_TARGET_API_KEY}"
            f"&keyword={quote_plus(query)}"
            f"&store_id={store_id}"
            f"&pricing_store_id={store_id}"
            f"&count={max_results}"
            f"&offset=0"
            f"&include_sponsored_search_v2=true"
        )

        captured: list[RawProduct] = []
        try:
            async with AsyncSession(impersonate="chrome131") as session:
                resp = await session.get(url, headers=_HEADERS, timeout=20)
                if resp.status_code != 200:
                    return []

                data = resp.json()
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

                    # Use retailer-provided unit price when available
                    unit_price_info = price_info.get("unit_price", {})
                    unit_desc = ""
                    if unit_price_info and unit_price_info.get("price"):
                        unit_desc = (
                            f"{unit_price_info['price']} "
                            f"per {unit_price_info.get('unit_of_measure', '')}"
                        ).strip()

                    item_attrs = item.get("item", {})
                    if not unit_desc:
                        bullets = (
                            item_attrs.get("product_description", {})
                            .get("soft_bullets", {})
                            .get("bullets", [])
                        )
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

        return captured
