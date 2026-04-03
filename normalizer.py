"""
normalizer.py — Pure Python regex-based unit price parser.
No external dependencies. No LLM API required.

Pipeline:
  Stage 1: Parse a unit price directly from unit_desc
           (retailer already computed it — e.g. "0.034/sheet", "9.2¢/oz")
  Stage 2: Extract a count from name + unit_desc, divide total price by count
           (e.g. "64 fl oz", "100 ct", "8 double rolls" → 16 rolls)
  Stage 3: Return unit_price=None (table renders "n/a")
"""
import re
from scrapers.base import RawProduct


# ---------------------------------------------------------------------------
# Price string parser
# ---------------------------------------------------------------------------

def _parse_price_str(price_str: str) -> float | None:
    """Parse '$12.99', '12.99', '$9' → float."""
    if not price_str:
        return None
    m = re.search(r'\$?([\d]+(?:\.[\d]+)?)', price_str.replace(',', ''))
    return float(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Unit label normalization
# ---------------------------------------------------------------------------

UNIT_ALIASES: dict[str, str] = {
    # Count / generic
    "count": "ct", "counts": "ct", "ct": "ct",
    "unit": "ct", "units": "ct",
    "piece": "ct", "pieces": "ct", "pc": "ct", "pcs": "ct",
    "item": "ct", "items": "ct",
    "each": "ct", "ea": "ct",
    # Rolls
    "roll": "roll", "rolls": "roll",
    # Sheets / wipes / napkins
    "sheet": "sheet", "sheets": "sheet",
    "wipe": "wipe", "wipes": "wipe",
    "napkin": "sheet", "napkins": "sheet",
    # Loads
    "load": "load", "loads": "load",
    # Fluid ounces
    "fl oz": "fl oz", "fl. oz": "fl oz", "fl. oz.": "fl oz",
    "floz": "fl oz", "fluid oz": "fl oz",
    "fluid ounce": "fl oz", "fluid ounces": "fl oz",
    # Dry ounces
    "oz": "oz", "ounce": "oz", "ounces": "oz",
    # Weight
    "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb",
    "g": "g", "gram": "g", "grams": "g",
    # Volume
    "liter": "L", "liters": "L", "litre": "L", "litres": "L", "l": "L",
    "ml": "mL", "milliliter": "mL", "milliliters": "mL",
    # Bags / diapers / batteries
    "bag": "bag", "bags": "bag",
    "diaper": "diaper", "diapers": "diaper",
    "battery": "battery", "batteries": "battery",
    # Pack (catch-all)
    "pack": "pack", "packs": "pack",
}


def _normalize_label(raw: str) -> str:
    key = raw.strip().lower().rstrip('.')
    return UNIT_ALIASES.get(key, key)


# ---------------------------------------------------------------------------
# Stage 1: parse a unit price directly from unit_desc
# ---------------------------------------------------------------------------
#
# Patterns ordered highest-to-lowest priority so the first match wins.
# Each tuple is (pattern, is_cents_not_dollars).

_STAGE1_PATTERNS: list[tuple[re.Pattern, bool]] = [
    # $0.034/sheet   $0.21/load
    (re.compile(r'\$\s*([\d]+(?:\.[\d]+)?)\s*/\s*([a-zA-Z][a-zA-Z .]*)', re.IGNORECASE), False),
    # 9.2¢/oz   10.7¢/count
    (re.compile(r'([\d]+(?:\.[\d]+)?)\s*[¢]\s*/?\s*([a-zA-Z][a-zA-Z .]*)', re.IGNORECASE), True),
    # $0.21 per load
    (re.compile(r'\$\s*([\d]+(?:\.[\d]+)?)\s+per\s+([a-zA-Z][a-zA-Z .]*)', re.IGNORECASE), False),
    # 9.2 cents per oz
    (re.compile(r'([\d]+(?:\.[\d]+)?)\s+cents?\s+per\s+([a-zA-Z][a-zA-Z .]*)', re.IGNORECASE), True),
    # 0.034/sheet   0.034/fl oz   (bare decimal — Target API format)
    (re.compile(r'(?<![A-Za-z\$])([\d]+\.[\d]+)\s*/\s*([a-zA-Z][a-zA-Z .]*)', re.IGNORECASE), False),
    # 0.034 per sheet   (bare decimal + "per")
    (re.compile(r'(?<![A-Za-z\$])([\d]+\.[\d]+)\s+per\s+([a-zA-Z][a-zA-Z .]*)', re.IGNORECASE), False),
]


def _stage1_parse_unit_price(unit_desc: str) -> tuple[float, str] | None:
    """Return (unit_price_dollars, canonical_label) or None."""
    if not unit_desc:
        return None
    for pattern, is_cents in _STAGE1_PATTERNS:
        m = pattern.search(unit_desc)
        if m:
            price = float(m.group(1))
            if is_cents:
                price /= 100.0
            label = _normalize_label(m.group(2))
            if price > 0:
                return (price, label)
    return None


# ---------------------------------------------------------------------------
# Stage 2: extract unit count from name + unit_desc
# ---------------------------------------------------------------------------

_ROLL_MULTIPLIERS: dict[str, int] = {
    "double plus": 3,   # approximated as 3 (2.5 rounds to nearest int)
    "double":      2,
    "triple":      3,
    "mega":        4,
    "family":      4,
    "giant":       2,
    "super":       2,
    "jumbo":       2,
    "huge":        2,
    "big":         1,
}

# Stage 2 patterns: (compiled_regex, handler)
# Handlers receive match groups and return (count: int, label: str) or None.

_P_PACK_OF = re.compile(r'(\d+)\s+pack\s+of\s+(\d+)', re.IGNORECASE)
_P_MARKETING_ROLLS = re.compile(
    r'(\d+)\s+(double\s+plus|double|triple|mega|family|giant|super|jumbo|huge|big)\s+rolls?',
    re.IGNORECASE,
)
_P_PLAIN_ROLLS = re.compile(r'(\d+)\s+rolls?', re.IGNORECASE)
_P_FL_OZ = re.compile(r'(\d+(?:\.\d+)?)\s+fl(?:uid)?\.?\s*oz', re.IGNORECASE)
_P_SHEETS = re.compile(r'(\d+)\s+sheets?', re.IGNORECASE)
_P_LOADS = re.compile(r'(\d+)\s+loads?', re.IGNORECASE)
_P_CT = re.compile(r'(\d+)\s+(?:ct|count)', re.IGNORECASE)
_P_BAGS = re.compile(r'(\d+)\s+bags?', re.IGNORECASE)
_P_WIPES = re.compile(r'(\d+)\s+wipes?', re.IGNORECASE)
_P_DIAPERS = re.compile(r'(\d+)\s+diapers?', re.IGNORECASE)
_P_OZ = re.compile(r'(\d+(?:\.\d+)?)\s+oz', re.IGNORECASE)
_P_PACK = re.compile(r'(\d+)\s+packs?(?!\s+of)', re.IGNORECASE)


def _stage2_extract_count(name: str, unit_desc: str) -> tuple[int, str] | None:
    """Return (count, canonical_label) or None."""
    text = f"{name} {unit_desc or ''}"

    # 1. "X pack of Y" → X*Y ct
    m = _P_PACK_OF.search(text)
    if m:
        return (int(m.group(1)) * int(m.group(2)), "ct")

    # 2. "X double/mega/... rolls" → X*multiplier roll
    m = _P_MARKETING_ROLLS.search(text)
    if m:
        n = int(m.group(1))
        modifier = m.group(2).strip().lower()
        multiplier = _ROLL_MULTIPLIERS.get(modifier, 1)
        return (n * multiplier, "roll")

    # 3. Plain rolls
    m = _P_PLAIN_ROLLS.search(text)
    if m:
        return (int(m.group(1)), "roll")

    # 4. fl oz (before plain oz)
    m = _P_FL_OZ.search(text)
    if m:
        return (max(1, int(float(m.group(1)))), "fl oz")

    # 5. sheets
    m = _P_SHEETS.search(text)
    if m:
        return (int(m.group(1)), "sheet")

    # 6. loads
    m = _P_LOADS.search(text)
    if m:
        return (int(m.group(1)), "load")

    # 7. ct / count
    m = _P_CT.search(text)
    if m:
        return (int(m.group(1)), "ct")

    # 8. bags
    m = _P_BAGS.search(text)
    if m:
        return (int(m.group(1)), "bag")

    # 9. wipes
    m = _P_WIPES.search(text)
    if m:
        return (int(m.group(1)), "wipe")

    # 10. diapers
    m = _P_DIAPERS.search(text)
    if m:
        return (int(m.group(1)), "diaper")

    # 11. plain oz
    m = _P_OZ.search(text)
    if m:
        return (max(1, int(float(m.group(1)))), "oz")

    # 12. pack (no "of Y")
    m = _P_PACK.search(text)
    if m:
        return (int(m.group(1)), "pack")

    return None


# ---------------------------------------------------------------------------
# Public entry point — synchronous, no I/O
# ---------------------------------------------------------------------------

def normalize_product(raw: RawProduct) -> dict:
    """
    Parse price/unit from a RawProduct using regex heuristics.

    Returns a dict with keys:
        price_usd   float | None
        unit_count  int | None
        unit_label  str | None
        unit_price  float | None
        confidence  "high" | "medium" | "low"
    """
    price_usd = _parse_price_str(raw.price_str)

    # Stage 1: retailer-provided unit price in unit_desc
    result1 = _stage1_parse_unit_price(raw.unit_desc)
    if result1 is not None:
        unit_price, unit_label = result1
        unit_count = round(price_usd / unit_price) if price_usd and unit_price > 0 else None
        return {
            "price_usd": price_usd,
            "unit_count": unit_count,
            "unit_label": unit_label,
            "unit_price": round(unit_price, 6),
            "confidence": "high",
        }

    # Stage 2: extract count from name + unit_desc, then calculate
    result2 = _stage2_extract_count(raw.name, raw.unit_desc)
    if result2 is not None and price_usd:
        count, unit_label = result2
        if count > 0:
            return {
                "price_usd": price_usd,
                "unit_count": count,
                "unit_label": unit_label,
                "unit_price": round(price_usd / count, 6),
                "confidence": "medium",
            }

    # Stage 3: cannot determine unit price
    return {
        "price_usd": price_usd,
        "unit_count": None,
        "unit_label": None,
        "unit_price": None,
        "confidence": "low",
    }
