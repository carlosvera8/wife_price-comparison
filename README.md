# wife_price-comparison

Compares household product prices across Walmart, Target, and Giant Food by ZIP code. Recommends the best value per unit.

## Setup

### 1. Install Python dependencies

```bash
py -m pip install playwright rich python-dotenv pyyaml curl_cffi
```

### 2. Install the Chromium browser (used for scraping)

```bash
py -m playwright install chromium
```

### 3. Copy the environment file

```bash
cp .env.example .env
```

No changes to `.env` are needed — the defaults work out of the box.

## Running

```bash
py compare.py "paper towels" --zip 19103
```

### Options

| Flag | Description |
|------|-------------|
| `--zip` | **(Required)** ZIP code for store location |
| `--retailers` | Limit to specific stores: `walmart`, `target`, `giant_food` |
| `--max-results` | Products per retailer (default: `3`) |
| `--headful` | Show the browser window (useful for debugging) |
| `--mock` | Use fake data — no scraping, useful for testing output |

### Examples

```bash
# Single retailer
py compare.py "laundry detergent" --zip 10001 --retailers walmart

# More results
py compare.py "dish soap" --zip 90210 --max-results 5

# Debug a scraping issue
py compare.py "paper towels" --zip 19103 --headful

# Test output without scraping
py compare.py "paper towels" --zip 19103 --mock
```

## Example Output

```
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

**Conf.** = confidence in the unit calculation: **H** high, **M** medium, **L** low.

## Notes

- **Walmart** uses aggressive bot detection and may block requests. Retry or use `--headful` to debug.
- **Target** is scraped via their internal JSON API — no browser needed.
- **Giant Food** uses DOM scraping — most likely to break if their site layout changes.
- Prices reflect the nearest store to your ZIP code at the time of the search.
