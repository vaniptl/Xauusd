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
    TERMINAL_CSS, section_header, stat_box,
    signal_card, live_price_bar, status_footer
)
from database.db import Database

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="XAUUSD // INTELLIGENCE TERMINAL",
    page_icon="🟡",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(TERMINAL_CSS, unsafe_allow_html=True)

# ── INIT SESSION STATE ────────────────────────────────────────────────────────
if "last_fetch" not in st.session_state:
    st.session_state.last_fetch = None
if "signals_fired" not in st.session_state:
    st.session_state.signals_fired = []
if "balance" not in st.session_state:
    st.session_state.balance = CONFIG["risk"]["account_balance"]
if "cot_data" not in st.session_state:
    st.session_state.cot_data = {}
if "cot_bias" not in st.session_state:
    st.session_state.cot_bias = "neutral"

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="font-family:'IBM Plex Mono',monospace;font-size:13px;font-weight:600;
                color:#f0a500;letter-spacing:2px;padding:10px 0;border-bottom:1px solid #1e2736;
                margin-bottom:12px">
    ◈ XAUUSD TERMINAL
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div style="font-size:9px;color:#4a5568;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px">Account Config</div>', unsafe_allow_html=True)
    balance = st.number_input("Balance ($)", value=st.session_state.balance,
                              min_value=1000, step=500, label_visibility="collapsed")
    st.session_state.balance = balance

    st.markdown('<div style="font-size:9px;color:#4a5568;letter-spacing:1px;text-transform:uppercase;margin:10px 0 6px">Min Confluence Score</div>', unsafe_allow_html=True)
    min_score = st.slider("Score", 4, 9, 6, label_visibility="collapsed")

    st.markdown('<div style="font-size:9px;color:#4a5568;letter-spacing:1px;text-transform:uppercase;margin:10px 0 6px">Auto Refresh</div>', unsafe_allow_html=True)
    auto_refresh = st.toggle("15-min cycle", value=False)
    refresh_interval = st.selectbox(
        "Interval", ["15 min", "5 min", "30 min"],
        label_visibility="collapsed"
    )

    st.markdown("---")
    st.markdown('<div style="font-size:9px;color:#4a5568;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px">Strategy Filters</div>', unsafe_allow_html=True)
    show_liq   = st.checkbox("Liquidity Sweep",    value=True)
    show_trend = st.checkbox("Trend Continuation", value=True)
    show_bo    = st.checkbox("Breakout Expansion", value=True)
    show_ema   = st.checkbox("EMA Momentum",       value=True)

    st.markdown("---")
    run_btn = st.button("▶  RUN CYCLE", use_container_width=True)

    st.markdown("""
    <div style="font-family:'IBM Plex Mono',monospace;font-size:8px;color:#2a3040;
                text-align:center;margin-top:20px;letter-spacing:1px">
    XAUUSD INTELLIGENCE v1.0<br>FREE STACK // STREAMLIT CLOUD
    </div>
    """, unsafe_allow_html=True)

# ── LOAD DATA ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=900)
def load_data():
    de = DataEngine()
    de.fetch_all()
    return de

@st.cache_data(ttl=3600)
def load_cot():
    cot = COTIntegration()
    return cot.fetch()

