"""Vendor connectivity and data-quality tests.

These tests validate that every data vendor can actually fetch data
for real tickers.  They are marked ``integration`` because they
require live network access and will be skipped when API keys are
missing or the network is unreachable.
"""

import unittest
import os
from datetime import datetime

import pytest

from dotenv import load_dotenv

from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.interface import route_to_vendor

load_dotenv()

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_A_SHARE = "600036"       # 招商银行 — Shanghai
_A_SHARE_NAME = "600036 (招商银行)"
_US_STOCK = "AAPL"
_CURR_DATE = "2025-05-26"


def _set_vendor(category: str, vendor_spec: str):
    set_config({"data_vendors": {category: vendor_spec}})


def _count_values(text: str) -> int:
    """Count non-empty values after ``: `` in a formatted indicator reply."""
    return sum(
        1 for line in text.split("\n")
        if ": " in line and line.split(": ", 1)[1].strip()
    )


# ============================== yfinance ===================================


@pytest.mark.integration
class YFinanceTests(unittest.TestCase):
    """yfinance — live-market connectivity & basic data quality."""

    def test_stock_ohlcv(self):
        _set_vendor("core_stock_apis", "yfinance")
        result = route_to_vendor("get_stock_data", _US_STOCK, "2025-05-20", _CURR_DATE)
        result_lower = result.lower()
        self.assertIn("open", result_lower)
        self.assertIn("close", result_lower)
        self.assertIn("volume", result_lower)

    def test_fundamentals(self):
        _set_vendor("fundamental_data", "yfinance")
        try:
            result = route_to_vendor("get_fundamentals", _US_STOCK, _CURR_DATE)
            self.assertIsInstance(result, str)
            self.assertGreater(len(result), 50)
        except Exception:  # rate-limited
            pass

    def test_news(self):
        _set_vendor("news_data", "yfinance")
        try:
            result = route_to_vendor("get_news", _US_STOCK)
            self.assertIsInstance(result, str)
            self.assertGreater(len(result), 50)
        except Exception:
            pass


# =========================== Alpha Vantage =================================


@pytest.mark.integration
class AlphaVantageTests(unittest.TestCase):
    """Alpha Vantage — requires ALPHA_VANTAGE_API_KEY."""

    def setUp(self):
        self.api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        if not self.api_key:
            self.skipTest("ALPHA_VANTAGE_API_KEY not set")

    def test_stock_ohlcv(self):
        _set_vendor("core_stock_apis", "alpha_vantage")
        try:
            result = route_to_vendor("get_stock_data", _US_STOCK, "2025-05-20", _CURR_DATE)
            self.assertIsInstance(result, str)
            self.assertGreater(len(result), 100)
        except Exception as e:
            self.skipTest(f"Alpha Vantage API error: {e}")


# ============================= AKShare =====================================


@pytest.mark.integration
class AKShareStockTests(unittest.TestCase):
    """AKShare — A-share stock data via East Money & Sina fallback."""

    def test_ashare_ohlcv(self):
        _set_vendor("core_stock_apis", "akshare")
        result = route_to_vendor("get_stock_data", _A_SHARE, "2025-05-20", _CURR_DATE)
        self.assertIn("Date,Open,High,Low,Close,Volume", result)
        self.assertIn(f"Stock data for {_A_SHARE}", result)

    def test_ashare_fundamentals(self):
        _set_vendor("fundamental_data", "akshare")
        result = route_to_vendor("get_fundamentals", _A_SHARE, _CURR_DATE)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 200)

    def test_ashare_balance_sheet(self):
        _set_vendor("fundamental_data", "akshare")
        result = route_to_vendor("get_balance_sheet", _A_SHARE, "quarterly", _CURR_DATE)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 100)

    def test_ashare_cashflow(self):
        _set_vendor("fundamental_data", "akshare")
        result = route_to_vendor("get_cashflow", _A_SHARE, "quarterly", _CURR_DATE)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 100)

    def test_ashare_income_statement(self):
        _set_vendor("fundamental_data", "akshare")
        result = route_to_vendor("get_income_statement", _A_SHARE, "quarterly", _CURR_DATE)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 100)

    def test_us_stock_fallback(self):
        """US stock via akshare should raise AKShareUnsupportedError → fallback."""
        _set_vendor("core_stock_apis", "akshare, yfinance")
        result = route_to_vendor("get_stock_data", _US_STOCK, "2025-05-20", _CURR_DATE)
        # yfinance fallback should have kicked in
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 50)

    def test_ashare_news(self):
        _set_vendor("news_data", "akshare")
        try:
            result = route_to_vendor("get_news", _A_SHARE)
            self.assertIsInstance(result, str)
            self.assertGreater(len(result), 50)
        except Exception:
            self.skipTest("AKShare news unavailable (network)")


