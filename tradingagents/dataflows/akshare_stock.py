import akshare as ak
import pandas as pd
from datetime import datetime


class AKShareUnsupportedError(Exception):
    """Raised when AKShare does not support the requested symbol/market.
    Caught by the routing layer to trigger vendor fallback.
    """
    pass


_AKSHARE_INDICATORS = {
    # Moving Averages
    "close_50_sma": "50 SMA: A medium-term trend indicator. Usage: Identify trend direction and serve as dynamic support/resistance.",
    "close_200_sma": "200 SMA: A long-term trend benchmark. Usage: Confirm overall market trend and identify golden/death cross setups.",
    "close_10_ema": "10 EMA: A responsive short-term average. Usage: Capture quick shifts in momentum and potential entry points.",
    # MACD Related
    "macd": "MACD: Computes momentum via differences of EMAs. Usage: Look for crossovers and divergence as signals of trend changes.",
    "macds": "MACD Signal: An EMA smoothing of the MACD line. Usage: Use crossovers with the MACD line to trigger trades.",
    "macdh": "MACD Histogram: Shows the gap between the MACD line and its signal. Usage: Visualize momentum strength and spot divergence early.",
    # Momentum Indicators
    "rsi": "RSI: Measures momentum to flag overbought/oversold conditions. Usage: Apply 70/30 thresholds and watch for divergence to signal reversals.",
    "mfi": "MFI: Money Flow Index uses price and volume to measure buying/selling pressure. Usage: Identify overbought (>80) or oversold (<20) conditions.",
    # KDJ (Stochastic)
    "kdjk": "KDJ-K: Fast stochastic line (K). Usage: Reacts quickly to price changes; crossovers with D signal entry/exit points.",
    "kdjd": "KDJ-D: Slow stochastic line (D). Usage: Smoothed version of K; used as signal line for K crossover confirmation.",
    "kdjj": "KDJ-J: Divergence indicator (J = 3K - 2D). Usage: Most sensitive KDJ component; extreme values signal potential reversals.",
    # Volatility Indicators
    "boll": "Bollinger Middle: A 20 SMA serving as the basis for Bollinger Bands. Usage: Acts as a dynamic benchmark for price movement.",
    "boll_ub": "Bollinger Upper Band: Typically 2 standard deviations above the middle line. Usage: Signals potential overbought conditions and breakout zones.",
    "boll_lb": "Bollinger Lower Band: Typically 2 standard deviations below the middle line. Usage: Indicates potential oversold conditions.",
    "atr": "ATR: Averages true range to measure volatility. Usage: Set stop-loss levels and adjust position sizes based on current market volatility.",
    # Trend Strength
    "dx": "DX: Directional Movement Index. Usage: Measures trend strength regardless of direction. Values above 25 indicate strong trend.",
    "adx": "ADX: Average Directional Index. Usage: Smoothed DX; above 25 = strong trend, below 20 = weak/range-bound market.",
    "adxr": "ADXR: ADX Rating. Usage: Average of current ADX and ADX from N periods ago; smooths ADX further.",
    # Volume-Based
    "vwma": "VWMA: A moving average weighted by volume. Usage: Confirm trends by integrating price action with volume data.",
}


def _is_ashare(symbol: str) -> bool:
    """Detect if symbol is a Chinese A-share (6-digit code)."""
    clean = symbol.split(".")[0]
    return clean.isdigit() and len(clean) == 6


def _ashare_prefix(clean: str) -> str:
    """Map A-share code to Sina prefix (sh/sz)."""
    if clean.startswith(("6", "9")):
        return "sh"
    return "sz"


def _is_hk_stock(symbol: str) -> bool:
    """Detect if symbol is a Hong Kong stock (5-digit code)."""
    clean = symbol.split(".")[0]
    return clean.isdigit() and len(clean) == 5


def _normalize_ashare_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize A-share DataFrame to standard OHLCV columns."""
    col_map = {
        "日期": "Date",
        "开盘": "Open",
        "收盘": "Close",
        "最高": "High",
        "最低": "Low",
        "成交量": "Volume",
    }
    rename = {k: v for k, v in col_map.items() if k in df.columns}
    df = df.rename(columns=rename)
    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    return df[list(col_map.values())]


def _normalize_us_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize US stock DataFrame to standard OHLCV columns."""
    df = df.rename(columns={
        "date": "Date",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    })
    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    return df[["Date", "Open", "High", "Low", "Close", "Volume"]]


