import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.terminal_theme import TERMINAL_CSS, section_header
from core.data_engine import DataEngine
from core.backtest import BacktestEngine
from core.config import CONFIG, REGIME_LABELS, STRATEGY_DISPLAY

st.set_page_config(page_title="BACKTEST // XAUUSD", layout="wide")
st.markdown(TERMINAL_CSS, unsafe_allow_html=True)

st.markdown("""
<div style="font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;
            color:#f0a500;letter-spacing:2px;border-bottom:1px solid #1e2736;
            padding-bottom:8px;margin-bottom:14px">
◈ BACKTEST ENGINE // 1-YEAR DATA — REGIME PERFORMANCE ANALYSIS
</div>
""", unsafe_allow_html=True)

# ── CONFIG ────────────────────────────────────────────────────────────────────
bc1, bc2, bc3 = st.columns(3)
with bc1:
    balance = st.number_input("Starting Balance ($)", value=10000, min_value=1000, step=1000)
with bc2:
    risk_pct = st.slider("Risk per trade (%)", 0.5, 3.0, 1.0, 0.1)
with bc3:
    run_bt = st.button("▶  RUN BACKTEST (1 YEAR)", use_container_width=True)

@st.cache_data(ttl=3600, show_spinner=False)
def load_history():
    de = DataEngine()
    df = de.fetch_history(period="1y", interval="1h")
    return de.add_indicators(df)

@st.cache_data(ttl=3600, show_spinner=False)
def run_backtest_cached(balance, risk_pct):
    df = load_history()
    if df.empty:
        return None, None, None
    bt = BacktestEngine()
    full_results    = bt.run_full_backtest(df, balance=balance)
    regime_results, df_tagged = bt.run_regime_backtest(df, balance=balance)
    return full_results, regime_results, df_tagged

if run_bt or st.session_state.get("bt_run"):
    st.session_state.bt_run = True

