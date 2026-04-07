import asyncio
import importlib
import json
import os
import random
from pathlib import Path
from typing import Optional

import yaml
from playwright.async_api import async_playwright
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from normalizer import normalize_product
from scrapers.base import BaseScraper, RawProduct

_console = Console()


# ---------------------------------------------------------------------------
# Mock data — used when --mock flag is passed (no scraping)
# ---------------------------------------------------------------------------

_MOCK_PRODUCTS: list[dict] = [
    {
        "retailer": "Walmart",
        "name": "Bounty Select-A-Size Paper Towels, 12 Double Rolls",
        "price_str": "$19.94",
        "unit_desc": "12 double rolls = 24 regular rolls, 90 sheets per regular roll",
        "url": "https://www.walmart.com/ip/bounty-paper-towels/123456",
    },
    {
        "retailer": "Target",
        "name": "Bounty Select-A-Size Paper Towels - 8 Double Plus Rolls",
        "price_str": "$14.99",
        "unit_desc": "8 double plus rolls = 20 regular rolls, 74 sheets per roll",
        "url": "https://www.target.com/p/bounty/-/A-11111",
    },
    {
        "retailer": "Giant Food",
        "name": "Brawny Pick-A-Size Paper Towels, 6 Giant Rolls",
        "price_str": "$9.99",
        "unit_desc": "6 giant rolls = 12 regular rolls, 120 sheets per roll",
        "url": "https://giantfood.com/product/brawny-6pack",
    },
]


# ---------------------------------------------------------------------------
# Browser helpers
# ---------------------------------------------------------------------------

def _pick_random_ua() -> str:
    ua_path = Path(__file__).parent / "config" / "user_agents.txt"
    agents = [line.strip() for line in ua_path.read_text().splitlines() if line.strip()]
    return random.choice(agents)


def _load_scrapers(retailer_filter: Optional[list[str]] = None) -> list[BaseScraper]:
    config_path = Path(__file__).parent / "config" / "retailers.yaml"
    config = yaml.safe_load(config_path.read_text())

    scrapers = []
    for r in config["retailers"]:
        if not r.get("enabled", True):
            continue
        if retailer_filter and r["id"] not in retailer_filter:
            continue
        module = importlib.import_module(f"scrapers.{r['id']}")
        cls = getattr(module, r["class"])
        scrapers.append(cls(r))

    return scrapers


async def _safe_scrape(
    scraper: BaseScraper,
    query: str,
    zip_code: str,
    page,
    max_results: int,
) -> list[RawProduct]:
    try:
        return await asyncio.wait_for(
            scraper.search_products(query, zip_code, page, max_results),
            timeout=60.0,
        )
    except asyncio.TimeoutError:
        _console.print(f"[yellow]Warning: {scraper.name} timed out — skipping[/yellow]")
        return []
    except Exception as e:
        _console.print(f"[yellow]Warning: {scraper.name} failed ({e}) — skipping[/yellow]")
        return []


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_comparison(
    query: str,
    zip_code: str,
    retailer_filter: Optional[list[str]] = None,
    max_results: int = 3,
    mock: bool = False,
) -> list[dict]:
    """
    Orchestrates scraping + normalization and returns a sorted list of result dicts.
    Each dict has: retailer, name, price_str, url, price_usd, unit_count,
                   unit_label, unit_price, confidence
    """
    from output import render_results

    if mock:
        _console.print(f'\n[dim]Using mock data for "[bold]{query}[/bold]" near {zip_code}[/dim]\n')
        raw_products = [RawProduct(**p) for p in _MOCK_PRODUCTS]
        if retailer_filter:
            raw_products = [p for p in raw_products if p.retailer.lower().replace(" ", "_") in retailer_filter]
    else:
        scrapers = _load_scrapers(retailer_filter)
        if not scrapers:
            _console.print("No enabled retailers matched your filter.")
            return []

        headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
        _console.print(f'\nSearching for "[bold]{query}[/bold]" near {zip_code}...\n')

        with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=_console) as progress:
            task_ids = [
                progress.add_task(f"  [dim]{s.name:<14}[/dim]  Searching...", total=None)
                for s in scrapers
            ]

            async def _tracked(i: int, scraper: BaseScraper, page, task_id):
                await asyncio.sleep(i * 1.5)
                results = await _safe_scrape(scraper, query, zip_code, page, max_results)
                count = len(results)
                if count:
                    progress.update(task_id, description=f"  [green]✓[/green]  {scraper.name:<14}  {count} result{'s' if count != 1 else ''}")
                else:
                    progress.update(task_id, description=f"  [red]✗[/red]  {scraper.name:<14}  no results")
                progress.stop_task(task_id)
                return results

            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=headless,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                    ],
                )

                context = await browser.new_context(
                    user_agent=_pick_random_ua(),
                    viewport={"width": 1280, "height": 800},
                    locale="en-US",
                    timezone_id="America/New_York",
                    device_scale_factor=random.choice([1, 1.25, 1.5, 2]),
                )

                # Sec-Fetch-* headers: sent automatically by real Chrome but NOT by
                # Playwright by default. Adding them makes requests look legitimate.
                await context.set_extra_http_headers({
                    "Accept-Language": "en-US,en;q=0.9",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1",
                })

                # Spoof navigator.webdriver and other common automation signals
                await context.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                    "Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});"
                    "Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});"
                    "window.chrome = {runtime: {}};"
                )

                pages = [await context.new_page() for _ in scrapers]

                tasks = [
                    _tracked(i, scraper, page, task_ids[i])
                    for i, (scraper, page) in enumerate(zip(scrapers, pages))
                ]
                results_nested = await asyncio.gather(*tasks)

                for page in pages:
                    await page.close()
                await context.close()
                await browser.close()

        raw_products = [p for sublist in results_nested for p in sublist]

    if not raw_products:
        render_results(query, zip_code, [])
        return []

    # Normalize each product using pure Python regex heuristics (synchronous)
    normalized: list[dict] = []
    for product in raw_products:
        norm = normalize_product(product)
        result = {
            "retailer": product.retailer,
            "name": product.name,
            "price_str": product.price_str,
            "url": product.url,
            **norm,
        }
        normalized.append(result)

    # Sort by unit_price (None values go to the end)
    normalized.sort(
        key=lambda r: r["unit_price"] if r["unit_price"] is not None else float("inf")
    )

    render_results(query, zip_code, normalized)
    return normalized
