import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.terminal_theme import TERMINAL_CSS, section_header, signal_card
from database.db import Database

st.set_page_config(page_title="SIGNALS // XAUUSD", layout="wide")
st.markdown(TERMINAL_CSS, unsafe_allow_html=True)

st.markdown("""
<div style="font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;
            color:#f0a500;letter-spacing:2px;border-bottom:1px solid #1e2736;
            padding-bottom:8px;margin-bottom:14px">
◈ SIGNAL HISTORY // ALL FIRED SIGNALS
</div>
""", unsafe_allow_html=True)

db = Database()
df = db.get_signals(limit=200)

if df.empty:
    st.markdown("""
    <div style="background:#0d111a;border:1px solid #1e2736;padding:30px;text-align:center;
                font-family:'IBM Plex Mono',monospace">
      <div style="font-size:11px;color:#4a5568;letter-spacing:1px">NO SIGNALS IN DATABASE YET</div>
      <div style="font-size:9px;color:#2a3040;margin-top:4px">RUN A CYCLE FROM THE DASHBOARD TO GENERATE SIGNALS</div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# Summary row
stats = db.summary_stats()
c1, c2, c3, c4, c5 = st.columns(5)
for col, (label, val, color) in zip(
    [c1, c2, c3, c4, c5],
    [
        ("Total Signals", stats["total_signals"], "#f0f4ff"),
        ("Open",          stats["open_signals"],  "#f0a500"),
        ("Win Rate",      f"{stats['win_rate']}%", "#26d17a"),
        ("Avg Score",     f"{stats['avg_score']}/10", "#4da8f0"),
        ("Total P&L (R)", stats["total_pnl_r"],   "#26d17a" if stats["total_pnl_r"] >= 0 else "#e05555"),
    ]
):
    col.markdown(f"""
    <div style="background:#0d111a;border:1px solid #1e2736;padding:10px;
                font-family:IBM Plex Mono,monospace;text-align:center">
      <div style="font-size:8px;color:#4a5568;text-transform:uppercase;letter-spacing:1px">{label}</div>
      <div style="font-size:18px;font-weight:600;color:{color};margin-top:3px">{val}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# Filters
fc1, fc2, fc3 = st.columns([1, 1, 2])
with fc1:
    status_filter = st.selectbox("Status", ["ALL", "OPEN", "CLOSED"], key="sf_status")
with fc2:
    strat_filter  = st.selectbox("Strategy", ["ALL"] + list(df["strategy"].unique()), key="sf_strat")
with fc3:
    dir_filter    = st.selectbox("Direction", ["ALL", "long", "short"], key="sf_dir")

dff = df.copy()
if status_filter != "ALL":
    dff = dff[dff["status"] == status_filter]
if strat_filter != "ALL":
    dff = dff[dff["strategy"] == strat_filter]
if dir_filter != "ALL":
    dff = dff[dff["direction"] == dir_filter]

st.markdown(section_header(f"SIGNALS TABLE — {len(dff)} RECORDS"), unsafe_allow_html=True)

# Color-code the table
def color_direction(val):
    if val == "long":
        return "color: #26d17a"
    elif val == "short":
        return "color: #e05555"
    return ""

def color_outcome(val):
    if val == "WIN":
        return "color: #26d17a"
    elif val == "LOSS":
        return "color: #e05555"
    return "color: #f0a500"

def color_score(val):
    try:
        v = float(val)
        if v >= 7:   return "color: #26d17a"
        if v >= 6:   return "color: #f0a500"
        return "color: #e05555"
    except Exception:
        return ""

display_cols = ["id", "ts", "strategy", "direction", "entry", "sl", "tp", "rr",
                "score", "regime", "session", "status", "outcome", "pnl_r", "lots"]
display_cols = [c for c in display_cols if c in dff.columns]
dff_disp = dff[display_cols].copy()
dff_disp["ts"] = dff_disp["ts"].astype(str).str[:16]
dff_disp["strategy"] = dff_disp["strategy"].str.replace("_", " ").str.upper()
dff_disp["rr"]  = dff_disp["rr"].round(2)
dff_disp["score"] = dff_disp["score"].round(1)

styled = dff_disp.style\
    .applymap(color_direction, subset=["direction"])\
    .applymap(color_outcome,   subset=["outcome"] if "outcome" in dff_disp.columns else [])\
    .applymap(color_score,     subset=["score"])\
    .set_properties(**{
        "font-family": "IBM Plex Mono, monospace",
        "font-size":   "11px",
        "background":  "#0d111a",
        "color":       "#c8d0e0",
    })\
    .set_table_styles([
        {"selector": "th", "props": [
            ("background", "#06080c"), ("color", "#f0a500"),
            ("font-size", "9px"), ("letter-spacing", "1px"),
            ("text-transform", "uppercase"), ("border-bottom", "1px solid #1e2736"),
        ]},
        {"selector": "tr:hover td", "props": [("background", "#111827")]},
    ], overwrite=False)

st.dataframe(styled, use_container_width=True, height=450)

# Download
csv = dff.to_csv(index=False)
st.download_button(
    label="⬇  EXPORT CSV",
    data=csv,
    file_name=f"xauusd_signals_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
    mime="text/csv",
)