if not st.session_state.get("bt_run"):
    st.markdown("""
    <div style="background:#0d111a;border:1px solid #1e2736;border-top:2px solid #f0a500;
                padding:40px;text-align:center;font-family:IBM Plex Mono,monospace">
      <div style="font-size:13px;color:#c8d0e0;letter-spacing:1px;margin-bottom:8px">
        BACKTEST ENGINE READY
      </div>
      <div style="font-size:10px;color:#4a5568;line-height:2">
        ● Fetches 1 year of 1H XAUUSD data from yfinance<br>
        ● Runs all 4 strategies with walk-forward signal generation<br>
        ● Classifies each bar into one of 5 market regimes<br>
        ● Identifies which strategy performs BEST per regime<br>
        ● Monthly P&amp;L breakdown + equity curve per strategy
      </div>
      <div style="font-size:9px;color:#2a3040;margin-top:12px">NOTE: FIRST RUN MAY TAKE 30-60 SECONDS</div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

with st.spinner("FETCHING 1 YEAR DATA + RUNNING REGIME ANALYSIS..."):
    full_results, regime_results, df_tagged = run_backtest_cached(balance, risk_pct)

if full_results is None:
    st.error("Could not fetch historical data. Check internet connection.")
    st.stop()

# ── OVERALL STRATEGY PERFORMANCE ─────────────────────────────────────────────
st.markdown(section_header("STRATEGY PERFORMANCE — FULL YEAR"), unsafe_allow_html=True)

strat_cols = st.columns(4)
strat_order = ["liquidity_sweep", "trend_continuation", "breakout_expansion", "ema_momentum"]
for i, strat in enumerate(strat_order):
    r = full_results[strat]
    sh_color   = "#26d17a" if r["sharpe"] > 0.5 else "#f0a500" if r["sharpe"] > 0 else "#e05555"
    pnl_color  = "#26d17a" if r["total_pnl"] >= 0 else "#e05555"
    wr_color   = "#26d17a" if r["win_rate"] >= 0.55 else "#f0a500" if r["win_rate"] >= 0.45 else "#e05555"
    with strat_cols[i]:
        st.markdown(f"""
        <div style="background:#0d111a;border:1px solid #1e2736;padding:12px;
                    font-family:IBM Plex Mono,monospace">
          <div style="font-size:9px;color:#f0a500;text-transform:uppercase;letter-spacing:1.5px;
                      margin-bottom:8px;border-bottom:1px solid #1e2736;padding-bottom:4px">
            {STRATEGY_DISPLAY[strat]}
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:10px">
            <div><div style="color:#4a5568;font-size:8px">SHARPE</div>
                 <div style="color:{sh_color};font-weight:600">{r['sharpe']:.2f}</div></div>
            <div><div style="color:#4a5568;font-size:8px">WIN RATE</div>
                 <div style="color:{wr_color};font-weight:600">{r['win_rate']*100:.0f}%</div></div>
            <div><div style="color:#4a5568;font-size:8px">TRADES</div>
                 <div style="color:#c8d0e0">{r['total_trades']}</div></div>
            <div><div style="color:#4a5568;font-size:8px">P.FACTOR</div>
                 <div style="color:#c8d0e0">{r['profit_factor']:.2f}</div></div>
            <div><div style="color:#4a5568;font-size:8px">MAX DD</div>
                 <div style="color:#e05555">{r['max_drawdown']:.1f}%</div></div>
            <div><div style="color:#4a5568;font-size:8px">P&L</div>
                 <div style="color:{pnl_color};font-weight:600">{r['pnl_pct']:+.1f}%</div></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

# ── EQUITY CURVES ─────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(section_header("EQUITY CURVES — ALL STRATEGIES"), unsafe_allow_html=True)

fig_eq = go.Figure()
colors = {"liquidity_sweep": "#f0a500", "trend_continuation": "#26d17a",
          "breakout_expansion": "#4da8f0", "ema_momentum": "#a855f7"}

for strat in strat_order:
    eq = full_results[strat].get("equity_curve", [])
    if eq:
        fig_eq.add_trace(go.Scatter(
            y=eq,
            line=dict(width=1.5, color=colors[strat]),
            name=STRATEGY_DISPLAY[strat],
        ))

fig_eq.add_hline(y=balance, line_dash="dot", line_color="#4a5568", line_width=1)
fig_eq.update_layout(
    height=280,
    plot_bgcolor="#0a0c10",
    paper_bgcolor="#0a0c10",
    font=dict(family="IBM Plex Mono", color="#c8d0e0", size=10),
    margin=dict(l=40, r=20, t=10, b=30),
    legend=dict(orientation="h", y=1.02, font=dict(size=9), bgcolor="rgba(0,0,0,0)"),
    xaxis=dict(gridcolor="#1e2736", showgrid=True, zeroline=False, tickfont=dict(size=9)),
    yaxis=dict(gridcolor="#1e2736", showgrid=True, zeroline=False, tickfont=dict(size=9),
               tickprefix="$"),
)
st.plotly_chart(fig_eq, use_container_width=True, config={"displayModeBar": False})

# ── REGIME ANALYSIS ────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(section_header("REGIME PERFORMANCE — WHICH STRATEGY WINS WHERE?"), unsafe_allow_html=True)

if regime_results:
    for regime, data in sorted(regime_results.items(), key=lambda x: -x[1]["pct_of_time"]):
        regime_label = REGIME_LABELS.get(regime, regime)
        regime_color = {"TRENDING BULL": "#26d17a", "TRENDING BEAR": "#e05555",
                        "RANGING": "#f0a500", "HIGH VOL/NEWS": "#e05555",
                        "LOW LIQ GRIND": "#4da8f0"}.get(regime_label, "#c8d0e0")

        best = data["best_strategy"]
        best_r = data["strategies"][best]

        with st.expander(
            f"  {regime_label}  |  {data['pct_of_time']:.0f}% of year  |  {data['bars']} bars  |  BEST: {STRATEGY_DISPLAY[best]}",
            expanded=True
        ):
            rc1, rc2, rc3, rc4 = st.columns(4)
            for col, strat in zip([rc1, rc2, rc3, rc4], strat_order):
                r = data["strategies"][strat]
                is_best = strat == best
                border  = regime_color if is_best else "#1e2736"
                sh_c    = "#26d17a" if r["sharpe"] > 0 else "#e05555"
                col.markdown(f"""
                <div style="background:#0d111a;border:1px solid {border};padding:10px;
                            font-family:IBM Plex Mono,monospace;
                            {'border-top:2px solid '+regime_color+';' if is_best else ''}">
                  <div style="font-size:8px;text-transform:uppercase;letter-spacing:1px;
                              color:{'#f0a500' if is_best else '#4a5568'};margin-bottom:6px">
                    {STRATEGY_DISPLAY[strat]}{' ★ BEST' if is_best else ''}
                  </div>
                  <div style="font-size:10px;display:grid;grid-template-columns:1fr 1fr;gap:2px">
                    <div><div style="color:#4a5568;font-size:7px">SHARPE</div>
                         <div style="color:{sh_c}">{r['sharpe']:.2f}</div></div>
                    <div><div style="color:#4a5568;font-size:7px">WIN%</div>
                         <div style="color:#c8d0e0">{r['win_rate']*100:.0f}%</div></div>
                    <div><div style="color:#4a5568;font-size:7px">TRADES</div>
                         <div style="color:#c8d0e0">{r['total_trades']}</div></div>
                    <div><div style="color:#4a5568;font-size:7px">PNL%</div>
                         <div style="color:{'#26d17a' if r['pnl_pct']>=0 else '#e05555'}">{r['pnl_pct']:+.1f}%</div></div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

# ── MONTHLY P&L TABLE ──────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(section_header("MONTHLY P&L BREAKDOWN"), unsafe_allow_html=True)

best_overall = max(strat_order, key=lambda s: full_results[s]["sharpe"])
selected_strat = st.selectbox(
    "Strategy",
    strat_order,
    format_func=lambda s: STRATEGY_DISPLAY[s],
    index=strat_order.index(best_overall),
    key="monthly_strat"
)

df_hist = load_history()
if not df_hist.empty:
    bt = BacktestEngine()
    monthly = bt.monthly_equity(df_hist, selected_strat, balance=balance)
    if not monthly.empty:
        monthly_data = []
        for _, row in monthly.iterrows():
            pnl_c = "#26d17a" if row["pnl"] >= 0 else "#e05555"
            wr_c  = "#26d17a" if row["win_rate"] >= 55 else "#f0a500" if row["win_rate"] >= 45 else "#e05555"
            monthly_data.append({
                "MONTH":    str(row["month"]),
                "P&L ($)":  f'<span style="color:{pnl_c};font-weight:600">{row["pnl"]:+.2f}</span>',
                "TRADES":   int(row["trades"]),
                "WINS":     int(row["wins"]),
                "WIN RATE": f'<span style="color:{wr_c}">{row["win_rate"]:.1f}%</span>',
            })

        # Bar chart
        fig_m = go.Figure()
        fig_m.add_trace(go.Bar(
            x=[str(r["month"]) for _, r in monthly.iterrows()],
            y=monthly["pnl"].tolist(),
            marker_color=["#26d17a" if v >= 0 else "#e05555" for v in monthly["pnl"]],
            name="Monthly P&L"
        ))
        fig_m.update_layout(
            height=220,
            plot_bgcolor="#0a0c10", paper_bgcolor="#0a0c10",
            font=dict(family="IBM Plex Mono", color="#c8d0e0", size=10),
            margin=dict(l=40, r=20, t=10, b=30),
            xaxis=dict(gridcolor="#1e2736", tickfont=dict(size=8)),
            yaxis=dict(gridcolor="#1e2736", tickfont=dict(size=9), tickprefix="$"),
        )
        fig_m.add_hline(y=0, line_color="#4a5568", line_width=0.5)
        st.plotly_chart(fig_m, use_container_width=True, config={"displayModeBar": False})

        # Table
        df_monthly_disp = monthly.copy()
        df_monthly_disp["month"] = df_monthly_disp["month"].astype(str)
        df_monthly_disp["pnl_pct"] = (df_monthly_disp["pnl"] / balance * 100).round(2)
        df_monthly_disp.columns = ["Month","P&L ($)","Trades","Wins","Win Rate (%)","P&L (%)"]
        st.dataframe(df_monthly_disp.style.applymap(
            lambda v: "color:#26d17a" if isinstance(v,(int,float)) and v>0
                      else "color:#e05555" if isinstance(v,(int,float)) and v<0 else "",
            subset=["P&L ($)", "P&L (%)"]
        ).set_properties(**{"font-family":"IBM Plex Mono,monospace","font-size":"11px",
                            "background":"#0d111a","color":"#c8d0e0"}).set_table_styles([
            {"selector":"th","props":[("background","#06080c"),("color","#f0a500"),
                                      ("font-size","9px"),("text-transform","uppercase"),
                                      ("letter-spacing","1px"),("border-bottom","1px solid #1e2736")]}
        ]), use_container_width=True)

        # Summary metrics below monthly table
        total_pnl  = monthly["pnl"].sum()
        avg_mo_pnl = monthly["pnl"].mean()
        best_mo    = monthly.loc[monthly["pnl"].idxmax(), "month"] if not monthly.empty else "-"
        worst_mo   = monthly.loc[monthly["pnl"].idxmin(), "month"] if not monthly.empty else "-"
        green_mos  = (monthly["pnl"] > 0).sum()
        pct_green  = green_mos / len(monthly) * 100

        sm1, sm2, sm3, sm4, sm5 = st.columns(5)
        for col, (lbl, val, c) in zip(
            [sm1,sm2,sm3,sm4,sm5],
            [
                ("Total P&L", f"${total_pnl:+,.0f}", "#26d17a" if total_pnl>=0 else "#e05555"),
                ("Avg Monthly", f"${avg_mo_pnl:+,.0f}", "#26d17a" if avg_mo_pnl>=0 else "#e05555"),
                ("Green Months", f"{green_mos}/{len(monthly)}", "#26d17a"),
                ("Best Month", str(best_mo), "#26d17a"),
                ("Worst Month", str(worst_mo), "#e05555"),
            ]
        ):
            col.markdown(f"""
            <div style="background:#0d111a;border:1px solid #1e2736;padding:8px;text-align:center;
                        font-family:IBM Plex Mono,monospace;margin-top:8px">
              <div style="font-size:8px;color:#4a5568;text-transform:uppercase;letter-spacing:1px">{lbl}</div>
              <div style="font-size:13px;font-weight:600;color:{c};margin-top:2px">{val}</div>
            </div>
            """, unsafe_allow_html=True)
