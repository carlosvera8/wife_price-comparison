import asyncio
import json
import random
from typing import Optional

from .base import BaseScraper, RawProduct


class WalmartScraper(BaseScraper):
    """
    Scrapes Walmart by intercepting the internal Next.js JSON API calls
    rather than parsing DOM elements. This is more resilient to layout changes.
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
        await page.wait_for_timeout(max(500, delay_ms + jitter))

        try:
            search_url = (
                f"https://www.walmart.com/search?q={query.replace(' ', '+')}"
                f"&store={store_id}"
            )
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            # Allow time for the Next.js internal data fetch to fire
            await page.wait_for_timeout(3500)
        except Exception:
            pass

        page.remove_listener("response", intercept_search)

        if self._check_blocked_title(await page.title()):
            return []

        return captured
