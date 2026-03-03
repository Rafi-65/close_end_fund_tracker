# CEF NAV Relative-Value Model

An automated Python pipeline that scrapes **Closed-End Fund (CEF)** market prices and Net Asset Values, computes premium/discount percentages and 1-year Z-scores, validates data integrity, and exports daily snapshots for historical tracking.

---

## Features

- **Market Data** — Fetches last closing prices via `yfinance`
- **NAV Scraping** — Extracts daily NAV from [CEFConnect.com](https://www.cefconnect.com) using BeautifulSoup with randomised User-Agent headers and polite request delays
- **Premium / Discount %** — `((Market Price − NAV) / NAV) × 100`
- **1-Year Z-Score** — Shows how the current discount compares to its trailing 252-day average
- **Validation Flags** — Alerts when a price is zero or a NAV reading is older than 48 hours
- **Resilient Pipeline** — Per-ticker `try/except` ensures one failure never crashes the run
- **CSV / JSON Export** — Timestamped snapshots saved to `output/`

---

## Default Ticker Universe

| Ticker | Fund |
|--------|------|
| PDI | PIMCO Dynamic Income Fund |
| BST | BlackRock Science and Technology Trust |
| UTF | Cohen & Steers Infrastructure Fund |
| AWP | abrdn Global Premier Properties Fund |
| ECC | Eagle Point Credit Company |
| GOF | Guggenheim Strategic Opportunities Fund |
| PTY | PIMCO Corporate & Income Opportunity Fund |
| RQI | Cohen & Steers Quality Income Realty Fund |
| EVN | Eaton Vance Municipal Income Trust |
| HYT | BlackRock Corporate High Yield Fund |

Edit `TICKERS` in `config.py` or pass `--tickers` on the command line to customise.

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/Rafi-65/close_end_fund_tracker.git
cd close_end_fund_tracker
pip install -r requirements.txt
```

### 2. Run

```bash
# Default 10 tickers → CSV
python main.py

# Custom tickers → JSON
python main.py --tickers PDI BST UTF GOF --fmt json

# Custom output directory
python main.py --output-dir ~/my_cef_data
```

### 3. Output

A summary table is printed to the terminal:

```
==========================================================================================
  CEF NAV RELATIVE-VALUE MODEL  —  Snapshot
==========================================================================================
Ticker  Mkt_Price     NAV  Disc_Prem_Pct  Z_Score  Price_Invalid  NAV_Stale  NAV_Missing
   PDI    18.0000 23.8500       -24.5283   0.6370          False      False        False
   BST    40.2700 19.0600       111.2802   1.0895          False      False        False
==========================================================================================
```

The full data (including timestamps) is saved to `output/cef_snapshot_YYYYMMDD_HHMMSS.csv`.

---

## Project Structure

```
CEF models/
├── config.py          # Tickers, User-Agent pool, constants
├── scraper.py         # yfinance prices + CEFConnect NAV scraper
├── model.py           # Discount/Premium %, Z-Score, validation
├── storage.py         # DataFrame assembly, CSV/JSON export
├── main.py            # CLI orchestrator
├── requirements.txt   # Dependencies
├── cef_pipeline.log   # Runtime log (auto-generated)
├── WALKTHROUGH.md     # Technical deep-dive
└── output/            # Timestamped snapshot files
```

---

## Output Columns

| Column | Description |
|--------|-------------|
| `Ticker` | CEF ticker symbol |
| `Mkt_Price` | Latest market closing price (yfinance) |
| `NAV` | Net Asset Value (CEFConnect) |
| `Disc_Prem_Pct` | Premium (+) or Discount (−) percentage |
| `Z_Score` | 1-year Z-score of current discount vs. trailing average |
| `NAV_Date` | As-of date for the NAV reading |
| `Price_Invalid` | `True` if price ≤ 0 or missing |
| `NAV_Stale` | `True` if NAV is older than 48 hours |
| `NAV_Missing` | `True` if NAV could not be scraped |
| `Timestamp` | UTC timestamp of this pipeline run |

---

## Configuration

All tuneable parameters live in `config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `TICKERS` | 10 CEFs | List of ticker symbols to process |
| `REQUEST_DELAY_SECONDS` | 3.0 | Sleep between web requests |
| `REQUEST_TIMEOUT_SECONDS` | 15 | HTTP timeout per request |
| `ZSCORE_LOOKBACK_DAYS` | 252 | Trading days for Z-score window |
| `NAV_STALENESS_HOURS` | 48 | Threshold to flag stale NAV data |

---

## Dependencies

- Python 3.10+
- `yfinance` — market price data
- `beautifulsoup4` + `lxml` — HTML parsing
- `requests` — HTTP client
- `pandas` — DataFrame operations
- `numpy` — Z-score statistics

---

## License

MIT
