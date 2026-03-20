import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.terminal_theme import TERMINAL_CSS, section_header
from database.db import Database
from core.config import STRATEGY_DISPLAY

st.set_page_config(page_title="TRADE HISTORY // XAUUSD", layout="wide")
st.markdown(TERMINAL_CSS, unsafe_allow_html=True)

st.markdown("""
<div style="font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;
            color:#f0a500;letter-spacing:2px;border-bottom:1px solid #1e2736;
            padding-bottom:8px;margin-bottom:14px">
◈ TRADE HISTORY // DAILY LOG + MONTHLY PROFIT %
</div>
""", unsafe_allow_html=True)

db      = Database()
all_sig = db.get_signals(limit=1000)

if all_sig.empty:
    st.markdown("""
    <div style="background:#0d111a;border:1px solid #1e2736;padding:40px;text-align:center;
                font-family:'IBM Plex Mono',monospace">
      <div style="font-size:11px;color:#4a5568;letter-spacing:1px">NO TRADE HISTORY YET</div>
      <div style="font-size:9px;color:#2a3040;margin-top:6px">
        RUN SIGNAL CYCLES FROM THE DASHBOARD TO BUILD TRADE HISTORY
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── PREPROCESS ────────────────────────────────────────────────────────────────
all_sig["ts"]      = pd.to_datetime(all_sig["ts"], errors="coerce")
all_sig["date"]    = all_sig["ts"].dt.date
all_sig["month"]   = all_sig["ts"].dt.to_period("M").astype(str)
all_sig["hour"]    = all_sig["ts"].dt.hour
closed             = all_sig[all_sig["status"] == "CLOSED"].copy()
open_trades        = all_sig[all_sig["status"] == "OPEN"].copy()

# ── SUMMARY METRICS ───────────────────────────────────────────────────────────
st.markdown(section_header("ACCOUNT SUMMARY"), unsafe_allow_html=True)
balance_input = st.number_input("Account Balance ($)", value=10000, min_value=100, step=500, key="hist_bal")

total_signals = len(all_sig)
total_closed  = len(closed)
total_open    = len(open_trades)
wins          = len(closed[closed["outcome"] == "WIN"]) if not closed.empty else 0
losses        = len(closed[closed["outcome"] == "LOSS"]) if not closed.empty else 0
win_rate      = wins / total_closed * 100 if total_closed > 0 else 0
total_pnl_r   = closed["pnl_r"].sum() if not closed.empty else 0
total_pnl_usd = total_pnl_r * balance_input * 0.01
avg_score     = all_sig["score"].mean() if "score" in all_sig else 0
avg_rr        = closed["rr"].mean() if not closed.empty else 0
best_trade    = closed["pnl_r"].max() if not closed.empty else 0
worst_trade   = closed["pnl_r"].min() if not closed.empty else 0

m1,m2,m3,m4,m5,m6,m7,m8 = st.columns(8)
for col,(lbl,val,c) in zip(
    [m1,m2,m3,m4,m5,m6,m7,m8],
    [
        ("Total Signals",  total_signals, "#c8d0e0"),
        ("Closed",         total_closed,  "#c8d0e0"),
        ("Open",           total_open,    "#f0a500"),
        ("Win Rate",       f"{win_rate:.1f}%",  "#26d17a" if win_rate>=55 else "#f0a500" if win_rate>=45 else "#e05555"),
        ("Total P&L (R)",  f"{total_pnl_r:+.2f}R", "#26d17a" if total_pnl_r>=0 else "#e05555"),
        ("Total P&L ($)",  f"${total_pnl_usd:+,.0f}", "#26d17a" if total_pnl_usd>=0 else "#e05555"),
        ("Avg Score",      f"{avg_score:.1f}/10", "#4da8f0"),
        ("Avg R:R",        f"{avg_rr:.2f}",  "#c8d0e0"),
    ]
):
    col.markdown(f"""
    <div style="background:#0d111a;border:1px solid #1e2736;padding:8px 6px;
                font-family:IBM Plex Mono,monospace;text-align:center">
      <div style="font-size:7px;color:#4a5568;text-transform:uppercase;letter-spacing:1px">{lbl}</div>
      <div style="font-size:14px;font-weight:600;color:{c};margin-top:2px">{val}</div>
    </div>
    """, unsafe_allow_html=True)

# ── DAILY TRADE LOG ────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(section_header("DAILY TRADE LOG", "FILTER BY DATE RANGE"), unsafe_allow_html=True)

date_col1, date_col2 = st.columns(2)
with date_col1:
    start_date = st.date_input(
        "From", value=datetime.utcnow().date() - timedelta(days=30), key="hist_start"
    )
with date_col2:
    end_date = st.date_input(
        "To", value=datetime.utcnow().date(), key="hist_end"
    )

mask = (all_sig["date"] >= start_date) & (all_sig["date"] <= end_date)
period_df = all_sig[mask].copy()

if period_df.empty:
    st.markdown("""
    <div style="background:#0d111a;border:1px solid #1e2736;padding:16px;text-align:center;
                font-family:'IBM Plex Mono',monospace;font-size:10px;color:#4a5568">
      NO TRADES IN SELECTED DATE RANGE
    </div>
    """, unsafe_allow_html=True)
else:
    # Group by date
    dates_available = sorted(period_df["date"].unique(), reverse=True)

    for d in dates_available[:30]:
        day_trades = period_df[period_df["date"] == d].copy()
        day_closed = day_trades[day_trades["status"] == "CLOSED"]
        day_wins   = len(day_closed[day_closed["outcome"] == "WIN"]) if not day_closed.empty else 0
        day_losses = len(day_closed[day_closed["outcome"] == "LOSS"]) if not day_closed.empty else 0
        day_pnl    = day_closed["pnl_r"].sum() if not day_closed.empty else 0
        day_pnl_c  = "#26d17a" if day_pnl >= 0 else "#e05555"
        day_wr     = day_wins / max(day_wins + day_losses, 1) * 100

        with st.expander(
            f"  {str(d)}   |   {len(day_trades)} signals  |  {day_wins}W/{day_losses}L  |  P&L: {day_pnl:+.2f}R",
            expanded=(d == dates_available[0])
        ):
            for _, row in day_trades.iterrows():
                dir_c   = "#26d17a" if row["direction"] == "long" else "#e05555"
                dir_l   = "▲ LONG" if row["direction"] == "long" else "▼ SHORT"
                out_c   = "#26d17a" if row.get("outcome") == "WIN" else "#e05555" if row.get("outcome") == "LOSS" else "#f0a500"
                out_l   = row.get("outcome") or row.get("status", "OPEN")
                pnl_val = row.get("pnl_r")
                pnl_str = f"{pnl_val:+.2f}R" if pd.notna(pnl_val) else "---"
                pnl_c   = "#26d17a" if (pd.notna(pnl_val) and pnl_val >= 0) else "#e05555"
                lots_val= row.get("lots", 0)
                risk_val= row.get("risk_usd", 0)
                strat   = STRATEGY_DISPLAY.get(row.get("strategy",""), row.get("strategy",""))
                score   = row.get("score", 0)
                bar_w   = int(score * 10) if pd.notna(score) else 0

                st.markdown(f"""
                <div style="background:#0d111a;border-left:2px solid {dir_c};padding:8px 12px;
                            margin-bottom:4px;font-family:IBM Plex Mono,monospace">
                  <div style="display:grid;grid-template-columns:80px 100px 1fr 1fr 1fr 1fr 1fr 80px;
                              gap:8px;align-items:center;font-size:10px">
                    <span style="color:{dir_c};font-weight:600">{dir_l}</span>
                    <span style="color:#7a849a;text-transform:uppercase;font-size:9px">{strat}</span>
                    <span><div style="color:#4a5568;font-size:7px">ENTRY</div>
                          <div style="color:#f0f4ff">{row.get('entry',0):.2f}</div></span>
                    <span><div style="color:#4a5568;font-size:7px">SL</div>
                          <div style="color:#e05555">{row.get('sl',0):.2f}</div></span>
                    <span><div style="color:#4a5568;font-size:7px">TP</div>
                          <div style="color:#26d17a">{row.get('tp',0):.2f}</div></span>
                    <span><div style="color:#4a5568;font-size:7px">LOTS / RISK</div>
                          <div style="color:#c8d0e0">{lots_val:.2f} / ${risk_val:.0f}</div></span>
                    <span><div style="color:#4a5568;font-size:7px">P&L</div>
                          <div style="color:{pnl_c};font-weight:600">{pnl_str}</div></span>
                    <span style="background:#111520;color:{out_c};padding:2px 8px;
                                 font-size:10px;font-weight:600;text-align:center">{out_l}</span>
                  </div>
                  <div style="display:flex;justify-content:space-between;margin-top:4px;font-size:9px;color:#4a5568">
                    <span>Score: <span style="color:#f0a500">{score:.1f}/10</span></span>
                    <span>Regime: <span style="color:#c8d0e0">{row.get('regime','?').upper()}</span></span>
                    <span>Session: <span style="color:#4da8f0">{row.get('session','?').upper()}</span></span>
                    <span>R:R <span style="color:#c8d0e0">{row.get('rr',0):.1f}</span></span>
                    <span style="color:#2a3040">{str(row.get('ts',''))[:16]}</span>
                  </div>
                  <div style="height:1px;background:#1e2736;margin-top:5px">
                    <div style="height:1px;width:{bar_w}%;background:#f0a500"></div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

# ── MONTHLY P&L ───────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(section_header("MONTHLY PROFIT %", "CLOSED TRADES ONLY"), unsafe_allow_html=True)

if not closed.empty and "pnl_r" in closed.columns:
    monthly_grp = closed.groupby("month").agg(
        pnl_r   = ("pnl_r",    "sum"),
        trades  = ("pnl_r",    "count"),
        wins    = ("outcome",  lambda x: (x == "WIN").sum()),
        avg_rr  = ("rr",       "mean"),
    ).reset_index()
    monthly_grp["pnl_usd"]  = monthly_grp["pnl_r"] * balance_input * 0.01
    monthly_grp["pnl_pct"]  = monthly_grp["pnl_r"] * balance_input * 0.01 / balance_input * 100
    monthly_grp["win_rate"] = monthly_grp["wins"] / monthly_grp["trades"] * 100

    # Chart
    fig_mo = go.Figure()
    fig_mo.add_trace(go.Bar(
        x=monthly_grp["month"].tolist(),
        y=monthly_grp["pnl_pct"].round(2).tolist(),
        marker_color=["#26d17a" if v >= 0 else "#e05555"
                      for v in monthly_grp["pnl_pct"]],
        text=[f"{v:+.2f}%" for v in monthly_grp["pnl_pct"]],
        textfont=dict(family="IBM Plex Mono", size=10,
                      color=["#f0f4ff"]*len(monthly_grp)),
        textposition="outside",
        name="Monthly %",
    ))
    fig_mo.add_hline(y=0, line_color="#4a5568", line_width=0.5)
    fig_mo.update_layout(
        height=240,
        plot_bgcolor="#0a0c10", paper_bgcolor="#0a0c10",
        font=dict(family="IBM Plex Mono", color="#c8d0e0", size=10),
        margin=dict(l=40, r=20, t=20, b=30),
        xaxis=dict(gridcolor="#1e2736", tickfont=dict(size=9)),
        yaxis=dict(gridcolor="#1e2736", tickfont=dict(size=9), ticksuffix="%"),
    )
    st.plotly_chart(fig_mo, use_container_width=True, config={"displayModeBar": False})

    # Table
    disp = monthly_grp.copy()
    disp = disp.rename(columns={
        "month":    "MONTH",
        "trades":   "TRADES",
        "wins":     "WINS",
        "pnl_r":    "P&L (R)",
        "pnl_usd":  "P&L ($)",
        "pnl_pct":  "P&L %",
        "win_rate": "WIN RATE %",
        "avg_rr":   "AVG R:R",
    })
    disp["P&L (R)"] = disp["P&L (R)"].round(2)
    disp["P&L ($)"] = disp["P&L ($)"].round(2)
    disp["P&L %"]   = disp["P&L %"].round(2)
    disp["WIN RATE %"] = disp["WIN RATE %"].round(1)
    disp["AVG R:R"] = disp["AVG R:R"].round(2)

    def color_pnl(val):
        try:
            return "color:#26d17a" if float(val) >= 0 else "color:#e05555"
        except Exception:
            return ""

    styled = disp.style\
        .applymap(color_pnl, subset=["P&L (R)", "P&L ($)", "P&L %"])\
        .set_properties(**{
            "font-family": "IBM Plex Mono,monospace",
            "font-size":   "11px",
            "background":  "#0d111a",
            "color":       "#c8d0e0",
        })\
        .set_table_styles([{
            "selector": "th",
            "props": [
                ("background", "#06080c"), ("color", "#f0a500"),
                ("font-size", "9px"), ("text-transform", "uppercase"),
                ("letter-spacing", "1px"), ("border-bottom", "1px solid #1e2736"),
            ]
        }])
    st.dataframe(styled, use_container_width=True)

    # Bottom summary
    best_mo  = monthly_grp.loc[monthly_grp["pnl_pct"].idxmax()]
    worst_mo = monthly_grp.loc[monthly_grp["pnl_pct"].idxmin()]
    green    = (monthly_grp["pnl_pct"] > 0).sum()
    red      = (monthly_grp["pnl_pct"] < 0).sum()

    bs1, bs2, bs3, bs4, bs5 = st.columns(5)
    for col, (lbl, val, c) in zip(
        [bs1, bs2, bs3, bs4, bs5],
        [
            ("Green Months",  f"{green}/{len(monthly_grp)}", "#26d17a"),
            ("Red Months",    f"{red}/{len(monthly_grp)}",   "#e05555"),
            ("Best Month",    f"{best_mo['month']} ({best_mo['pnl_pct']:+.2f}%)", "#26d17a"),
            ("Worst Month",   f"{worst_mo['month']} ({worst_mo['pnl_pct']:+.2f}%)", "#e05555"),
            ("Total Return",  f"{monthly_grp['pnl_pct'].sum():+.2f}%", "#26d17a" if monthly_grp["pnl_pct"].sum() >= 0 else "#e05555"),
        ]
    ):
        col.markdown(f"""
        <div style="background:#0d111a;border:1px solid #1e2736;padding:10px;text-align:center;
                    font-family:IBM Plex Mono,monospace;margin-top:8px">
          <div style="font-size:8px;color:#4a5568;text-transform:uppercase;letter-spacing:1px">{lbl}</div>
          <div style="font-size:12px;font-weight:600;color:{c};margin-top:3px">{val}</div>
        </div>
        """, unsafe_allow_html=True)

# ── STRATEGY BREAKDOWN ────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(section_header("STRATEGY PERFORMANCE BREAKDOWN", "FROM LIVE CLOSED TRADES"), unsafe_allow_html=True)

if not closed.empty:
    strat_grp = closed.groupby("strategy").agg(
        trades   = ("pnl_r",   "count"),
        wins     = ("outcome", lambda x: (x == "WIN").sum()),
        total_pnl= ("pnl_r",   "sum"),
        avg_score= ("score",   "mean"),
        avg_rr   = ("rr",      "mean"),
    ).reset_index()
    strat_grp["win_rate"]   = strat_grp["wins"] / strat_grp["trades"] * 100
    strat_grp["pnl_usd"]    = strat_grp["total_pnl"] * balance_input * 0.01
    strat_grp["label"]      = strat_grp["strategy"].map(STRATEGY_DISPLAY)

    sc = st.columns(len(strat_grp))
    for i, (_, row) in enumerate(strat_grp.iterrows()):
        wr_c  = "#26d17a" if row["win_rate"] >= 55 else "#f0a500" if row["win_rate"] >= 45 else "#e05555"
        pnl_c = "#26d17a" if row["pnl_usd"] >= 0 else "#e05555"
        with sc[min(i, len(sc)-1)]:
            st.markdown(f"""
            <div style="background:#0d111a;border:1px solid #1e2736;padding:12px;
                        font-family:IBM Plex Mono,monospace">
              <div style="font-size:9px;color:#f0a500;text-transform:uppercase;letter-spacing:1.5px;
                          margin-bottom:8px;border-bottom:1px solid #1e2736;padding-bottom:4px">
                {row.get('label', row['strategy'])}
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:10px">
                <div><div style="color:#4a5568;font-size:8px">WIN RATE</div>
                     <div style="color:{wr_c};font-weight:600">{row['win_rate']:.1f}%</div></div>
                <div><div style="color:#4a5568;font-size:8px">TRADES</div>
                     <div style="color:#c8d0e0">{int(row['trades'])}</div></div>
                <div><div style="color:#4a5568;font-size:8px">P&L ($)</div>
                     <div style="color:{pnl_c};font-weight:600">{row['pnl_usd']:+.0f}</div></div>
                <div><div style="color:#4a5568;font-size:8px">AVG SCORE</div>
                     <div style="color:#c8d0e0">{row['avg_score']:.1f}</div></div>
              </div>
            </div>
            """, unsafe_allow_html=True)

# ── EXPORT ────────────────────────────────────────────────────────────────────
st.markdown("---")
csv = all_sig.to_csv(index=False)
st.download_button(
    label="⬇  EXPORT FULL HISTORY CSV",
    data=csv,
    file_name=f"xauusd_trade_history_{datetime.utcnow().strftime('%Y%m%d')}.csv",
    mime="text/csv",
)