def run_pipeline(balance, min_score):
    de = DataEngine()
    with st.spinner("FETCHING MARKET DATA..."):
        de.fetch_all()

    df_15m = de.get("15M"); df_1h = de.get("1H")
    df_4h  = de.get("4H");  df_1d  = de.get("1D")

    if df_1h.empty:
        return None, None, None, None, None, None

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

    sre      = SREngine()
    sr_all   = sre.detect_all_tf({"1D": de.data.get("1D"), "4H": de.data.get("4H"),
                                   "1H": de.data.get("1H"), "15M": de.data.get("15M")}, de)

    fib_levels = {}
    if not df_4h.empty and len(df_4h) > 20:
        recent   = df_4h.tail(100)
        lo_i     = recent["low"].idxmin(); hi_i = recent["high"].idxmax()
        lo, hi   = recent["low"].min(), recent["high"].max()
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

    se  = StrategyEngine()
    cs  = ConfluenceScorer()
    re  = RiskEngine(balance=balance)
    db  = Database()

    CONFIG["strategies"]["liquidity_sweep"]["active"]    = show_liq
    CONFIG["strategies"]["trend_continuation"]["active"] = show_trend
    CONFIG["strategies"]["breakout_expansion"]["active"] = show_bo
    CONFIG["strategies"]["ema_momentum"]["active"]       = show_ema

    candidates = se.run_all(df_15m, df_1h, sr_all, session, htf_bias, regime, rw)

    signals_out = []
    for sig in candidates:
        sig.regime  = regime
        sig.session = session
        w = rw.get(sig.strategy, 1.0)
        if w < 0.4:
            continue
        score, breakdown = cs.score(
            sig, df_1h, df_4h, df_1d, sr_all, fib_levels,
            regime, session, cot_bias, rw
        )
        sig.score = score
        if score < min_score:
            continue
        st_stats = db.get_stats(sig.strategy)
        wr       = st_stats["wins"] / max(st_stats["wins"] + st_stats["losses"], 1) or 0.5
        sizing   = re.position_size(sig.entry, sig.sl, win_rate=wr, avg_rr=sig.rr)
        if sizing.get("blocked"):
            continue
        db.save_signal(sig, sizing)
        signals_out.append((sig, score, sizing, breakdown))

    state = {
        "price": price, "change": change, "ch_pct": ch_pct,
        "regime": regime, "rw": rw, "htf_bias": htf_bias,
        "session": session, "cot_bias": cot_bias, "cot_data": cot_data,
        "sr_all": sr_all, "fib_levels": fib_levels,
        "balance": re.bal, "dd": re.dd(), "kill": re.kill_switch(),
    }
    return state, df_1h, df_4h, df_1d, sr_all, signals_out

# ── TITLE BAR ─────────────────────────────────────────────────────────────────
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
                 font-family:'IBM Plex Mono',monospace;font-size:9px;padding:2px 8px;
                 letter-spacing:1px">● LIVE</span>
    <span style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:#4a5568">{now_utc} UTC</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── RUN PIPELINE ─────────────────────────────────────────────────────────────
if run_btn or (auto_refresh and st.session_state.last_fetch is None):
    with st.spinner("RUNNING SIGNAL PIPELINE..."):
        result = run_pipeline(st.session_state.balance, min_score)
        st.session_state.last_result = result
        st.session_state.last_fetch  = datetime.utcnow()

result = st.session_state.get("last_result", None)

