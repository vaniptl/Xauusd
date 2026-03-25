import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.terminal_theme import TERMINAL_CSS, section_header
from core.config import STRATEGY_DISPLAY
from database.db import Database

st.set_page_config(page_title="TRADE HISTORY // XAUUSD", layout="wide")
st.markdown(TERMINAL_CSS, unsafe_allow_html=True)

st.markdown("""
<div style="font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;
            color:#f0a500;letter-spacing:2px;border-bottom:1px solid #1e2736;
            padding-bottom:8px;margin-bottom:14px">
◈ TRADE HISTORY — PERSISTENT LOG + EQUITY CURVE + MONTHLY P&L
</div>
""", unsafe_allow_html=True)

db  = Database()
all_sig = db.get_signals(limit=5000)
bal     = db.get_balance()

# ── SIDEBAR: balance management ───────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style="background:#0a2818;border:1px solid #1a4a30;padding:10px;
                font-family:IBM Plex Mono,monospace;margin-bottom:10px">
      <div style="font-size:8px;color:#4a5568;letter-spacing:1px">LIVE BALANCE</div>
      <div style="font-size:20px;font-weight:600;color:#26d17a">${bal:,.2f}</div>
    </div>
    """, unsafe_allow_html=True)
    dep = st.number_input("Add Deposit ($)", min_value=0, value=0, step=100)
    if st.button("Deposit") and dep > 0:
        db.deposit(dep)
        st.success(f"${dep} added")
        st.rerun()

if all_sig.empty:
    st.markdown("""
    <div style="background:#0d111a;border:1px solid #1e2736;padding:40px;text-align:center;
                font-family:'IBM Plex Mono',monospace">
      <div style="font-size:11px;color:#4a5568">NO TRADE HISTORY YET</div>
      <div style="font-size:9px;color:#2a3040;margin-top:6px">
        Run cycles from Dashboard — every trade auto-saves permanently here
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── PREPROCESS ─────────────────────────────────────────────────────────────────
all_sig["ts"]    = pd.to_datetime(all_sig["ts"], errors="coerce")
all_sig["date"]  = all_sig["ts"].dt.date
all_sig["month"] = all_sig["ts"].dt.to_period("M").astype(str)
closed           = all_sig[all_sig["status"] == "CLOSED"].copy()
open_t           = all_sig[all_sig["status"] == "OPEN"].copy()

wins   = len(closed[closed["outcome"] == "WIN"]) if not closed.empty else 0
losses = len(closed[closed["outcome"] == "LOSS"]) if not closed.empty else 0
total_c= len(closed)
wr     = wins / total_c * 100 if total_c > 0 else 0
pnl_usd= closed["pnl_usd"].sum() if not closed.empty and "pnl_usd" in closed else 0

# ── ACCOUNT EQUITY CURVE ──────────────────────────────────────────────────────
acct_df = db.get_account_history()
if not acct_df.empty:
    st.markdown(section_header("EQUITY CURVE", "INITIAL DEPOSIT + ALL PnL COMPOUNDED"), unsafe_allow_html=True)
    fig_eq = go.Figure()
    fig_eq.add_trace(go.Scatter(
        x=acct_df.index,
        y=acct_df["balance"],
        line=dict(color="#26d17a", width=2),
        fill="tozeroy",
        fillcolor="rgba(38,209,122,0.05)",
        name="Balance"
    ))
    fig_eq.add_hline(y=float(acct_df["balance"].iloc[0]),
                     line_dash="dot", line_color="#4a5568", line_width=1)
    fig_eq.update_layout(
        height=220,
        plot_bgcolor="#0a0c10", paper_bgcolor="#0a0c10",
        font=dict(family="IBM Plex Mono", color="#c8d0e0", size=10),
        margin=dict(l=50, r=20, t=10, b=30),
        xaxis=dict(gridcolor="#1e2736", tickfont=dict(size=8)),
        yaxis=dict(gridcolor="#1e2736", tickfont=dict(size=9), tickprefix="$"),
    )
    st.plotly_chart(fig_eq, width='stretch', config={"displayModeBar": False})

