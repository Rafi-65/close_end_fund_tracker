"""
scraper.py
----------
Data ingestion layer for the CEF NAV Model pipeline.

  - fetch_market_price(ticker)  : last close via yfinance
  - fetch_nav(ticker)           : NAV + as-of date scraped from CEFConnect.com
"""

import logging
import random
import re
import time
from datetime import datetime, timezone
from typing import Optional

import requests
import yfinance as yf
from bs4 import BeautifulSoup

from config import (
    CEFCONNECT_BASE,
    REQUEST_DELAY_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    USER_AGENTS,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _random_headers() -> dict[str, str]:
    """Return an HTTP headers dict with a randomly selected User-Agent."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def _get_with_retry(url: str, retries: int = 3) -> Optional[requests.Response]:
    """GET *url* with randomised headers; retry up to *retries* times on failure."""
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                url,
                headers=_random_headers(),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if resp.status_code == 200:
                return resp
            logger.warning(
                "HTTP %s for %s (attempt %d/%d)",
                resp.status_code,
                url,
                attempt,
                retries,
            )
        except requests.RequestException as exc:
            logger.warning("Request error for %s (attempt %d/%d): %s", url, attempt, retries, exc)

        if attempt < retries:
            time.sleep(REQUEST_DELAY_SECONDS * attempt)  # progressive back-off

    return None


# ---------------------------------------------------------------------------
# Market price
# ---------------------------------------------------------------------------

def fetch_market_price(ticker: str) -> dict:
    """
    Fetch the latest market price for *ticker* using yfinance.

    Returns
    -------
    dict with keys:
        price  (float | None)
        source (str)
    """
    result = {"price": None, "source": "yfinance"}
    try:
        tkr = yf.Ticker(ticker)
        hist = tkr.history(period="2d")
        if not hist.empty:
            result["price"] = round(float(hist["Close"].iloc[-1]), 4)
            logger.info("Market price for %s: %s", ticker, result["price"])
        else:
            logger.warning("yfinance returned empty history for %s", ticker)
    except Exception as exc:  # noqa: BLE001
        logger.error("yfinance error for %s: %s", ticker, exc)

    return result


# ---------------------------------------------------------------------------
# NAV scraping — CEFConnect.com
# ---------------------------------------------------------------------------

def fetch_nav(ticker: str) -> dict:
    """
    Scrape the latest NAV and its as-of date from CEFConnect.com.

    CEFConnect renders its core data in the page HTML, so BeautifulSoup
    is sufficient.  The function applies a REQUEST_DELAY_SECONDS sleep
    BEFORE making the request to be polite to the server.

    Returns
    -------
    dict with keys:
        nav      (float | None)
        nav_date (datetime | None)   — timezone-aware UTC
        source   (str)
    """
    result = {"nav": None, "nav_date": None, "source": "CEFConnect"}

    url = CEFCONNECT_BASE.format(ticker=ticker.upper())
    logger.info("Sleeping %.1fs before scraping %s", REQUEST_DELAY_SECONDS, url)
    time.sleep(REQUEST_DELAY_SECONDS)

    resp = _get_with_retry(url)
    if resp is None:
        logger.error("Failed to fetch NAV page for %s", ticker)
        return result

    soup = BeautifulSoup(resp.text, "lxml")

    # -----------------------------------------------------------------------
    # CEFConnect page layout (as of early 2025):
    #   NAV value sits inside a <td> or <span> that follows a label containing
    #   "NAV" or "Net Asset Value".  We attempt multiple strategies.
    # -----------------------------------------------------------------------
    nav_value: Optional[float] = None
    nav_date_str: Optional[str] = None

    # Strategy 1: look for JSON-like data embedded in the page (common in
    #             JavaScript-rendered partials served as inline script data)
    scripts = soup.find_all("script")
    for script in scripts:
        text = script.string or ""
        # Match patterns like: "nav":12.34 or "Nav":12.34
        m_nav = re.search(r'"[Nn][Aa][Vv]"\s*:\s*([\d.]+)', text)
        m_date = re.search(
            r'"[Nn][Aa][Vv][Dd]ate"\s*:\s*"([^"]+)"',
            text,
            re.IGNORECASE,
        )
        if m_nav:
            nav_value = float(m_nav.group(1))
            if m_date:
                nav_date_str = m_date.group(1)
            break

    # Strategy 2: look for visible table/label → value pairs
    if nav_value is None:
        # Try to find a row/cell labelled "NAV" and take the adjacent value
        for tag in soup.find_all(string=re.compile(r"\bNAV\b|\bNet Asset Value\b", re.I)):
            parent = tag.find_parent()
            if parent is None:
                continue
            # sibling cell or span
            sibling = parent.find_next_sibling()
            if sibling:
                txt = sibling.get_text(strip=True).replace("$", "").replace(",", "")
                try:
                    nav_value = float(txt)
                    break
                except ValueError:
                    pass
            # look for a dollar amount within the parent's container
            container = parent.find_parent()
            if container:
                m = re.search(r"\$\s*([\d,]+\.[\d]{2})", container.get_text())
                if m:
                    try:
                        nav_value = float(m.group(1).replace(",", ""))
                        break
                    except ValueError:
                        pass

    # Strategy 3: generic dollar-amount regex on full page text (last resort)
    if nav_value is None:
        page_text = soup.get_text()
        # Find "NAV" followed closely by a dollar amount
        m = re.search(
            r"NAV[^$\d]{0,30}\$?\s*([\d,]+\.\d{2})",
            page_text,
            re.IGNORECASE,
        )
        if m:
            try:
                nav_value = float(m.group(1).replace(",", ""))
            except ValueError:
                pass

    # -----------------------------------------------------------------------
    # Parse date
    # -----------------------------------------------------------------------
    nav_date: Optional[datetime] = None
    if nav_date_str:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%m/%d/%Y", "%Y-%m-%d"):
            try:
                nav_date = datetime.strptime(nav_date_str, fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue

    if nav_date is None:
        # Default: assume today's date if we got a value
        if nav_value is not None:
            nav_date = datetime.now(tz=timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

    result["nav"] = nav_value
    result["nav_date"] = nav_date

    if nav_value is not None:
        logger.info("NAV for %s: %.4f (as of %s)", ticker, nav_value, nav_date)
    else:
        logger.warning("Could not parse NAV for %s from %s", ticker, url)

    return result


# ---------------------------------------------------------------------------
# Historical discount series (for Z-score calculation)
# ---------------------------------------------------------------------------

def fetch_historical_prices(ticker: str, period: str = "1y") -> list[float]:
    """
    Return a list of daily closing prices for *ticker* over *period*.
    Used by model.py to build the historical discount series.
    """
    try:
        tkr = yf.Ticker(ticker)
        hist = tkr.history(period=period)
        if hist.empty:
            logger.warning("Empty price history for %s", ticker)
            return []
        return [round(float(p), 4) for p in hist["Close"].tolist()]
    except Exception as exc:  # noqa: BLE001
        logger.error("Error fetching historical prices for %s: %s", ticker, exc)
        return []