if result is None or result[0] is None:
    # Show placeholder dashboard
    st.markdown("""
    <div style="background:#0d111a;border:1px solid #1e2736;border-top:2px solid #f0a500;
                padding:40px;text-align:center;font-family:'IBM Plex Mono',monospace">
      <div style="font-size:32px;color:#f0a500;margin-bottom:12px">◈</div>
      <div style="font-size:14px;font-weight:600;color:#c8d0e0;letter-spacing:2px;margin-bottom:8px">
        XAUUSD INTELLIGENCE TERMINAL READY
      </div>
      <div style="font-size:10px;color:#4a5568;letter-spacing:1px;margin-bottom:24px">
        CLICK "▶  RUN CYCLE" IN SIDEBAR TO START LIVE ANALYSIS
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px;max-width:600px;margin:0 auto;text-align:left">
        <div style="border:1px solid #1e2736;padding:12px">
          <div style="font-size:8px;color:#4a5568;letter-spacing:1px;margin-bottom:4px">STRATEGIES</div>
          <div style="font-size:13px;color:#26d17a">4 ACTIVE</div>
        </div>
        <div style="border:1px solid #1e2736;padding:12px">
          <div style="font-size:8px;color:#4a5568;letter-spacing:1px;margin-bottom:4px">DATA SOURCE</div>
          <div style="font-size:13px;color:#4da8f0">YFINANCE</div>
        </div>
        <div style="border:1px solid #1e2736;padding:12px">
          <div style="font-size:8px;color:#4a5568;letter-spacing:1px;margin-bottom:4px">TIMEFRAMES</div>
          <div style="font-size:13px;color:#c8d0e0">15M 1H 4H 1D</div>
        </div>
        <div style="border:1px solid #1e2736;padding:12px">
          <div style="font-size:8px;color:#4a5568;letter-spacing:1px;margin-bottom:4px">RISK MODEL</div>
          <div style="font-size:13px;color:#f0a500">KELLY 25%</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Show navigation hint
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""<div style="background:#0d111a;border:1px solid #1e2736;padding:14px;font-family:'IBM Plex Mono',monospace">
        <div style="font-size:9px;color:#f0a500;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:6px">PAGES AVAILABLE</div>
        <div style="font-size:10px;color:#7a849a;line-height:1.8">
        ◈ Dashboard (this page)<br>◈ Signals &amp; Confluence<br>◈ Backtest Engine<br>◈ Risk Manager<br>◈ Trade History<br>◈ S/R Chart
        </div></div>""", unsafe_allow_html=True)
    with col2:
        st.markdown("""<div style="background:#0d111a;border:1px solid #1e2736;padding:14px;font-family:'IBM Plex Mono',monospace">
        <div style="font-size:9px;color:#f0a500;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:6px">STRATEGY GUIDE</div>
        <div style="font-size:10px;color:#7a849a;line-height:1.8">
        ◈ Liquidity Sweep (range)<br>◈ Trend Continuation<br>◈ Breakout Expansion<br>◈ EMA Momentum<br>◈ 9-Factor Confluence<br>◈ Walk-Forward WFO
        </div></div>""", unsafe_allow_html=True)
    with col3:
        st.markdown("""<div style="background:#0d111a;border:1px solid #1e2736;padding:14px;font-family:'IBM Plex Mono',monospace">
        <div style="font-size:9px;color:#f0a500;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:6px">RISK CONTROLS</div>
        <div style="font-size:10px;color:#7a849a;line-height:1.8">
        ◈ Fractional Kelly 25%<br>◈ 5% DD → half size<br>◈ 10% DD → quarter size<br>◈ 3% daily → kill switch<br>◈ Dead strategy suspend<br>◈ 5 consec loss alert
        </div></div>""", unsafe_allow_html=True)
    st.stop()

state, df_1h, df_4h, df_1d, sr_all, signals_out = result

# ── PRICE BAR ─────────────────────────────────────────────────────────────────
atr = float(df_1h["atr"].iloc[-1]) if "atr" in df_1h.columns else 0
adx = float(df_1h["adx"].iloc[-1]) if "adx" in df_1h.columns else 0
rsi = float(df_1h["rsi"].iloc[-1]) if "rsi" in df_1h.columns else 50

st.markdown(live_price_bar(
    state["price"], state["change"], state["ch_pct"],
    state["session"], REGIME_LABELS.get(state["regime"], state["regime"]),
    atr, adx, rsi, datetime.utcnow().strftime("%H:%M:%S")
), unsafe_allow_html=True)

# ── MAIN GRID ─────────────────────────────────────────────────────────────────
col_sr, col_regime, col_signals, col_risk = st.columns([1.1, 1, 1.3, 1])

