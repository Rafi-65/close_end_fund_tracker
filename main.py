"""
main.py
-------
Orchestrator for the CEF NAV Model pipeline.

Usage
-----
    # Run with default tickers (from config.py):
    python main.py

    # Custom tickers and JSON output:
    python main.py --tickers PDI BST UTF --fmt json

    # Override output directory:
    python main.py --output-dir /path/to/my/output
"""

import argparse
import logging
import sys
from datetime import datetime, timezone

from config import TICKERS
from model import build_hist_discounts, calc_premium_discount, calc_z_score, validate_row
from scraper import fetch_historical_prices, fetch_market_price, fetch_nav
from storage import build_dataframe, export_snapshot, print_summary

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("cef_pipeline.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")


# ---------------------------------------------------------------------------
# Per-ticker processing
# ---------------------------------------------------------------------------

def process_ticker(ticker: str) -> dict:
    """
    Run the full ingestion → model → validation pipeline for one *ticker*.
    Returns a flat dict suitable for storage.build_dataframe().
    All exceptions are caught and re-raised so the caller can log & skip.
    """
    ticker = ticker.upper().strip()
    logger.info("── Processing %s ──", ticker)

    # 1. Market price (yfinance)
    mkt_data = fetch_market_price(ticker)
    price: float | None = mkt_data["price"]

    # 2. NAV (CEFConnect scrape)
    nav_data = fetch_nav(ticker)
    nav: float | None = nav_data["nav"]
    nav_date = nav_data["nav_date"]

    # 3. Premium / discount
    disc_prem = calc_premium_discount(price, nav) if (price and nav) else None

    # 4. Z-score — build from historical price series
    z_score = None
    if nav:
        hist_prices = fetch_historical_prices(ticker, period="1y")
        if hist_prices:
            hist_discounts = build_hist_discounts(hist_prices, nav)
            if disc_prem is not None and hist_discounts:
                z_score = calc_z_score(disc_prem, hist_discounts)

    # 5. Validation
    flags = validate_row(ticker, price, nav, nav_date)

    return {
        "Ticker": ticker,
        "Mkt_Price": price,
        "NAV": nav,
        "Disc_Prem_Pct": disc_prem,
        "Z_Score": z_score,
        "NAV_Date": nav_date.isoformat() if nav_date else None,
        "Price_Invalid": flags["price_invalid"],
        "NAV_Stale": flags["nav_stale"],
        "NAV_Missing": flags["nav_missing"],
        "Timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(tickers: list[str], fmt: str = "csv", output_dir: str | None = None) -> None:
    """
    Iterate over *tickers*, collect results, build DataFrame, export snapshot.

    Any per-ticker error is logged and skipped — the pipeline never aborts.
    """
    logger.info("Starting CEF NAV pipeline for %d tickers: %s", len(tickers), tickers)

    records: list[dict] = []
    failed: list[str] = []

    for ticker in tickers:
        try:
            record = process_ticker(ticker)
            records.append(record)
        except Exception as exc:  # noqa: BLE001
            logger.error("[%s] Pipeline error — skipping: %s", ticker, exc, exc_info=True)
            failed.append(ticker)

    if not records:
        logger.error("All tickers failed — no data to export.")
        return

    # Assemble & display
    df = build_dataframe(records)
    print_summary(df)

    # Export
    kwargs = {} if output_dir is None else {"output_dir": output_dir}
    output_path = export_snapshot(df, fmt=fmt, **kwargs)
    logger.info("Pipeline complete. Output: %s", output_path)

    if failed:
        logger.warning("Failed tickers (no data): %s", failed)

    print(f"\n✅  Snapshot saved → {output_path}")
    if failed:
        print(f"⚠️   Skipped (errors): {failed}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CEF NAV Relative-Value Model Pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=TICKERS,
        metavar="TICKER",
        help="Space-separated list of CEF ticker symbols.",
    )
    parser.add_argument(
        "--fmt",
        choices=["csv", "json"],
        default="csv",
        help="Output file format.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        metavar="DIR",
        help="Directory for exported snapshots (default: ./output/).",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    run_pipeline(
        tickers=args.tickers,
        fmt=args.fmt,
        output_dir=args.output_dir,
    )
