import pandas as pd
import numpy as np
from core.config import CONFIG


class ConfluenceScorer:
    FACTORS = {
        "htf_alignment":  2.0,
        "sr_confluence":  1.5,
        "volume_confirm": 1.0,
        "fib_confluence": 1.0,
        "session_prime":  1.0,
        "regime_fit":     1.5,
        "cot_alignment":  1.0,
        "rsi_ok":         0.5,
        "spread_ok":      0.5,
    }

    def score(self, sig, df_1h, df_4h, df_1d, sr_levels,
              fib_levels, regime, session, cot_bias, rw):
        t = 0.0
        breakdown = {}

        htf = self._htf_bias(df_4h, df_1d)
        if (sig.direction == "long" and htf == "bullish") or \
           (sig.direction == "short" and htf == "bearish"):
            t += self.FACTORS["htf_alignment"]
            breakdown["htf_alignment"] = self.FACTORS["htf_alignment"]
        else:
            breakdown["htf_alignment"] = 0

        if any(abs(sig.entry - l.price) / sig.entry < 0.003 for l in sr_levels):
            t += self.FACTORS["sr_confluence"]
            breakdown["sr_confluence"] = self.FACTORS["sr_confluence"]
        else:
            breakdown["sr_confluence"] = 0

        if not df_1h.empty and df_1h.iloc[-1].get("vol_ratio", 1.0) >= 1.2:
            t += self.FACTORS["volume_confirm"]
            breakdown["volume_confirm"] = self.FACTORS["volume_confirm"]
        else:
            breakdown["volume_confirm"] = 0

        fib_hit = False
        for role in ("retracements", "extensions"):
            for _, p in fib_levels.get(role, {}).items():
                if abs(sig.entry - p) / sig.entry < 0.003:
                    fib_hit = True
                    break
        if fib_hit:
            t += self.FACTORS["fib_confluence"]
            breakdown["fib_confluence"] = self.FACTORS["fib_confluence"]
        else:
            breakdown["fib_confluence"] = 0

        if session in ("london", "ny", "overlap"):
            t += self.FACTORS["session_prime"]
            breakdown["session_prime"] = self.FACTORS["session_prime"]
        else:
            breakdown["session_prime"] = 0

        w = rw.get(sig.strategy, 1.0)
        if w >= 1.2:
            t += self.FACTORS["regime_fit"]
            breakdown["regime_fit"] = self.FACTORS["regime_fit"]
        elif w < 0.5:
            t -= self.FACTORS["regime_fit"] * 0.5
            breakdown["regime_fit"] = -self.FACTORS["regime_fit"] * 0.5
        else:
            breakdown["regime_fit"] = 0

        if (sig.direction == "long" and cot_bias in ("bullish", "neutral")) or \
           (sig.direction == "short" and cot_bias in ("bearish", "neutral")):
            t += self.FACTORS["cot_alignment"]
            breakdown["cot_alignment"] = self.FACTORS["cot_alignment"]
        else:
            breakdown["cot_alignment"] = 0

        if not df_1h.empty:
            rsi = df_1h.iloc[-1].get("rsi", 50)
            if (sig.direction == "long" and rsi < 70) or \
               (sig.direction == "short" and rsi > 30):
                t += self.FACTORS["rsi_ok"]
                breakdown["rsi_ok"] = self.FACTORS["rsi_ok"]
            else:
                breakdown["rsi_ok"] = 0
        else:
            breakdown["rsi_ok"] = 0

        t += self.FACTORS["spread_ok"]
        breakdown["spread_ok"] = self.FACTORS["spread_ok"]

        return round(min(t, 10.0), 2), breakdown

    def _htf_bias(self, df_4h, df_1d):
        biases = []
        for df in [df_4h, df_1d]:
            if df is None or df.empty or len(df) < 10:
                continue
            last = df.iloc[-1]
            ef = last.get("ema_fast", 0)
            es = last.get("ema_slow", 0)
            c  = last["close"]
            if ef > es and c > ef:
                biases.append("bullish")
            elif ef < es and c < ef:
                biases.append("bearish")
        if biases and all(b == "bullish" for b in biases):
            return "bullish"
        if biases and all(b == "bearish" for b in biases):
            return "bearish"
        return "neutral"
