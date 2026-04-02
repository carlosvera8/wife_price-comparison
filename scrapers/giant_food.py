import asyncio
import random
from typing import Optional
from urllib.parse import quote_plus

from .base import BaseScraper, RawProduct


class GiantFoodScraper(BaseScraper):
    """
    Scrapes Giant Food (Ahold Delhaize, mid-Atlantic) by:
    1. Finding the nearest store via their store-finder page and setting the store cookie.
    2. Searching the product catalog — prices are then localized to that store.
    """

    async def get_store_id(self, zip_code: str, page) -> Optional[str]:
        try:
            # Navigate to store finder and enter ZIP to set the store session cookie
            await page.goto(
                "https://giantfood.com/store-locator",
                wait_until="domcontentloaded",
                timeout=20000,
            )
            await page.wait_for_timeout(1500)

            # Fill in ZIP and submit
            zip_input = page.locator("input[placeholder*='ZIP'], input[type='search'], input[name='zip']")
            await zip_input.first.fill(zip_code)
            await zip_input.first.press("Enter")
            await page.wait_for_timeout(2000)

            # Click the first store result to set the store cookie
            store_btn = page.locator("button:has-text('Set as my store'), a:has-text('Shop this store'), button:has-text('Shop here')")
            if await store_btn.count() > 0:
                await store_btn.first.click()
                await page.wait_for_timeout(1500)

            # Extract store ID from cookies or URL
            cookies = await page.context.cookies()
            for c in cookies:
                if "store" in c["name"].lower() and c["value"].isdigit():
                    return c["value"]

            # Fallback: extract from current URL if redirected to a store page
            url = page.url
            if "/stores/" in url:
                return url.split("/stores/")[-1].split("/")[0]

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
        # Set the store context first (sets session cookie)
        await self.get_store_id(zip_code, page)

        delay_ms = self.config.get("request_delay_ms", 2000)
        jitter = random.randint(-400, 400)
        await page.wait_for_timeout(max(500, delay_ms + jitter))

        captured: list[RawProduct] = []

        try:
            search_url = (
                f"https://giantfood.com/search?query={quote_plus(query)}"
                f"&sort=relevance&inStockOnly=false"
            )
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2500)

            if self._check_blocked_title(await page.title()):
                return []

            # Product cards — Giant Food uses a consistent product card structure
            product_cards = page.locator(
                "[data-testid='product-card'], .product-card, article[class*='product']"
            )
            count = await product_cards.count()

            for i in range(min(count, max_results)):
                card = product_cards.nth(i)
                try:
                    name_el = card.locator(
                        "[data-testid='product-title'], .product-title, h3, h2"
                    )
                    price_el = card.locator(
                        "[data-testid='product-price'], .product-price, [class*='price']"
                    )
                    unit_el = card.locator(
                        "[data-testid='unit-price'], .unit-price, [class*='unit']"
                    )
                    link_el = card.locator("a[href*='/product'], a[href*='/p/']")

                    name = (await name_el.first.inner_text()).strip() if await name_el.count() > 0 else ""
                    price_str = (await price_el.first.inner_text()).strip() if await price_el.count() > 0 else ""
                    unit_desc = (await unit_el.first.inner_text()).strip() if await unit_el.count() > 0 else ""
                    href = await link_el.first.get_attribute("href") if await link_el.count() > 0 else ""
                    url = f"https://giantfood.com{href}" if href and href.startswith("/") else (href or "https://giantfood.com")

                    if name and price_str:
                        captured.append(
                            RawProduct(
                                retailer="Giant Food",
                                name=name,
                                price_str=price_str,
                                unit_desc=unit_desc,
                                url=url,
                            )
                        )
                except Exception:
                    continue

        except Exception:
            pass

        return captured
