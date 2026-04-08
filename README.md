# wife_price-comparison

Compares household product prices across Google Shopping results by ZIP code. Recommends the best value per unit.

## Setup

### 1. Install Python dependencies

```bash
py -m pip install -r requirements.txt
```

### 2. Get a free SerpAPI key

Sign up at [serpapi.com](https://serpapi.com/) — the free tier gives you 100 searches/month, which is plenty for daily personal use.

### 3. Add your API key

```bash
cp .env.example .env
```

Then open `.env` and replace `your_serpapi_key_here` with your actual key:

```
SERPAPI_KEY=abc123yourkeyhere
```

## Running

```bash
py compare.py "paper towels" --zip YOUR_ZIP
```

### Options

| Flag | Description |
|------|-------------|
| `--zip` | **(Required)** ZIP code for local pricing |
| `--retailers` | Filter to specific stores: `walmart`, `target`, `costco`, `"giant food"` |
| `--max-results` | Max results to show (per retailer when `--retailers` is set, total otherwise). Default: `3` |
| `--mock` | Use fake data — no API call, useful for testing output |
| `--debug` | Print detailed logs |

### Examples

```bash
# Basic search
py compare.py "paper towels" --zip YOUR_ZIP

# Filter to specific retailers
py compare.py "laundry detergent" --zip YOUR_ZIP --retailers walmart target

# Multi-word retailer name
py compare.py "dish soap" --zip YOUR_ZIP --retailers "giant food"

# More results
py compare.py "dish soap" --zip YOUR_ZIP --max-results 5

# Test output without using an API credit
py compare.py "paper towels" --zip YOUR_ZIP --mock
```

## Example Output

```
Product: Paper Towels
ZIP:     YOUR_ZIP

╭──────────────┬────────────────────────────────────────┬─────────┬──────────────────┬───────┬───────╮
│ Retailer     │ Product                                │   Price │ Unit Price       │ Units │ Conf. │
├──────────────┼────────────────────────────────────────┼─────────┼──────────────────┼───────┼───────┤
│ Walmart      │ Bounty Select-A-Size 12 Double Rolls   │  $19.94 │ $0.0092/sheet    │  2160 │ H     │
│ Target       │ Bounty Select-A-Size 8 Double Plus Ro… │  $14.99 │ $0.0101/sheet    │  1480 │ H     │
│ Giant Food   │ Brawny Pick-A-Size 6 Giant Rolls       │   $9.99 │ $0.0139/sheet    │   720 │ M     │
╰──────────────┴────────────────────────────────────────┴─────────┴──────────────────┴───────┴───────╯

BEST VALUE: Walmart — Bounty Select-A-Size 12 Double Rolls ($0.0092/sheet)
```

**Conf.** = confidence in the unit calculation: **H** high, **M** medium, **L** low.

## Notes

- Results come from Google Shopping via SerpAPI — no browser scraping, no bot detection issues.
- Prices reflect what Google Shopping shows for your ZIP code at the time of the search.
- Each search uses 1 API credit. The free tier (100/month) is enough for several searches per day.
