# wife_price-comparison

A CLI tool that compares household product prices across retailers (Walmart, Target, Giant Food) by ZIP code and recommends the best value per unit.

## Example

```
$ python compare.py "paper towels" --zip 19103

Product: Paper Towels
ZIP:     19103

╭──────────────┬────────────────────────────────────────┬─────────┬──────────────────┬───────┬───────╮
│ Retailer     │ Product                                │   Price │ Unit Price       │ Units │ Conf. │
├──────────────┼────────────────────────────────────────┼─────────┼──────────────────┼───────┼───────┤
│ Target       │ Bounty Select-A-Size 8 Double Plus Ro… │  $14.99 │ $0.0101/sheet    │  1480 │ H     │
│ Walmart      │ Bounty Select-A-Size 12 Double Rolls   │  $19.94 │ $0.0092/sheet    │  2160 │ H     │
│ Giant Food   │ Brawny Pick-A-Size 6 Giant Rolls       │   $9.99 │ $0.0139/sheet    │   720 │ M     │
╰──────────────┴────────────────────────────────────────┴─────────┴──────────────────┴───────┴───────╯

BEST VALUE: Walmart — Bounty Select-A-Size 12 Double Rolls ($0.0092/sheet)
```

## How It Works

1. **Scraping** — Playwright (headless Chromium) hits each retailer's site with your ZIP code to get location-specific prices. It intercepts the retailers' internal JSON API calls rather than scraping HTML, making it more resilient to layout changes.
2. **Unit parsing** — Raw product descriptions (e.g. "8 Double Plus Rolls") are sent to Claude (Haiku) which converts marketing units to standard units (sheets, loads, fl oz) and calculates price/unit.
3. **Comparison** — Results are sorted by unit price and displayed in a table. The best value is highlighted.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure your API key

```bash
cp .env.example .env
```

Edit `.env` and set your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Get a key at [console.anthropic.com](https://console.anthropic.com).

## Usage

```bash
# Compare across all retailers
python compare.py "paper towels" --zip 19103

# Limit to specific retailers
python compare.py "laundry detergent" --zip 10001 --retailers walmart target

# Show more results per retailer (default: 3)
python compare.py "dish soap" --zip 90210 --max-results 5

# Show the browser window while scraping (useful for debugging)
python compare.py "paper towels" --zip 19103 --headful

# Run with mock data — no scraping, no API key needed
python compare.py "paper towels" --zip 19103 --mock
```

### Available retailer IDs

| ID           | Store       |
|--------------|-------------|
| `walmart`    | Walmart     |
| `target`     | Target      |
| `giant_food` | Giant Food  |

## Adding a New Retailer

1. Add an entry to `config/retailers.yaml`:
   ```yaml
   - id: whole_foods
     name: "Whole Foods"
     class: WholeFoodsScraper
     base_url: "https://www.wholefoodsmarket.com"
     enabled: true
     request_delay_ms: 2000
   ```
2. Create `scrapers/whole_foods.py` implementing `BaseScraper` (see `scrapers/base.py`).
3. Register it in `scrapers/__init__.py`.

No changes to `orchestrator.py` are needed.

## Configuration

| Variable                    | Default  | Description                              |
|-----------------------------|----------|------------------------------------------|
| `ANTHROPIC_API_KEY`         | required | Your Anthropic API key                   |
| `PLAYWRIGHT_HEADLESS`       | `true`   | Set to `false` to show the browser       |
| `REQUEST_TIMEOUT_MS`        | `30000`  | Per-request timeout in milliseconds      |
| `MAX_PRODUCTS_PER_RETAILER` | `3`      | Default max results per retailer         |

## Notes

- **Walmart** uses Akamai Bot Manager and is the most likely to block automated requests. Use `--headful` to debug.
- **Target's** internal API key is embedded in their public frontend. If it stops working, open target.com in browser devtools and grab the new `key=` value from any `/v3/plp/search` network request.
- **Giant Food** falls back to DOM scraping since their API is not easily accessible — selectors may need updating if their site changes.
- Prices are location-specific and change frequently. Results reflect the nearest store to your ZIP code at the time of the search.
- Unit confidence is shown as **H** (high), **M** (medium), or **L** (low) based on how clearly the product description stated the unit count.
