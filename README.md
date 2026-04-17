# wife_price-comparison

Compares household product prices across Google Shopping results by ZIP code. Recommends the best value per unit.

Available as a **mobile-friendly web app** (install to home screen on iOS/Android) or a classic **command-line tool**.

---

## Mobile App (Recommended)

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Get a free SerpAPI key

Sign up at [serpapi.com](https://serpapi.com/) — the free tier gives you 100 searches/month.

### 3. Add your API key

```bash
cp .env.example .env
# open .env and fill in your SERPAPI_KEY
```

### 4. Start the server

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

### 5. Open on your phone

On any phone connected to the same Wi-Fi, open:

```
http://<your-computer-ip>:8000
```

> **Find your IP:** run `ipconfig` (Windows) or `ifconfig` (Mac/Linux) and look for your local address (e.g. `192.168.1.42`).

### 6. Install to home screen

**iPhone (Safari):** tap the Share button → "Add to Home Screen"

**Android (Chrome):** tap the three-dot menu → "Add to Home Screen"

The app will appear like any other app. Your ZIP code is remembered after the first search.

---

## Command-Line Tool

### Setup

```bash
py -m pip install -r requirements.txt
cp .env.example .env
# fill in your SERPAPI_KEY
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
