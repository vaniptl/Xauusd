import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.terminal_theme import TERMINAL_CSS, section_header
from core.data_engine import DataEngine
from core.backtest import BacktestEngine
from core.config import REGIME_LABELS, STRATEGY_DISPLAY

st.set_page_config(page_title="BACKTEST // XAUUSD", layout="wide")
st.markdown(TERMINAL_CSS, unsafe_allow_html=True)

st.markdown("""
<div style="font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;
            color:#f0a500;letter-spacing:2px;border-bottom:1px solid #1e2736;
            padding-bottom:8px;margin-bottom:14px">
◈ BACKTEST ENGINE // MULTI-PERIOD REGIME PERFORMANCE ANALYSIS
</div>
""", unsafe_allow_html=True)

# ── PERIOD/TIMEFRAME MATRIX ───────────────────────────────────────────────────
PERIODS = {
    "1 Month": {
        "yf_period": "1mo",
        "timeframes": ["15M", "1H", "4H"],
        "intervals":  {"15M": "15m", "1H": "1h", "4H": "1h"},
        "desc": "15M · 1H · 4H",
    },
    "3 Months": {
        "yf_period": "3mo",
        "timeframes": ["1H", "4H", "1D"],
        "intervals":  {"1H": "1h", "4H": "1h", "1D": "1d"},
        "desc": "1H · 4H · 1D",
    },
    "6 Months": {
        "yf_period": "6mo",
        "timeframes": ["1H", "4H", "1D"],
        "intervals":  {"1H": "1h", "4H": "1h", "1D": "1d"},
        "desc": "1H · 4H · 1D",
    },
    "1 Year": {
        "yf_period": "1y",
        "timeframes": ["4H", "1D"],
        "intervals":  {"4H": "1h", "1D": "1d"},
        "desc": "4H · 1D",
    },
}

# ── CONTROLS ──────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns([1.4, 1, 1])
with c1:
    sel_period = st.selectbox("Backtest Period", list(PERIODS.keys()), key="bt_period")
with c2:
    balance = st.number_input("Balance ($)", value=10000, min_value=1000, step=1000)
with c3:
    run_btn = st.button("▶  RUN BACKTEST", use_container_width=True)

pcfg   = PERIODS[sel_period]
sel_tf = st.selectbox("Primary Timeframe", pcfg["timeframes"], key="bt_tf")

st.markdown(f"""
<div style="background:#0d111a;border:1px solid #1e2736;padding:7px 14px;
            font-family:IBM Plex Mono,monospace;font-size:9px;
            display:flex;gap:20px;margin-bottom:10px">
  <span style="color:#4a5568">PERIOD</span><span style="color:#f0a500">{sel_period.upper()}</span>
  <span style="color:#4a5568">TF</span><span style="color:#4da8f0">{sel_tf}</span>
  <span style="color:#4a5568">ALL TFs</span><span style="color:#c8d0e0">{pcfg['desc']}</span>
</div>
""", unsafe_allow_html=True)

# ── FETCH ──────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=1800, show_spinner=False)
def get_bt_data(period_key, tf_name):
    p   = PERIODS[period_key]
    inv = p["intervals"][tf_name]
    de  = DataEngine()
    df  = de.fetch_history(period=p["yf_period"], interval=inv)
    if tf_name == "4H" and inv == "1h":
        df = df.resample("4h").agg({"open":"first","high":"max",
                                     "low":"min","close":"last","volume":"sum"}).dropna()
    return de.add_indicators(df)

state_key = f"bt_{sel_period}_{sel_tf}"

if not (run_btn or st.session_state.get(state_key)):
    # Landing state - show period grid
    st.markdown("""
    <div style="background:#0d111a;border:1px solid #1e2736;border-top:2px solid #f0a500;
                padding:30px;text-align:center;font-family:IBM Plex Mono,monospace;margin-bottom:16px">
      <div style="font-size:12px;color:#c8d0e0;letter-spacing:1px;margin-bottom:16px">
        SELECT PERIOD + TIMEFRAME THEN CLICK RUN BACKTEST
      </div>
    </div>
    """, unsafe_allow_html=True)
    pg = st.columns(4)
    for col, (pname, pdata) in zip(pg, PERIODS.items()):
        is_sel = pname == sel_period
        col.markdown(f"""
        <div style="border:1px solid {'#f0a500' if is_sel else '#1e2736'};
                    {'border-top:2px solid #f0a500;' if is_sel else ''}
                    padding:12px;font-family:IBM Plex Mono,monospace">
          <div style="font-size:11px;font-weight:600;
                      color:{'#f0a500' if is_sel else '#c8d0e0'};margin-bottom:5px">
            {pname.upper()}
          </div>
          <div style="font-size:9px;color:#4a5568;line-height:1.8">
            TFs: <span style="color:#4da8f0">{pdata['desc']}</span><br>
            Data: <span style="color:#26d17a">{pdata['yf_period']}</span>
          </div>
        </div>
        """, unsafe_allow_html=True)
    st.stop()

