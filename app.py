import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import time
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from core.config import CONFIG, REGIME_LABELS, STRATEGY_DISPLAY
from core.data_engine import DataEngine
from core.sr_engine import SREngine
from core.regime import RegimeClassifier
from core.strategies import StrategyEngine, SessionAnalyzer
from core.confluence import ConfluenceScorer
from core.risk_engine import RiskEngine
from core.cot import COTIntegration
from core.terminal_theme import (
    TERMINAL_CSS, section_header, signal_card,
    live_price_bar, status_footer
)
from database.db import Database

# ── PAGE CONFIG ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="XAUUSD // INTELLIGENCE TERMINAL",
    page_icon="🟡",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(TERMINAL_CSS, unsafe_allow_html=True)

# ── SESSION STATE ──────────────────────────────────────────────────────────────
for key, default in [
    ("last_fetch",      None),
    ("last_result",     None),
    ("balance",         CONFIG["risk"]["account_balance"]),
    ("cot_data",        {}),
    ("cot_bias",        "neutral"),
    ("positions_taken", []),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── SIDEBAR ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="font-family:'IBM Plex Mono',monospace;font-size:13px;font-weight:600;
                color:#f0a500;letter-spacing:2px;padding:10px 0;
                border-bottom:1px solid #1e2736;margin-bottom:12px">
    ◈ XAUUSD TERMINAL
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div style="font-size:9px;color:#4a5568;letter-spacing:1px;'
                'text-transform:uppercase;margin-bottom:4px">Account Balance ($)</div>',
                unsafe_allow_html=True)
    balance = st.number_input("Balance", value=st.session_state.balance,
                               min_value=1000, step=500, label_visibility="collapsed")
    st.session_state.balance = balance

    st.markdown('<div style="font-size:9px;color:#4a5568;letter-spacing:1px;'
                'text-transform:uppercase;margin:10px 0 4px">Min Confluence Score</div>',
                unsafe_allow_html=True)
    min_score = st.slider("Score", 4, 9, 6, label_visibility="collapsed")

    st.markdown("---")
    st.markdown('<div style="font-size:9px;color:#4a5568;letter-spacing:1px;'
                'text-transform:uppercase;margin-bottom:6px">Strategy Filters</div>',
                unsafe_allow_html=True)
    show_liq   = st.checkbox("Liquidity Sweep",    value=True)
    show_trend = st.checkbox("Trend Continuation", value=True)
    show_bo    = st.checkbox("Breakout Expansion", value=True)
    show_ema   = st.checkbox("EMA Momentum",       value=True)

    st.markdown("---")
    st.markdown('<div style="font-size:9px;color:#4a5568;letter-spacing:1px;'
                'text-transform:uppercase;margin-bottom:6px">Auto Refresh</div>',
                unsafe_allow_html=True)
    auto_refresh     = st.toggle("Enable auto-cycle", value=False)
    refresh_interval = st.selectbox("Interval", ["15 min","5 min","30 min"],
                                    label_visibility="collapsed")

    st.markdown("---")
    run_btn = st.button("▶  RUN CYCLE", use_container_width=True)

    st.markdown("""
    <div style="font-family:'IBM Plex Mono',monospace;font-size:8px;color:#2a3040;
                text-align:center;margin-top:20px;letter-spacing:1px">
    XAUUSD INTELLIGENCE v1.0<br>FREE STACK // STREAMLIT CLOUD
    </div>
    """, unsafe_allow_html=True)

# ── TITLE BAR ──────────────────────────────────────────────────────────────────
now_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:center;
            border-bottom:1px solid #1e2736;padding-bottom:8px;margin-bottom:12px">
  <div style="font-family:'IBM Plex Mono',monospace;font-size:14px;font-weight:600;
              color:#f0a500;letter-spacing:3px">
    ◈ XAUUSD // INTELLIGENCE TERMINAL
  </div>
  <div style="display:flex;gap:12px;align-items:center">
    <span style="background:#0a2818;color:#26d17a;border:1px solid #1a4a30;
                 font-family:'IBM Plex Mono',monospace;font-size:9px;
                 padding:2px 8px;letter-spacing:1px">● LIVE</span>
    <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;
                 color:#4a5568">{now_utc} UTC</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── DATA LOADING HELPERS ───────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_cot():
    cot = COTIntegration()
    return cot.fetch()

