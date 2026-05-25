"""Isolated AKShare vendor tests — helper functions & edge cases.

Does not go through the routing layer; calls AKShare module functions
directly so failures can be diagnosed independently of other vendors.
"""

import unittest
import pytest

from dotenv import load_dotenv
load_dotenv()


@pytest.mark.integration
class AKShareHelpersTests(unittest.TestCase):
    """AKShare symbol detection helpers."""

    def setUp(self):
        from tradingagents.dataflows.akshare_stock import (
            _is_ashare, _is_hk_stock, _ashare_prefix, AKShareUnsupportedError,
        )
        self._is_ashare = _is_ashare
        self._is_hk_stock = _is_hk_stock
        self._ashare_prefix = _ashare_prefix
        self.AKShareUnsupportedError = AKShareUnsupportedError

    def test_is_ashare_6digit(self):
        self.assertTrue(self._is_ashare("600036"))
        self.assertTrue(self._is_ashare("000001"))
        self.assertTrue(self._is_ashare("688981"))

    def test_is_ashare_rejects_non_digit(self):
        self.assertFalse(self._is_ashare("AAPL"))
        self.assertFalse(self._is_ashare("MSFT"))

    def test_is_ashare_strips_suffix(self):
        self.assertTrue(self._is_ashare("600036.SH"))
        self.assertTrue(self._is_ashare("000001.SZ"))

    def test_is_hk_stock_5digit(self):
        self.assertTrue(self._is_hk_stock("00700"))
        self.assertTrue(self._is_hk_stock("09988"))

    def test_ashare_prefix_sh(self):
        self.assertEqual(self._ashare_prefix("600036"), "sh")  # Shanghai
        self.assertEqual(self._ashare_prefix("688981"), "sh")  # STAR

    def test_ashare_prefix_sz(self):
        self.assertEqual(self._ashare_prefix("000001"), "sz")  # Shenzhen
        self.assertEqual(self._ashare_prefix("300750"), "sz")  # ChiNext


@pytest.mark.integration
class AKShareStockTests(unittest.TestCase):
    """AKShare stock data & indicator end-points."""

    _SYMBOL = "600036"
    _CURR_DATE = "2025-05-26"

    def setUp(self):
        from tradingagents.dataflows.akshare_stock import (
            get_stock, get_indicator, get_fundamentals,
            get_balance_sheet, get_cashflow, get_income_statement,
            AKShareUnsupportedError,
        )
        self.get_stock = get_stock
        self.get_indicator = get_indicator
        self.get_fundamentals = get_fundamentals
        self.get_balance_sheet = get_balance_sheet
        self.get_cashflow = get_cashflow
        self.get_income_statement = get_income_statement
        self.AKShareUnsupportedError = AKShareUnsupportedError

    def test_get_stock_returns_csv(self):
        result = self.get_stock(self._SYMBOL, "2025-05-20", self._CURR_DATE)
        self.assertIn("Date,Open,High,Low,Close,Volume", result)
        self.assertIn(f"Stock data for {self._SYMBOL}", result)

    def test_get_stock_rejects_us(self):
        with self.assertRaises(self.AKShareUnsupportedError):
            self.get_stock("AAPL", "2025-05-20", self._CURR_DATE)

    def test_get_fundamentals(self):
        result = self.get_fundamentals(self._SYMBOL)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 200)

    def test_get_balance_sheet(self):
        result = self.get_balance_sheet(self._SYMBOL)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 100)

    def test_get_cashflow(self):
        result = self.get_cashflow(self._SYMBOL)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 100)

    def test_get_income_statement(self):
        result = self.get_income_statement(self._SYMBOL)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 100)

    def test_indicator_rsi(self):
        result = self.get_indicator(self._SYMBOL, "rsi", self._CURR_DATE, 60)
        self.assertIn("RSI values", result)
        self.assertIn(":", result)

    def test_indicator_macd(self):
        result = self.get_indicator(self._SYMBOL, "macd", self._CURR_DATE, 60)
        self.assertIn("MACD values", result)
        self.assertIn(":", result)

    def test_indicator_kdjk(self):
        result = self.get_indicator(self._SYMBOL, "kdjk", self._CURR_DATE, 60)
        self.assertIn("KDJK", result.upper())
        self.assertIn(":", result)

    def test_indicator_adx(self):
        result = self.get_indicator(self._SYMBOL, "adx", self._CURR_DATE, 60)
        self.assertIn("ADX values", result)
        self.assertIn(":", result)

    def test_indicator_bollinger(self):
        result = self.get_indicator(self._SYMBOL, "boll", self._CURR_DATE, 60)
        self.assertIn("BOLL values", result)

    def test_unsupported_indicator_raises(self):
        with self.assertRaises(ValueError):
            self.get_indicator(self._SYMBOL, "invalid_indicator_xyz", self._CURR_DATE, 30)
