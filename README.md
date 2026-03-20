# XAUUSD Intelligence Terminal

Bloomberg-style algorithmic trading dashboard for XAUUSD (Gold Spot).  
**100% free stack — deploys to Streamlit Cloud in under 5 minutes.**

---

## Pages

| Page | What it does |
|------|-------------|
| **Dashboard** | Live price + regime + S/R + active signals + confluence breakdown |
| **Signals** | Full signal history table with filters + export |
| **Backtest** | 1-year backtest across all 4 strategies, regime breakdown, monthly P&L |
| **Risk Manager** | Lot size calculator, next buy/sell levels, drawdown circuit breakers |
| **Trade History** | Daily trade log, monthly profit %, strategy breakdown |
| **S/R Chart** | Interactive candlestick + all S/R levels + EMA + RSI + ADX |

---

## Deploy to Streamlit Cloud (Free)

### Step 1 — Push to GitHub

```bash
# In your terminal
git init
git add .
git commit -m "XAUUSD Intelligence Terminal v1.0"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/xauusd-terminal.git
git push -u origin main
```

### Step 2 — Deploy on Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Sign in with GitHub
3. Click **New app**
4. Select your repo: `YOUR_USERNAME/xauusd-terminal`
5. Main file: `app.py`
6. Click **Deploy**

That's it. Your terminal will be live at:  
`https://YOUR_USERNAME-xauusd-terminal-app-XXXX.streamlit.app`

---

## Folder Structure

```
xauusd-terminal/
├── app.py                      ← Main dashboard (Bloomberg terminal)
├── requirements.txt
├── .streamlit/
│   └── config.toml             ← Dark theme + font config
├── core/
│   ├── config.py               ← All strategy parameters (edit here)
│   ├── data_engine.py          ← yfinance multi-TF data fetcher
│   ├── sr_engine.py            ← Fractal pivot + zone flip S/R detection
│   ├── regime.py               ← 5-state market regime classifier
│   ├── strategies.py           ← 4 trading strategies
│   ├── confluence.py           ← 9-factor scoring system (0-10)
│   ├── risk_engine.py          ← Fractional Kelly + drawdown control
│   ├── backtest.py             ← 1-year backtest + regime breakdown
│   ├── cot.py                  ← CFTC COT data integration (free API)
│   └── terminal_theme.py       ← Bloomberg CSS + HTML components
├── database/
│   └── db.py                   ← SQLite persistence
└── pages/
    ├── 01_Signals.py           ← Signal history + export
    ├── 02_Backtest.py          ← 1-year backtest engine
    ├── 03_Risk_Manager.py      ← Lot sizing + next levels
    ├── 04_Trade_History.py     ← Daily log + monthly %
    └── 05_SR_Chart.py          ← Interactive S/R chart
```

---

## Configuration

All parameters in `core/config.py`:

```python
CONFIG = {
    "risk": {
        "account_balance":      10000,   # ← YOUR BALANCE
        "risk_per_trade_pct":   1.0,     # % risk per trade
        "max_daily_loss_pct":   3.0,     # kill switch trigger
        "drawdown_half_at":     5.0,     # half size at 5% DD
        "drawdown_quarter_at":  10.0,    # quarter size at 10% DD
        "kelly_fraction":       0.25,    # 25% fractional Kelly
    },
    "signal": {
        "min_confluence_score": 6,       # min score out of 10 to fire
    },
}
```

---

## Tech Stack (All Free)

| Component | Library |
|-----------|---------|
| UI | Streamlit |
| Data | yfinance |
| Indicators | pandas-ta |
| Optimization | Optuna |
| Charts | Plotly |
| Database | SQLite |
| COT Data | CFTC Public API |
| Deployment | Streamlit Cloud |

---

## Strategies

1. **Liquidity Sweep** — Stop hunt reversal. Best in ranging markets (1.8× weight).
2. **Trend Continuation** — EMA50 pullback. Best in trending markets (1.5× weight).
3. **Breakout Expansion** — Volume-confirmed retest. London/NY only.
4. **EMA Momentum** — Golden/death cross + RSI filter. Disabled in high-vol.

All signals require **6/10 minimum confluence score** from 9 factors before firing.

---

## Live Data

- **Price**: `GC=F` (Gold Futures) via yfinance — auto-falls back to `XAUUSD=X`
- **COT**: CFTC Public Reporting API (free, weekly)
- **Refresh**: Manual (Run Cycle button) or auto every 5/15/30 min

---

*Built for professional XAUUSD equity management. 100% free stack.*