# ── SUMMARY METRICS ────────────────────────────────────────────────────────────
m1,m2,m3,m4,m5,m6 = st.columns(6)
for col,(lbl,val,c) in zip(
    [m1,m2,m3,m4,m5,m6],
    [
        ("Balance",     f"${bal:,.2f}",                     "#26d17a"),
        ("Total Trades",total_c,                             "#c8d0e0"),
        ("Open",        len(open_t),                         "#f0a500"),
        ("Win Rate",    f"{wr:.1f}%",                        "#26d17a" if wr>=55 else "#f0a500"),
        ("Total P&L",   f"${pnl_usd:+,.2f}",                "#26d17a" if pnl_usd>=0 else "#e05555"),
        ("Wins/Losses", f"{wins}W / {losses}L",              "#c8d0e0"),
    ]
):
    col.markdown(f"""
    <div style="background:#0d111a;border:1px solid #1e2736;padding:8px;
                font-family:IBM Plex Mono,monospace;text-align:center">
      <div style="font-size:7px;color:#4a5568;text-transform:uppercase;letter-spacing:1px">{lbl}</div>
      <div style="font-size:14px;font-weight:600;color:{c};margin-top:2px">{val}</div>
    </div>
    """, unsafe_allow_html=True)

# ── FULL TRADE LOG TABLE ───────────────────────────────────────────────────────
st.markdown("---")
st.markdown(section_header("COMPLETE TRADE LOG",
                            f"{len(all_sig)} RECORDS — PERSISTS ACROSS APP RESTARTS"),
            unsafe_allow_html=True)

# Date filter
df1, df2, df3 = st.columns(3)
with df1:
    start_d = st.date_input("From", value=datetime.now(timezone.utc).date() - timedelta(days=30))
with df2:
    end_d   = st.date_input("To",   value=datetime.now(timezone.utc).date())
with df3:
    stat_f  = st.selectbox("Status", ["ALL", "OPEN", "CLOSED"])

mask = (all_sig["date"] >= start_d) & (all_sig["date"] <= end_d)
filt = all_sig[mask].copy()
if stat_f != "ALL":
    filt = filt[filt["status"] == stat_f]

def build_table(df):
    rows = []
    for no, (_, row) in enumerate(df.iterrows(), 1):
        open_t_str  = str(row["ts"])[:16] if pd.notna(row["ts"]) else "---"
        close_t_str = str(row.get("close_ts",""))[:16] if pd.notna(row.get("close_ts")) else "OPEN"
        pnl_val     = row.get("pnl_usd")
        pnl_str     = f"${float(pnl_val):+.2f}" if pd.notna(pnl_val) else "---"
        lots        = float(row.get("lots", 0.01)) or 0.01
        rows.append({
            "NO":         no,
            "DATE":       str(row["date"]),
            "B/S":        "BUY"  if row["direction"] == "long" else "SELL",
            "STRATEGY":   STRATEGY_DISPLAY.get(row.get("strategy",""), row.get("strategy","")),
            "LOTS":       f"{lots:.2f}",
            "OPEN TIME":  open_t_str,
            "ENTRY":      f"{float(row.get('entry',0)):.2f}",
            "SL":         f"{float(row.get('sl',0)):.2f}",
            "TP":         f"{float(row.get('tp',0)):.2f}",
            "CLOSE TIME": close_t_str,
            "P&L ($)":    pnl_str,
            "STATUS":     row.get("outcome", row.get("status","OPEN")),
            "SCORE":      f"{float(row.get('score',0)):.1f}",
        })
    return pd.DataFrame(rows)

if filt.empty:
    st.info("No trades in selected date range.")
