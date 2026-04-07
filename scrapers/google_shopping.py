"""
scrapers/google_shopping.py — SerpAPI Google Shopping client

Fetches product results from Google Shopping via SerpAPI and maps them to
RawProduct instances. One API credit is consumed per search regardless of
how many results are requested.

Free tier: 100 searches/month at https://serpapi.com/
"""
import logging
import os
from typing import Optional

import httpx

from .base import RawProduct

log = logging.getLogger(__name__)

_SERPAPI_URL = "https://serpapi.com/search"
_NUM_FETCH = 20  # results to request from SerpAPI per call (1 credit regardless)


def _normalize_source(source: str) -> str:
    """
    Normalize a SerpAPI source string for retailer name matching.
    'Walmart.com' → 'walmart', 'Giant Food Stores' → 'giant food stores'
    """
    s = source.lower().strip()
    for suffix in (".com", ".net", ".org", ".co"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    return s


def _matches_retailer_filter(source: str, retailer_filter: list[str]) -> bool:
    """
    Return True if the normalized source matches any token in retailer_filter.

    Tokens are normalized (underscores → spaces, lowercased, TLD stripped).
    Uses prefix-match in both directions so 'walmart' matches 'walmart supercenter'
    and 'giant_food' matches 'giant food'.
    """
    normalized_source = _normalize_source(source)
    for token in retailer_filter:
        normalized_token = token.lower().replace("_", " ").strip()
        if normalized_source.startswith(normalized_token) or normalized_token.startswith(normalized_source):
            return True
    return False


async def search(
    query: str,
    zip_code: str,
    retailer_filter: Optional[list[str]] = None,
    max_results: int = 3,
) -> list[RawProduct]:
    """
    Search Google Shopping via SerpAPI and return a list of RawProduct objects.

    Without retailer_filter: returns the top max_results products overall.
    With retailer_filter:    returns up to max_results per matching retailer.

    Raises:
        EnvironmentError: if SERPAPI_KEY is not set in the environment.
        httpx.HTTPStatusError: on non-2xx API responses.
    """
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        raise EnvironmentError(
            "SERPAPI_KEY is not set. "
            "Add it to your .env file (see .env.example). "
            "Get a free key at https://serpapi.com/"
        )

    params = {
        "engine": "google_shopping",
        "q": query,
        "location": zip_code,
        "gl": "us",
        "hl": "en",
        "num": _NUM_FETCH,
        "api_key": api_key,
    }

    log.debug("SerpAPI request: q=%r location=%s num=%d", query, zip_code, _NUM_FETCH)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(_SERPAPI_URL, params=params)
        response.raise_for_status()
        data = response.json()

    shopping_results = data.get("shopping_results", [])
    log.debug("SerpAPI returned %d shopping_results", len(shopping_results))

    raw_products: list[RawProduct] = []
    retailer_counts: dict[str, int] = {}  # used only when filtering

    for item in shopping_results:
        source = item.get("source", "")
        if not source:
            continue

        if retailer_filter:
            if not _matches_retailer_filter(source, retailer_filter):
                continue
            # Cap per-retailer
            key = _normalize_source(source)
            if retailer_counts.get(key, 0) >= max_results:
                continue
            retailer_counts[key] = retailer_counts.get(key, 0) + 1
        else:
            # No filter: cap total
            if len(raw_products) >= max_results:
                break

        # extensions contains size/count info like "8 Double Rolls", "64 fl oz"
        # Join them all — normalizer.py scans name + unit_desc for count patterns
        extensions = item.get("extensions", [])
        unit_desc = ", ".join(extensions) if extensions else ""

        price_str = item.get("price", "")
        title = item.get("title", "")
        link = item.get("link", "")

        log.debug(
            "SerpAPI item: source=%r title=%r price=%r unit_desc=%r",
            source, title, price_str, unit_desc,
        )

        raw_products.append(
            RawProduct(
                retailer=source,
                name=title,
                price_str=price_str,
                unit_desc=unit_desc,
                url=link,
            )
        )

    log.debug("google_shopping.search returning %d products", len(raw_products))
    return raw_products
