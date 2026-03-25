"""
Strategy Engine — 5 strategies:
1. Liquidity Sweep
2. Trend Continuation
3. Breakout Expansion
4. EMA Momentum
5. Intraday Scalp ($20/day, 200 pips target)
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List
from core.config import CONFIG


@dataclass
class Signal:
    strategy:  str
    direction: str
    entry:     float
    sl:        float
    tp:        float
    rr:        float
    score:     float
    regime:    str
    session:   str
    timeframe: str
    notes:     str = ""
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SessionAnalyzer:
    def __init__(self):
        self.s = CONFIG["sessions"]

    def get(self, dt=None):
        if dt is None:
            dt = datetime.now(timezone.utc)
        h = dt.hour
        if self.s["london"]["start"] <= h < self.s["london"]["end"]:   return "london"
        if self.s["ny"]["start"]     <= h < self.s["ny"]["end"]:       return "ny"
        if self.s["overlap"]["start"]<= h < self.s["overlap"]["end"]:  return "overlap"
        return "asian"

    def allowed(self, session, strategy):
        if session == "asian":
            return strategy == "liquidity_sweep"
        return True

    def is_london_open(self, dt=None):
        if dt is None: dt = datetime.now(timezone.utc)
        return self.s["london"]["start"] <= dt.hour < self.s["london"]["start"] + 2

    def is_ny_open(self, dt=None):
        if dt is None: dt = datetime.now(timezone.utc)
        return self.s["ny"]["start"] <= dt.hour < self.s["ny"]["start"] + 2


class StrategyEngine:

    def __init__(self):
        self.cfg = CONFIG

    # ── 1: LIQUIDITY SWEEP ────────────────────────────────────────────────────
    def liquidity_sweep(self, df, sr_levels, direction="both"):
        if len(df) < 5:
            return None
        cfg = self.cfg["strategies"]["liquidity_sweep"]
        atr = float(df["atr"].iloc[-1]) if "atr" in df.columns else 10
        for lvl in sr_levels:
            if lvl.role == "support" and direction in ("both", "long"):
                win = df.tail(cfg["reverse_bars"] + 2)
                if (win["low"] < lvl.price * (1 - cfg["sweep_pct"])).any() and \
                        float(win["close"].iloc[-1]) > lvl.price:
                    e  = float(win["close"].iloc[-1])
                    sl = float(win["low"].tail(cfg["reverse_bars"] + 1).min()) - atr * 0.3
                    tp = e + (e - sl) * cfg["min_rr"]
                    rr = (tp - e) / (e - sl) if (e - sl) > 0 else 0
                    if rr >= cfg["min_rr"]:
                        return Signal("liquidity_sweep", "long",
                                      round(e, 2), round(sl, 2), round(tp, 2), round(rr, 2),
                                      0, "", "", lvl.timeframe,
                                      f"Sweep {lvl.price} ({lvl.touches}t)")
            if lvl.role == "resistance" and direction in ("both", "short"):
                win = df.tail(cfg["reverse_bars"] + 2)
                if (win["high"] > lvl.price * (1 + cfg["sweep_pct"])).any() and \
                        float(win["close"].iloc[-1]) < lvl.price:
                    e  = float(win["close"].iloc[-1])
                    sl = float(win["high"].tail(cfg["reverse_bars"] + 1).max()) + atr * 0.3
                    tp = e - (sl - e) * cfg["min_rr"]
                    rr = (e - tp) / (sl - e) if (sl - e) > 0 else 0
                    if rr >= cfg["min_rr"]:
                        return Signal("liquidity_sweep", "short",
                                      round(e, 2), round(sl, 2), round(tp, 2), round(rr, 2),
                                      0, "", "", lvl.timeframe,
                                      f"Sweep {lvl.price} ({lvl.touches}t)")
        return None

    # ── 2: TREND CONTINUATION ─────────────────────────────────────────────────
    def trend_continuation(self, df, htf_bias):
        if len(df) < 60 or htf_bias == "neutral":
            return None
        cfg  = self.cfg["strategies"]["trend_continuation"]
        last = df.iloc[-1]
        atr  = float(last.get("atr", 10))
        ema  = float(last.get("ema_med", last["close"]))
        if htf_bias == "bullish":
            if abs(float(last["low"]) - ema) / ema < 0.002 and \
               float(last["close"]) > ema and \
               last.get("ema_fast", 0) > last.get("ema_med", 0) > last.get("ema_slow", 0):
                e  = float(last["close"])
                sl = min(float(last["low"]), ema) - atr * 0.5
                tp = e + (e - sl) * cfg["min_rr"]
                rr = (tp - e) / (e - sl) if (e - sl) > 0 else 0
                if rr >= cfg["min_rr"]:
                    return Signal("trend_continuation", "long",
                                  round(e, 2), round(sl, 2), round(tp, 2), round(rr, 2),
                                  0, "", "", "1H", f"PB EMA50 {ema:.2f}")
        if htf_bias == "bearish":
            if abs(float(last["high"]) - ema) / ema < 0.002 and \
               float(last["close"]) < ema and \
               last.get("ema_fast", 0) < last.get("ema_med", 0) < last.get("ema_slow", 0):
                e  = float(last["close"])
                sl = max(float(last["high"]), ema) + atr * 0.5
                tp = e - (sl - e) * cfg["min_rr"]
                rr = (e - tp) / (sl - e) if (sl - e) > 0 else 0
                if rr >= cfg["min_rr"]:
                    return Signal("trend_continuation", "short",
                                  round(e, 2), round(sl, 2), round(tp, 2), round(rr, 2),
                                  0, "", "", "1H", f"PB EMA50 {ema:.2f}")
        return None

    # ── 3: BREAKOUT EXPANSION ─────────────────────────────────────────────────
    def breakout_expansion(self, df, sr_levels):
        if len(df) < 20:
            return None
        cfg  = self.cfg["strategies"]["breakout_expansion"]
        last = df.iloc[-1]
        atr  = float(last.get("atr", 10))
        vr   = float(last.get("vol_ratio", 1.0))
        for lvl in sr_levels:
            if lvl.role == "support":
                win = df.tail(cfg["consolidation_bars"] + 5)
                if (win["close"] > lvl.price * 1.001).any() and \
                   abs(float(last["close"]) - lvl.price) / lvl.price < 0.003 and \
                   vr >= cfg["vol_multiplier"] and float(last["close"]) > lvl.price:
                    e  = float(last["close"])
                    sl = lvl.price - atr * self.cfg["risk"]["atr_sl_multiplier"]
                    tp = e + (e - sl) * cfg["min_rr"]
                    rr = (tp - e) / (e - sl) if (e - sl) > 0 else 0
                    if rr >= cfg["min_rr"]:
                        return Signal("breakout_expansion", "long",
                                      round(e, 2), round(sl, 2), round(tp, 2), round(rr, 2),
                                      0, "", "", lvl.timeframe,
                                      f"BO retest {lvl.price:.2f} vol x{vr:.1f}")
        return None

    # ── 4: EMA MOMENTUM ───────────────────────────────────────────────────────
    def ema_momentum(self, df):
        if len(df) < 60:
            return None
        cfg   = self.cfg["strategies"]["ema_momentum"]
        last  = df.iloc[-1]
        prev  = df.iloc[-2]
        ef    = float(last.get("ema_fast", 0))
        em    = float(last.get("ema_med",  0))
        es    = float(last.get("ema_slow", 0))
        pef   = float(prev.get("ema_fast", 0))
        pem   = float(prev.get("ema_med",  0))
        rsi   = float(last.get("rsi", 50))
        atr   = float(last.get("atr", 10))
        slope = (ef - pef) / pef if pef else 0
        golden = pef < pem and ef > em
        bull_a = ef > em > es and slope > cfg["slope_min"] and rsi < 65
        if (golden or bull_a) and float(last["close"]) > es:
            e = float(last["close"]); sl = em - atr
            tp = e + (e - sl) * cfg["min_rr"]
            rr = (tp - e) / (e - sl) if (e - sl) > 0 else 0
            if rr >= cfg["min_rr"]:
                return Signal("ema_momentum", "long",
                              round(e, 2), round(sl, 2), round(tp, 2), round(rr, 2),
                              0, "", "", "1H",
                              f"{'Golden X' if golden else 'Bull aln'} RSI {rsi:.0f}")
        death  = pef > pem and ef < em
        bear_a = ef < em < es and slope < -cfg["slope_min"] and rsi > 35
        if (death or bear_a) and float(last["close"]) < es:
            e = float(last["close"]); sl = em + atr
            tp = e - (sl - e) * cfg["min_rr"]
            rr = (e - tp) / (sl - e) if (sl - e) > 0 else 0
            if rr >= cfg["min_rr"]:
                return Signal("ema_momentum", "short",
                              round(e, 2), round(sl, 2), round(tp, 2), round(rr, 2),
                              0, "", "", "1H",
                              f"{'Death X' if death else 'Bear aln'} RSI {rsi:.0f}")
        return None

    # ── 5: INTRADAY SCALP — $20/day, 200 pip target ───────────────────────────
    # 10+ year XAUUSD trader logic:
    # ● Only trade London Open (07:00-09:00 UTC) and NY Open (13:00-15:00 UTC)
    #   These two windows produce 70% of the day's range. Outside them = noise.
    # ● Gold moves in the SAME DIRECTION as the first strong 15M candle of
    #   the session 68% of the time (session open momentum rule).
    # ● Wait for the FIRST PULLBACK after the opening move.
    #   Never chase the initial candle. Enter on the retest.
    # ● SL: 100 pips (10 price points) below/above pullback low/high
    # ● TP: 200 pips (20 price points) = 2:1 R:R minimum
    # ● On 0.01 lot: 200 pips = $20. That's the daily goal.
    # ● Stop strategy once $20 daily target hit (avoid overtrading)
    # ● Regime filter: only run in trending or ranging. Not high vol.
    # ● RSI filter: don't buy above 65, don't sell below 35 (avoid exhaustion)
    def intraday_scalp(self, df_15m, session, regime, daily_achieved=0.0):
        """
        Parameters:
            df_15m:          15M DataFrame with indicators
            session:         current session string
            regime:          current market regime
            daily_achieved:  how much $ already made today
        """
        if len(df_15m) < 10:
            return None

        cfg = self.cfg["strategies"]["intraday_scalp"]

        # Stop if daily goal already hit
        if daily_achieved >= cfg["daily_target"]:
            return None

        # Only run during London open OR NY open (first 2 hours each)
        sa  = SessionAnalyzer()
        now = datetime.now(timezone.utc)
        is_london_open = sa.is_london_open(now)
        is_ny_open     = sa.is_ny_open(now)
        if not (is_london_open or is_ny_open):
            return None

        # No trading in high vol regime (news events)
        if regime == "high_vol_news":
            return None

        last = df_15m.iloc[-1]
        prev = df_15m.iloc[-2]
        cur  = float(last["close"])
        atr  = float(last.get("atr", 15))
        rsi  = float(last.get("rsi", 50))

        # 200 pips on gold = 20 price points (gold quoted in USD, 1 pip = $0.10 on 0.01 lot)
        pip_size = 0.1   # 1 pip = $0.10 price move on gold
        sl_dist  = cfg["sl_pips"] * pip_size       # 100 pips = $10 distance
        tp_dist  = cfg["target_pips"] * pip_size   # 200 pips = $20 distance

        # ── Session open momentum detection ──────────────────────────────────
        # Look at the last 3 bars — if there's a clear directional push,
        # the session direction is established. Enter on first pullback.
        recent = df_15m.tail(cfg["session_open_bars"] + 2)
        opens  = float(recent["open"].iloc[0])
        highs  = float(recent["high"].max())
        lows   = float(recent["low"].min())
        closes = float(recent["close"].iloc[-1])

        # Session range
        sess_range = highs - lows
        if sess_range < sl_dist * 0.5:  # not enough movement yet
            return None

        # Direction: close of last N bars vs open of first bar
        bull_session = closes > opens and (closes - opens) > sess_range * 0.3
        bear_session = closes < opens and (opens - closes) > sess_range * 0.3

        # Pullback detection: after initial push, price pulled back
        # Bull pullback: recent low is lower than mid-session price
        mid = (highs + lows) / 2

        # ── LONG SETUP ────────────────────────────────────────────────────────
        if bull_session and rsi < 65:
            # Detect pullback: current price came down from the high
            pulled_back  = float(last["low"]) < float(prev["high"])
            near_ema     = float(last.get("ema_fast", cur)) > 0
            ema20        = float(last.get("ema_fast", cur))
            # Entry: on pullback to EMA20 or mid-session level
            at_pullback  = abs(cur - max(ema20, lows + sess_range * 0.3)) / cur < 0.002
            closing_up   = float(last["close"]) > float(last["open"])  # bull confirmation candle

            if (pulled_back or at_pullback) and closing_up:
                e  = cur
                sl = round(e - sl_dist, 2)
                tp = round(e + tp_dist, 2)
                rr = tp_dist / sl_dist  # always 2.0
                sess_name = "London" if is_london_open else "NY"
                return Signal(
                    "intraday_scalp", "long",
                    round(e, 2), sl, tp, round(rr, 2),
                    0, "", session, "15M",
                    f"{sess_name} open pullback | SL {sl:.2f} | TP {tp:.2f} | "
                    f"Target: 200 pips = $20 | Daily: ${daily_achieved:.1f}/${cfg['daily_target']}"
                )

        # ── SHORT SETUP ───────────────────────────────────────────────────────
        if bear_session and rsi > 35:
            pulled_back = float(last["high"]) > float(prev["low"])
            ema20       = float(last.get("ema_fast", cur))
            at_pullback = abs(cur - min(ema20, highs - sess_range * 0.3)) / cur < 0.002
            closing_dn  = float(last["close"]) < float(last["open"])

            if (pulled_back or at_pullback) and closing_dn:
                e  = cur
                sl = round(e + sl_dist, 2)
                tp = round(e - tp_dist, 2)
                rr = tp_dist / sl_dist
                sess_name = "London" if is_london_open else "NY"
                return Signal(
                    "intraday_scalp", "short",
                    round(e, 2), sl, tp, round(rr, 2),
                    0, "", session, "15M",
                    f"{sess_name} open pullback | SL {sl:.2f} | TP {tp:.2f} | "
                    f"Target: 200 pips = $20 | Daily: ${daily_achieved:.1f}/${cfg['daily_target']}"
                )

        return None

    # ── PIPELINE ──────────────────────────────────────────────────────────────
    def run_all(self, df_15m, df_1h, sr_all, session, htf_bias,
                regime, rw, daily_achieved=0.0):
        from core.config import CONFIG as CFG
        candidates = []
        sa = SessionAnalyzer()

        if CFG["strategies"]["liquidity_sweep"]["active"]:
            s = self.liquidity_sweep(df_15m, sr_all[:8])
            if s and sa.allowed(session, "liquidity_sweep"):
                candidates.append(s)

        if CFG["strategies"]["trend_continuation"]["active"] and session != "asian":
            s = self.trend_continuation(df_1h, htf_bias)
            if s:
                candidates.append(s)

        if CFG["strategies"]["breakout_expansion"]["active"] and \
                session in ("london", "ny", "overlap"):
            s = self.breakout_expansion(df_1h, sr_all[:8])
            if s:
                candidates.append(s)

        if CFG["strategies"]["ema_momentum"]["active"] and regime != "high_vol_news":
            s = self.ema_momentum(df_1h)
            if s:
                candidates.append(s)

        if CFG["strategies"]["intraday_scalp"]["active"]:
            s = self.intraday_scalp(df_15m, session, regime, daily_achieved)
            if s:
                candidates.append(s)

        return candidates
