import logging
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from normalizer import normalize_product
from scrapers.base import RawProduct
from scrapers.google_shopping import search as google_shopping_search

_console = Console()
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mock data — used when --mock flag is passed (no API call)
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
    Fetch products via SerpAPI Google Shopping (or mock data), normalize each
    result, sort by unit price, and render a rich table to the terminal.

    Returns the sorted list of result dicts with keys:
        retailer, name, price_str, url,
        price_usd, unit_count, unit_label, unit_price, confidence
    """
    from output import render_results

    if mock:
        _console.print(
            f'\n[dim]Using mock data for "[bold]{query}[/bold]" near {zip_code}[/dim]\n'
        )
        raw_products = [RawProduct(**p) for p in _MOCK_PRODUCTS]
        if retailer_filter:
            def _mock_matches(retailer: str) -> bool:
                normalized = retailer.lower().replace(" ", "_")
                return any(
                    t.lower() in normalized or normalized.startswith(t.lower())
                    for t in retailer_filter
                )
            raw_products = [p for p in raw_products if _mock_matches(p.retailer)]
    else:
        _console.print(
            f'\nSearching "[bold]{query}[/bold]" near {zip_code}...\n'
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            console=_console,
            transient=True,
        ) as progress:
            task = progress.add_task(
                "  [dim]Google Shopping[/dim]  Fetching...", total=None
            )
            try:
                raw_products = await google_shopping_search(
                    query=query,
                    zip_code=zip_code,
                    retailer_filter=retailer_filter,
                    max_results=max_results,
                )
                count = len(raw_products)
                progress.update(
                    task,
                    description=(
                        f"  [green]✓[/green]  Google Shopping  "
                        f"{count} result{'s' if count != 1 else ''}"
                    ),
                )
                log.debug("SerpAPI search complete: %d products", count)
            except EnvironmentError as e:
                progress.stop()
                _console.print(f"\n[red bold]Configuration error:[/red bold] {e}\n")
                return []
            except Exception as e:
                progress.stop()
                log.debug("SerpAPI search failed: %s", e, exc_info=True)
                _console.print(f"\n[red bold]Search failed:[/red bold] {e}\n")
                return []

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
