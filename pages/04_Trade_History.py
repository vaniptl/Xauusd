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
◈ TRADE HISTORY // AUTOMATED DAILY LOG + MONTHLY PERFORMANCE
</div>
""", unsafe_allow_html=True)

db = Database()

# ── ACCOUNT CONFIG ─────────────────────────────────────────────────────────────
balance_input = st.sidebar.number_input(
    "Account Balance ($)", value=10000, min_value=100, step=500, key="hist_bal"
)
st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style="font-family:'IBM Plex Mono',monospace;font-size:9px;color:#4a5568;
            letter-spacing:1px;text-transform:uppercase">
Trade history auto-populates from the positions taken by the system when you click
RUN CYCLE on the Dashboard.
</div>
""", unsafe_allow_html=True)

# ── FETCH ALL DATA ──────────────────────────────────────────────────────────────
all_sig = db.get_signals(limit=5000)

if all_sig.empty:
    st.markdown("""
    <div style="background:#0d111a;border:1px solid #1e2736;
                border-top:2px solid #f0a500;padding:40px;text-align:center;
                font-family:'IBM Plex Mono',monospace">
      <div style="font-size:11px;color:#4a5568;letter-spacing:1px;margin-bottom:8px">
        NO TRADE HISTORY YET
      </div>
      <div style="font-size:9px;color:#2a3040;line-height:2">
        Run signal cycles from the Dashboard to automatically build trade history.<br>
        Every position taken by the system appears here automatically.<br>
        No manual entry needed.
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── PREPROCESS ─────────────────────────────────────────────────────────────────
all_sig["ts"]         = pd.to_datetime(all_sig["ts"], errors="coerce")
all_sig["close_time"] = pd.to_datetime(all_sig.get("close_time", pd.NaT), errors="coerce")
all_sig["date"]       = all_sig["ts"].dt.date
all_sig["month"]      = all_sig["ts"].dt.to_period("M").astype(str)
closed                = all_sig[all_sig["status"] == "CLOSED"].copy()
open_trades           = all_sig[all_sig["status"] == "OPEN"].copy()

# ── SUMMARY STRIP ──────────────────────────────────────────────────────────────
wins      = len(closed[closed["outcome"] == "WIN"]) if not closed.empty else 0
losses    = len(closed[closed["outcome"] == "LOSS"]) if not closed.empty else 0
total_c   = len(closed)
wr        = wins / total_c * 100 if total_c > 0 else 0
pnl_r     = closed["pnl_r"].sum() if not closed.empty else 0
pnl_usd   = pnl_r * balance_input * 0.01
avg_score = all_sig["score"].mean() if "score" in all_sig else 0

m1,m2,m3,m4,m5,m6,m7 = st.columns(7)
for col,(lbl,val,c) in zip(
    [m1,m2,m3,m4,m5,m6,m7],
    [
        ("Total Trades",  len(all_sig),                        "#c8d0e0"),
        ("Closed",        total_c,                             "#c8d0e0"),
        ("Open",          len(open_trades),                    "#f0a500"),
        ("Wins",          wins,                                "#26d17a"),
        ("Losses",        losses,                              "#e05555"),
        ("Win Rate",      f"{wr:.1f}%",                        "#26d17a" if wr>=55 else "#f0a500" if wr>=45 else "#e05555"),
        ("Total P&L",     f"${pnl_usd:+,.0f}",                "#26d17a" if pnl_usd>=0 else "#e05555"),
    ]
):
    col.markdown(f"""
    <div style="background:#0d111a;border:1px solid #1e2736;padding:8px 6px;
                font-family:IBM Plex Mono,monospace;text-align:center">
      <div style="font-size:7px;color:#4a5568;text-transform:uppercase;letter-spacing:1px">{lbl}</div>
      <div style="font-size:15px;font-weight:600;color:{c};margin-top:2px">{val}</div>
    </div>
    """, unsafe_allow_html=True)

# ── MAIN HISTORY TABLE (Bloomberg style) ──────────────────────────────────────
st.markdown("---")
st.markdown(section_header("COMPLETE TRADE LOG", "ALL POSITIONS TAKEN BY THE SYSTEM"), unsafe_allow_html=True)

# Date range filter
fc1, fc2, fc3, fc4 = st.columns(4)
with fc1:
    start_d = st.date_input("From", value=datetime.utcnow().date()-timedelta(days=30), key="th_start")
with fc2:
    end_d   = st.date_input("To",   value=datetime.utcnow().date(), key="th_end")
with fc3:
    dir_f   = st.selectbox("Direction", ["ALL","long","short"], key="th_dir")
with fc4:
    stat_f  = st.selectbox("Status", ["ALL","OPEN","CLOSED"], key="th_stat")

filtered = all_sig[
    (all_sig["date"] >= start_d) &
    (all_sig["date"] <= end_d)
].copy()
if dir_f  != "ALL": filtered = filtered[filtered["direction"] == dir_f]
if stat_f != "ALL": filtered = filtered[filtered["status"]    == stat_f]

# Build the clean display table
def build_display_table(df):
    rows = []
    for idx, (_, row) in enumerate(df.iterrows(), 1):
        open_t  = str(row["ts"])[:16] if pd.notna(row["ts"]) else "---"
        close_t = "OPEN" if row["status"] == "OPEN" else (
            str(row.get("close_time", ""))[:16]
            if pd.notna(row.get("close_time")) and str(row.get("close_time")) not in ("", "NaT")
            else open_t   # approximate: use open time if close not recorded separately
        )
        pnl_val = row.get("pnl_r")
        pnl_str = f"{pnl_val:+.2f}R" if pd.notna(pnl_val) else "---"
        lots    = row.get("lots", 0) or 0
        rows.append({
            "NO":         idx,
            "DATE":       str(row["date"]),
            "B/S":        "BUY" if row["direction"] == "long" else "SELL",
            "STRATEGY":   STRATEGY_DISPLAY.get(row.get("strategy",""), row.get("strategy","")),
            "LOT SIZE":   f"{float(lots):.2f}",
            "OPEN TIME":  open_t,
            "OPEN PRICE": f"{row.get('entry',0):.2f}",
            "SL":         f"{row.get('sl',0):.2f}",
            "TP":         f"{row.get('tp',0):.2f}",
            "CLOSE TIME": close_t,
            "P&L":        pnl_str,
            "STATUS":     row.get("outcome", row.get("status","OPEN")),
            "SCORE":      f"{row.get('score',0):.1f}",
        })
    return pd.DataFrame(rows)

if filtered.empty:
    st.markdown("""
    <div style="background:#0d111a;border:1px solid #1e2736;padding:16px;text-align:center;
                font-family:'IBM Plex Mono',monospace;font-size:10px;color:#4a5568">
      NO TRADES IN SELECTED DATE RANGE / FILTER
    </div>
    """, unsafe_allow_html=True)
else:
    disp_df = build_display_table(filtered)

    # Style the table
    def color_bs(val):
        if val == "BUY":  return "color:#26d17a;font-weight:bold"
        if val == "SELL": return "color:#e05555;font-weight:bold"
        return ""

    def color_status(val):
        if val in ("WIN",):    return "color:#26d17a"
        if val in ("LOSS",):   return "color:#e05555"
        if val == "OPEN":      return "color:#f0a500"
        return "color:#c8d0e0"

    def color_pnl(val):
        if isinstance(val, str) and val.startswith("+"):  return "color:#26d17a;font-weight:bold"
        if isinstance(val, str) and val.startswith("-"):  return "color:#e05555;font-weight:bold"
        return "color:#c8d0e0"

    styled = disp_df.style \
        .applymap(color_bs,     subset=["B/S"]) \
        .applymap(color_status, subset=["STATUS"]) \
        .applymap(color_pnl,    subset=["P&L"]) \
        .set_properties(**{
            "font-family": "IBM Plex Mono,monospace",
            "font-size":   "11px",
            "background":  "#0d111a",
            "color":       "#c8d0e0",
        }) \
        .set_table_styles([{
            "selector": "th",
            "props": [
                ("background",    "#06080c"),
                ("color",         "#f0a500"),
                ("font-size",     "9px"),
                ("text-transform","uppercase"),
                ("letter-spacing","1px"),
                ("border-bottom", "1px solid #1e2736"),
                ("padding",       "6px 8px"),
            ]
        }, {
            "selector": "td",
            "props": [("padding", "5px 8px"), ("border-bottom", "1px solid #0f1420")]
        }, {
            "selector": "tr:hover td",
            "props": [("background", "#111827")]
        }])

    st.dataframe(styled, use_container_width=True, height=480, hide_index=True)
    st.markdown(f"""
    <div style="font-family:IBM Plex Mono,monospace;font-size:9px;color:#4a5568;
                padding-top:4px;text-align:right">
      SHOWING {len(disp_df)} TRADES
    </div>
    """, unsafe_allow_html=True)

# ── OPEN POSITIONS PANEL ───────────────────────────────────────────────────────
if not open_trades.empty:
    st.markdown("---")
    st.markdown(section_header("OPEN POSITIONS", f"{len(open_trades)} ACTIVE"), unsafe_allow_html=True)
    for _, row in open_trades.iterrows():
        dc = "#26d17a" if row["direction"]=="long" else "#e05555"
        dl = "▲ LONG" if row["direction"]=="long" else "▼ SHORT"
        lots = row.get("lots",0) or 0
        st.markdown(f"""
        <div style="background:#0d111a;border-left:2px solid {dc};padding:8px 12px;
                    margin-bottom:4px;font-family:IBM Plex Mono,monospace">
          <div style="display:grid;grid-template-columns:80px 110px 110px 110px 110px 110px 110px 1fr;
                      gap:8px;align-items:center;font-size:10px">
            <span style="color:{dc};font-weight:600">{dl}</span>
            <span><div style="color:#4a5568;font-size:7px">STRATEGY</div>
                  <div style="color:#7a849a">{STRATEGY_DISPLAY.get(row.get('strategy',''),row.get('strategy',''))}</div></span>
            <span><div style="color:#4a5568;font-size:7px">OPEN TIME</div>
                  <div style="color:#c8d0e0">{str(row['ts'])[:16]}</div></span>
            <span><div style="color:#4a5568;font-size:7px">OPEN PRICE</div>
                  <div style="color:#f0f4ff;font-weight:600">{row.get('entry',0):.2f}</div></span>
            <span><div style="color:#4a5568;font-size:7px">SL</div>
                  <div style="color:#e05555">{row.get('sl',0):.2f}</div></span>
            <span><div style="color:#4a5568;font-size:7px">TP</div>
                  <div style="color:#26d17a">{row.get('tp',0):.2f}</div></span>
            <span><div style="color:#4a5568;font-size:7px">LOT SIZE</div>
                  <div style="color:#c8d0e0">{float(lots):.2f}</div></span>
            <span><div style="color:#4a5568;font-size:7px">R:R</div>
                  <div style="color:#f0a500;font-weight:600">{row.get('rr',0):.1f}</div></span>
          </div>
        </div>
        """, unsafe_allow_html=True)

# ── MONTHLY P&L CHART ─────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(section_header("MONTHLY PROFIT %", "CLOSED POSITIONS ONLY"), unsafe_allow_html=True)

if not closed.empty and "pnl_r" in closed.columns:
    mo = closed.groupby("month").agg(
        pnl_r   = ("pnl_r","sum"),
        trades  = ("pnl_r","count"),
        wins    = ("outcome", lambda x: (x=="WIN").sum()),
    ).reset_index()
    mo["pnl_usd"] = mo["pnl_r"] * balance_input * 0.01
    mo["pnl_pct"] = mo["pnl_usd"] / balance_input * 100
    mo["win_rate"]= mo["wins"] / mo["trades"] * 100

    fig_mo = go.Figure(go.Bar(
        x=mo["month"].tolist(),
        y=mo["pnl_pct"].round(2).tolist(),
        marker_color=["#26d17a" if v>=0 else "#e05555" for v in mo["pnl_pct"]],
        text=[f"{v:+.2f}%" for v in mo["pnl_pct"]],
        textfont=dict(family="IBM Plex Mono",size=10,color="#c8d0e0"),
        textposition="outside",
    ))
    fig_mo.add_hline(y=0, line_color="#4a5568", line_width=0.5)
    fig_mo.update_layout(
        height=220, plot_bgcolor="#0a0c10", paper_bgcolor="#0a0c10",
        font=dict(family="IBM Plex Mono",color="#c8d0e0",size=10),
        margin=dict(l=50,r=20,t=20,b=30),
        xaxis=dict(gridcolor="#1e2736",tickfont=dict(size=9)),
        yaxis=dict(gridcolor="#1e2736",tickfont=dict(size=9),ticksuffix="%"),
    )
    st.plotly_chart(fig_mo, use_container_width=True, config={"displayModeBar":False})

    # Monthly table
    disp_mo = mo.copy()
    disp_mo["month"]    = disp_mo["month"].astype(str)
    disp_mo["pnl_usd"]  = disp_mo["pnl_usd"].round(2)
    disp_mo["pnl_pct"]  = disp_mo["pnl_pct"].round(2)
    disp_mo["win_rate"] = disp_mo["win_rate"].round(1)
    disp_mo.columns     = ["MONTH","P&L (R)","TRADES","WINS","P&L ($)","P&L %","WIN RATE %"]
    st.dataframe(
        disp_mo.style.applymap(
            lambda v: "color:#26d17a" if isinstance(v,(int,float)) and v>0
                      else "color:#e05555" if isinstance(v,(int,float)) and v<0 else "",
            subset=["P&L (R)","P&L ($)","P&L %"]
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

    # Summary row
    best_mo  = mo.loc[mo["pnl_pct"].idxmax()]
    worst_mo = mo.loc[mo["pnl_pct"].idxmin()]
    green    = (mo["pnl_pct"]>0).sum()
    bs1,bs2,bs3,bs4,bs5 = st.columns(5)
    for col,(lbl,val,c) in zip(
        [bs1,bs2,bs3,bs4,bs5],
        [
            ("Green Months",  f"{green}/{len(mo)}",                    "#26d17a"),
            ("Red Months",    f"{(mo['pnl_pct']<0).sum()}/{len(mo)}", "#e05555"),
            ("Best Month",    f"{best_mo['month']} ({best_mo['pnl_pct']:+.1f}%)",  "#26d17a"),
            ("Worst Month",   f"{worst_mo['month']} ({worst_mo['pnl_pct']:+.1f}%)","#e05555"),
            ("Total Return",  f"{mo['pnl_pct'].sum():+.2f}%",          "#26d17a" if mo["pnl_pct"].sum()>=0 else "#e05555"),
        ]
    ):
        col.markdown(f"""
        <div style="background:#0d111a;border:1px solid #1e2736;padding:10px;text-align:center;
                    font-family:IBM Plex Mono,monospace;margin-top:8px">
          <div style="font-size:8px;color:#4a5568;text-transform:uppercase;letter-spacing:1px">{lbl}</div>
          <div style="font-size:12px;font-weight:600;color:{c};margin-top:3px">{val}</div>
        </div>
        """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div style="background:#0d111a;border:1px solid #1e2736;padding:20px;text-align:center;
                font-family:IBM Plex Mono,monospace;font-size:10px;color:#4a5568">
      NO CLOSED TRADES YET — MONTHLY CHART WILL POPULATE AUTOMATICALLY
    </div>
    """, unsafe_allow_html=True)

# ── EXPORT ────────────────────────────────────────────────────────────────────
st.markdown("---")
csv = all_sig.to_csv(index=False)
st.download_button(
    label="⬇  EXPORT FULL HISTORY CSV",
    data=csv,
    file_name=f"xauusd_trade_history_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv",
    mime="text/csv",
)
