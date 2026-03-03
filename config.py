"""
config.py
---------
Central configuration for the CEF NAV Model pipeline.
Edit this file to change tickers, file paths, or scraping behaviour.
"""

import os

# ---------------------------------------------------------------------------
# Ticker universe
# ---------------------------------------------------------------------------
TICKERS: list[str] = [
    "PDI",   # PIMCO Dynamic Income Fund
    "BST",   # BlackRock Science and Technology Trust
    "UTF",   # Cohen & Steers Infrastructure Fund
    "AWP",   # abrdn Global Premier Properties Fund
    "ECC",   # Eagle Point Credit Company
    "GOF",   # Guggenheim Strategic Opportunities Fund
    "PTY",   # PIMCO Corporate & Income Opportunity Fund
    "RQI",   # Cohen & Steers Quality Income Realty Fund
    "EVN",   # Eaton Vance Municipal Income Trust
    "HYT",   # BlackRock Corporate High Yield Fund
]

# ---------------------------------------------------------------------------
# CEFConnect URL template
# ---------------------------------------------------------------------------
CEFCONNECT_BASE = "https://www.cefconnect.com/fund/{ticker}"

# ---------------------------------------------------------------------------
# HTTP request settings
# ---------------------------------------------------------------------------
REQUEST_DELAY_SECONDS: float = 3.0   # sleep between web requests
REQUEST_TIMEOUT_SECONDS: int = 15

# Rotate headers on every request to reduce blocking risk
USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

# ---------------------------------------------------------------------------
# Model constants
# ---------------------------------------------------------------------------
# Number of trading days used to compute the rolling Z-score window (≈1 year)
ZSCORE_LOOKBACK_DAYS: int = 252

# Maximum age of a NAV reading before it is flagged as stale
NAV_STALENESS_HOURS: int = 48

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
