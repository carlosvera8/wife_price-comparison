import json
import os

import anthropic

from scrapers.base import RawProduct

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


_SYSTEM_PROMPT = """\
You are a unit price calculator for household products.
Given a product name, price, and unit description, calculate the price per standard unit.

Standard units by product category:
- Paper towels: sheets
- Toilet paper: sheets
- Laundry detergent: loads
- Dish soap / liquid soap: fluid ounces
- Trash bags / garbage bags: bags
- Paper plates / cups: pieces
- Napkins: sheets
- Batteries: batteries
- Cleaning wipes: wipes
- Shampoo / conditioner / body wash: fluid ounces
- Diapers: diapers
- Default (unknown category): ounces or units

Marketing unit conversions to apply:
- "double rolls" = 2x single roll sheet count
- "triple rolls" = 3x single roll sheet count
- "double plus rolls" = 2.5x single roll sheet count
- "mega rolls" = 4x single roll sheet count
- "family rolls" = 4x single roll sheet count
- "select-a-size" sheets are typically 74 sheets per single roll for paper towels

When the exact count is not stated, use typical industry values and report confidence as "medium" or "low".
When the count IS clearly stated, report confidence as "high".

Respond ONLY with a JSON object. No explanation text outside the JSON.
""".strip()


async def normalize_product(product: RawProduct) -> dict:
    """
    Call Claude to extract normalized price/unit data from a raw product.

    Returns a dict with keys:
        price_usd     float  — parsed dollar amount
        unit_count    int    — number of standard units
        unit_label    str    — e.g. "sheet", "load", "fl oz"
        unit_price    float  — price_usd / unit_count
        confidence    str    — "high", "medium", or "low"
    On failure, returns a dict with unit_price=None.
    """
    client = _get_client()

    user_msg = (
        f"Product: {product.name}\n"
        f"Price: {product.price_str}\n"
        f"Unit description: {product.unit_desc or '(not provided)'}\n"
        f"Retailer: {product.retailer}\n\n"
        "Return JSON with keys: price_usd, unit_count, unit_label, unit_price, confidence"
    )

    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = response.content[0].text.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()

        parsed = json.loads(text)

        # Ensure required keys exist and unit_price is sane
        price_usd = float(parsed.get("price_usd", 0))
        unit_count = int(parsed.get("unit_count", 1))
        unit_label = str(parsed.get("unit_label", "unit"))
        unit_price = float(parsed.get("unit_price", price_usd / max(unit_count, 1)))
        confidence = str(parsed.get("confidence", "low"))

        return {
            "price_usd": price_usd,
            "unit_count": unit_count,
            "unit_label": unit_label,
            "unit_price": unit_price,
            "confidence": confidence,
        }

    except Exception:
        return {
            "price_usd": None,
            "unit_count": None,
            "unit_label": None,
            "unit_price": None,
            "confidence": "low",
        }
