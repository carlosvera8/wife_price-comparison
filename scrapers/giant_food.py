import asyncio
import logging
import random
from typing import Optional
from urllib.parse import quote_plus

from .base import BaseScraper, RawProduct

log = logging.getLogger(__name__)


class GiantFoodScraper(BaseScraper):
    """
    Scrapes Giant Food (Ahold Delhaize, mid-Atlantic) by:
    1. Finding the nearest store via their store-finder page and setting the store cookie.
    2. Searching the product catalog — prices are then localized to that store.
    """

    async def get_store_id(self, zip_code: str, page) -> Optional[str]:
        log.debug("Giant Food store lookup: navigating to store-locator for ZIP %s", zip_code)
        try:
            await page.goto(
                "https://giantfood.com/store-locator",
                wait_until="domcontentloaded",
                timeout=20000,
            )
            log.debug("Giant Food store lookup: page loaded, title=%r", await page.title())
            await page.wait_for_timeout(1500)

            zip_input = page.locator("input[placeholder*='ZIP'], input[type='search'], input[name='zip']")
            zip_count = await zip_input.count()
            log.debug("Giant Food store lookup: ZIP input elements found: %d", zip_count)
            if zip_count == 0:
                log.debug("Giant Food store lookup: no ZIP input found — page HTML snippet: %s", (await page.content())[:500])
                return None

            await zip_input.first.fill(zip_code)
            await zip_input.first.press("Enter")
            await page.wait_for_timeout(2000)

            store_btn = page.locator("button:has-text('Set as my store'), a:has-text('Shop this store'), button:has-text('Shop here')")
            btn_count = await store_btn.count()
            log.debug("Giant Food store lookup: store action buttons found: %d", btn_count)
            if btn_count > 0:
                await store_btn.first.click()
                await page.wait_for_timeout(1500)
            else:
                log.debug("Giant Food store lookup: no 'set store' button found after ZIP search")

            cookies = await page.context.cookies()
            log.debug("Giant Food store lookup: cookies after store selection: %s", [c["name"] for c in cookies])
            for c in cookies:
                if "store" in c["name"].lower() and c["value"].isdigit():
                    log.debug("Giant Food store lookup: found store cookie %s=%s", c["name"], c["value"])
                    return c["value"]

            url = page.url
            log.debug("Giant Food store lookup: current URL after store selection: %s", url)
            if "/stores/" in url:
                store_id = url.split("/stores/")[-1].split("/")[0]
                log.debug("Giant Food store lookup: extracted store ID from URL: %s", store_id)
                return store_id

            log.debug("Giant Food store lookup: could not determine store ID")

        except Exception as e:
            log.debug("Giant Food store lookup exception: %s", e, exc_info=True)

        return None

    async def search_products(
        self,
        query: str,
        zip_code: str,
        page,
        max_results: int = 3,
    ) -> list[RawProduct]:
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
            log.debug("Giant Food product search: navigating to %s", search_url)
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2500)

            title = await page.title()
            log.debug("Giant Food product search: page title=%r", title)
            if self._check_blocked_title(title):
                log.debug("Giant Food product search: blocked by bot detection")
                return []

            product_cards = page.locator(
                "[data-testid='product-card'], .product-card, article[class*='product']"
            )
            count = await product_cards.count()
            log.debug("Giant Food product search: product cards found: %d", count)

            if count == 0:
                log.debug("Giant Food product search: no cards — page HTML snippet: %s", (await page.content())[:800])

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

                    log.debug("Giant Food: card %d — name=%r price=%r unit=%r", i, name, price_str, unit_desc)
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
                    else:
                        log.debug("Giant Food: card %d skipped (missing name or price)", i)
                except Exception as e:
                    log.debug("Giant Food: card %d exception: %s", i, e)
                    continue

        except Exception as e:
            log.debug("Giant Food product search exception: %s", e, exc_info=True)

        log.debug("Giant Food: returning %d products", len(captured))
        return captured
