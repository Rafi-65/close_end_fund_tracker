"""
storage.py
----------
Output layer for the CEF NAV Model pipeline.

  - build_dataframe(records)       : assemble records into a DataFrame
  - export_snapshot(df, fmt, path) : save timestamped CSV or JSON snapshot
"""

import logging
import os
from datetime import datetime, timezone

import pandas as pd

from config import OUTPUT_DIR

logger = logging.getLogger(__name__)

# Column order for the final DataFrame
COLUMNS = [
    "Ticker",
    "Mkt_Price",
    "Total_Assets",
    "Total_Liabilities",
    "Shares_Outstanding",
    "NAV",
    "NAV_Source",
    "Disc_Prem_Pct",
    "Z_Score",
    "NAV_Date",
    "Price_Invalid",
    "NAV_Stale",
    "NAV_Missing",
    "Timestamp",
]


# ---------------------------------------------------------------------------
# DataFrame assembly
# ---------------------------------------------------------------------------

def build_dataframe(records: list[dict]) -> pd.DataFrame:
    """
    Convert a list of per-ticker result dicts into a tidy DataFrame.

    Expected keys per record (any missing key defaults to None):
        Ticker, Mkt_Price, NAV, Disc_Prem_Pct, Z_Score,
        NAV_Date, Price_Invalid, NAV_Stale, NAV_Missing, Timestamp
    """
    if not records:
        logger.warning("build_dataframe called with empty records list")
        return pd.DataFrame(columns=COLUMNS)

    df = pd.DataFrame(records)

    # Ensure all expected columns exist
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None

    df = df[COLUMNS]

    # Type coercions
    for num_col in ["Mkt_Price", "Total_Assets", "Total_Liabilities",
                    "Shares_Outstanding", "NAV", "Disc_Prem_Pct", "Z_Score"]:
        df[num_col] = pd.to_numeric(df[num_col], errors="coerce")

    for bool_col in ["Price_Invalid", "NAV_Stale", "NAV_Missing"]:
        df[bool_col] = df[bool_col].astype(bool)

    logger.info("DataFrame assembled: %d rows × %d cols", len(df), len(df.columns))
    return df


# ---------------------------------------------------------------------------
# Export snapshot
# ---------------------------------------------------------------------------

def export_snapshot(
    df: pd.DataFrame,
    fmt: str = "csv",
    output_dir: str = OUTPUT_DIR,
) -> str:
    """
    Write a timestamped snapshot of *df* to *output_dir*.

    Parameters
    ----------
    df         : DataFrame produced by build_dataframe()
    fmt        : "csv" (default) or "json"
    output_dir : destination directory (created if needed)

    Returns
    -------
    str : absolute path of the file that was written
    """
    fmt = fmt.lower().strip()
    if fmt not in ("csv", "json"):
        raise ValueError(f"Unsupported format '{fmt}'. Choose 'csv' or 'json'.")

    os.makedirs(output_dir, exist_ok=True)

    timestamp_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"cef_snapshot_{timestamp_str}.{fmt}"
    filepath = os.path.join(output_dir, filename)

    if fmt == "csv":
        df.to_csv(filepath, index=False)
    else:
        df.to_json(filepath, orient="records", indent=2, date_format="iso")

    logger.info("Snapshot exported → %s", filepath)
    return filepath


# ---------------------------------------------------------------------------
# Pretty print to stdout
# ---------------------------------------------------------------------------

def print_summary(df: pd.DataFrame) -> None:
    """Print a formatted summary table to the terminal."""
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 180)
    pd.set_option("display.float_format", "{:.4f}".format)

    display_cols = ["Ticker", "Mkt_Price", "NAV", "NAV_Source", "Disc_Prem_Pct",
                    "Z_Score", "Price_Invalid", "NAV_Stale", "NAV_Missing"]
    subset = df[[c for c in display_cols if c in df.columns]]

    print("\n" + "=" * 90)
    print("  CEF NAV RELATIVE-VALUE MODEL  —  Snapshot")
    print("=" * 90)
    print(subset.to_string(index=False))
    print("=" * 90 + "\n")