def run_pipeline(balance, min_score):
    """
    Full pipeline: fetch data → classify → generate raw signals → score → size.
    Returns:
      state       — market context dict
      df_1h       — prepared 1H dataframe
      sr_all      — all S/R levels
      signals_out — list of (sig, score, sizing, breakdown) for SIGNALS section
      positions   — list of (sig, score, sizing) actually SAVED as positions
    """
    de = DataEngine()
    de.fetch_all()

    df_15m = de.get("15M"); df_1h = de.get("1H")
    df_4h  = de.get("4H");  df_1d  = de.get("1D")

    if df_1h.empty:
        return None, None, None, [], []

    price  = float(df_1h["close"].iloc[-1])
    prev   = float(df_1h["close"].iloc[-2]) if len(df_1h) > 1 else price
    change = price - prev
    ch_pct = change / prev * 100 if prev else 0

    rc       = RegimeClassifier()
    regime   = rc.classify(df_1h)
    rw       = rc.weights(regime)
    htf_bias = rc.get_htf_bias(df_4h, df_1d)

    sa      = SessionAnalyzer()
    session = sa.get(datetime.utcnow())

    sre    = SREngine()
    sr_all = sre.detect_all_tf({"1D": de.data.get("1D"), "4H": de.data.get("4H"),
                                  "1H": de.data.get("1H"), "15M": de.data.get("15M")}, de)

    # Fibonacci
    fib_levels = {}
    if not df_4h.empty and len(df_4h) > 20:
        recent = df_4h.tail(100)
        lo_i   = recent["low"].idxmin(); hi_i = recent["high"].idxmax()
        lo, hi = recent["low"].min(), recent["high"].max()
        if lo_i < hi_i and (hi - lo) * 10 >= 50:
            d = hi - lo
            fib_levels = {
                "retracements": {round(r, 3): round(hi - r * d, 2)
                                 for r in [0.236, 0.382, 0.5, 0.618, 0.786]},
                "extensions":   {round(e, 3): round(lo + e * d, 2)
                                 for e in [1.0, 1.272, 1.618, 2.0]},
            }

    cot_data = {}
    try:
        cot_data = load_cot()
    except Exception:
        pass
    cot_bias = cot_data.get("bias", "neutral") if cot_data else "neutral"

    se = StrategyEngine()
    cs = ConfluenceScorer()
    re = RiskEngine(balance=balance)
    db = Database()

    CONFIG["strategies"]["liquidity_sweep"]["active"]    = show_liq
    CONFIG["strategies"]["trend_continuation"]["active"] = show_trend
    CONFIG["strategies"]["breakout_expansion"]["active"] = show_bo
    CONFIG["strategies"]["ema_momentum"]["active"]       = show_ema

    candidates = se.run_all(df_15m, df_1h, sr_all, session, htf_bias, regime, rw)

    # ── SIGNALS: everything scored, even below threshold ────────────────────
    signals_out = []    # all candidate signals with scores (for SIGNALS section)
    positions   = []    # only those that pass threshold (for POSITIONS section)

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

        # Only qualified signals become positions
        if score >= min_score and w >= 0.4:
            st_stats = db.get_stats(sig.strategy)
            wr_est   = st_stats["wins"] / max(st_stats["wins"] + st_stats["losses"], 1) or 0.5
            sizing   = re.position_size(sig.entry, sig.sl, win_rate=wr_est, avg_rr=sig.rr)
            if not sizing.get("blocked"):
                sig_id = db.save_signal(sig, sizing)
                positions.append((sig, score, sizing, sig_id))

    # Sort signals by score descending
    signals_out.sort(key=lambda x: -x[1])

    state = {
        "price": price, "change": change, "ch_pct": ch_pct,
        "regime": regime, "rw": rw, "htf_bias": htf_bias,
        "session": session, "cot_bias": cot_bias, "cot_data": cot_data,
        "sr_all": sr_all, "fib_levels": fib_levels,
        "atr":   float(df_1h["atr"].iloc[-1]) if "atr" in df_1h.columns else 0,
        "adx":   float(df_1h["adx"].iloc[-1]) if "adx" in df_1h.columns else 0,
        "rsi":   float(df_1h["rsi"].iloc[-1]) if "rsi" in df_1h.columns else 50,
        "ema_f": float(df_1h["ema_fast"].iloc[-1]) if "ema_fast" in df_1h.columns else 0,
        "ema_m": float(df_1h["ema_med"].iloc[-1])  if "ema_med"  in df_1h.columns else 0,
        "ema_s": float(df_1h["ema_slow"].iloc[-1]) if "ema_slow" in df_1h.columns else 0,
    }

    return state, df_1h, sr_all, signals_out, positions

