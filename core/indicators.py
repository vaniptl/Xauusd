"""
Pure pandas/numpy technical indicators.
Replaces pandas-ta entirely — works on any Python version.
"""
import numpy as np
import pandas as pd


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(window=length).mean()


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_g = gain.ewm(com=length - 1, adjust=False).mean()
    avg_l = loss.ewm(com=length - 1, adjust=False).mean()
    rs    = avg_g / avg_l.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def atr(high: pd.Series, low: pd.Series, close: pd.Series,
        length: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(com=length - 1, adjust=False).mean()


def adx(high: pd.Series, low: pd.Series, close: pd.Series,
        length: int = 14) -> pd.DataFrame:
    prev_high  = high.shift(1)
    prev_low   = low.shift(1)
    prev_close = close.shift(1)

    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)

    dm_pos = np.where((high - prev_high) > (prev_low - low),
                      np.maximum(high - prev_high, 0), 0)
    dm_neg = np.where((prev_low - low) > (high - prev_high),
                      np.maximum(prev_low - low, 0), 0)

    dm_pos = pd.Series(dm_pos, index=high.index)
    dm_neg = pd.Series(dm_neg, index=high.index)

    atr_s   = tr.ewm(com=length - 1,    adjust=False).mean()
    di_pos  = 100 * dm_pos.ewm(com=length - 1, adjust=False).mean() / atr_s.replace(0, np.nan)
    di_neg  = 100 * dm_neg.ewm(com=length - 1, adjust=False).mean() / atr_s.replace(0, np.nan)
    dx      = 100 * (di_pos - di_neg).abs() / (di_pos + di_neg).replace(0, np.nan)
    adx_val = dx.ewm(com=length - 1, adjust=False).mean()

    return pd.DataFrame({"ADX": adx_val, "DMP": di_pos, "DMN": di_neg})


def macd(series: pd.Series, fast: int = 12, slow: int = 26,
         signal: int = 9) -> pd.DataFrame:
    ema_fast   = series.ewm(span=fast,   adjust=False).mean()
    ema_slow   = series.ewm(span=slow,   adjust=False).mean()
    macd_line  = ema_fast - ema_slow
    signal_line= macd_line.ewm(span=signal, adjust=False).mean()
    histogram  = macd_line - signal_line
    return pd.DataFrame({"MACD": macd_line, "MACDs": signal_line, "MACDh": histogram})


def bbands(series: pd.Series, length: int = 20,
           std: float = 2.0) -> pd.DataFrame:
    mid   = series.rolling(window=length).mean()
    sigma = series.rolling(window=length).std(ddof=0)
    upper = mid + std * sigma
    lower = mid - std * sigma
    return pd.DataFrame({"BBL": lower, "BBM": mid, "BBU": upper})
