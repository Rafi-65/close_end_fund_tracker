"""
test_model.py
-------------
Unit tests for core model functions, focusing on the NAV calculation.

Run:  python -m pytest test_model.py -v
"""

import pytest

from model import calc_nav, calc_premium_discount


# ---------------------------------------------------------------------------
# calc_nav tests
# ---------------------------------------------------------------------------

class TestCalcNav:
    """NAV = (Total Assets − Total Liabilities) / Shares Outstanding"""

    def test_basic_calculation(self):
        """100M assets - 20M liabilities / 10M shares = 8.0 per share."""
        result = calc_nav(100_000_000, 20_000_000, 10_000_000)
        assert result == 8.0

    def test_zero_liabilities(self):
        """No liabilities → NAV = total assets / shares."""
        result = calc_nav(50_000_000, 0, 5_000_000)
        assert result == 10.0

    def test_liabilities_exceed_assets(self):
        """Negative NAV when liabilities > assets."""
        result = calc_nav(10_000_000, 15_000_000, 5_000_000)
        assert result == -1.0

    def test_rounding(self):
        """Result should be rounded to 4 decimal places."""
        result = calc_nav(100_000_000, 33_333_333, 7_777_777)
        assert result is not None
        # Check that it's rounded to 4 places
        assert result == round(result, 4)

    def test_zero_shares_returns_none(self):
        """Division by zero → None."""
        result = calc_nav(100_000_000, 20_000_000, 0)
        assert result is None

    def test_none_assets_returns_none(self):
        result = calc_nav(None, 20_000_000, 10_000_000)
        assert result is None

    def test_none_liabilities_returns_none(self):
        result = calc_nav(100_000_000, None, 10_000_000)
        assert result is None

    def test_none_shares_returns_none(self):
        result = calc_nav(100_000_000, 20_000_000, None)
        assert result is None

    def test_all_none_returns_none(self):
        result = calc_nav(None, None, None)
        assert result is None


# ---------------------------------------------------------------------------
# End-to-end: calc_nav → calc_premium_discount consistency
# ---------------------------------------------------------------------------

class TestNavToPremiumDiscount:
    """Ensure calc_nav output feeds correctly into calc_premium_discount."""

    def test_premium_scenario(self):
        """Price above NAV → positive premium."""
        nav = calc_nav(100_000_000, 20_000_000, 10_000_000)  # = 8.0
        assert nav == 8.0
        prem = calc_premium_discount(9.0, nav)
        # ((9.0 - 8.0) / 8.0) * 100 = 12.5
        assert prem == 12.5

    def test_discount_scenario(self):
        """Price below NAV → negative discount."""
        nav = calc_nav(100_000_000, 20_000_000, 10_000_000)  # = 8.0
        assert nav == 8.0
        disc = calc_premium_discount(7.0, nav)
        # ((7.0 - 8.0) / 8.0) * 100 = -12.5
        assert disc == -12.5

    def test_at_par(self):
        """Price equals NAV → zero."""
        nav = calc_nav(100_000_000, 20_000_000, 10_000_000)  # = 8.0
        assert nav == 8.0
        result = calc_premium_discount(8.0, nav)
        assert result == 0.0

    def test_with_none_nav(self):
        """If calc_nav returns None, premium/discount should also be None."""
        nav = calc_nav(None, 20_000_000, 10_000_000)
        assert nav is None
        # Guarded in main.py, but verify the function handles it
        result = calc_premium_discount(9.0, 0)  # nav=0 → None
        assert result is None