def _normalize_hk_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize HK stock DataFrame to standard OHLCV columns."""
    col_map = {
        "日期": "Date",
        "开盘价": "Open",
        "收盘价": "Close",
        "最高价": "High",
        "最低价": "Low",
        "成交量": "Volume",
    }
    rename = {k: v for k, v in col_map.items() if k in df.columns}
    df = df.rename(columns=rename)
    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    return df[list(col_map.values())]


def get_stock(
    symbol: str,
    start_date: str,
    end_date: str,
) -> str:
    """Retrieve OHLCV stock data via AKShare.

    Auto-detects market type: A-share (6 digits) vs US vs HK.
    Returns CSV string with standard Date,Open,High,Low,Close,Volume columns.
    """
    clean = symbol.split(".")[0]
    start = start_date.replace("-", "")
    end = end_date.replace("-", "")

    if _is_ashare(clean):
        try:
            df = ak.stock_zh_a_hist(
                symbol=clean,
                period="daily",
                start_date=start,
                end_date=end,
                adjust="qfq",
            )
            df = _normalize_ashare_df(df)
        except Exception:
            # Fallback to Sina Finance when East Money is unreachable
            prefix = _ashare_prefix(clean)
            try:
                df = ak.stock_zh_a_daily(symbol=f"{prefix}{clean}", adjust="qfq", start_date=start, end_date=end)
            except Exception as e2:
                raise RuntimeError(f"AKShare failed for A-share {symbol} (both East Money and Sina): {e2}") from e2
            df = _normalize_us_df(df)  # Sina uses English column names same as US format
    elif _is_hk_stock(clean):
        try:
            df = ak.stock_hk_hist(symbol=clean, period="daily", start_date=start, end_date=end, adjust="qfq")
            df = _normalize_hk_df(df)
        except Exception as e:
            raise RuntimeError(f"AKShare failed for HK stock {symbol}: {e}") from e
    else:
        raise AKShareUnsupportedError(f"AKShare only supports A-share and HK stocks, got '{symbol}'")

    if df.empty:
        return f"No data found for symbol '{symbol}' between {start_date} and {end_date}"

    for col in ["Open", "High", "Low", "Close"]:
        if col in df.columns:
            df[col] = df[col].round(2)

    header = f"# Stock data for {symbol.upper()} from {start_date} to {end_date}\n"
    header += f"# Total records: {len(df)}\n"
    header += f"# Data retrieved via AKShare on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    return header + df.to_csv(index=False)


def get_fundamentals(ticker: str, curr_date: str = None) -> str:
    """Get company fundamentals via AKShare."""
    clean = ticker.split(".")[0]
    if not _is_ashare(clean):
        raise AKShareUnsupportedError(f"AKShare fundamentals only support A-share stocks, got {ticker}")
    try:
        df = ak.stock_financial_abstract(symbol=clean)
    except Exception as e:
        raise RuntimeError(f"AKShare fundamentals failed for {ticker}: {e}") from e

    header = f"# Company Fundamentals for {ticker.upper()}\n"
    header += f"# Data retrieved via AKShare on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    return header + df.to_csv(index=False)


def get_balance_sheet(ticker: str, freq: str = "quarterly", curr_date: str = None):
    """Get balance sheet via AKShare."""
    clean = ticker.split(".")[0]
    if not _is_ashare(clean):
        raise AKShareUnsupportedError(f"AKShare only supports A-share stocks, got {ticker}")
    try:
        df = ak.stock_balance_sheet_by_report_em(symbol=clean)
    except Exception:
        try:
            df = ak.stock_financial_debt_new_ths(symbol=clean)
        except Exception as e2:
            raise RuntimeError(f"AKShare balance sheet failed for {ticker}: {e2}") from e2
    return df.to_csv(index=False)


def get_cashflow(ticker: str, freq: str = "quarterly", curr_date: str = None):
    """Get cash flow statement via AKShare."""
    clean = ticker.split(".")[0]
    if not _is_ashare(clean):
        raise AKShareUnsupportedError(f"AKShare only supports A-share stocks, got {ticker}")
    try:
        df = ak.stock_cash_flow_sheet_by_report_em(symbol=clean)
    except Exception:
        try:
            df = ak.stock_financial_cash_new_ths(symbol=clean)
        except Exception as e2:
            raise RuntimeError(f"AKShare cash flow failed for {ticker}: {e2}") from e2
    return df.to_csv(index=False)


def get_income_statement(ticker: str, freq: str = "quarterly", curr_date: str = None):
    """Get income statement via AKShare."""
    clean = ticker.split(".")[0]
    if not _is_ashare(clean):
        raise AKShareUnsupportedError(f"AKShare only supports A-share stocks, got {ticker}")
    try:
        df = ak.stock_profit_sheet_by_report_em(symbol=clean)
    except Exception:
        try:
            df = ak.stock_financial_benefit_new_ths(symbol=clean)
        except Exception as e2:
            raise RuntimeError(f"AKShare income statement failed for {ticker}: {e2}") from e2
    return df.to_csv(index=False)


def get_indicator(
    symbol: str,
    indicator: str,
    curr_date: str,
    look_back_days: int,
    interval: str = "daily",
    time_period: int = 14,
    series_type: str = "close",
) -> str:
    """Get technical indicator values via stockstats on AKShare data."""
    from stockstats import wrap
    from dateutil.relativedelta import relativedelta

    indicator = indicator.lower()
    if indicator not in _AKSHARE_INDICATORS:
        raise ValueError(
            f"Indicator '{indicator}' is not supported. "
            f"Please choose from: {list(_AKSHARE_INDICATORS.keys())}"
        )

    clean = symbol.split(".")[0]
    curr_date_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    before = curr_date_dt - relativedelta(days=look_back_days)

    start = (curr_date_dt - relativedelta(days=look_back_days * 2)).strftime("%Y%m%d")
    end = curr_date_dt.strftime("%Y%m%d")

    if _is_ashare(clean):
        try:
            raw = ak.stock_zh_a_hist(symbol=clean, period="daily", start_date=start, end_date=end, adjust="qfq")
            raw = _normalize_ashare_df(raw)
        except Exception:
            prefix = _ashare_prefix(clean)
            try:
                raw = ak.stock_zh_a_daily(symbol=f"{prefix}{clean}", adjust="qfq", start_date=start, end_date=end)
            except Exception as e2:
                raise RuntimeError(f"AKShare indicator data fetch failed for {symbol}: {e2}") from e2
            raw = _normalize_us_df(raw)
    else:
        raise AKShareUnsupportedError(f"AKShare indicators only support A-share stocks, got '{symbol}'")

    if raw.empty:
        return f"No data available for {symbol} in the required range."

    df = wrap(raw)
    df[indicator]

    result = []
    for _, row in df.iterrows():
        dt = pd.to_datetime(row["Date"])
        if before <= dt <= curr_date_dt:
            val = row[indicator]
            result.append(f"{dt.strftime('%Y-%m-%d')}: {val if not pd.isna(val) else 'N/A'}")

    ind_string = "\n".join(result) if result else "No data available for the specified date range."
    desc = _AKSHARE_INDICATORS.get(indicator, "")
    return f"## {indicator.upper()} values from {before.strftime('%Y-%m-%d')} to {curr_date}:\n\n{ind_string}\n\n{desc}\n"


def get_news(ticker: str) -> str:
    """Get news via AKShare (East Money)."""
    clean = ticker.split(".")[0]
    if not _is_ashare(clean):
        raise AKShareUnsupportedError(f"AKShare news only supports A-share stocks, got {ticker}")
    try:
        df = ak.stock_news_em(symbol=clean)
    except Exception as e:
        raise RuntimeError(f"AKShare news failed for {ticker}: {e}") from e
    header = f"# News for {ticker.upper()}\n"
    header += f"# Data retrieved via AKShare on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    return header + df.to_csv(index=False)
