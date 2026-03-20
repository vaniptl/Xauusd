import pandas as pd
import numpy as np
from core.config import CONFIG, REGIME_LABELS, REGIME_WEIGHTS


class RegimeClassifier:
    def __init__(self):
        self.cfg = CONFIG["regime"]

    def classify(self, df):
        if df.empty or len(df) < 50:
            return "ranging"
        last = df.iloc[-1]
        adx   = last.get("adx",   20)
        atr_p = last.get("atr_pct", 0.01)
        ef    = last.get("ema_fast", 0)
        es    = last.get("ema_slow", 0)
        close = last["close"]
        lb    = min(self.cfg["atr_lookback"], len(df))
        pctile = (df["atr_pct"].tail(lb) < atr_p).mean()
        if atr_p > self.cfg["atr_pct_high"] and pctile > 0.85:
            return "high_vol_news"
        if atr_p < self.cfg["atr_pct_low"] and pctile < 0.20:
            return "low_liq_grind"
        if adx > self.cfg["adx_trend_threshold"]:
            if ef > es and close > ef:
                return "trending_bull"
            if ef < es and close < ef:
                return "trending_bear"
            return "trending_bull" if close > es else "trending_bear"
        return "ranging"

    def classify_bar(self, row, df_lookback):
        """Classify a single bar given lookback window."""
        try:
            adx   = row.get("adx", 20) if hasattr(row, 'get') else getattr(row, "adx", 20)
            atr_p = row.get("atr_pct", 0.01) if hasattr(row, 'get') else getattr(row, "atr_pct", 0.01)
            ef    = row.get("ema_fast", 0) if hasattr(row, 'get') else getattr(row, "ema_fast", 0)
            es    = row.get("ema_slow", 0) if hasattr(row, 'get') else getattr(row, "ema_slow", 0)
            close = row["close"] if hasattr(row, '__getitem__') else row.close

            if "atr_pct" in df_lookback.columns:
                pctile = (df_lookback["atr_pct"] < atr_p).mean()
            else:
                pctile = 0.5

            if atr_p > self.cfg["atr_pct_high"] and pctile > 0.85:
                return "high_vol_news"
            if atr_p < self.cfg["atr_pct_low"] and pctile < 0.20:
                return "low_liq_grind"
            if adx > self.cfg["adx_trend_threshold"]:
                if ef > es and close > ef:
                    return "trending_bull"
                if ef < es and close < ef:
                    return "trending_bear"
                return "trending_bull" if close > es else "trending_bear"
            return "ranging"
        except Exception:
            return "ranging"

    def weights(self, regime):
        return REGIME_WEIGHTS.get(regime, {s: 1.0 for s in CONFIG["strategies"]})

    def label(self, regime):
        return REGIME_LABELS.get(regime, regime.upper())

    def get_htf_bias(self, df_4h, df_1d):
        biases = []
        for df in [df_4h, df_1d]:
            if df is None or df.empty or len(df) < 10:
                continue
            last = df.iloc[-1]
            ef   = last.get("ema_fast", 0) if hasattr(last, 'get') else 0
            es   = last.get("ema_slow", 0) if hasattr(last, 'get') else 0
            c    = last["close"]
            if ef > es and c > ef:
                biases.append("bullish")
            elif ef < es and c < ef:
                biases.append("bearish")
        if biases and all(b == "bullish" for b in biases):
            return "bullish"
        if biases and all(b == "bearish" for b in biases):
            return "bearish"
        return "neutral"
