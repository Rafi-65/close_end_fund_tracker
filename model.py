"""
model.py
--------
Quantitative model logic for the CEF NAV pipeline.

  - calc_nav               : (total_assets - total_liabilities) / shares_outstanding
  - calc_premium_discount  : ((price - nav) / nav) * 100
  - calc_z_score           : rolling 1-year Z-score of premium/discount
  - build_hist_discounts   : assemble a historical discount series from prices
  - validate_row           : data-integrity flags
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from config import NAV_STALENESS_HOURS, ZSCORE_LOOKBACK_DAYS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core calculations
# ---------------------------------------------------------------------------

def calc_nav(
    total_assets: Optional[float],
    total_liabilities: Optional[float],
    shares_outstanding: Optional[float],
) -> Optional[float]:
    """
    Calculate Net Asset Value (NAV) per share from fundamental data.

    Formula:  NAV = (Total Assets − Total Liabilities) / Shares Outstanding

    Parameters
    ----------
    total_assets        : fund's total assets in currency units
    total_liabilities   : fund's total liabilities in currency units
    shares_outstanding  : number of shares currently outstanding

    Returns
    -------
    float  — NAV per share, rounded to 4 decimal places
    None   — if any input is missing or shares_outstanding is zero
    """
    if total_assets is None or total_liabilities is None or shares_outstanding is None:
        logger.warning(
            "calc_nav: missing input(s) — assets=%s, liabilities=%s, shares=%s",
            total_assets, total_liabilities, shares_outstanding,
        )
        return None

    if shares_outstanding == 0:
        logger.warning("calc_nav: shares_outstanding is zero — cannot compute NAV")
        return None

    nav = (total_assets - total_liabilities) / shares_outstanding
    logger.info(
        "calc_nav: assets=%.2f, liabilities=%.2f, shares=%.0f → NAV=%.4f",
        total_assets, total_liabilities, shares_outstanding, nav,
    )
    return round(nav, 4)


def calc_premium_discount(price: float, nav: float) -> Optional[float]:
    """
    Compute premium (+) or discount (−) percentage.

    Formula: ((Market Price − NAV) / NAV) × 100

    Returns None if inputs are invalid.
    """
    if not price or not nav or nav == 0:
        logger.warning("calc_premium_discount: invalid inputs price=%s nav=%s", price, nav)
        return None
    return round(((price - nav) / nav) * 100, 4)


def calc_z_score(
    current_disc: float,
    historical_discounts: list[float],
    lookback: int = ZSCORE_LOOKBACK_DAYS,
) -> Optional[float]:
    """
    Calculate the Z-score of *current_disc* relative to the trailing
    1-year window of *historical_discounts*.

    Z = (current − mean) / std

    Returns None when the series is too short or has zero variance.
    """
    if not historical_discounts:
        logger.warning("calc_z_score: empty historical discount series")
        return None

    window = historical_discounts[-lookback:]  # most-recent N obs
    if len(window) < 30:  # need a minimum sample
        logger.warning(
            "calc_z_score: only %d observations — Z-score may be unreliable",
            len(window),
        )

    arr = np.array(window, dtype=float)
    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1))

    if std == 0:
        logger.warning("calc_z_score: zero variance in discount series — returning 0")
        return 0.0

    return round((current_disc - mean) / std, 4)


def build_hist_discounts(
    hist_prices: list[float],
    current_nav: float,
) -> list[float]:
    """
    Approximate the historical discount series by applying the *current_nav*
    uniformly across all historical price points.

    This is a practical approximation when intraday historical NAVs are
    unavailable.  For higher accuracy, replace with a time-series NAV feed.

    Parameters
    ----------
    hist_prices   : list of daily closing prices (oldest → newest)
    current_nav   : today's NAV used as the denominator

    Returns
    -------
    list[float] of daily premium/discount percentages
    """
    if not hist_prices or current_nav == 0:
        return []

    discounts = []
    for price in hist_prices:
        disc = calc_premium_discount(price, current_nav)
        if disc is not None:
            discounts.append(disc)
    return discounts


# ---------------------------------------------------------------------------
# Data integrity validation
# ---------------------------------------------------------------------------

def validate_row(
    ticker: str,
    price: Optional[float],
    nav: Optional[float],
    nav_date: Optional[datetime],
) -> dict:
    """
    Run integrity checks and return a dict of flags.

    Flags (bool):
        price_invalid  — True if price is None or ≤ 0
        nav_stale      — True if nav_date is older than NAV_STALENESS_HOURS
        nav_missing    — True if nav is None
    """
    now = datetime.now(tz=timezone.utc)
    flags: dict[str, bool] = {
        "price_invalid": False,
        "nav_stale": False,
        "nav_missing": False,
    }

    if price is None or price <= 0:
        flags["price_invalid"] = True
        logger.warning("[%s] VALIDATION FAIL: market price is %s", ticker, price)

    if nav is None:
        flags["nav_missing"] = True
        logger.warning("[%s] VALIDATION FAIL: NAV is missing", ticker)

    if nav_date is not None:
        age_hours = (now - nav_date).total_seconds() / 3600
        if age_hours > NAV_STALENESS_HOURS:
            flags["nav_stale"] = True
            logger.warning(
                "[%s] VALIDATION FAIL: NAV is %.1f hours old (threshold %dh)",
                ticker,
                age_hours,
                NAV_STALENESS_HOURS,
            )
    else:
        # No date at all — treat as stale
        flags["nav_stale"] = True
        logger.warning("[%s] VALIDATION FAIL: NAV date is unknown", ticker)

    return flags