if run_btn:
    st.session_state[state_key] = True

with st.spinner(f"FETCHING {sel_period.upper()} {sel_tf} DATA..."):
    df_bt = get_bt_data(sel_period, sel_tf)

if df_bt is None or df_bt.empty:
    st.error("No data. Try another period/timeframe combo.")
    st.stop()

date_f = df_bt.index[0].strftime("%Y-%m-%d")
date_t = df_bt.index[-1].strftime("%Y-%m-%d")
st.markdown(f"""
<div style="background:#0d111a;border:1px solid #1e2736;padding:6px 14px;
            font-family:IBM Plex Mono,monospace;font-size:9px;display:flex;gap:20px;margin-bottom:6px">
  <span style="color:#26d17a">● DATA LOADED</span>
  <span style="color:#4a5568">BARS</span><span style="color:#c8d0e0">{len(df_bt)}</span>
  <span style="color:#4a5568">FROM</span><span style="color:#c8d0e0">{date_f}</span>
  <span style="color:#4a5568">TO</span><span style="color:#c8d0e0">{date_t}</span>
</div>
""", unsafe_allow_html=True)

bt = BacktestEngine()
with st.spinner("RUNNING 4 STRATEGIES..."):
    full_r = bt.run_full_backtest(df_bt, balance=balance)
with st.spinner("SEGMENTING BY REGIME..."):
    regime_r, df_tagged = bt.run_regime_backtest(df_bt, balance=balance)

# ── STRATEGY CARDS ─────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(section_header(f"ALL STRATEGIES — {sel_period.upper()} / {sel_tf}",
                            f"{date_f} → {date_t}"), unsafe_allow_html=True)

strat_order = ["liquidity_sweep","trend_continuation","breakout_expansion","ema_momentum"]
best_s      = max(strat_order, key=lambda s: full_r[s]["sharpe"])
cols        = st.columns(4)