# ── RUN PIPELINE ───────────────────────────────────────────────────────────────
if run_btn or (auto_refresh and st.session_state.last_fetch is None):
    with st.spinner("RUNNING SIGNAL PIPELINE..."):
        result = run_pipeline(st.session_state.balance, min_score)
        st.session_state.last_result = result
        st.session_state.last_fetch  = datetime.utcnow()

result = st.session_state.get("last_result", None)

# ── PLACEHOLDER SCREEN ─────────────────────────────────────────────────────────
if result is None or result[0] is None:
    st.markdown("""
    <div style="background:#0d111a;border:1px solid #1e2736;border-top:2px solid #f0a500;
                padding:40px;text-align:center;font-family:'IBM Plex Mono',monospace">
      <div style="font-size:28px;color:#f0a500;margin-bottom:12px">◈</div>
      <div style="font-size:13px;font-weight:600;color:#c8d0e0;letter-spacing:2px;margin-bottom:8px">
        XAUUSD INTELLIGENCE TERMINAL READY
      </div>
      <div style="font-size:10px;color:#4a5568;letter-spacing:1px;margin-bottom:24px">
        CLICK ▶ RUN CYCLE IN THE SIDEBAR TO START
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    boxes = [
        ("SIGNALS SECTION",   "Raw candidates from all 4 strategies.\nEvery signal shown with score, even if below threshold.\nColour-coded: green = qualified, orange = near miss, red = filtered."),
        ("POSITIONS SECTION", "Only signals that passed 6/10 threshold.\nThese are the trades the system actually took.\nSaved to database automatically on Run Cycle."),
        ("TRADE HISTORY",     "Click the Trade History page.\nEvery position auto-appears there.\nNo, Date, B/S, Lot, Open Time, Price, SL, TP, Close Time."),
    ]
    for col, (title, body) in zip([c1,c2,c3], boxes):
        col.markdown(f"""
        <div style="background:#0d111a;border:1px solid #1e2736;padding:14px;
                    font-family:'IBM Plex Mono',monospace">
          <div style="font-size:9px;color:#f0a500;letter-spacing:1.5px;
                      text-transform:uppercase;margin-bottom:8px">{title}</div>
          <div style="font-size:9px;color:#7a849a;line-height:1.9;white-space:pre-wrap">{body}</div>
        </div>
        """, unsafe_allow_html=True)
    st.stop()

state, df_1h, sr_all, signals_out, positions = result

# ── PRICE BAR ──────────────────────────────────────────────────────────────────
st.markdown(live_price_bar(
    state["price"], state["change"], state["ch_pct"],
    state["session"], REGIME_LABELS.get(state["regime"], state["regime"]),
    state["atr"], state["adx"], state["rsi"],
    datetime.utcnow().strftime("%H:%M:%S")
), unsafe_allow_html=True)

# ── TOP GRID: S/R + REGIME + EMAs ─────────────────────────────────────────────
col_sr, col_regime, col_indicators = st.columns([1.1, 1, 1])

with col_sr:
    st.markdown(section_header("S/R LEVELS", "ALL TIMEFRAMES"), unsafe_allow_html=True)
    if sr_all:
        price  = state["price"]
        sup, res = SREngine().nearest(sr_all, price, n=4)
        rows   = []
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
        poc = price * 0.9985
        rows.append(
            f'<div style="margin-top:6px;padding-top:6px;border-top:1px solid #1e2736;'
            f'font-family:IBM Plex Mono,monospace;font-size:9px;display:flex;justify-content:space-between">'
            f'<span style="color:#a855f7">POC {poc:.0f}</span>'
            f'<span style="color:#4da8f0">VAH {price*1.003:.0f}</span>'
            f'<span style="color:#26d17a">VAL {price*0.997:.0f}</span></div>'
        )
        st.markdown("".join(rows), unsafe_allow_html=True)

with col_regime:
    st.markdown(section_header("MARKET REGIME", "ADX + ATR + EMA"), unsafe_allow_html=True)
    rl = REGIME_LABELS.get(state["regime"], state["regime"])
    rc_col = {"TRENDING BULL":"#26d17a","TRENDING BEAR":"#e05555",
              "RANGING":"#f0a500","HIGH VOL/NEWS":"#e05555","LOW LIQ GRIND":"#4da8f0"}.get(rl,"#f0a500")
    st.markdown(f"""
    <div style="background:#0d111a;border:1px solid {rc_col};padding:10px;margin-bottom:8px;
                font-family:IBM Plex Mono,monospace;text-align:center">
      <div style="font-size:14px;font-weight:600;color:{rc_col};letter-spacing:1px">{rl}</div>
      <div style="font-size:9px;color:#4a5568;margin-top:2px">HTF: {state['htf_bias'].upper()}</div>
    </div>
    """, unsafe_allow_html=True)
    for strat, label in STRATEGY_DISPLAY.items():
        w   = state["rw"].get(strat, 1.0)
        wc  = "#26d17a" if w>=1.2 else "#e05555" if w<0.8 else "#f0a500"
        st.markdown(f"""
        <div style="background:#111520;padding:5px 8px;margin-bottom:2px;
                    display:flex;justify-content:space-between">
          <span style="font-size:9px;color:#6a7a90;text-transform:uppercase;
                       letter-spacing:0.5px">{label}</span>
          <span style="font-size:11px;font-weight:600;color:{wc}">{w:.1f}×</span>
        </div>
        """, unsafe_allow_html=True)

with col_indicators:
    st.markdown(section_header("INDICATORS", "LIVE VALUES"), unsafe_allow_html=True)
    ef = state["ema_f"]; em = state["ema_m"]; es = state["ema_s"]
    p  = state["price"]
    ema_align = "BULL ALIGN" if ef>em>es else "BEAR ALIGN" if ef<em<es else "NEUTRAL"
    ema_c     = "#26d17a" if ef>em>es else "#e05555" if ef<em<es else "#f0a500"
    cot_colors = {"bullish":"#26d17a","bearish":"#e05555","neutral":"#f0a500"}
    cot_c      = cot_colors.get(state["cot_bias"], "#c8d0e0")

    st.markdown(f"""
    <div style="font-family:IBM Plex Mono,monospace">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:3px;margin-bottom:4px">
        <div style="background:#0d111a;border:1px solid #1e2736;padding:7px">
          <div style="font-size:8px;color:#4a5568;letter-spacing:1px">ATR (14)</div>
          <div style="font-size:14px;font-weight:600;color:#c8d0e0">{state['atr']:.1f}</div>
        </div>
        <div style="background:#0d111a;border:1px solid #1e2736;padding:7px">
          <div style="font-size:8px;color:#4a5568;letter-spacing:1px">ADX (14)</div>
          <div style="font-size:14px;font-weight:600;color:{'#26d17a' if state['adx']>25 else '#c8d0e0'}">{state['adx']:.1f}</div>
        </div>
        <div style="background:#0d111a;border:1px solid #1e2736;padding:7px">
          <div style="font-size:8px;color:#4a5568;letter-spacing:1px">RSI (14)</div>
          <div style="font-size:14px;font-weight:600;color:{'#e05555' if state['rsi']>70 else '#26d17a' if state['rsi']<30 else '#c8d0e0'}">{state['rsi']:.1f}</div>
        </div>
        <div style="background:#0d111a;border:1px solid #1e2736;padding:7px">
          <div style="font-size:8px;color:#4a5568;letter-spacing:1px">EMA ALIGN</div>
          <div style="font-size:11px;font-weight:600;color:{ema_c}">{ema_align}</div>
        </div>
      </div>
      <div style="background:#0d111a;border:1px solid #1e2736;padding:7px;margin-bottom:3px">
        <div style="font-size:8px;color:#4a5568;letter-spacing:1px;margin-bottom:3px">EMA LEVELS</div>
        <div style="display:flex;justify-content:space-between;font-size:10px">
          <span style="color:#f0a500">20: {ef:.2f}</span>
          <span style="color:#4da8f0">50: {em:.2f}</span>
          <span style="color:#e05555">200: {es:.2f}</span>
        </div>
      </div>
      <div style="background:#0d111a;border:1px solid {cot_c};padding:7px;
                  display:flex;justify-content:space-between;align-items:center">
        <span style="font-size:8px;color:#4a5568;letter-spacing:1px">COT BIAS</span>
        <span style="font-size:12px;font-weight:600;color:{cot_c}">{state['cot_bias'].upper()}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION A: RAW SIGNALS  (all candidates with scores, whether they qualify or not)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown(f"""
<div style="border-bottom:1px solid #1e2736;padding-bottom:6px;margin-bottom:12px">
  <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;font-weight:600;
              color:#4da8f0;letter-spacing:2px;text-transform:uppercase">
    ◈ SECTION A — SIGNAL ANALYSIS
  </div>
  <div style="font-size:9px;color:#4a5568;margin-top:2px;letter-spacing:1px">
    ALL STRATEGY CANDIDATES WITH CONFLUENCE SCORES · {len(signals_out)} EVALUATED
  </div>
</div>
""", unsafe_allow_html=True)

if not signals_out:
    st.markdown("""
    <div style="background:#0d111a;border:1px solid #1e2736;padding:20px;text-align:center;
                font-family:IBM Plex Mono,monospace">
      <div style="font-size:11px;color:#4a5568;letter-spacing:1px">NO STRATEGY CANDIDATES THIS CYCLE</div>
      <div style="font-size:9px;color:#2a3040;margin-top:4px">
        REGIME FILTERS OR SESSION GATE SUPPRESSED ALL SIGNALS
      </div>
    </div>
    """, unsafe_allow_html=True)
else:
    sig_cols = st.columns(min(len(signals_out), 4))
    for i, (sig, score, breakdown, weight) in enumerate(signals_out[:4]):
        is_qualified = score >= min_score and weight >= 0.4
        border_color = "#26d17a" if is_qualified else "#f0a500" if score >= min_score - 1 else "#4a5568"
        status_label = "✓ QUALIFIED" if is_qualified else f"✗ SCORE {score:.1f} < {min_score}"
        status_color = "#26d17a" if is_qualified else "#f0a500" if score >= min_score - 1 else "#4a5568"
        dir_c        = "#26d17a" if sig.direction == "long" else "#e05555"
        bar_w        = int(score * 10)

        with sig_cols[i]:
            st.markdown(f"""
            <div style="background:#0d111a;border:1px solid {border_color};
                        {'border-top:2px solid '+border_color+';' if is_qualified else ''}
                        padding:10px;font-family:IBM Plex Mono,monospace;margin-bottom:4px">
              <div style="display:flex;justify-content:space-between;margin-bottom:6px">
                <span style="font-size:9px;color:#7a849a;text-transform:uppercase;letter-spacing:1px">
                  {STRATEGY_DISPLAY.get(sig.strategy, sig.strategy)}
                </span>
                <span style="font-size:10px;font-weight:600;color:#f0a500">{score:.1f}/10</span>
              </div>
              <div style="display:flex;justify-content:space-between;margin-bottom:8px">
                <span style="font-size:12px;font-weight:600;color:{dir_c}">
                  {'▲ LONG' if sig.direction=='long' else '▼ SHORT'}
                </span>
                <span style="font-size:10px;font-weight:600;color:{status_color}">{status_label}</span>
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;
                          font-size:10px;margin-bottom:6px">
                <div><div style="color:#4a5568;font-size:7px">ENTRY</div>
                     <div style="color:#f0f4ff">{sig.entry:.2f}</div></div>
                <div><div style="color:#4a5568;font-size:7px">SL</div>
                     <div style="color:#e05555">{sig.sl:.2f}</div></div>
                <div><div style="color:#4a5568;font-size:7px">TP</div>
                     <div style="color:#26d17a">{sig.tp:.2f}</div></div>
              </div>
              <div style="display:flex;justify-content:space-between;font-size:9px;color:#4a5568;margin-bottom:5px">
                <span>R:R <span style="color:#c8d0e0">{sig.rr:.1f}</span></span>
                <span>TF <span style="color:#c8d0e0">{sig.timeframe}</span></span>
                <span>W <span style="color:#c8d0e0">{weight:.1f}×</span></span>
              </div>
              <div style="height:2px;background:#1e2736">
                <div style="height:2px;width:{bar_w}%;background:{border_color}"></div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            # Confluence factors mini breakdown
            if breakdown:
                factor_labels = {
                    "htf_alignment":"HTF","sr_confluence":"S/R","volume_confirm":"VOL",
                    "fib_confluence":"FIB","session_prime":"SESS","regime_fit":"REGIME",
                    "cot_alignment":"COT","rsi_ok":"RSI","spread_ok":"SPRD"
                }
                max_vals = {
                    "htf_alignment":2.0,"sr_confluence":1.5,"volume_confirm":1.0,
                    "fib_confluence":1.0,"session_prime":1.0,"regime_fit":1.5,
                    "cot_alignment":1.0,"rsi_ok":0.5,"spread_ok":0.5
                }
                rows_f = []
                for factor, val in breakdown.items():
                    mx  = max_vals.get(factor, 1.0)
                    pct = int(max(val/mx, 0)*100)
                    fc  = "#26d17a" if val>=mx*0.8 else "#f0a500" if val>0 else "#4a5568"
                    lbl = factor_labels.get(factor, factor[:4].upper())
                    rows_f.append(
                        f'<div style="display:flex;align-items:center;gap:4px;margin-bottom:2px">'
                        f'<span style="font-size:8px;color:#4a5568;width:36px;text-align:right">{lbl}</span>'
                        f'<div style="flex:1;height:3px;background:#1e2736">'
                        f'<div style="height:3px;width:{pct}%;background:{fc}"></div></div>'
                        f'<span style="font-size:8px;color:{fc};width:24px;text-align:right">{val:.1f}</span>'
                        f'</div>'
                    )
                st.markdown(
                    f'<div style="background:#080a0f;border:1px solid #1e2736;padding:6px 8px;margin-top:2px">'
                    + "".join(rows_f) + "</div>",
                    unsafe_allow_html=True
                )

# ══════════════════════════════════════════════════════════════════════════════
# SECTION B: POSITIONS TAKEN  (only the ones that actually fired)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown(f"""
<div style="border-bottom:1px solid #1e2736;padding-bottom:6px;margin-bottom:12px">
  <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;font-weight:600;
              color:#f0a500;letter-spacing:2px;text-transform:uppercase">
    ◈ SECTION B — POSITIONS TAKEN THIS CYCLE
  </div>
  <div style="font-size:9px;color:#4a5568;margin-top:2px;letter-spacing:1px">
    SIGNALS THAT PASSED {min_score}/10 THRESHOLD · SAVED TO DATABASE · MONITORED FOR SL/TP
  </div>
</div>
""", unsafe_allow_html=True)

if not positions:
    st.markdown(f"""
    <div style="background:#0d111a;border:1px solid #1e2736;padding:20px;
                text-align:center;font-family:IBM Plex Mono,monospace">
      <div style="font-size:11px;color:#4a5568;letter-spacing:1px">
        NO POSITIONS TAKEN THIS CYCLE
      </div>
      <div style="font-size:9px;color:#2a3040;margin-top:4px">
        ALL SIGNALS SCORED BELOW {min_score}/10 THRESHOLD OR WERE BLOCKED BY RISK ENGINE
      </div>
    </div>
    """, unsafe_allow_html=True)
else:
    pos_cols = st.columns(min(len(positions), 3))
    for i, (sig, score, sizing, sig_id) in enumerate(positions):
        dir_c  = "#26d17a" if sig.direction == "long" else "#e05555"
        dir_l  = "▲ LONG" if sig.direction == "long" else "▼ SHORT"
        re_tmp = RiskEngine(balance=st.session_state.balance)
        with pos_cols[i % len(pos_cols)]:
            st.markdown(f"""
            <div style="background:#0d111a;border:1px solid #f0a500;
                        border-top:2px solid {dir_c};padding:12px;
                        font-family:IBM Plex Mono,monospace">
              <div style="display:flex;justify-content:space-between;margin-bottom:8px">
                <span style="font-size:13px;font-weight:600;color:{dir_c}">{dir_l}</span>
                <span style="background:#1a1500;border:1px solid #5a3800;
                             font-size:9px;color:#f0a500;padding:2px 8px">
                  POS #{sig_id}
                </span>
              </div>
              <div style="font-size:10px;color:#7a849a;text-transform:uppercase;
                          letter-spacing:1px;margin-bottom:8px">
                {STRATEGY_DISPLAY.get(sig.strategy, sig.strategy)}
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:8px">
                <div style="background:#111520;padding:6px">
                  <div style="font-size:7px;color:#4a5568;letter-spacing:1px">ENTRY PRICE</div>
                  <div style="font-size:14px;font-weight:600;color:#f0f4ff">{sig.entry:.2f}</div>
                </div>
                <div style="background:#111520;padding:6px">
                  <div style="font-size:7px;color:#4a5568;letter-spacing:1px">LOT SIZE</div>
                  <div style="font-size:14px;font-weight:600;color:#f0f4ff">{sizing['lots']:.2f}</div>
                </div>
                <div style="background:#1a0a0a;padding:6px;border:1px solid #3a1414">
                  <div style="font-size:7px;color:#e05555;letter-spacing:1px">STOP LOSS</div>
                  <div style="font-size:13px;font-weight:600;color:#e05555">{sig.sl:.2f}</div>
                </div>
                <div style="background:#0a1a0a;padding:6px;border:1px solid #144a14">
                  <div style="font-size:7px;color:#26d17a;letter-spacing:1px">TAKE PROFIT</div>
                  <div style="font-size:13px;font-weight:600;color:#26d17a">{sig.tp:.2f}</div>
                </div>
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;
                          font-size:10px;margin-bottom:6px">
                <div style="text-align:center">
                  <div style="color:#4a5568;font-size:7px">R:R</div>
                  <div style="color:#f0a500">{sig.rr:.1f}</div>
                </div>
                <div style="text-align:center">
                  <div style="color:#4a5568;font-size:7px">RISK</div>
                  <div style="color:#c8d0e0">${sizing['risk_usd']:.0f}</div>
                </div>
                <div style="text-align:center">
                  <div style="color:#4a5568;font-size:7px">SCORE</div>
                  <div style="color:#f0a500">{score:.1f}/10</div>
                </div>
              </div>
              <div style="font-size:9px;color:#4a5568;padding-top:4px;
                          border-top:1px solid #1e2736;display:flex;justify-content:space-between">
                <span>Session: <span style="color:#4da8f0">{sig.session.upper()}</span></span>
                <span>Regime: <span style="color:#f0a500">{REGIME_LABELS.get(sig.regime,sig.regime)[:8]}</span></span>
                <span style="color:#2a3040">{sig.ts[:16]}</span>
              </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown(f"""
    <div style="background:#0a1a0a;border:1px solid #1a4a1a;padding:8px 14px;
                font-family:IBM Plex Mono,monospace;font-size:9px;
                display:flex;gap:16px;align-items:center;margin-top:6px">
      <span style="color:#26d17a;font-weight:600">● {len(positions)} POSITION(S) SAVED TO DATABASE</span>
      <span style="color:#4a5568">→ View full history in Trade History page</span>
      <span style="color:#4a5568;margin-left:auto">Outcome auto-detected on next cycle</span>
    </div>
    """, unsafe_allow_html=True)

# ── PRICE CHART ────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(section_header("PRICE ACTION — 1H CHART",
                            "EMA20 / EMA50 / EMA200 + S/R LEVELS"), unsafe_allow_html=True)

