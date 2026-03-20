import numpy as np
import pandas as pd
import yfinance as yf
import logging
from core.config import CONFIG
from core.indicators import ema, sma, rsi, atr, adx, macd, bbands

log = logging.getLogger("XAUUSD.data")


class DataEngine:
    def __init__(self):
        self.data = {}

    def fetch(self, tf_name):
        tf = CONFIG["timeframes"][tf_name]
        df = pd.DataFrame()
        for sym in [CONFIG["symbol"], CONFIG["symbol_spot"]]:
            try:
                raw = yf.download(
                    sym,
                    period=tf["period"],
                    interval=tf["interval"],
                    progress=False,
                    auto_adjust=True,
                    multi_level_index=False,
                )
                if not raw.empty:
                    df = raw
                    break
            except TypeError:
                try:
                    raw = yf.download(
                        sym,
                        period=tf["period"],
                        interval=tf["interval"],
                        progress=False,
                        auto_adjust=True,
                    )
                    if not raw.empty:
                        df = raw
                        break
                except Exception:
                    continue
            except Exception:
                continue

        if df.empty:
            return pd.DataFrame()

        # Flatten MultiIndex columns (yfinance >= 0.2.18)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0].lower() for col in df.columns]
        else:
            df.columns = [str(c).lower() for c in df.columns]

        needed = ["open", "high", "low", "close", "volume"]
        df = df[[c for c in needed if c in df.columns]].dropna()

        if tf_name == "4H":
            df = df.resample("4h").agg({
                "open":   "first",
                "high":   "max",
                "low":    "min",
                "close":  "last",
                "volume": "sum",
            }).dropna()

        df.index = pd.to_datetime(df.index, utc=True)
        return df

    def fetch_history(self, period="1y", interval="1h"):
        """Fetch extended history for backtesting."""
        df = pd.DataFrame()
        for sym in [CONFIG["symbol"], CONFIG["symbol_spot"]]:
            try:
                raw = yf.download(
                    sym, period=period, interval=interval,
                    progress=False, auto_adjust=True,
                    multi_level_index=False,
                )
                if not raw.empty:
                    df = raw
                    break
            except TypeError:
                try:
                    raw = yf.download(
                        sym, period=period, interval=interval,
                        progress=False, auto_adjust=True,
                    )
                    if not raw.empty:
                        df = raw
                        break
                except Exception:
                    continue
            except Exception:
                continue

        if df.empty:
            return pd.DataFrame()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0].lower() for col in df.columns]
        else:
            df.columns = [str(c).lower() for c in df.columns]

        df = df[["open", "high", "low", "close", "volume"]].dropna()
        df.index = pd.to_datetime(df.index, utc=True)
        return df

    def fetch_all(self):
        for tf in ["1D", "4H", "1H", "15M"]:
            self.data[tf] = self.fetch(tf)
        return self.data

    def add_indicators(self, df):
        if df.empty or len(df) < 50:
            return df
        c  = df.copy()
        em = CONFIG["ema"]

        # EMAs
        c["ema_fast"] = ema(c["close"], em["fast"])
        c["ema_med"]  = ema(c["close"], em["medium"])
        c["ema_slow"] = ema(c["close"], em["slow"])

        # ATR
        c["atr"]     = atr(c["high"], c["low"], c["close"], 14)
        c["atr_pct"] = c["atr"] / c["close"]

        # ADX
        adx_df = adx(c["high"], c["low"], c["close"], 14)
        c["adx"]    = adx_df["ADX"]
        c["di_pos"] = adx_df["DMP"]
        c["di_neg"] = adx_df["DMN"]

        # RSI
        c["rsi"] = rsi(c["close"], 14)

        # MACD
        macd_df       = macd(c["close"])
        c["macd"]     = macd_df["MACD"]
        c["macd_sig"] = macd_df["MACDs"]
        c["macd_hist"]= macd_df["MACDh"]

        # Bollinger Bands
        bb_df   = bbands(c["close"], 20)
        c["bb_l"] = bb_df["BBL"]
        c["bb_m"] = bb_df["BBM"]
        c["bb_u"] = bb_df["BBU"]

        # Volume MA & ratio
        c["vol_ma"]    = sma(c["volume"], 20)
        c["vol_ratio"] = c["volume"] / c["vol_ma"].replace(0, np.nan)

        return c

    def get(self, tf):
        return self.add_indicators(self.data.get(tf, pd.DataFrame()))

    def get_current_price(self):
        df = self.data.get("1H", pd.DataFrame())
        if df.empty:
            df = self.fetch("1H")
        if df.empty:
            return None
        return float(df["close"].iloc[-1])
