import numpy as np
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import logging
from core.config import CONFIG

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
                "open": "first", "high": "max",
                "low": "min", "close": "last",
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
                    progress=False, auto_adjust=True, multi_level_index=False
                )
                if not raw.empty:
                    df = raw
                    break
            except TypeError:
                try:
                    raw = yf.download(
                        sym, period=period, interval=interval,
                        progress=False, auto_adjust=True
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
        c = df.copy()
        em = CONFIG["ema"]
        c["ema_fast"] = ta.ema(c["close"], length=em["fast"])
        c["ema_med"]  = ta.ema(c["close"], length=em["medium"])
        c["ema_slow"] = ta.ema(c["close"], length=em["slow"])
        c["atr"]      = ta.atr(c["high"], c["low"], c["close"], length=14)
        c["atr_pct"]  = c["atr"] / c["close"]
        adx = ta.adx(c["high"], c["low"], c["close"], length=14)
        if adx is not None and not adx.empty:
            c["adx"]    = adx.iloc[:, 0]
            c["di_pos"] = adx.iloc[:, 1]
            c["di_neg"] = adx.iloc[:, 2]
        c["rsi"]       = ta.rsi(c["close"], length=14)
        macd = ta.macd(c["close"])
        if macd is not None and not macd.empty:
            c["macd"]     = macd.iloc[:, 0]
            c["macd_sig"] = macd.iloc[:, 1]
        bb = ta.bbands(c["close"], length=20)
        if bb is not None and not bb.empty:
            c["bb_l"] = bb.iloc[:, 0]
            c["bb_m"] = bb.iloc[:, 1]
            c["bb_u"] = bb.iloc[:, 2]
        c["vol_ma"]    = ta.sma(c["volume"], length=20)
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
