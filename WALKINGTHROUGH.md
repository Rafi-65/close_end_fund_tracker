# Walkthrough — CEF NAV Relative-Value Model

A technical deep-dive into the pipeline architecture, data flow, and design rationale.

---

## Pipeline Data Flow

```
main.py (orchestrator)
  │
  ├── For each ticker:
  │     │
  │     ├── scraper.fetch_market_price(ticker)
  │     │     └── yfinance → latest closing price
  │     │
  │     ├── scraper.fetch_nav(ticker)
  │     │     └── HTTP GET CEFConnect.com → BeautifulSoup parse → NAV + date
  │     │
  │     ├── model.calc_premium_discount(price, nav)
  │     │     └── ((price − nav) / nav) × 100
  │     │
  │     ├── scraper.fetch_historical_prices(ticker, "1y")
  │     │     └── yfinance → 252 daily closes
  │     │
  │     ├── model.build_hist_discounts(hist_prices, nav)
  │     │     └── approximate historical discount series
  │     │
  │     ├── model.calc_z_score(current_disc, hist_discounts)
  │     │     └── (current − mean) / std
  │     │
  │     └── model.validate_row(ticker, price, nav, nav_date)
  │           └── price_invalid / nav_stale / nav_missing flags
  │
  ├── storage.build_dataframe(records)
  ├── storage.print_summary(df)
  └── storage.export_snapshot(df, fmt)
```

---

## Module Breakdown

### `config.py`

Centralises all tuneable parameters so nothing is hard-coded in logic modules:
- **Ticker universe** — easily add/remove funds
- **User-Agent pool** — 5 browser strings rotated randomly per request
- **Model constants** — Z-score lookback (252 days), NAV staleness (48 h)
- **Output directory** — auto-created on import

### `scraper.py`

Two data sources with distinct strategies:

**Market price** (`fetch_market_price`):
- Uses `yfinance.Ticker.history(period="2d")` to get the last available close
- Falls back gracefully if yfinance returns empty data

**NAV** (`fetch_nav`):
- Targets `https://www.cefconnect.com/fund/{TICKER}`
- **3-strategy parser** ensures resilience to page layout changes:
  1. **JSON embeds** — searches `<script>` tags for `"nav": 12.34` patterns
  2. **DOM traversal** — finds labels containing "NAV" and reads sibling elements
  3. **Regex fallback** — scans full page text for `NAV ... $XX.XX`
- Polite scraping: 3-second delay before each request, randomised User-Agent, progressive back-off on retries

**Historical prices** (`fetch_historical_prices`):
- 1-year daily closes via yfinance, used for Z-score calculation

### `model.py`

**Premium / Discount %:**
```
((Market Price − NAV) / NAV) × 100
```
- Positive = trading at a premium
- Negative = trading at a discount

**Z-Score:**
```
Z = (current_discount − mean) / std_dev
```
- Uses trailing 252 trading days (~1 year)
- Requires minimum 30 observations for statistical reliability
- Returns 0 on zero-variance series (constant discount)

**Historical discount approximation:**
- Since historical NAVs aren't freely available intraday, the pipeline applies today's NAV across all 252 historical price points
- This is a practical trade-off; replace `build_hist_discounts()` with a time-series NAV feed for higher accuracy

**Validation:**
- `price_invalid` — market price is `None`, zero, or negative
- `nav_stale` — NAV date is more than 48 hours old (or unknown)
- `nav_missing` — NAV could not be scraped at all

### `storage.py`

- Assembles records into a typed Pandas DataFrame (numeric coercion, boolean flags)
- Exports timestamped files: `cef_snapshot_20260303_131612.csv`
- Pretty-prints a summary table to the terminal

### `main.py`

- CLI via `argparse` with `--tickers`, `--fmt`, and `--output-dir`
- **Per-ticker try/except** — logs the error with full traceback and moves to the next ticker
- Dual logging: stdout + `cef_pipeline.log` file
- Summary of failed tickers printed at the end

---

## Anti-Blocking Measures

| Technique | Implementation |
|-----------|----------------|
| Randomised User-Agent | 5-string pool, selected per request |
| Request delay | 3-second `time.sleep()` before each CEFConnect call |
| Progressive back-off | Retry delay = `3s × attempt_number` |
| Standard headers | `Accept`, `Accept-Language`, `Connection` mimic real browsers |

---

## Error Handling Strategy

```
for ticker in tickers:
    try:
        record = process_ticker(ticker)   # full pipeline
        records.append(record)
    except Exception as exc:
        logger.error("[%s] Pipeline error — skipping: %s", ticker, exc)
        failed.append(ticker)
```

- Individual scraper/model functions also have internal try/except
- Errors are logged to both stdout and `cef_pipeline.log`
- The pipeline always produces output for whatever tickers succeeded

---

## Extending the Pipeline

| Enhancement | Where to modify |
|-------------|----------------|
| Add tickers | `config.py` → `TICKERS` list |
| Switch to Selenium | Replace `_get_with_retry()` in `scraper.py` |
| Historical NAV feed | Replace `build_hist_discounts()` in `model.py` |
| Database storage | Add a `db.py` module; call from `main.py` after `export_snapshot()` |
| Scheduling (cron) | `crontab -e` → `0 18 * * 1-5 python /path/to/main.py` |
| Email alerts | Add post-export hook in `main.py` for high Z-score tickers |
