import numpy as np
from core.config import CONFIG


class RiskEngine:
    def __init__(self, balance=None):
        self.cfg    = CONFIG["risk"]
        self.bal    = balance or self.cfg["account_balance"]
        self.peak   = self.bal
        self.d_bal  = self.bal
        self.d_pnl  = 0.0
        self.trades_today = 0

    def update(self, pnl):
        self.bal   += pnl
        self.d_pnl += pnl
        self.peak   = max(self.peak, self.bal)

    def dd(self):
        return (self.peak - self.bal) / self.peak * 100 if self.peak else 0

    def daily_loss(self):
        return abs(self.d_pnl) / self.d_bal * 100 if self.d_pnl < 0 else 0

    def kill_switch(self):
        dl = self.daily_loss()
        dd = self.dd()
        if dl >= self.cfg["max_daily_loss_pct"]:
            return True, f"Daily loss limit: {dl:.1f}%"
        if dd >= 15:
            return True, f"Max drawdown: {dd:.1f}%"
        return False, ""

    def size_mult(self):
        d = self.dd()
        if d >= self.cfg["drawdown_quarter_at"]:
            return 0.25
        if d >= self.cfg["drawdown_half_at"]:
            return 0.50
        return 1.0

    def kelly(self, win_rate, avg_rr):
        if avg_rr <= 0:
            return self.cfg["risk_per_trade_pct"] / 100
        k = max(0, win_rate - (1 - win_rate) / avg_rr)
        return min(k * self.cfg["kelly_fraction"], 0.02)

    def position_size(self, entry, sl, win_rate=0.5, avg_rr=1.5):
        kill, reason = self.kill_switch()
        if kill:
            return {"lots": 0, "blocked": True, "reason": reason,
                    "risk_usd": 0, "risk_pct": 0, "sl_pips": 0}
        sl_d = abs(entry - sl)
        if sl_d <= 0:
            return {"lots": 0, "blocked": True, "reason": "Invalid SL",
                    "risk_usd": 0, "risk_pct": 0, "sl_pips": 0}
        rp      = self.kelly(win_rate, avg_rr)
        ru      = self.bal * rp * self.size_mult()
        sl_pips = sl_d * 10
        pv      = self.cfg.get("pip_value_per_lot", 10.0)
        lots    = ru / (sl_pips * pv) if sl_pips > 0 else 0
        return {
            "lots":     round(lots, 2),
            "risk_usd": round(ru, 2),
            "risk_pct": round(rp * 100, 3),
            "sl_pips":  round(sl_pips, 1),
            "balance":  round(self.bal, 2),
            "dd_pct":   round(self.dd(), 2),
            "mult":     self.size_mult(),
            "blocked":  False,
        }

    def next_levels(self, current_price, sr_levels):
        """Compute next buy/sell price targets from S/R levels."""
        supports    = sorted([l for l in sr_levels if l.role == "support" and l.price < current_price],
                             key=lambda x: current_price - x.price)
        resistances = sorted([l for l in sr_levels if l.role == "resistance" and l.price > current_price],
                             key=lambda x: x.price - current_price)
        result = {
            "next_buy":     supports[0].price if supports else None,
            "next_buy_tf":  supports[0].timeframe if supports else None,
            "next_sell":    resistances[0].price if resistances else None,
            "next_sell_tf": resistances[0].timeframe if resistances else None,
        }
        return result

    def reset_daily(self):
        self.d_bal        = self.bal
        self.d_pnl        = 0.0
        self.trades_today = 0

    def monthly_profit_pct(self, trades_df):
        """Compute monthly profit % from closed trades DataFrame."""
        if trades_df is None or trades_df.empty:
            return {}
        closed = trades_df[trades_df["status"] == "CLOSED"].copy()
        if closed.empty:
            return {}
        closed["ts"] = pd.to_datetime(closed["ts"])
        closed["month"] = closed["ts"].dt.to_period("M")
        monthly = closed.groupby("month")["pnl_r"].sum().to_dict()
        return {str(k): round(v, 2) for k, v in monthly.items()}