for i, strat in enumerate(strat_order):
    r       = full_r[strat]
    is_best = strat == best_s
    sh_c    = "#26d17a" if r["sharpe"]>0.5 else "#f0a500" if r["sharpe"]>0 else "#e05555"
    pnl_c   = "#26d17a" if r["total_pnl"]>=0 else "#e05555"
    wr_c    = "#26d17a" if r["win_rate"]>=0.55 else "#f0a500" if r["win_rate"]>=0.45 else "#e05555"
    with cols[i]:
        st.markdown(f"""
        <div style="background:#0d111a;border:1px solid {'#f0a500' if is_best else '#1e2736'};
                    {'border-top:2px solid #f0a500;' if is_best else ''}padding:12px;
                    font-family:IBM Plex Mono,monospace">
          <div style="font-size:9px;color:{'#f0a500' if is_best else '#4a5568'};
                      text-transform:uppercase;letter-spacing:1.5px;
                      margin-bottom:8px;border-bottom:1px solid #1e2736;padding-bottom:4px">
            {STRATEGY_DISPLAY[strat]}{"  ★ BEST" if is_best else ""}
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;font-size:10px">
            <div><div style="color:#4a5568;font-size:7px">SHARPE</div>
                 <div style="color:{sh_c};font-weight:600;font-size:15px">{r['sharpe']:.2f}</div></div>
            <div><div style="color:#4a5568;font-size:7px">WIN RATE</div>
                 <div style="color:{wr_c};font-weight:600;font-size:15px">{r['win_rate']*100:.0f}%</div></div>
            <div><div style="color:#4a5568;font-size:7px">TRADES</div>
                 <div style="color:#c8d0e0">{r['total_trades']}</div></div>
            <div><div style="color:#4a5568;font-size:7px">PROFIT FACTOR</div>
                 <div style="color:#c8d0e0">{r['profit_factor']:.2f}</div></div>
            <div><div style="color:#4a5568;font-size:7px">MAX DD</div>
                 <div style="color:#e05555">{r['max_drawdown']:.1f}%</div></div>
            <div><div style="color:#4a5568;font-size:7px">P&L</div>
                 <div style="color:{pnl_c};font-weight:600">{r['pnl_pct']:+.1f}%</div></div>
          </div>
          <div style="height:2px;background:#1e2736;margin-top:8px">
            <div style="height:2px;width:{min(abs(r['sharpe'])/2*100,100):.0f}%;
                        background:{sh_c}"></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

# ── EQUITY CURVES ─────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(section_header("EQUITY CURVES"), unsafe_allow_html=True)

ec_c = {"liquidity_sweep":"#f0a500","trend_continuation":"#26d17a",
         "breakout_expansion":"#4da8f0","ema_momentum":"#a855f7"}
fig_eq = go.Figure()
for s in strat_order:
    eq = full_r[s].get("equity_curve", [])
    if eq:
        fig_eq.add_trace(go.Scatter(y=eq, line=dict(width=1.5, color=ec_c[s]),
                                     name=STRATEGY_DISPLAY[s]))
fig_eq.add_hline(y=balance, line_dash="dot", line_color="#4a5568", line_width=0.8)
fig_eq.update_layout(
    height=240, plot_bgcolor="#0a0c10", paper_bgcolor="#0a0c10",
    font=dict(family="IBM Plex Mono", color="#c8d0e0", size=10),
    margin=dict(l=50, r=20, t=10, b=30),
    legend=dict(orientation="h", y=1.02, font=dict(size=9), bgcolor="rgba(0,0,0,0)"),
    xaxis=dict(gridcolor="#1e2736", tickfont=dict(size=8)),
    yaxis=dict(gridcolor="#1e2736", tickfont=dict(size=8), tickprefix="$"),
)
st.plotly_chart(fig_eq, use_container_width=True, config={"displayModeBar": False})

# ── REGIME TABLE ──────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(section_header("REGIME BREAKDOWN — BEST STRATEGY PER STATE"), unsafe_allow_html=True)

if regime_r:
    rows = []
    for regime, data in sorted(regime_r.items(), key=lambda x: -x[1]["pct_of_time"]):
        best   = data["best_strategy"]
        best_r = data["strategies"][best]
        rows.append({
            "REGIME":        REGIME_LABELS.get(regime, regime),
            "% OF PERIOD":   f"{data['pct_of_time']:.0f}%",
            "BARS":          data["bars"],
            "BEST STRATEGY": STRATEGY_DISPLAY[best],
            "SHARPE":        f"{best_r['sharpe']:.2f}",
            "WIN %":         f"{best_r['win_rate']*100:.0f}%",
            "P&L %":         f"{best_r['pnl_pct']:+.1f}%",
        })
    df_rsum = pd.DataFrame(rows)
    st.dataframe(
        df_rsum.style.set_properties(**{
            "font-family":"IBM Plex Mono,monospace","font-size":"11px",
            "background":"#0d111a","color":"#c8d0e0",
        }).set_table_styles([{"selector":"th","props":[
            ("background","#06080c"),("color","#f0a500"),("font-size","9px"),
            ("text-transform","uppercase"),("letter-spacing","1px"),
            ("border-bottom","1px solid #1e2736"),
        ]}]),
        use_container_width=True, hide_index=True,
    )

    st.markdown("---")
    for regime, data in sorted(regime_r.items(), key=lambda x: -x[1]["pct_of_time"]):
        rl     = REGIME_LABELS.get(regime, regime)
        rc_col = {"TRENDING BULL":"#26d17a","TRENDING BEAR":"#e05555",
                  "RANGING":"#f0a500","HIGH VOL/NEWS":"#e05555","LOW LIQ GRIND":"#4da8f0"}.get(rl,"#c8d0e0")
        best   = data["best_strategy"]
        with st.expander(
            f"  {rl}  ·  {data['pct_of_time']:.0f}% of period  ·  BEST: {STRATEGY_DISPLAY[best]}",
            expanded=False
        ):
            rc = st.columns(4)
            for col, strat in zip(rc, strat_order):
                r       = data["strategies"][strat]
                is_best = strat == best
                sh_c    = "#26d17a" if r["sharpe"]>0 else "#e05555"
                pnl_c   = "#26d17a" if r["pnl_pct"]>=0 else "#e05555"
                with col:
                    st.markdown(f"""
                    <div style="background:#0d111a;border:1px solid {'#f0a500' if is_best else '#1e2736'};
                                padding:10px;font-family:IBM Plex Mono,monospace;
                                {'border-top:2px solid '+rc_col+';' if is_best else ''}">
                      <div style="font-size:8px;color:{'#f0a500' if is_best else '#4a5568'};
                                  text-transform:uppercase;letter-spacing:1px;margin-bottom:5px">
                        {STRATEGY_DISPLAY[strat]}{"  ★" if is_best else ""}
                      </div>
                      <div style="font-size:10px;display:grid;grid-template-columns:1fr 1fr;gap:3px">
                        <div><div style="color:#4a5568;font-size:7px">SHARPE</div>
                             <div style="color:{sh_c}">{r['sharpe']:.2f}</div></div>
                        <div><div style="color:#4a5568;font-size:7px">WIN%</div>
                             <div style="color:#c8d0e0">{r['win_rate']*100:.0f}%</div></div>
                        <div><div style="color:#4a5568;font-size:7px">TRADES</div>
                             <div style="color:#c8d0e0">{r['total_trades']}</div></div>
                        <div><div style="color:#4a5568;font-size:7px">P&L%</div>
                             <div style="color:{pnl_c}">{r['pnl_pct']:+.1f}%</div></div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

# ── MONTHLY P&L ────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(section_header("MONTHLY P&L"), unsafe_allow_html=True)

mo_strat = st.selectbox("Strategy", strat_order,
                         format_func=lambda s: STRATEGY_DISPLAY[s],
                         index=strat_order.index(best_s), key="mo_bt")
mo_df    = bt.monthly_equity(df_bt, mo_strat, balance=balance)

if not mo_df.empty:
    fig_m = go.Figure(go.Bar(
        x=[str(r) for r in mo_df["month"]],
        y=mo_df["pnl"].round(2).tolist(),
        marker_color=["#26d17a" if v>=0 else "#e05555" for v in mo_df["pnl"]],
        text=[f"${v:+.0f}" for v in mo_df["pnl"]],
        textfont=dict(family="IBM Plex Mono",size=9,color="#c8d0e0"),
        textposition="outside",
    ))
    fig_m.add_hline(y=0, line_color="#4a5568", line_width=0.5)
    fig_m.update_layout(
        height=200, plot_bgcolor="#0a0c10", paper_bgcolor="#0a0c10",
        font=dict(family="IBM Plex Mono",color="#c8d0e0",size=10),
        margin=dict(l=50,r=20,t=20,b=30),
        xaxis=dict(gridcolor="#1e2736",tickfont=dict(size=8)),
        yaxis=dict(gridcolor="#1e2736",tickfont=dict(size=9),tickprefix="$"),
    )
    st.plotly_chart(fig_m, use_container_width=True, config={"displayModeBar":False})

    disp = mo_df.copy()
    disp["month"]    = disp["month"].astype(str)
    disp["pnl_pct"]  = (disp["pnl"]/balance*100).round(2)
    disp["win_rate"] = disp["win_rate"].round(1)
    disp["pnl"]      = disp["pnl"].round(2)
    disp.columns     = ["Month","P&L ($)","Trades","Wins","Win Rate (%)","P&L (%)"]
    st.dataframe(
        disp.style.applymap(
            lambda v: "color:#26d17a" if isinstance(v,(int,float)) and v>0
                      else "color:#e05555" if isinstance(v,(int,float)) and v<0 else "",
            subset=["P&L ($)","P&L (%)"]
        ).set_properties(**{
            "font-family":"IBM Plex Mono,monospace","font-size":"11px",
            "background":"#0d111a","color":"#c8d0e0",
        }).set_table_styles([{"selector":"th","props":[
            ("background","#06080c"),("color","#f0a500"),("font-size","9px"),
            ("text-transform","uppercase"),("letter-spacing","1px"),
            ("border-bottom","1px solid #1e2736"),
        ]}]),
        use_container_width=True, hide_index=True,
    )