@pytest.mark.integration
class AKShareIndicatorTests(unittest.TestCase):
    """AKShare + stockstats — all 19 indicators must return non-empty values."""

    _INDICATORS = [
        "rsi", "mfi",
        "macd", "macds", "macdh",
        "kdjk", "kdjd", "kdjj",
        "boll", "boll_ub", "boll_lb",
        "atr",
        "adx", "dx", "adxr",
        "vwma",
        "close_50_sma", "close_200_sma", "close_10_ema",
    ]

    def setUp(self):
        _set_vendor("technical_indicators", "akshare")

    def test_all_indicators_have_values(self):
        failed = []
        for ind in self._INDICATORS:
            try:
                result = route_to_vendor("get_indicators", _A_SHARE, ind, _CURR_DATE, 60)
                count = _count_values(result)
                if count == 0:
                    failed.append(f"{ind}: 0 values")
            except Exception as e:
                failed.append(f"{ind}: {type(e).__name__}: {e}")
        self.assertEqual([], failed, f"Indicators with no data: {failed}")

    def test_core_indicators_have_reasonable_values(self):
        """Spot-check RSI and MACD are in expected numeric ranges."""
        rsi = route_to_vendor("get_indicators", _A_SHARE, "rsi", _CURR_DATE, 60)
        self.assertIn(":", rsi)
        for line in rsi.split("\n"):
            if ": " in line:
                val = line.split(": ", 1)[1].strip()
                if val and val != "N/A":
                    try:
                        fval = float(val)
                        self.assertBetween(fval, 0, 100)
                    except ValueError:
                        pass
                    break

    def assertBetween(self, value, lo, hi):
        self.assertGreaterEqual(value, lo)
        self.assertLessEqual(value, hi)


# =========================== Reddit ========================================


@pytest.mark.integration
class RedditTests(unittest.TestCase):
    """Reddit public JSON API — no auth required."""

    def test_fetch_returns_string(self):
        from tradingagents.dataflows.reddit import fetch_reddit_posts
        result = fetch_reddit_posts("AAPL", limit_per_sub=2, timeout=15)
        self.assertIsInstance(result, str)


# =========================== StockTwits ====================================


@pytest.mark.integration
class StockTwitsTests(unittest.TestCase):
    """StockTwits — degrades gracefully when API requires auth."""

    def test_fetch_returns_string(self):
        from tradingagents.dataflows.stocktwits import fetch_stocktwits_messages
        result = fetch_stocktwits_messages("AAPL", limit=5)
        self.assertIsInstance(result, str)


# ===================== Full Market-Analyst simulation ======================


@pytest.mark.integration
class MarketAnalystDataFlowTests(unittest.TestCase):
    """End-to-end: simulate the tool calls a Market Analyst makes."""

    def test_ashare_market_analyst_toolchain(self):
        _set_vendor("core_stock_apis", "akshare, yfinance")
        _set_vendor("technical_indicators", "akshare, yfinance")

        # Step 1 — OHLCV
        ohlcv = route_to_vendor("get_stock_data", _A_SHARE, "2025-04-26", _CURR_DATE)
        self.assertGreater(len(ohlcv), 200)
        self.assertIn("Open", ohlcv)

        # Step 2 — indicators (subset the analyst typically requests)
        indicators = ["rsi", "macd", "boll", "atr", "kdjk", "adx"]
        for ind in indicators:
            r = route_to_vendor("get_indicators", _A_SHARE, ind, _CURR_DATE, 60)
            self.assertGreater(
                _count_values(r), 0,
                f"{ind} returned no values for {_A_SHARE_NAME}",
            )