with col_sr:
    st.markdown(section_header("S/R LEVELS", "ALL TIMEFRAMES"), unsafe_allow_html=True)
    if sr_all:
        price = state["price"]
        sup, res = SREngine().nearest(sr_all, price, n=4)
        rows = []
        for r in reversed(res[:3]):
            rows.append(f'<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #0f1420;font-family:IBM Plex Mono,monospace;font-size:11px">'
                        f'<span style="color:#e05555;font-weight:500">{r.price:.2f}</span>'
                        f'<span style="font-size:8px;color:#4a5568;background:#1a0a0a;padding:1px 5px">{r.timeframe}</span>'
                        f'<span style="color:#4a5568;font-size:9px">{"●"*min(r.touches,4)}</span></div>')
        rows.append(f'<div style="background:#1a1500;border:1px solid #5a3800;padding:4px 8px;margin:3px 0;font-family:IBM Plex Mono,monospace;font-size:12px;display:flex;justify-content:space-between">'
                    f'<span style="color:#f0a500;font-weight:600">▶ {price:.2f}</span>'
                    f'<span style="color:#f0a500;font-size:9px">CURRENT</span></div>')
        for s in sup[:3]:
            rows.append(f'<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #0f1420;font-family:IBM Plex Mono,monospace;font-size:11px">'
                        f'<span style="color:#26d17a;font-weight:500">{s.price:.2f}</span>'
                        f'<span style="font-size:8px;color:#4a5568;background:#0a1a0a;padding:1px 5px">{s.timeframe}</span>'
                        f'<span style="color:#4a5568;font-size:9px">{"●"*min(s.touches,4)}</span></div>')
        # Volume profile placeholder
        poc = price * 0.9985
        vah = price * 1.003
        val = price * 0.997
        rows.append(f'<div style="margin-top:6px;padding-top:6px;border-top:1px solid #1e2736;font-family:IBM Plex Mono,monospace;font-size:9px;display:flex;justify-content:space-between">'
                    f'<span style="color:#a855f7">POC {poc:.0f}</span>'
                    f'<span style="color:#4da8f0">VAH {vah:.0f}</span>'
                    f'<span style="color:#26d17a">VAL {val:.0f}</span></div>')
        st.markdown("".join(rows), unsafe_allow_html=True)

with col_regime:
    st.markdown(section_header("MARKET REGIME", "ADX + ATR + EMA ALIGNMENT"), unsafe_allow_html=True)
    regime_label = REGIME_LABELS.get(state["regime"], state["regime"])
    rw = state["rw"]
    regime_color = {"TRENDING BULL": "#26d17a", "TRENDING BEAR": "#e05555",
                    "RANGING": "#f0a500", "HIGH VOL/NEWS": "#e05555", "LOW LIQ GRIND": "#4da8f0"}.get(regime_label, "#f0a500")
    st.markdown(f"""
    <div style="background:#0d111a;border:1px solid {regime_color};padding:10px;margin-bottom:8px;
                font-family:IBM Plex Mono,monospace;text-align:center">
      <div style="font-size:15px;font-weight:600;color:{regime_color};letter-spacing:1px">{regime_label}</div>
      <div style="font-size:9px;color:#4a5568;margin-top:2px">HTF: {state['htf_bias'].upper()}</div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:3px;font-family:IBM Plex Mono,monospace">
    """, unsafe_allow_html=True)

    for strat, label in STRATEGY_DISPLAY.items():
        w = rw.get(strat, 1.0)
        wc = "#26d17a" if w >= 1.2 else "#e05555" if w < 0.8 else "#f0a500"
        st.markdown(f"""
        <div style="background:#111520;padding:6px 8px;margin-bottom:2px;
                    display:flex;justify-content:space-between">
          <span style="font-size:9px;color:#6a7a90;text-transform:uppercase;letter-spacing:0.5px">{label}</span>
          <span style="font-size:11px;font-weight:600;color:{wc}">{w:.1f}×</span>
        </div>
        """, unsafe_allow_html=True)

    htf_colors = {"bullish": "#26d17a", "bearish": "#e05555", "neutral": "#f0a500"}
    htf_c = htf_colors.get(state["htf_bias"], "#c8d0e0")
    cot_colors = {"bullish": "#26d17a", "bearish": "#e05555", "neutral": "#f0a500"}
    cot_c = cot_colors.get(state["cot_bias"], "#c8d0e0")

    st.markdown(f"""
    <div style="margin-top:6px;display:flex;gap:4px;font-family:IBM Plex Mono,monospace">
      <div style="flex:1;background:#111520;padding:5px 6px;text-align:center">
        <div style="font-size:8px;color:#4a5568">HTF</div>
        <div style="font-size:10px;color:{htf_c};font-weight:500">{state['htf_bias'].upper()}</div>
      </div>
      <div style="flex:1;background:#111520;padding:5px 6px;text-align:center">
        <div style="font-size:8px;color:#4a5568">COT</div>
        <div style="font-size:10px;color:{cot_c};font-weight:500">{state['cot_bias'].upper()}</div>
      </div>
      <div style="flex:1;background:#111520;padding:5px 6px;text-align:center">
        <div style="font-size:8px;color:#4a5568">SESSION</div>
        <div style="font-size:10px;color:#4da8f0;font-weight:500">{state['session'].upper()}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

with col_signals:
    st.markdown(section_header("ACTIVE SIGNALS", f"{len(signals_out)} QUALIFIED"), unsafe_allow_html=True)
    if signals_out:
        for sig, score, sizing, _ in signals_out[:3]:
            st.markdown(signal_card(sig, score, sizing), unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background:#0d111a;border:1px solid #1e2736;padding:20px;
                    text-align:center;font-family:IBM Plex Mono,monospace">
          <div style="font-size:11px;color:#4a5568;letter-spacing:1px">NO QUALIFYING SIGNALS</div>
          <div style="font-size:9px;color:#2a3040;margin-top:4px">
            MIN SCORE {CONFIG['signal']['min_confluence_score']}/10 NOT MET
          </div>
        </div>
        """, unsafe_allow_html=True)

