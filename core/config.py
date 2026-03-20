CONFIG = {
    "symbol":       "GC=F",
    "symbol_spot":  "XAUUSD=X",
    "timeframes": {
        "1D":  {"period": "2y",   "interval": "1d"},
        "4H":  {"period": "60d",  "interval": "1h"},
        "1H":  {"period": "60d",  "interval": "1h"},
        "15M": {"period": "30d",  "interval": "15m"},
    },
    "sr": {
        "pivot_left":    10,
        "pivot_right":   10,
        "cluster_pct":   0.002,
        "min_touches":   2,
        "lookback_bars": 250,
        "zone_flip_pct": 0.003,
        "max_levels":    15,
    },
    "strategies": {
        "liquidity_sweep":    {"weight": 1.0, "min_rr": 2.0, "active": True,
                               "sweep_pct": 0.001, "reverse_bars": 3},
        "trend_continuation": {"weight": 1.0, "min_rr": 1.5, "active": True,
                               "pullback_ema": 50, "confirm_bars": 2},
        "breakout_expansion": {"weight": 1.0, "min_rr": 2.0, "active": True,
                               "consolidation_bars": 4, "vol_multiplier": 1.5},
        "ema_momentum":       {"weight": 1.0, "min_rr": 1.5, "active": True,
                               "slope_min": 0.0001},
    },
    "ema": {"fast": 20, "medium": 50, "slow": 200},
    "risk": {
        "account_balance":      10000,
        "risk_per_trade_pct":   1.0,
        "max_daily_loss_pct":   3.0,
        "drawdown_half_at":     5.0,
        "drawdown_quarter_at":  10.0,
        "kelly_fraction":       0.25,
        "min_rr":               1.5,
        "atr_sl_multiplier":    1.5,
        "atr_period":           14,
        "pip_value_per_lot":    10.0,
    },
    "wfo": {
        "in_sample_bars":     300,
        "out_sample_bars":    75,
        "n_trials":           30,
        "metric":             "sharpe",
    },
    "regime": {
        "adx_period":           14,
        "adx_trend_threshold":  25,
        "atr_pct_high":         0.015,
        "atr_pct_low":          0.005,
        "atr_lookback":         20,
    },
    "fibonacci": {
        "retracements":   [0.236, 0.382, 0.5, 0.618, 0.786],
        "extensions":     [1.0, 1.272, 1.618, 2.0],
        "tolerance_pct":  0.002,
        "min_swing_pips": 50,
    },
    "sessions": {
        "asian":   {"start": 23, "end": 7},
        "london":  {"start": 7,  "end": 12},
        "ny":      {"start": 13, "end": 17},
        "overlap": {"start": 12, "end": 16},
    },
    "signal": {
        "min_confluence_score": 6,
    },
    "dead_strategy": {
        "min_sharpe":              0.3,
        "max_consecutive_losses":  5,
    },
    "db_path": "xauusd_trading.db",
}

REGIME_LABELS = {
    "trending_bull":  "TRENDING BULL",
    "trending_bear":  "TRENDING BEAR",
    "ranging":        "RANGING",
    "high_vol_news":  "HIGH VOL/NEWS",
    "low_liq_grind":  "LOW LIQ GRIND",
}

REGIME_WEIGHTS = {
    "trending_bull":  {"liquidity_sweep": 0.8, "trend_continuation": 1.5,
                       "breakout_expansion": 1.2, "ema_momentum": 1.5},
    "trending_bear":  {"liquidity_sweep": 0.8, "trend_continuation": 1.5,
                       "breakout_expansion": 1.2, "ema_momentum": 1.5},
    "ranging":        {"liquidity_sweep": 1.8, "trend_continuation": 0.5,
                       "breakout_expansion": 0.6, "ema_momentum": 0.5},
    "high_vol_news":  {"liquidity_sweep": 0.3, "trend_continuation": 0.3,
                       "breakout_expansion": 0.5, "ema_momentum": 0.3},
    "low_liq_grind":  {"liquidity_sweep": 1.5, "trend_continuation": 0.6,
                       "breakout_expansion": 0.4, "ema_momentum": 0.7},
}

STRATEGY_DISPLAY = {
    "liquidity_sweep":    "LIQ SWEEP",
    "trend_continuation": "TREND CONT",
    "breakout_expansion": "BREAKOUT",
    "ema_momentum":       "EMA MOM",
}
