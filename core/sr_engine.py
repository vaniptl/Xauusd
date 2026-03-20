import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from datetime import datetime
from core.config import CONFIG


@dataclass
class SRLevel:
    price: float
    role: str           # 'support' | 'resistance'
    touches: int
    timeframe: str
    strength: float
    last_touch: Optional[datetime] = None


class SREngine:
    def __init__(self):
        self.cfg = CONFIG["sr"]

    def find_pivots(self, df):
        L, R = self.cfg["pivot_left"], self.cfg["pivot_right"]
        highs, lows = [], []
        for i in range(L, len(df) - R):
            if all(df["high"].iloc[i] >= df["high"].iloc[i - j] for j in range(1, L + 1)) and \
               all(df["high"].iloc[i] >= df["high"].iloc[i + j] for j in range(1, R + 1)):
                highs.append(df["high"].iloc[i])
            if all(df["low"].iloc[i] <= df["low"].iloc[i - j] for j in range(1, L + 1)) and \
               all(df["low"].iloc[i] <= df["low"].iloc[i + j] for j in range(1, R + 1)):
                lows.append(df["low"].iloc[i])
        return highs, lows

    def cluster(self, levels):
        if not levels:
            return []
        pct = self.cfg["cluster_pct"]
        out, cur = [], [sorted(levels)[0]]
        for lvl in sorted(levels)[1:]:
            if abs(lvl - cur[0]) / cur[0] <= pct:
                cur.append(lvl)
            else:
                out.append((np.mean(cur), len(cur)))
                cur = [lvl]
        out.append((np.mean(cur), len(cur)))
        return [(p, t) for p, t in out if t >= self.cfg["min_touches"]]

    def apply_flips(self, levels, df):
        fp = self.cfg["zone_flip_pct"]
        for bar in df.itertuples():
            for lvl in levels:
                if lvl.role == "support" and bar.close < lvl.price * (1 - fp):
                    lvl.role = "resistance"
                    lvl.last_touch = bar.Index
                elif lvl.role == "resistance" and bar.close > lvl.price * (1 + fp):
                    lvl.role = "support"
                    lvl.last_touch = bar.Index
        return levels

    def detect(self, df, timeframe):
        if df.empty or len(df) < 30:
            return []
        recent = df.tail(self.cfg["lookback_bars"])
        ph, pl = self.find_pivots(recent)
        cur = df["close"].iloc[-1]
        rounds = [round(cur / 50) * 50 + i * 50 for i in range(-6, 7)]
        ph += [p for p in rounds if p > cur * 0.998]
        pl += [p for p in rounds if p < cur * 1.002]
        levels = []
        for price, touches in self.cluster(pl):
            levels.append(SRLevel(
                round(price, 2),
                "support" if price < cur else "resistance",
                touches, timeframe, min(touches / 5.0, 1.0)
            ))
        for price, touches in self.cluster(ph):
            levels.append(SRLevel(
                round(price, 2),
                "resistance" if price > cur else "support",
                touches, timeframe, min(touches / 5.0, 1.0)
            ))
        levels = self.apply_flips(levels, recent)
        return sorted(levels, key=lambda x: x.price)[:self.cfg["max_levels"]]

    def nearest(self, levels, price, n=4):
        sup = sorted(
            [l for l in levels if l.role == "support" and l.price < price],
            key=lambda x: price - x.price
        )
        res = sorted(
            [l for l in levels if l.role == "resistance" and l.price > price],
            key=lambda x: x.price - price
        )
        return sup[:n], res[:n]

    def detect_all_tf(self, data_dict, de):
        """Detect S/R across all timeframes."""
        all_levels = []
        for tf in ["1D", "4H", "1H", "15M"]:
            df = de.add_indicators(data_dict.get(tf, pd.DataFrame()))
            if not df.empty:
                all_levels.extend(self.detect(df, tf))
        return all_levels