else:
    tbl = build_table(filt)

    def cbs(v): return "color:#26d17a;font-weight:bold" if v=="BUY" else "color:#e05555;font-weight:bold"
    def cos(v):
        if v=="WIN":  return "color:#26d17a"
        if v=="LOSS": return "color:#e05555"
        return "color:#f0a500"
    def cpnl(v):
        if isinstance(v,str):
            if v.startswith("$+"): return "color:#26d17a;font-weight:bold"
            if v.startswith("$-"): return "color:#e05555;font-weight:bold"
        return ""

    styled = tbl.style\
        .map(cbs,  subset=["B/S"])\
        .map(cos,  subset=["STATUS"])\
        .map(cpnl, subset=["P&L ($)"])\
        .set_properties(**{
            "font-family":"IBM Plex Mono,monospace",
            "font-size":"10px","background":"#0d111a","color":"#c8d0e0",
        })\
        .set_table_styles([{"selector":"th","props":[
            ("background","#06080c"),("color","#f0a500"),("font-size","8px"),
            ("text-transform","uppercase"),("letter-spacing","1px"),
            ("border-bottom","1px solid #1e2736"),("padding","5px 8px"),
        ]},{"selector":"td","props":[("padding","4px 8px")]}])

    st.dataframe(styled, width='stretch', height=450, hide_index=True)

# ── MONTHLY P&L CHART ──────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(section_header("MONTHLY P&L", "FROM CLOSED TRADES"), unsafe_allow_html=True)

monthly_df = db.monthly_pnl()
if not monthly_df.empty:
    fig_m = go.Figure(go.Bar(
        x=monthly_df["month"].tolist(),
        y=monthly_df["amount"].round(2).tolist(),
        marker_color=["#26d17a" if v >= 0 else "#e05555" for v in monthly_df["amount"]],
        text=[f"${v:+.2f}" for v in monthly_df["amount"]],
        textfont=dict(family="IBM Plex Mono", size=9, color="#c8d0e0"),
        textposition="outside",
    ))
    fig_m.add_hline(y=0, line_color="#4a5568", line_width=0.5)
    fig_m.update_layout(
        height=200, plot_bgcolor="#0a0c10", paper_bgcolor="#0a0c10",
        font=dict(family="IBM Plex Mono", color="#c8d0e0", size=10),
        margin=dict(l=50, r=20, t=20, b=30),
        xaxis=dict(gridcolor="#1e2736", tickfont=dict(size=9)),
        yaxis=dict(gridcolor="#1e2736", tickfont=dict(size=9), tickprefix="$"),
    )
    st.plotly_chart(fig_m, width='stretch', config={"displayModeBar": False})
else:
    st.info("No closed trades yet — monthly chart will populate automatically.")

# ── DAILY GOAL HISTORY ─────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(section_header("DAILY $20 GOAL TRACKER"), unsafe_allow_html=True)

with db.conn() as c:
    goal_df = pd.read_sql(
        "SELECT * FROM daily_goal ORDER BY date_str DESC LIMIT 30", c
    )

if not goal_df.empty:
    goal_df["hit"] = goal_df["achieved"] >= goal_df["target_usd"]
    goal_df["pct"] = (goal_df["achieved"] / goal_df["target_usd"] * 100).round(1)
    st.dataframe(
        goal_df.style.map(
            lambda v: "color:#26d17a;font-weight:bold" if v is True
                      else "color:#e05555" if v is False else "",
            subset=["hit"]
        ).map(
            lambda v: "color:#26d17a" if isinstance(v,(int,float)) and v>=0
                      else "color:#e05555" if isinstance(v,(int,float)) and v<0 else "",
            subset=["achieved"]
        ).set_properties(**{
            "font-family":"IBM Plex Mono,monospace","font-size":"11px",
            "background":"#0d111a","color":"#c8d0e0",
        }).set_table_styles([{"selector":"th","props":[
            ("background","#06080c"),("color","#f0a500"),("font-size","9px"),
            ("text-transform","uppercase"),("letter-spacing","1px"),
            ("border-bottom","1px solid #1e2736"),
        ]}]),
        width='stretch', hide_index=True,
    )

# ── EXPORT ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.download_button(
    "⬇  EXPORT FULL HISTORY CSV",
    all_sig.to_csv(index=False),
    f"xauusd_history_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.csv",
    "text/csv"
)
