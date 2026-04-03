import asyncio
import random
from typing import Optional

from .base import BaseScraper, RawProduct

# Headers that make Playwright page requests look more like a real browser.
# Sec-Fetch-* headers are sent automatically by Chrome but NOT by Playwright by default.
_PAGE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "DNT": "1",
}

_MAX_RETRIES = 2


class WalmartScraper(BaseScraper):
    """
    Scrapes Walmart by intercepting the internal Next.js JSON API calls
    rather than parsing DOM elements. More resilient to layout changes.

    WARNING: Walmart uses Akamai Bot Manager. Detection is possible even with
    stealth measures. The scraper retries up to 2 times on empty results.
    """

    async def get_store_id(self, zip_code: str, page) -> Optional[str]:
        store_id = None

        async def handle_response(response):
            nonlocal store_id
            if "stores/nearby" in response.url and response.status == 200:
                try:
                    data = await response.json()
                    stores = data.get("payload", {}).get("stores", [])
                    if stores:
                        store_id = str(stores[0]["id"])
                except Exception:
                    pass

        await page.set_extra_http_headers(_PAGE_HEADERS)
        page.on("response", handle_response)
        try:
            url = (
                f"https://www.walmart.com/store/electrode/api/stores/nearby"
                f"?zip={zip_code}&limit=1&types=STORE"
            )
            await page.goto(url, wait_until="networkidle", timeout=20000)
            await page.wait_for_timeout(1000)
        except Exception:
            pass
        finally:
            page.remove_listener("response", handle_response)

        return store_id

    async def _attempt_search(
        self,
        query: str,
        zip_code: str,
        store_id: str,
        page,
        max_results: int,
    ) -> list[RawProduct]:
        """Single scrape attempt. Returns [] on block or failure."""
        captured: list[RawProduct] = []

        async def intercept_search(response):
            if "electrode/api/search" in response.url and response.status == 200:
                try:
                    data = await response.json()
                    items = (
                        data.get("props", {})
                        .get("pageProps", {})
                        .get("initialData", {})
                        .get("searchResult", {})
                        .get("itemStacks", [{}])[0]
                        .get("items", [])
                    )
                    for item in items[:max_results]:
                        price_info = item.get("price", {})
                        price = price_info.get("currentPrice", price_info.get("price"))
                        if price is None:
                            continue
                        short_desc = item.get("shortDescription", "")
                        unit_desc = item.get("unitPriceDisplayCondition", short_desc or "")
                        captured.append(
                            RawProduct(
                                retailer="Walmart",
                                name=item.get("name", ""),
                                price_str=f"${price}",
                                unit_desc=unit_desc,
                                url=f"https://www.walmart.com{item.get('canonicalUrl', '')}",
                            )
                        )
                except Exception:
                    pass

        page.on("response", intercept_search)

        delay_ms = self.config.get("request_delay_ms", 2000)
        jitter = random.randint(-400, 400)
        await page.wait_for_timeout(max(800, delay_ms + jitter))

        try:
            search_url = (
                f"https://www.walmart.com/search?q={query.replace(' ', '+')}"
                f"&store={store_id}"
            )
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3500)
        except Exception:
            pass

        page.remove_listener("response", intercept_search)

        title = await page.title()
        if self._check_blocked_title(title):
            return []

        return captured

    async def search_products(
        self,
        query: str,
        zip_code: str,
        page,
        max_results: int = 3,
    ) -> list[RawProduct]:
        await page.set_extra_http_headers(_PAGE_HEADERS)

        store_id = await self.get_store_id(zip_code, page)
        if not store_id:
            return []

        for attempt in range(1, _MAX_RETRIES + 1):
            results = await self._attempt_search(query, zip_code, store_id, page, max_results)
            if results:
                return results
            if attempt < _MAX_RETRIES:
                # Back off before retrying
                await asyncio.sleep(3 + random.uniform(0, 2))

        return []
