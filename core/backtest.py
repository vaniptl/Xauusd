import numpy as np
import pandas as pd
from core.config import CONFIG, REGIME_LABELS, REGIME_WEIGHTS
from core.regime import RegimeClassifier


class BacktestEngine:

    def _make_signals(self, df, strategy, p):
        sigs = pd.Series(0, index=df.index)
        ef  = df.get("ema_fast", pd.Series(index=df.index))
        em  = df.get("ema_med",  pd.Series(index=df.index))
        es  = df.get("ema_slow", pd.Series(index=df.index))
        rsi = df.get("rsi",      pd.Series(50, index=df.index))
        vr  = df.get("vol_ratio", pd.Series(1.0, index=df.index))
        if strategy == "ema_momentum":
            sigs[(ef > em) & (em > es) & (rsi < p.get("rsi_up", 65))]  =  1
            sigs[(ef < em) & (em < es) & (rsi > p.get("rsi_dn", 35))]  = -1
        elif strategy == "trend_continuation":
            t = p.get("tol", 0.002)
            sigs[(ef > es) & (df["close"] > em * (1 - t))] =  1
            sigs[(ef < es) & (df["close"] < em * (1 + t))] = -1
        elif strategy == "breakout_expansion":
            vm = p.get("vm", 1.5)
            sigs[(df["close"] > df["close"].shift(1)) & (vr >= vm)] =  1
            sigs[(df["close"] < df["close"].shift(1)) & (vr >= vm)] = -1
        elif strategy == "liquidity_sweep":
            lk  = p.get("lk", 5)
            sl2 = df["low"].rolling(lk).min()
            sh2 = df["high"].rolling(lk).max()
            sigs[(df["low"] < sl2.shift(1)) & (df["close"] > sl2.shift(1))]  =  1
            sigs[(df["high"] > sh2.shift(1)) & (df["close"] < sh2.shift(1))] = -1
        return sigs.shift(1).fillna(0)

    def run_strategy(self, df, strategy, sl_pct=0.008, tp_pct=0.016,
                     balance=10000, risk_pct=0.01):
        p = {"sl": sl_pct, "tp": tp_pct}
        sigs = self._make_signals(df, strategy, p)
        return self._simulate(df, sigs, sl_pct, tp_pct, balance, risk_pct)

    def _simulate(self, df, signals, sl_pct, tp_pct, balance, risk_pct):
        eq = [balance]; trades = []
        in_t = False; dir_ = 0; ep = sl = tp = 0.0
        entry_idx = None

        for i in range(1, len(df)):
            row = df.iloc[i]; sig = signals.iloc[i - 1]
            if not in_t and sig != 0:
                dir_ = sig; ep = row["open"]
                sl = ep * (1 - sl_pct) if dir_ == 1 else ep * (1 + sl_pct)
                tp = ep * (1 + tp_pct) if dir_ == 1 else ep * (1 - tp_pct)
                in_t = True; entry_idx = i
            elif in_t:
                hit_sl = (dir_ == 1 and row["low"] <= sl) or \
                         (dir_ == -1 and row["high"] >= sl)
                hit_tp = (dir_ == 1 and row["high"] >= tp) or \
                         (dir_ == -1 and row["low"] <= tp)
                if hit_sl:
                    balance -= balance * risk_pct
                    trades.append({"win": False, "pnl": -balance * risk_pct,
                                   "date": row.name, "dir": dir_})
                    in_t = False
                elif hit_tp:
                    rr = tp_pct / sl_pct
                    balance += balance * risk_pct * rr
                    trades.append({"win": True, "pnl": balance * risk_pct * rr,
                                   "date": row.name, "dir": dir_})
                    in_t = False
            eq.append(balance)

        return self._metrics(np.array(eq), trades, eq[0])

    def _metrics(self, eq, trades, initial):
        ret  = np.diff(eq) / eq[:-1]
        wins = [t for t in trades if t["win"]]
        loss = [t for t in trades if not t["win"]]
        sh   = (ret.mean() / (ret.std() + 1e-10)) * np.sqrt(252 * 24)
        peak = eq[0]; mdd = 0
        for e in eq:
            if e > peak: peak = e
            mdd = max(mdd, (peak - e) / peak)
        pf = abs(sum(t["pnl"] for t in wins) /
                 (sum(abs(t["pnl"]) for t in loss) + 1e-10))
        return {
            "sharpe":        round(sh, 3),
            "win_rate":      round(len(wins) / max(len(trades), 1), 3),
            "total_trades":  len(trades),
            "wins":          len(wins),
            "losses":        len(loss),
            "total_pnl":     round(eq[-1] - initial, 2),
            "final_balance": round(eq[-1], 2),
            "pnl_pct":       round((eq[-1] - initial) / initial * 100, 2),
            "max_drawdown":  round(mdd * 100, 2),
            "profit_factor": round(pf, 3),
            "trades":        trades,
            "equity_curve":  eq.tolist(),
        }

    def run_full_backtest(self, df, balance=10000):
        """Run all 4 strategies on 1-year data, return per-strategy + per-regime results."""
        results = {}
        default_params = {"sl_pct": 0.008, "tp_pct": 0.016}

        for strategy in CONFIG["strategies"]:
            r = self.run_strategy(
                df, strategy,
                sl_pct=default_params["sl_pct"],
                tp_pct=default_params["tp_pct"],
                balance=balance
            )
            results[strategy] = r

        return results

    def run_regime_backtest(self, df, balance=10000):
        """Run backtest segmented by regime."""
        rc = RegimeClassifier()

        # Tag each bar with regime
        df = df.copy()
        regimes = []
        window = CONFIG["regime"]["atr_lookback"]
        for i in range(len(df)):
            lb = df.iloc[max(0, i - window):i + 1]
            row = df.iloc[i]
            r = rc.classify_bar(row, lb)
            regimes.append(r)
        df["regime"] = regimes

        regime_results = {}
        all_regimes = df["regime"].unique()

        for regime in all_regimes:
            regime_df = df[df["regime"] == regime].copy()
            if len(regime_df) < 50:
                continue
            strategy_results = {}
            for strategy in CONFIG["strategies"]:
                r = self.run_strategy(
                    regime_df, strategy,
                    sl_pct=0.008, tp_pct=0.016,
                    balance=balance
                )
                strategy_results[strategy] = r
            # Find best strategy for this regime
            best_strat = max(
                strategy_results,
                key=lambda s: strategy_results[s]["sharpe"]
            )
            regime_results[regime] = {
                "strategies": strategy_results,
                "best_strategy": best_strat,
                "bars": len(regime_df),
                "pct_of_time": round(len(regime_df) / len(df) * 100, 1),
            }

        return regime_results, df

    def monthly_equity(self, df, strategy, balance=10000):
        """Return monthly P&L breakdown."""
        r = self.run_strategy(df, strategy, balance=balance)
        trades = r.get("trades", [])
        if not trades:
            return pd.DataFrame()
        tdf = pd.DataFrame(trades)
        tdf["date"] = pd.to_datetime(tdf["date"])
        tdf["month"] = tdf["date"].dt.to_period("M")
        monthly = tdf.groupby("month").agg(
            pnl=("pnl", "sum"),
            trades=("pnl", "count"),
            wins=("win", "sum")
        ).reset_index()
        monthly["win_rate"] = (monthly["wins"] / monthly["trades"] * 100).round(1)
        monthly["pnl"] = monthly["pnl"].round(2)
        return monthly