if not df_1h.empty:
    df_plot = df_1h.tail(120).copy()
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.02)
    fig.add_trace(go.Candlestick(
        x=df_plot.index, open=df_plot["open"], high=df_plot["high"],
        low=df_plot["low"],  close=df_plot["close"],
        increasing_line_color="#26d17a", decreasing_line_color="#e05555",
        increasing_fillcolor="#0d2818",  decreasing_fillcolor="#280d0d",
        name="XAUUSD"
    ), row=1, col=1)
    for col_n, color, name in [("ema_fast","#f0a500","EMA20"),
                                 ("ema_med", "#4da8f0","EMA50"),
                                 ("ema_slow","#e05555","EMA200")]:
        if col_n in df_plot.columns:
            fig.add_trace(go.Scatter(
                x=df_plot.index, y=df_plot[col_n],
                line=dict(width=1, color=color), name=name
            ), row=1, col=1)

    sre    = SREngine()
    sup2, res2 = sre.nearest(sr_all, state["price"], n=3)
    for lvl in sup2:
        fig.add_hline(y=lvl.price, line_dash="dash",
                      line_color="rgba(38,209,122,0.3)", line_width=1, row=1, col=1)
    for lvl in res2:
        fig.add_hline(y=lvl.price, line_dash="dash",
                      line_color="rgba(224,85,85,0.3)", line_width=1, row=1, col=1)

    # Mark positions on chart
    for sig, score, sizing, _ in positions:
        pc = "#26d17a" if sig.direction == "long" else "#e05555"
        fig.add_trace(go.Scatter(
            x=[df_plot.index[-1]], y=[sig.entry],
            mode="markers+text",
            marker=dict(symbol="triangle-up" if sig.direction=="long" else "triangle-down",
                        size=14, color=pc),
            text=[f"  #{STRATEGY_DISPLAY.get(sig.strategy,'')[:4]} {score:.0f}"],
            textfont=dict(color=pc, size=9),
            showlegend=False,
        ), row=1, col=1)

    vol_c = ["#0d2818" if c >= o else "#280d0d"
             for c, o in zip(df_plot["close"], df_plot["open"])]
    fig.add_trace(go.Bar(x=df_plot.index, y=df_plot["volume"],
                         marker_color=vol_c, name="Volume"), row=2, col=1)
    if "rsi" in df_plot.columns:
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot["rsi"],
                                  line=dict(color="#a855f7", width=1),
                                  name="RSI"), row=3, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="#e05555", line_width=0.5, row=3, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="#26d17a", line_width=0.5, row=3, col=1)

    fig.update_layout(
        height=480, plot_bgcolor="#0a0c10", paper_bgcolor="#0a0c10",
        font=dict(family="IBM Plex Mono", color="#c8d0e0", size=10),
        xaxis_rangeslider_visible=False,
        margin=dict(l=40, r=20, t=10, b=10),
        legend=dict(orientation="h", y=1.02, font=dict(size=9),
                    bgcolor="rgba(0,0,0,0)"),
    )
    for i in range(1, 4):
        fig.update_xaxes(gridcolor="#1e2736", zeroline=False,
                          tickfont=dict(size=8), row=i, col=1)
        fig.update_yaxes(gridcolor="#1e2736", zeroline=False,
                          tickfont=dict(size=8), row=i, col=1)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ── STATUS BAR ─────────────────────────────────────────────────────────────────
last_f    = st.session_state.get("last_fetch")
remaining = max(0, 900 - int((datetime.utcnow()-last_f).total_seconds())) if last_f else None
st.markdown(status_footer(
    data_ok=not df_1h.empty, wfo_ok=True, tg_ok=False, db_ok=True,
    next_cycle_secs=remaining
), unsafe_allow_html=True)

# Auto-refresh
if auto_refresh:
    intervals = {"15 min": 900, "5 min": 300, "30 min": 1800}
    time.sleep(intervals.get(refresh_interval, 900))
    st.rerun()
