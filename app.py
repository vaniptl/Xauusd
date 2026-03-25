"""
XAUUSD Intelligence Terminal — app.py
Fixes applied:
  #1 Persistent DB — trades saved permanently across sessions
  #2 Signals tab shows exact buy/sell/SL/TP prices
  #3 PnL compounds into account balance automatically
  #4 Intraday Scalp strategy — $20/day, 200 pip target
  #5 Positions section always populated (fixed pipeline pass-through)
  #6 Auto 15-min refresh for 24/7 operation
  #7 Mobile-responsive UI — collapsible sidebar, touch-friendly
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta, timezone
import time, sys, os
sys.path.insert(0, os.path.dirname(__file__))

from core.config import CONFIG, REGIME_LABELS, STRATEGY_DISPLAY
from core.data_engine import DataEngine
from core.sr_engine import SREngine
from core.regime import RegimeClassifier
from core.strategies import StrategyEngine, SessionAnalyzer
from core.confluence import ConfluenceScorer
from core.risk_engine import RiskEngine
from core.cot import COTIntegration
from core.terminal_theme import TERMINAL_CSS, section_header, live_price_bar, status_footer
from database.db import Database

# ── PAGE CONFIG ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="XAUUSD TERMINAL",
    page_icon="🟡",
    layout="wide",
    initial_sidebar_state="expanded",   # Always show sidebar
)

# ── MOBILE-RESPONSIVE CSS ──────────────────────────────────────────────────────
MOBILE_CSS = """
<style>
/* Force hamburger/arrow always visible on all screen sizes */
[data-testid="collapsedControl"] {
  display: flex !important;
  visibility: visible !important;
  opacity: 1 !important;
}
section[data-testid="stSidebarCollapsedControl"] {
  display: flex !important;
  visibility: visible !important;
}
/* Sidebar width */
[data-testid="stSidebar"] {
  min-width: 240px !important;
  max-width: 280px !important;
}
/* Mobile: stack columns */
@media (max-width: 640px) {
  .main .block-container { padding: 0.4rem !important; }
  section[data-testid="stSidebar"] { min-width: 200px !important; }
}
</style>
"""
st.markdown(TERMINAL_CSS + MOBILE_CSS, unsafe_allow_html=True)

# ── SESSION STATE ──────────────────────────────────────────────────────────────
for key, default in [
    ("last_fetch",  None),
    ("last_result", None),
    ("auto_running", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default

db = Database()

# ── SIDEBAR ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;
                color:#f0a500;letter-spacing:2px;padding:8px 0;
                border-bottom:1px solid #1e2736;margin-bottom:10px">
    ◈ XAUUSD TERMINAL
    </div>
    """, unsafe_allow_html=True)

    # Account balance from DB
    live_balance = db.get_balance()
    st.markdown(f"""
    <div style="background:#0a2818;border:1px solid #1a4a30;padding:8px;
                font-family:IBM Plex Mono,monospace;margin-bottom:8px">
      <div style="font-size:8px;color:#4a5568;letter-spacing:1px">LIVE BALANCE</div>
      <div style="font-size:18px;font-weight:600;color:#26d17a">${live_balance:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)

    min_score = st.slider("Min Score", 4, 9, 6)

    st.markdown("---")
    st.markdown('<div style="font-size:9px;color:#4a5568;text-transform:uppercase;'
                'letter-spacing:1px;margin-bottom:6px">Strategies</div>',
                unsafe_allow_html=True)
    show_liq   = st.checkbox("Liq Sweep",    value=True)
    show_trend = st.checkbox("Trend Cont",   value=True)
    show_bo    = st.checkbox("Breakout",     value=True)
    show_ema   = st.checkbox("EMA Mom",      value=True)
    show_intra = st.checkbox("Intra $20",    value=True)

    st.markdown("---")

    # Fix #6: 24/7 auto-refresh
    auto_on = st.toggle("🤖 24/7 AUTO BOT", value=st.session_state.auto_running)
    st.session_state.auto_running = auto_on
    if auto_on:
        st.markdown("""
        <div style="background:#0a1a0a;border:1px solid #1a4a1a;padding:6px;
                    font-family:IBM Plex Mono,monospace;font-size:9px;color:#26d17a">
          ● BOT ACTIVE — auto cycle every 15 min
        </div>
        """, unsafe_allow_html=True)

    run_btn = st.button("▶ RUN NOW", width='stretch')

    # Daily goal progress
    goal = db.get_daily_goal()
    pct  = min(goal["pct"], 100)
    gc   = "#26d17a" if goal["achieved"] >= goal["target"] else "#f0a500"
    st.markdown(f"""
    <div style="margin-top:8px;background:#0d111a;border:1px solid #1e2736;
                padding:8px;font-family:IBM Plex Mono,monospace">
      <div style="font-size:8px;color:#4a5568;letter-spacing:1px;margin-bottom:4px">
        DAILY GOAL — $20 TARGET
      </div>
      <div style="font-size:14px;font-weight:600;color:{gc}">
        ${goal['achieved']:.2f} / ${goal['target']:.0f}
      </div>
      <div style="height:4px;background:#1e2736;margin-top:5px;border-radius:2px">
        <div style="height:4px;width:{pct}%;background:{gc};border-radius:2px"></div>
      </div>
      <div style="font-size:8px;color:#4a5568;margin-top:3px">
        {goal['trades']} trades today
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Quick deposit input
    st.markdown("---")
    dep_amt = st.number_input("Deposit / Adjust Balance ($)", min_value=0,
                               value=0, step=100)
    if st.button("Add to Account") and dep_amt > 0:
        db.deposit(dep_amt)
        st.success(f"Added ${dep_amt}")
        st.rerun()

# ── TITLE BAR ──────────────────────────────────────────────────────────────────
now_utc   = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
bot_active = st.session_state.auto_running
st.markdown(
    f"""
    <div style="display:flex;justify-content:space-between;align-items:center;
                border-bottom:1px solid #1e2736;padding-bottom:6px;margin-bottom:10px;
                flex-wrap:wrap;gap:6px">
      <div style="font-family:'IBM Plex Mono',monospace;font-size:13px;font-weight:600;
                  color:#f0a500;letter-spacing:2px">◈ XAUUSD TERMINAL</div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        {'<span style="background:#0a2818;color:#26d17a;border:1px solid #1a4a30;font-family:IBM Plex Mono,monospace;font-size:9px;padding:2px 8px;letter-spacing:1px">● BOT ON</span>' if bot_active else ""}
        <span style="font-family:IBM Plex Mono,monospace;font-size:9px;color:#4a5568">{now_utc} UTC</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True
)

# ── COT (cached 1h) ───────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_cot():
    try:
        return COTIntegration().fetch()
    except Exception:
        return {}

# ── PIPELINE ───────────────────────────────────────────────────────────────────
def run_pipeline(min_score):
    """
    Full signal pipeline. Returns (state, df_1h, sr_all, signals_out, positions).
    Fix #5: signals saved to DB here — positions always reflect what was saved.
    """
    de = DataEngine()
    de.fetch_all()

    df_15m = de.get("15M")
    df_1h  = de.get("1H")
    df_4h  = de.get("4H")
    df_1d  = de.get("1D")

    if df_1h.empty:
        return None, None, None, [], []

    price  = float(df_1h["close"].iloc[-1])
    prev   = float(df_1h["close"].iloc[-2]) if len(df_1h) > 1 else price
    change = price - prev
    ch_pct = change / prev * 100 if prev else 0

    # Fix #3: auto-close open trades at current price
    closed_now = db.auto_close_open_trades(price)

    rc       = RegimeClassifier()
    regime   = rc.classify(df_1h)
    rw       = rc.weights(regime)
    htf_bias = rc.get_htf_bias(df_4h, df_1d)
    session  = SessionAnalyzer().get(datetime.now(timezone.utc))

    sre    = SREngine()
    sr_all = sre.detect_all_tf(
        {"1D": de.data.get("1D"), "4H": de.data.get("4H"),
         "1H": de.data.get("1H"), "15M": de.data.get("15M")}, de
    )

    # Fibonacci
    fib_levels = {}
    if not df_4h.empty and len(df_4h) > 20:
        recent = df_4h.tail(100)
        lo, hi = float(recent["low"].min()), float(recent["high"].max())
        lo_i   = recent["low"].idxmin()
        hi_i   = recent["high"].idxmax()
        if lo_i < hi_i and (hi - lo) * 10 >= 50:
            d = hi - lo
            fib_levels = {
                "retracements": {round(r, 3): round(hi - r * d, 2)
                                 for r in [0.236, 0.382, 0.5, 0.618, 0.786]},
                "extensions":   {round(e, 3): round(lo + e * d, 2)
                                 for e in [1.0, 1.272, 1.618, 2.0]},
            }

    cot_data = load_cot()
    cot_bias = cot_data.get("bias", "neutral") if cot_data else "neutral"

    # Set strategy active flags from sidebar checkboxes
    CONFIG["strategies"]["liquidity_sweep"]["active"]    = show_liq
    CONFIG["strategies"]["trend_continuation"]["active"] = show_trend
    CONFIG["strategies"]["breakout_expansion"]["active"] = show_bo
    CONFIG["strategies"]["ema_momentum"]["active"]       = show_ema
    CONFIG["strategies"]["intraday_scalp"]["active"]     = show_intra

    # Daily goal from DB
    goal           = db.get_daily_goal()
    daily_achieved = goal["achieved"]

    se  = StrategyEngine()
    cs  = ConfluenceScorer()
    balance = db.get_balance()
    re  = RiskEngine(balance=balance)

    # Fix #5: run_all now passes daily_achieved so intraday stops at $20
    candidates = se.run_all(
        df_15m, df_1h, sr_all, session, htf_bias, regime, rw,
        daily_achieved=daily_achieved
    )

    signals_out = []   # Section A: all candidates with scores
    positions   = []   # Section B: only qualified positions saved to DB

    for sig in candidates:
        sig.regime  = regime
        sig.session = session
        w           = rw.get(sig.strategy, 1.0)
        score, breakdown = cs.score(
            sig, df_1h, df_4h, df_1d, sr_all, fib_levels,
            regime, session, cot_bias, rw
        )
        sig.score = score
        signals_out.append((sig, score, breakdown, w))

        # Fix #5: threshold check — this is why positions were empty
        if score >= min_score and w >= 0.4:
            st_stats = db.get_stats(sig.strategy)
            wr_est   = st_stats["wins"] / max(st_stats["wins"] + st_stats["losses"], 1) or 0.5
            sizing   = re.position_size(sig.entry, sig.sl, win_rate=wr_est, avg_rr=sig.rr)
            if not sizing.get("blocked"):
                sig_id = db.save_signal(sig, sizing)   # Fix #1: always saved to SQLite
                positions.append((sig, score, sizing, sig_id))

    signals_out.sort(key=lambda x: -x[1])

    state = {
        "price":      price,    "change":   change,    "ch_pct":   ch_pct,
        "regime":     regime,   "rw":       rw,        "htf_bias": htf_bias,
        "session":    session,  "cot_bias": cot_bias,  "cot_data": cot_data,
        "sr_all":     sr_all,   "fib":      fib_levels,
        "closed_now": closed_now,
        "balance":    balance,
        "atr":   float(df_1h["atr"].iloc[-1])      if "atr"      in df_1h.columns else 0,
        "adx":   float(df_1h["adx"].iloc[-1])      if "adx"      in df_1h.columns else 0,
        "rsi":   float(df_1h["rsi"].iloc[-1])      if "rsi"      in df_1h.columns else 50,
        "ema_f": float(df_1h["ema_fast"].iloc[-1]) if "ema_fast" in df_1h.columns else 0,
        "ema_m": float(df_1h["ema_med"].iloc[-1])  if "ema_med"  in df_1h.columns else 0,
        "ema_s": float(df_1h["ema_slow"].iloc[-1]) if "ema_slow" in df_1h.columns else 0,
    }
    return state, df_1h, sr_all, signals_out, positions

# ── RUN ────────────────────────────────────────────────────────────────────────
trigger = run_btn or (st.session_state.auto_running and st.session_state.last_fetch is None)
if trigger:
    with st.spinner("RUNNING PIPELINE..."):
        result = run_pipeline(min_score)
        # Validate result is 5-tuple before saving
        if result is not None and len(result) == 5:
            st.session_state.last_result = result
            st.session_state.last_fetch  = datetime.now(timezone.utc)

result = st.session_state.get("last_result")

# Guard against stale 6-value results from old session
if result is not None and len(result) != 5:
    st.session_state.last_result = None
    result = None

# ── PLACEHOLDER ────────────────────────────────────────────────────────────────
if result is None or result[0] is None:
    stats = db.summary_stats()
    bal   = db.get_balance()
    goal  = db.get_daily_goal()
    st.markdown(f"""
    <div style="background:#0d111a;border:1px solid #1e2736;border-top:2px solid #f0a500;
                padding:30px;text-align:center;font-family:'IBM Plex Mono',monospace;
                margin-bottom:16px">
      <div style="font-size:24px;color:#f0a500;margin-bottom:10px">◈</div>
      <div style="font-size:12px;color:#c8d0e0;letter-spacing:2px;margin-bottom:6px">
        XAUUSD INTELLIGENCE TERMINAL
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px;
                  max-width:600px;margin:20px auto 0">
        <div style="border:1px solid #1e2736;padding:10px">
          <div style="font-size:7px;color:#4a5568;letter-spacing:1px">BALANCE</div>
          <div style="font-size:14px;color:#26d17a;font-weight:600">${bal:,.2f}</div>
        </div>
        <div style="border:1px solid #1e2736;padding:10px">
          <div style="font-size:7px;color:#4a5568;letter-spacing:1px">TOTAL TRADES</div>
          <div style="font-size:14px;color:#c8d0e0;font-weight:600">{stats['total_signals']}</div>
        </div>
        <div style="border:1px solid #1e2736;padding:10px">
          <div style="font-size:7px;color:#4a5568;letter-spacing:1px">WIN RATE</div>
          <div style="font-size:14px;color:#{'26d17a' if stats['win_rate']>=55 else 'f0a500'};font-weight:600">{stats['win_rate']}%</div>
        </div>
        <div style="border:1px solid #1e2736;padding:10px">
          <div style="font-size:7px;color:#4a5568;letter-spacing:1px">TODAY P&L</div>
          <div style="font-size:14px;color:#{'26d17a' if goal['achieved']>=0 else 'e05555'};font-weight:600">${goal['achieved']:.2f}</div>
        </div>
      </div>
      <div style="font-size:10px;color:#4a5568;margin-top:20px">
        CLICK ▶ RUN NOW IN SIDEBAR — OR ENABLE 24/7 AUTO BOT
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

state, df_1h, sr_all, signals_out, positions = result

# ── PRICE BAR ──────────────────────────────────────────────────────────────────
st.markdown(live_price_bar(
    state["price"], state["change"], state["ch_pct"],
    state["session"], REGIME_LABELS.get(state["regime"], state["regime"]),
    state["atr"], state["adx"], state["rsi"],
    datetime.now(timezone.utc).strftime("%H:%M:%S")
), unsafe_allow_html=True)

# Auto-close notification
if state.get("closed_now"):
    for ct in state["closed_now"]:
        color = "#26d17a" if ct["outcome"] == "WIN" else "#e05555"
        st.markdown(f"""
        <div style="background:{'#0a1a0a' if ct['outcome']=='WIN' else '#1a0a0a'};
                    border:1px solid {color};padding:6px 12px;
                    font-family:IBM Plex Mono,monospace;font-size:10px;margin-bottom:4px">
          ● AUTO-CLOSED Trade #{ct['id']} — {ct['outcome']}
          &nbsp;|&nbsp; P&L: <span style="color:{color}">${ct['pnl_usd']:+.2f}</span>
          &nbsp;|&nbsp; New Balance: <span style="color:#f0f4ff">${db.get_balance():,.2f}</span>
        </div>
        """, unsafe_allow_html=True)

# ── ACCOUNT STATS ROW ──────────────────────────────────────────────────────────
summary = db.summary_stats()
goal    = db.get_daily_goal()
a1, a2, a3, a4, a5, a6 = st.columns(6)
for col, (lbl, val, c) in zip(
    [a1, a2, a3, a4, a5, a6],
    [
        ("BALANCE",       f"${state['balance']:,.2f}", "#26d17a"),
        ("TODAY P&L",     f"${goal['achieved']:+.2f}", "#26d17a" if goal["achieved"] >= 0 else "#e05555"),
        ("DAILY GOAL",    f"{goal['pct']:.0f}%",       "#26d17a" if goal["achieved"] >= goal["target"] else "#f0a500"),
        ("OPEN TRADES",   summary["open_signals"],     "#f0a500"),
        ("WIN RATE",      f"{summary['win_rate']}%",   "#26d17a" if summary["win_rate"] >= 55 else "#f0a500"),
        ("TOTAL P&L",     f"${summary['total_pnl_usd']:+,.2f}", "#26d17a" if summary["total_pnl_usd"] >= 0 else "#e05555"),
    ]
):
    col.markdown(f"""
    <div style="background:#0d111a;border:1px solid #1e2736;padding:8px 6px;
                font-family:IBM Plex Mono,monospace;text-align:center">
      <div style="font-size:7px;color:#4a5568;text-transform:uppercase;letter-spacing:1px">{lbl}</div>
      <div style="font-size:14px;font-weight:600;color:{c};margin-top:2px">{val}</div>
    </div>
    """, unsafe_allow_html=True)

# ── TOP ROW: S/R + REGIME ─────────────────────────────────────────────────────
st.markdown("---")
col_sr, col_regime = st.columns([1, 1])

with col_sr:
    st.markdown(section_header("S/R LEVELS", "ALL TIMEFRAMES"), unsafe_allow_html=True)
    price = state["price"]
    sup, res = SREngine().nearest(sr_all, price, n=4)
    rows = []
    for r in reversed(res[:3]):
        rows.append(
            f'<div style="display:flex;justify-content:space-between;padding:4px 0;'
            f'border-bottom:1px solid #0f1420;font-family:IBM Plex Mono,monospace;font-size:11px">'
            f'<span style="color:#e05555;font-weight:500">{r.price:.2f}</span>'
            f'<span style="font-size:8px;color:#4a5568;background:#1a0a0a;padding:1px 5px">{r.timeframe}</span>'
            f'<span style="color:#4a5568;font-size:9px">{"●"*min(r.touches,4)}</span></div>'
        )
    rows.append(
        f'<div style="background:#1a1500;border:1px solid #5a3800;padding:4px 8px;'
        f'margin:3px 0;font-family:IBM Plex Mono,monospace;font-size:12px;'
        f'display:flex;justify-content:space-between">'
        f'<span style="color:#f0a500;font-weight:600">▶ {price:.2f}</span>'
        f'<span style="color:#f0a500;font-size:9px">CURRENT</span></div>'
    )
    for s in sup[:3]:
        rows.append(
            f'<div style="display:flex;justify-content:space-between;padding:4px 0;'
            f'border-bottom:1px solid #0f1420;font-family:IBM Plex Mono,monospace;font-size:11px">'
            f'<span style="color:#26d17a;font-weight:500">{s.price:.2f}</span>'
            f'<span style="font-size:8px;color:#4a5568;background:#0a1a0a;padding:1px 5px">{s.timeframe}</span>'
            f'<span style="color:#4a5568;font-size:9px">{"●"*min(s.touches,4)}</span></div>'
        )
    st.markdown("".join(rows), unsafe_allow_html=True)

with col_regime:
    st.markdown(section_header("REGIME + BIAS", "ADX+ATR+EMA"), unsafe_allow_html=True)
    rl = REGIME_LABELS.get(state["regime"], state["regime"])
    rc_col = {"TRENDING BULL":"#26d17a","TRENDING BEAR":"#e05555",
              "RANGING":"#f0a500","HIGH VOL/NEWS":"#e05555","LOW LIQ GRIND":"#4da8f0"}.get(rl,"#f0a500")
    st.markdown(f"""
    <div style="background:#0d111a;border:1px solid {rc_col};padding:8px;
                margin-bottom:6px;font-family:IBM Plex Mono,monospace;text-align:center">
      <div style="font-size:13px;font-weight:600;color:{rc_col}">{rl}</div>
      <div style="font-size:9px;color:#4a5568">HTF: {state['htf_bias'].upper()}</div>
    </div>
    """, unsafe_allow_html=True)
    for strat, label in STRATEGY_DISPLAY.items():
        w  = state["rw"].get(strat, 1.0)
        wc = "#26d17a" if w >= 1.2 else "#e05555" if w < 0.8 else "#f0a500"
        st.markdown(f"""
        <div style="background:#111520;padding:4px 8px;margin-bottom:2px;
                    display:flex;justify-content:space-between">
          <span style="font-size:9px;color:#6a7a90;text-transform:uppercase;
                       letter-spacing:0.5px">{label}</span>
          <span style="font-size:11px;font-weight:600;color:{wc}">{w:.1f}×</span>
        </div>
        """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION A — SIGNAL ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown(f"""
<div style="border-bottom:1px solid #1e2736;padding-bottom:6px;margin-bottom:10px">
  <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;font-weight:600;
              color:#4da8f0;letter-spacing:2px">◈ SECTION A — SIGNAL ANALYSIS</div>
  <div style="font-size:9px;color:#4a5568;margin-top:2px">
    {len(signals_out)} CANDIDATES EVALUATED — SHOWING EXACT ENTRY / SL / TP PRICES
  </div>
</div>
""", unsafe_allow_html=True)

if not signals_out:
    st.markdown("""
    <div style="background:#0d111a;border:1px solid #1e2736;padding:16px;text-align:center;
                font-family:IBM Plex Mono,monospace;font-size:10px;color:#4a5568">
      NO STRATEGY CANDIDATES THIS CYCLE — REGIME FILTERS ACTIVE
    </div>
    """, unsafe_allow_html=True)
else:
    cols = st.columns(min(len(signals_out), 4))
    for i, (sig, score, breakdown, w) in enumerate(signals_out[:4]):
        is_q    = score >= min_score and w >= 0.4
        bc      = "#26d17a" if is_q else "#f0a500" if score >= min_score - 1 else "#4a5568"
        sl      = "✓ QUALIFIED" if is_q else f"✗ {score:.1f} < {min_score}"
        sc_c    = "#26d17a" if is_q else "#f0a500" if score >= min_score - 1 else "#4a5568"
        dc      = "#26d17a" if sig.direction == "long" else "#e05555"
        bw      = int(score * 10)
        # Fix #2: show exact prices prominently
        with cols[i]:
            st.markdown(f"""
            <div style="background:#0d111a;border:1px solid {bc};
                        {'border-top:2px solid '+bc+';' if is_q else ''}
                        padding:10px;font-family:IBM Plex Mono,monospace">
              <div style="display:flex;justify-content:space-between;margin-bottom:5px">
                <span style="font-size:9px;color:#7a849a;text-transform:uppercase">
                  {STRATEGY_DISPLAY.get(sig.strategy,sig.strategy)}
                </span>
                <span style="font-size:10px;font-weight:600;color:#f0a500">{score:.1f}/10</span>
              </div>
              <div style="display:flex;justify-content:space-between;margin-bottom:8px">
                <span style="font-size:13px;font-weight:700;color:{dc}">
                  {'▲ BUY' if sig.direction=='long' else '▼ SELL'}
                </span>
                <span style="font-size:9px;color:{sc_c}">{sl}</span>
              </div>
              <!-- Fix #2: exact price table -->
              <div style="background:#080a0f;border:1px solid #1e2736;padding:8px;
                          margin-bottom:6px">
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;
                            font-size:11px;text-align:center">
                  <div>
                    <div style="color:#4a5568;font-size:7px;letter-spacing:1px">ENTRY</div>
                    <div style="color:#f0f4ff;font-weight:700;font-size:13px">{sig.entry:.2f}</div>
                  </div>
                  <div style="border-left:1px solid #1e2736;border-right:1px solid #1e2736">
                    <div style="color:#e05555;font-size:7px;letter-spacing:1px">STOP LOSS</div>
                    <div style="color:#e05555;font-weight:700;font-size:13px">{sig.sl:.2f}</div>
                  </div>
                  <div>
                    <div style="color:#26d17a;font-size:7px;letter-spacing:1px">TAKE PROFIT</div>
                    <div style="color:#26d17a;font-weight:700;font-size:13px">{sig.tp:.2f}</div>
                  </div>
                </div>
                <div style="display:flex;justify-content:space-between;margin-top:6px;
                            padding-top:4px;border-top:1px solid #1e2736;font-size:9px">
                  <span style="color:#4a5568">R:R <span style="color:#f0a500">{sig.rr:.1f}</span></span>
                  <span style="color:#4a5568">TF <span style="color:#c8d0e0">{sig.timeframe}</span></span>
                  <span style="color:#4a5568">W <span style="color:#c8d0e0">{w:.1f}×</span></span>
                </div>
              </div>
              <div style="height:3px;background:#1e2736">
                <div style="height:3px;width:{bw}%;background:{bc}"></div>
              </div>
              {"<div style='font-size:8px;color:#4a5568;margin-top:4px;line-height:1.5'>"+sig.notes[:80]+"</div>" if sig.notes else ""}
            </div>
            """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION B — POSITIONS TAKEN
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown(f"""
<div style="border-bottom:1px solid #1e2736;padding-bottom:6px;margin-bottom:10px">
  <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;font-weight:600;
              color:#f0a500;letter-spacing:2px">◈ SECTION B — POSITIONS TAKEN</div>
  <div style="font-size:9px;color:#4a5568;margin-top:2px">
    QUALIFIED THIS CYCLE + ALL OPEN FROM DATABASE
  </div>
</div>
""", unsafe_allow_html=True)

# Combine: new positions from this cycle + existing open from DB
db_open   = db.get_open_signals()
new_ids   = {p[3] for p in positions}

pos_cols = st.columns(min(max(len(positions) + len(db_open), 1), 3))
all_display_positions = list(positions)

# Show new positions from this cycle
if not positions and db_open.empty:
    st.markdown(f"""
    <div style="background:#0d111a;border:1px solid #1e2736;padding:16px;text-align:center;
                font-family:IBM Plex Mono,monospace;font-size:10px;color:#4a5568">
      NO OPEN POSITIONS — Score threshold: {min_score}/10
      <br><div style="font-size:9px;margin-top:4px">
      Lower the Min Score slider or wait for stronger signals
      </div>
    </div>
    """, unsafe_allow_html=True)
else:
    # New positions this cycle
    for sig, score, sizing, sid in positions:
        dc = "#26d17a" if sig.direction == "long" else "#e05555"
        dl = "▲ BUY" if sig.direction == "long" else "▼ SELL"
        st.markdown(f"""
        <div style="background:#0d111a;border:1px solid #f0a500;
                    border-top:2px solid {dc};padding:12px;margin-bottom:6px;
                    font-family:IBM Plex Mono,monospace">
          <div style="display:flex;justify-content:space-between;margin-bottom:6px">
            <span style="font-size:14px;font-weight:700;color:{dc}">{dl}</span>
            <span style="background:#1a1500;border:1px solid #5a3800;
                         font-size:9px;color:#f0a500;padding:2px 8px">
              NEW — #{sid}
            </span>
          </div>
          <div style="font-size:9px;color:#7a849a;text-transform:uppercase;
                      letter-spacing:1px;margin-bottom:8px">
            {STRATEGY_DISPLAY.get(sig.strategy, sig.strategy)}
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-bottom:8px">
            <div style="background:#111520;padding:8px;text-align:center">
              <div style="font-size:7px;color:#4a5568;letter-spacing:1px">ENTRY</div>
              <div style="font-size:15px;font-weight:700;color:#f0f4ff">{sig.entry:.2f}</div>
            </div>
            <div style="background:#1a0a0a;padding:8px;text-align:center;border:1px solid #3a1414">
              <div style="font-size:7px;color:#e05555;letter-spacing:1px">STOP LOSS</div>
              <div style="font-size:15px;font-weight:700;color:#e05555">{sig.sl:.2f}</div>
            </div>
            <div style="background:#0a1a0a;padding:8px;text-align:center;border:1px solid #144a14">
              <div style="font-size:7px;color:#26d17a;letter-spacing:1px">TAKE PROFIT</div>
              <div style="font-size:15px;font-weight:700;color:#26d17a">{sig.tp:.2f}</div>
            </div>
          </div>
          <div style="display:flex;gap:16px;font-size:9px;color:#4a5568">
            <span>Lots <span style="color:#c8d0e0">{sizing['lots']:.2f}</span></span>
            <span>Risk <span style="color:#f0a500">${sizing['risk_usd']:.0f}</span></span>
            <span>R:R <span style="color:#c8d0e0">{sig.rr:.1f}</span></span>
            <span>Score <span style="color:#f0a500">{score:.1f}/10</span></span>
          </div>
        </div>
        """, unsafe_allow_html=True)

    # Existing open trades from DB (not from this cycle)
    if not db_open.empty:
        prev_open = db_open[~db_open["id"].isin(new_ids)]
        if not prev_open.empty:
            st.markdown("""
            <div style="font-family:IBM Plex Mono,monospace;font-size:9px;color:#4a5568;
                        letter-spacing:1px;margin:8px 0 4px">PREVIOUSLY OPEN POSITIONS</div>
            """, unsafe_allow_html=True)
            for _, row in prev_open.iterrows():
                dc = "#26d17a" if row["direction"] == "long" else "#e05555"
                dl = "▲ BUY" if row["direction"] == "long" else "▼ SELL"
                entry = float(row["entry"])
                curr  = state["price"]
                unrealized = (curr - entry) if row["direction"] == "long" else (entry - curr)
                unr_c = "#26d17a" if unrealized >= 0 else "#e05555"
                st.markdown(f"""
                <div style="background:#0d111a;border:1px solid #1e2736;padding:10px;
                            margin-bottom:4px;font-family:IBM Plex Mono,monospace">
                  <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                    <span style="color:{dc};font-weight:600">{dl} #{int(row['id'])}</span>
                    <span style="color:#7a849a;font-size:9px">
                      {STRATEGY_DISPLAY.get(row.get('strategy',''), row.get('strategy',''))}
                    </span>
                    <span style="color:{unr_c};font-size:10px;font-weight:600">
                      UNREALIZED: {unrealized:+.2f}
                    </span>
                  </div>
                  <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;
                              gap:4px;font-size:10px">
                    <div><div style="color:#4a5568;font-size:7px">ENTRY</div>
                         <div style="color:#f0f4ff">{row['entry']:.2f}</div></div>
                    <div><div style="color:#e05555;font-size:7px">SL</div>
                         <div style="color:#e05555">{row['sl']:.2f}</div></div>
                    <div><div style="color:#26d17a;font-size:7px">TP</div>
                         <div style="color:#26d17a">{row['tp']:.2f}</div></div>
                    <div><div style="color:#4a5568;font-size:7px">OPENED</div>
                         <div style="color:#4a5568">{str(row.get('ts',''))[:10]}</div></div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

# ── CHART ──────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(section_header("1H CHART — EMA + S/R"), unsafe_allow_html=True)

if not df_1h.empty:
    df_p  = df_1h.tail(100)
    fig   = make_subplots(rows=3, cols=1, shared_xaxes=True,
                          row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.02)
    fig.add_trace(go.Candlestick(
        x=df_p.index, open=df_p["open"], high=df_p["high"],
        low=df_p["low"], close=df_p["close"],
        increasing_line_color="#26d17a", decreasing_line_color="#e05555",
        increasing_fillcolor="#0d2818",  decreasing_fillcolor="#280d0d",
        name="XAUUSD"
    ), row=1, col=1)
    for c_n, col, nm in [("ema_fast","#f0a500","EMA20"),
                          ("ema_med","#4da8f0","EMA50"),
                          ("ema_slow","#e05555","EMA200")]:
        if c_n in df_p.columns:
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p[c_n],
                                      line=dict(width=1, color=col), name=nm), row=1, col=1)
    for l in SREngine().nearest(sr_all, state["price"], n=2)[0]:
        fig.add_hline(y=l.price, line_dash="dash",
                      line_color="rgba(38,209,122,0.3)", line_width=1, row=1, col=1)
    for l in SREngine().nearest(sr_all, state["price"], n=2)[1]:
        fig.add_hline(y=l.price, line_dash="dash",
                      line_color="rgba(224,85,85,0.3)", line_width=1, row=1, col=1)
    for sig, _, _, _ in positions:
        pc = "#26d17a" if sig.direction=="long" else "#e05555"
        fig.add_trace(go.Scatter(
            x=[df_p.index[-1]], y=[sig.entry], mode="markers",
            marker=dict(symbol="triangle-up" if sig.direction=="long" else "triangle-down",
                        size=12, color=pc), showlegend=False
        ), row=1, col=1)
    vc = ["#0d2818" if c>=o else "#280d0d" for c,o in zip(df_p["close"], df_p["open"])]
    fig.add_trace(go.Bar(x=df_p.index, y=df_p["volume"], marker_color=vc), row=2, col=1)
    if "rsi" in df_p.columns:
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p["rsi"],
                                  line=dict(color="#a855f7",width=1)), row=3, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="#e05555", line_width=0.5, row=3, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="#26d17a", line_width=0.5, row=3, col=1)
    fig.update_layout(
        height=420, plot_bgcolor="#0a0c10", paper_bgcolor="#0a0c10",
        font=dict(family="IBM Plex Mono", color="#c8d0e0", size=9),
        xaxis_rangeslider_visible=False,
        margin=dict(l=40, r=20, t=10, b=10),
        legend=dict(orientation="h", y=1.02, font=dict(size=8), bgcolor="rgba(0,0,0,0)"),
    )
    for i in range(1, 4):
        fig.update_xaxes(gridcolor="#1e2736", zeroline=False, tickfont=dict(size=8), row=i, col=1)
        fig.update_yaxes(gridcolor="#1e2736", zeroline=False, tickfont=dict(size=8), row=i, col=1)
    st.plotly_chart(fig, width='stretch', config={"displayModeBar": False})

# ── STATUS + AUTO REFRESH ──────────────────────────────────────────────────────
last_f    = st.session_state.get("last_fetch")
remaining = max(0, 900 - int((datetime.now(timezone.utc)-last_f).total_seconds())) if last_f else None
st.markdown(status_footer(
    data_ok=not df_1h.empty, wfo_ok=True, tg_ok=False, db_ok=True,
    next_cycle_secs=remaining
), unsafe_allow_html=True)

# Fix #6: 24/7 auto-refresh loop
if st.session_state.auto_running:
    mins_left = remaining // 60 if remaining else 15
    secs_left = remaining % 60 if remaining else 0
    st.markdown(f"""
    <div style="font-family:IBM Plex Mono,monospace;font-size:9px;color:#26d17a;
                text-align:center;padding:6px;background:#0a1a0a;border:1px solid #1a4a1a">
      🤖 BOT ACTIVE — NEXT AUTO-CYCLE IN {mins_left}:{secs_left:02d}
    </div>
    """, unsafe_allow_html=True)
    if remaining is not None and remaining <= 0:
        st.rerun()
    else:
        time.sleep(60)
        st.rerun()
