from dataclasses import dataclass, field


@dataclass
class RawProduct:
    retailer: str
    name: str
    price_str: str      # e.g. "$12.99" — raw, unparsed
    unit_desc: str      # e.g. "8 double rolls = 160 sheets" or "64 fl oz"
    url: str
    in_stock: bool = True
