import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from core.config import CONFIG


@dataclass
class Signal:
    strategy: str
    direction: str
    entry: float
    sl: float
    tp: float
    rr: float
    score: float
    regime: str
    session: str
    timeframe: str
    notes: str = ""
    ts: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class SessionAnalyzer:
    def __init__(self):
        self.s = CONFIG["sessions"]

    def get(self, dt=None):
        if dt is None:
            dt = datetime.utcnow()
        h = dt.hour
        if self.s["london"]["start"] <= h < self.s["london"]["end"]:
            return "london"
        if self.s["ny"]["start"] <= h < self.s["ny"]["end"]:
            return "ny"
        if self.s["overlap"]["start"] <= h < self.s["overlap"]["end"]:
            return "overlap"
        return "asian"

    def allowed(self, session, strategy):
        if session == "asian":
            return strategy == "liquidity_sweep"
        return True


class StrategyEngine:
    def __init__(self):
        self.cfg = CONFIG

    def liquidity_sweep(self, df, sr_levels, direction="both"):
        if len(df) < 5:
            return None
        cfg = self.cfg["strategies"]["liquidity_sweep"]
        atr = df["atr"].iloc[-1] if "atr" in df.columns else 10
        for lvl in sr_levels:
            if lvl.role == "support" and direction in ("both", "long"):
                win = df.tail(cfg["reverse_bars"] + 2)
                swept  = (win["low"] < lvl.price * (1 - cfg["sweep_pct"])).any()
                backed = win["close"].iloc[-1] > lvl.price
                if swept and backed:
                    e  = win["close"].iloc[-1]
                    sl = win["low"].tail(cfg["reverse_bars"] + 1).min() - atr * 0.3
                    tp = e + (e - sl) * cfg["min_rr"]
                    rr = (tp - e) / (e - sl) if (e - sl) > 0 else 0
                    if rr >= cfg["min_rr"]:
                        return Signal("liquidity_sweep", "long", round(e, 2),
                                      round(sl, 2), round(tp, 2), round(rr, 2),
                                      0, "", "", lvl.timeframe,
                                      f"Sweep {lvl.price} ({lvl.touches}t)")
            if lvl.role == "resistance" and direction in ("both", "short"):
                win = df.tail(cfg["reverse_bars"] + 2)
                swept  = (win["high"] > lvl.price * (1 + cfg["sweep_pct"])).any()
                backed = win["close"].iloc[-1] < lvl.price
                if swept and backed:
                    e  = win["close"].iloc[-1]
                    sl = win["high"].tail(cfg["reverse_bars"] + 1).max() + atr * 0.3
                    tp = e - (sl - e) * cfg["min_rr"]
                    rr = (e - tp) / (sl - e) if (sl - e) > 0 else 0
                    if rr >= cfg["min_rr"]:
                        return Signal("liquidity_sweep", "short", round(e, 2),
                                      round(sl, 2), round(tp, 2), round(rr, 2),
                                      0, "", "", lvl.timeframe,
                                      f"Sweep {lvl.price} ({lvl.touches}t)")
        return None

    def trend_continuation(self, df, htf_bias):
        if len(df) < 60 or htf_bias == "neutral":
            return None
        cfg  = self.cfg["strategies"]["trend_continuation"]
        last = df.iloc[-1]
        atr  = last.get("atr", 10)
        ema  = last.get("ema_med", last["close"])
        if htf_bias == "bullish":
            at  = abs(last["low"] - ema) / ema < 0.002
            rev = last["close"] > ema
            aln = last.get("ema_fast", 0) > last.get("ema_med", 0) > last.get("ema_slow", 0)
            if at and rev and aln:
                e = last["close"]; sl = min(last["low"], ema) - atr * 0.5
                tp = e + (e - sl) * cfg["min_rr"]
                rr = (tp - e) / (e - sl) if (e - sl) > 0 else 0
                if rr >= cfg["min_rr"]:
                    return Signal("trend_continuation", "long", round(e, 2),
                                  round(sl, 2), round(tp, 2), round(rr, 2),
                                  0, "", "", "1H", f"PB EMA50 {ema:.2f} HTF bull")
        if htf_bias == "bearish":
            at  = abs(last["high"] - ema) / ema < 0.002
            rev = last["close"] < ema
            aln = last.get("ema_fast", 0) < last.get("ema_med", 0) < last.get("ema_slow", 0)
            if at and rev and aln:
                e = last["close"]; sl = max(last["high"], ema) + atr * 0.5
                tp = e - (sl - e) * cfg["min_rr"]
                rr = (e - tp) / (sl - e) if (sl - e) > 0 else 0
                if rr >= cfg["min_rr"]:
                    return Signal("trend_continuation", "short", round(e, 2),
                                  round(sl, 2), round(tp, 2), round(rr, 2),
                                  0, "", "", "1H", f"PB EMA50 {ema:.2f} HTF bear")
        return None

    def breakout_expansion(self, df, sr_levels):
        if len(df) < 20:
            return None
        cfg  = self.cfg["strategies"]["breakout_expansion"]
        last = df.iloc[-1]
        atr  = last.get("atr", 10)
        vr   = last.get("vol_ratio", 1.0)
        for lvl in sr_levels:
            if lvl.role == "support":
                win = df.tail(cfg["consolidation_bars"] + 5)
                broke  = (win["close"] > lvl.price * 1.001).any()
                retest = abs(last["close"] - lvl.price) / lvl.price < 0.003
                vol_ok = vr >= cfg["vol_multiplier"]
                if broke and retest and vol_ok and last["close"] > lvl.price:
                    e = last["close"]
                    sl = lvl.price - atr * self.cfg["risk"]["atr_sl_multiplier"]
                    tp = e + (e - sl) * cfg["min_rr"]
                    rr = (tp - e) / (e - sl) if (e - sl) > 0 else 0
                    if rr >= cfg["min_rr"]:
                        return Signal("breakout_expansion", "long", round(e, 2),
                                      round(sl, 2), round(tp, 2), round(rr, 2),
                                      0, "", "", lvl.timeframe,
                                      f"BO retest {lvl.price:.2f} vol x{vr:.1f}")
        return None

    def ema_momentum(self, df):
        if len(df) < 60:
            return None
        cfg  = self.cfg["strategies"]["ema_momentum"]
        last = df.iloc[-1]; prev = df.iloc[-2]
        ef   = last.get("ema_fast", 0); em = last.get("ema_med", 0)
        es   = last.get("ema_slow", 0)
        pef  = prev.get("ema_fast", 0); pem = prev.get("ema_med", 0)
        rsi  = last.get("rsi", 50); atr = last.get("atr", 10)
        slope = (ef - pef) / pef if pef else 0
        golden = pef < pem and ef > em
        bull_a = ef > em > es and slope > cfg["slope_min"] and rsi < 65
        if (golden or bull_a) and last["close"] > es:
            e = last["close"]; sl = em - atr
            tp = e + (e - sl) * cfg["min_rr"]
            rr = (tp - e) / (e - sl) if (e - sl) > 0 else 0
            if rr >= cfg["min_rr"]:
                return Signal("ema_momentum", "long", round(e, 2),
                              round(sl, 2), round(tp, 2), round(rr, 2),
                              0, "", "", "1H",
                              f"{'Golden X' if golden else 'Bull aln'} RSI {rsi:.0f}")
        death  = pef > pem and ef < em
        bear_a = ef < em < es and slope < -cfg["slope_min"] and rsi > 35
        if (death or bear_a) and last["close"] < es:
            e = last["close"]; sl = em + atr
            tp = e - (sl - e) * cfg["min_rr"]
            rr = (e - tp) / (sl - e) if (sl - e) > 0 else 0
            if rr >= cfg["min_rr"]:
                return Signal("ema_momentum", "short", round(e, 2),
                              round(sl, 2), round(tp, 2), round(rr, 2),
                              0, "", "", "1H",
                              f"{'Death X' if death else 'Bear aln'} RSI {rsi:.0f}")
        return None

    def run_all(self, df_15m, df_1h, sr_all, session, htf_bias, regime, rw):
        from core.config import CONFIG as CFG
        candidates = []
        if CFG["strategies"]["liquidity_sweep"]["active"]:
            s = self.liquidity_sweep(df_15m, sr_all[:8])
            if s:
                candidates.append(s)
        sa = SessionAnalyzer()
        if CFG["strategies"]["trend_continuation"]["active"] and session != "asian":
            s = self.trend_continuation(df_1h, htf_bias)
            if s:
                candidates.append(s)
        if CFG["strategies"]["breakout_expansion"]["active"] and session in ("london", "ny", "overlap"):
            s = self.breakout_expansion(df_1h, sr_all[:8])
            if s:
                candidates.append(s)
        if CFG["strategies"]["ema_momentum"]["active"] and regime != "high_vol_news":
            s = self.ema_momentum(df_1h)
            if s:
                candidates.append(s)
        return candidates