with col_risk:
    st.markdown(section_header("RISK ENGINE", f"BAL ${state['balance']:,.0f}"), unsafe_allow_html=True)
    kill_on, kill_reason = state["kill"]
    dd_pct = state["dd"]
    dd_color = "#e05555" if dd_pct > 8 else "#f0a500" if dd_pct > 4 else "#26d17a"
    kill_color = "#e05555" if kill_on else "#26d17a"
    st.markdown(f"""
    <div style="font-family:IBM Plex Mono,monospace">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:3px;margin-bottom:6px">
        <div style="background:#0d111a;border:1px solid #1e2736;padding:8px">
          <div style="font-size:8px;color:#4a5568;text-transform:uppercase;letter-spacing:1px">Balance</div>
          <div style="font-size:14px;font-weight:600;color:#f0f4ff">${state['balance']:,.0f}</div>
        </div>
        <div style="background:#0d111a;border:1px solid #1e2736;padding:8px">
          <div style="font-size:8px;color:#4a5568;text-transform:uppercase;letter-spacing:1px">Drawdown</div>
          <div style="font-size:14px;font-weight:600;color:{dd_color}">{dd_pct:.1f}%</div>
        </div>
      </div>
      <div style="background:#0d111a;border:1px solid {kill_color};padding:8px;margin-bottom:6px;
                  display:flex;justify-content:space-between;align-items:center">
        <span style="font-size:9px;color:#4a5568;text-transform:uppercase;letter-spacing:1px">Kill Switch</span>
        <span style="font-size:11px;font-weight:600;color:{kill_color}">{'ON: '+kill_reason[:20] if kill_on else 'INACTIVE'}</span>
      </div>
    """, unsafe_allow_html=True)

    # COT summary
    cot = state.get("cot_data", {})
    if cot:
        st.markdown(f"""
      <div style="border:1px solid #1e2736;padding:8px;font-size:9px">
        <div style="color:#4a5568;letter-spacing:1px;text-transform:uppercase;margin-bottom:4px">COT — GOLD FUTURES</div>
        <div style="display:flex;justify-content:space-between;margin-bottom:2px">
          <span style="color:#6a7a90">Comm Net</span>
          <span style="color:{'#e05555' if cot.get('comm_net',0)<0 else '#26d17a'}">{cot.get('comm_net',0):+,.0f}</span>
        </div>
        <div style="display:flex;justify-content:space-between;margin-bottom:2px">
          <span style="color:#6a7a90">Spec Net</span>
          <span style="color:{'#e05555' if cot.get('spec_net',0)>200000 else '#c8d0e0'}">{cot.get('spec_net',0):+,.0f}</span>
        </div>
        <div style="margin-top:4px;padding-top:4px;border-top:1px solid #1e2736;text-align:center">
          <span style="font-size:11px;font-weight:600;color:{cot_colors.get(state['cot_bias'],'#c8d0e0')}">{state['cot_bias'].upper()} BIAS</span>
        </div>
      </div>
    </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("</div>", unsafe_allow_html=True)

# ── PRICE CHART ───────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(section_header("PRICE ACTION — 1H CHART", "EMA20 / EMA50 / EMA200 + S/R LEVELS"), unsafe_allow_html=True)

if not df_1h.empty:
    df_plot = df_1h.tail(120).copy()
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        row_heights=[0.6, 0.2, 0.2],
                        vertical_spacing=0.02)

    fig.add_trace(go.Candlestick(
        x=df_plot.index, open=df_plot["open"], high=df_plot["high"],
        low=df_plot["low"], close=df_plot["close"],
        increasing_line_color="#26d17a", decreasing_line_color="#e05555",
        increasing_fillcolor="#0d2818", decreasing_fillcolor="#280d0d",
        name="XAUUSD"
    ), row=1, col=1)

    for col_name, color, name in [
        ("ema_fast", "#f0a500", "EMA20"),
        ("ema_med",  "#4da8f0", "EMA50"),
        ("ema_slow", "#e05555", "EMA200"),
    ]:
        if col_name in df_plot.columns:
            fig.add_trace(go.Scatter(
                x=df_plot.index, y=df_plot[col_name],
                line=dict(width=1, color=color), name=name
            ), row=1, col=1)

    # Add S/R levels
    price = state["price"]
    sup2, res2 = SREngine().nearest(sr_all, price, n=3)
    for lvl in sup2:
        fig.add_hline(y=lvl.price, line_dash="dash",
                      line_color="rgba(38,209,122,0.3)", line_width=1, row=1, col=1)
    for lvl in res2:
        fig.add_hline(y=lvl.price, line_dash="dash",
                      line_color="rgba(224,85,85,0.3)", line_width=1, row=1, col=1)

    # Volume
    vol_colors = ["#0d2818" if c >= o else "#280d0d"
                  for c, o in zip(df_plot["close"], df_plot["open"])]
    fig.add_trace(go.Bar(
        x=df_plot.index, y=df_plot["volume"],
        marker_color=vol_colors, name="Volume"
    ), row=2, col=1)

    # RSI
    if "rsi" in df_plot.columns:
        fig.add_trace(go.Scatter(
            x=df_plot.index, y=df_plot["rsi"],
            line=dict(color="#a855f7", width=1), name="RSI"
        ), row=3, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="#e05555", line_width=0.5, row=3, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="#26d17a", line_width=0.5, row=3, col=1)

    # Add signals as annotations
    for sig, score, _, _ in signals_out:
        color = "#26d17a" if sig.direction == "long" else "#e05555"
        symbol = "triangle-up" if sig.direction == "long" else "triangle-down"
        fig.add_trace(go.Scatter(
            x=[df_plot.index[-1]], y=[sig.entry],
            mode="markers+text",
            marker=dict(symbol=symbol, size=14, color=color),
            text=[f"  {score}/10"], textfont=dict(color=color, size=10),
            name=sig.strategy.replace("_", " ").upper(),
            showlegend=False,
        ), row=1, col=1)

    fig.update_layout(
        height=500,
        plot_bgcolor="#0a0c10",
        paper_bgcolor="#0a0c10",
        font=dict(family="IBM Plex Mono", color="#c8d0e0", size=10),
        xaxis_rangeslider_visible=False,
        margin=dict(l=40, r=20, t=10, b=10),
        legend=dict(orientation="h", y=1.02, font=dict(size=9),
                    bgcolor="rgba(0,0,0,0)"),
        showlegend=True,
    )
    for i in range(1, 4):
        fig.update_xaxes(
            gridcolor="#1e2736", showgrid=True, zeroline=False,
            tickfont=dict(size=9), row=i, col=1
        )
        fig.update_yaxes(
            gridcolor="#1e2736", showgrid=True, zeroline=False,
            tickfont=dict(size=9), row=i, col=1
        )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

# ── CONFLUENCE BREAKDOWN (if signals exist) ────────────────────────────────────
if signals_out:
    st.markdown("---")
    st.markdown(section_header("CONFLUENCE BREAKDOWN", "SCORING DETAIL PER SIGNAL"), unsafe_allow_html=True)
    cols = st.columns(min(len(signals_out), 3))
    factor_labels = {
        "htf_alignment": "HTF Alignment", "sr_confluence": "S/R Zone",
        "volume_confirm": "Volume", "fib_confluence": "Fibonacci",
        "session_prime": "Session", "regime_fit": "Regime Fit",
        "cot_alignment": "COT Bias", "rsi_ok": "RSI OK", "spread_ok": "Spread"
    }
    max_vals = {
        "htf_alignment": 2.0, "sr_confluence": 1.5, "volume_confirm": 1.0,
        "fib_confluence": 1.0, "session_prime": 1.0, "regime_fit": 1.5,
        "cot_alignment": 1.0, "rsi_ok": 0.5, "spread_ok": 0.5
    }
    for i, (sig, score, _, breakdown) in enumerate(signals_out[:3]):
        with cols[i]:
            dir_color = "#26d17a" if sig.direction == "long" else "#e05555"
            st.markdown(f"""
            <div style="font-family:IBM Plex Mono,monospace;font-size:10px;
                        color:{dir_color};margin-bottom:8px;font-weight:600">
              {sig.direction.upper()} / {sig.strategy.replace('_',' ').upper()}  •  {score}/10
            </div>
            """, unsafe_allow_html=True)
            for factor, val in breakdown.items():
                max_v = max_vals.get(factor, 1.0)
                pct   = int(max(val / max_v, 0) * 100)
                fc    = "#26d17a" if val >= max_v * 0.8 else "#f0a500" if val > 0 else "#e05555"
                label = factor_labels.get(factor, factor)
                st.markdown(f"""
                <div style="margin-bottom:4px;font-family:IBM Plex Mono,monospace">
                  <div style="display:flex;justify-content:space-between;font-size:9px">
                    <span style="color:#6a7a90">{label}</span>
                    <span style="color:{fc}">{val:.1f}/{max_v:.1f}</span>
                  </div>
                  <div style="height:2px;background:#1e2736;margin-top:2px">
                    <div style="height:2px;width:{pct}%;background:{fc}"></div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

# ── STATUS BAR ────────────────────────────────────────────────────────────────
last_fetch = st.session_state.get("last_fetch")
if last_fetch:
    elapsed = (datetime.utcnow() - last_fetch).total_seconds()
    remaining = max(0, 900 - int(elapsed))
else:
    remaining = None

st.markdown(status_footer(
    data_ok=result[1] is not None and not result[1].empty,
    wfo_ok=True, tg_ok=False, db_ok=True,
    next_cycle_secs=remaining
), unsafe_allow_html=True)

# Auto-refresh
if auto_refresh:
    intervals = {"15 min": 900, "5 min": 300, "30 min": 1800}
    wait = intervals.get(refresh_interval, 900)
    time.sleep(wait)
    st.rerun()
