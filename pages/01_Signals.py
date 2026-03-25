import streamlit as st
import pandas as pd
from datetime import datetime, timezone
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.terminal_theme import TERMINAL_CSS, section_header
from core.config import STRATEGY_DISPLAY
from database.db import Database

st.set_page_config(page_title="SIGNALS // XAUUSD", layout="wide")
st.markdown(TERMINAL_CSS, unsafe_allow_html=True)

st.markdown("""
<div style="font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;
            color:#f0a500;letter-spacing:2px;border-bottom:1px solid #1e2736;
            padding-bottom:8px;margin-bottom:14px">
◈ SIGNALS — ENTRY / SL / TP PRICES + FULL HISTORY
</div>
""", unsafe_allow_html=True)

db  = Database()
df  = db.get_signals(limit=500)
bal = db.get_balance()

if df.empty:
    st.markdown("""
    <div style="background:#0d111a;border:1px solid #1e2736;padding:30px;text-align:center;
                font-family:'IBM Plex Mono',monospace">
      <div style="font-size:11px;color:#4a5568;letter-spacing:1px">NO SIGNALS YET</div>
      <div style="font-size:9px;color:#2a3040;margin-top:6px">
        RUN A CYCLE FROM THE DASHBOARD TO GENERATE SIGNALS
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

stats = db.summary_stats()

# ── SUMMARY ───────────────────────────────────────────────────────────────────
s1,s2,s3,s4,s5,s6 = st.columns(6)
for col,(lbl,val,c) in zip(
    [s1,s2,s3,s4,s5,s6],
    [
        ("SIGNALS",    stats["total_signals"],                    "#c8d0e0"),
        ("OPEN",       stats["open_signals"],                     "#f0a500"),
        ("WIN RATE",   f"{stats['win_rate']}%",                   "#26d17a" if stats["win_rate"]>=55 else "#f0a500"),
        ("TOTAL P&L",  f"${stats['total_pnl_usd']:+,.2f}",       "#26d17a" if stats["total_pnl_usd"]>=0 else "#e05555"),
        ("BALANCE",    f"${bal:,.2f}",                            "#26d17a"),
        ("AVG SCORE",  f"{stats['avg_score']:.1f}/10",            "#4da8f0"),
    ]
):
    col.markdown(f"""
    <div style="background:#0d111a;border:1px solid #1e2736;padding:8px;
                font-family:IBM Plex Mono,monospace;text-align:center">
      <div style="font-size:7px;color:#4a5568;text-transform:uppercase;letter-spacing:1px">{lbl}</div>
      <div style="font-size:14px;font-weight:600;color:{c};margin-top:2px">{val}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ── OPEN POSITIONS WITH EXACT PRICES (Fix #2) ─────────────────────────────────
open_df = df[df["status"] == "OPEN"]
if not open_df.empty:
    st.markdown(section_header("OPEN POSITIONS — EXACT ENTRY / SL / TP"), unsafe_allow_html=True)
    for _, row in open_df.iterrows():
        dc   = "#26d17a" if row["direction"] == "long" else "#e05555"
        dl   = "▲ BUY" if row["direction"] == "long" else "▼ SELL"
        lots = float(row.get("lots", 0.01))
        risk = float(row.get("risk_usd", 0))
        sl_pts  = abs(float(row["entry"]) - float(row["sl"]))
        tp_pts  = abs(float(row["tp"])   - float(row["entry"]))
        sl_pips = sl_pts * 10
        tp_pips = tp_pts * 10
        st.markdown(f"""
        <div style="background:#0d111a;border:1px solid {dc};padding:12px;
                    margin-bottom:8px;font-family:IBM Plex Mono,monospace">
          <div style="display:flex;justify-content:space-between;align-items:center;
                      margin-bottom:10px">
            <div>
              <span style="font-size:14px;font-weight:700;color:{dc}">{dl}</span>
              <span style="font-size:10px;color:#7a849a;margin-left:10px">
                #{int(row['id'])} · {STRATEGY_DISPLAY.get(row.get('strategy',''),row.get('strategy',''))}
              </span>
            </div>
            <span style="font-size:9px;color:#4a5568">{str(row.get('ts',''))[:16]}</span>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:8px">
            <div style="background:#111520;padding:10px;text-align:center;border-radius:2px">
              <div style="font-size:8px;color:#4a5568;letter-spacing:1px;margin-bottom:4px">
                ENTRY PRICE
              </div>
              <div style="font-size:18px;font-weight:700;color:#f0f4ff">{row['entry']:.2f}</div>
              <div style="font-size:8px;color:#4a5568">Enter at market</div>
            </div>
            <div style="background:#1a0a0a;padding:10px;text-align:center;
                        border:1px solid #3a1414;border-radius:2px">
              <div style="font-size:8px;color:#e05555;letter-spacing:1px;margin-bottom:4px">
                STOP LOSS
              </div>
              <div style="font-size:18px;font-weight:700;color:#e05555">{row['sl']:.2f}</div>
              <div style="font-size:8px;color:#4a5568">{sl_pips:.0f} pips · ${risk:.0f} risk</div>
            </div>
            <div style="background:#0a1a0a;padding:10px;text-align:center;
                        border:1px solid #144a14;border-radius:2px">
              <div style="font-size:8px;color:#26d17a;letter-spacing:1px;margin-bottom:4px">
                TAKE PROFIT
              </div>
              <div style="font-size:18px;font-weight:700;color:#26d17a">{row['tp']:.2f}</div>
              <div style="font-size:8px;color:#4a5568">{tp_pips:.0f} pips · R:R {row['rr']:.1f}</div>
            </div>
          </div>
          <div style="display:flex;gap:16px;font-size:9px;color:#4a5568;flex-wrap:wrap">
            <span>Lots <span style="color:#c8d0e0">{lots:.2f}</span></span>
            <span>Score <span style="color:#f0a500">{float(row.get('score',0)):.1f}/10</span></span>
            <span>Regime <span style="color:#c8d0e0">{row.get('regime','?').upper()}</span></span>
            <span>Session <span style="color:#4da8f0">{row.get('session','?').upper()}</span></span>
            {"<span>"+str(row.get('notes',''))[:60]+"</span>" if row.get('notes') else ""}
          </div>
        </div>
        """, unsafe_allow_html=True)

# ── FILTERS ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(section_header("COMPLETE SIGNAL HISTORY", f"{len(df)} TOTAL RECORDS"), unsafe_allow_html=True)

fc1, fc2, fc3 = st.columns(3)
with fc1:
    sf = st.selectbox("Status", ["ALL", "OPEN", "CLOSED"])
with fc2:
    stf = st.selectbox("Strategy", ["ALL"] + [s for s in df["strategy"].unique().tolist()])
with fc3:
    df_ = st.selectbox("Direction", ["ALL", "long", "short"])

dff = df.copy()
if sf  != "ALL": dff = dff[dff["status"]    == sf]
if stf != "ALL": dff = dff[dff["strategy"]  == stf]
if df_ != "ALL": dff = dff[dff["direction"] == df_]

# ── FULL TABLE ────────────────────────────────────────────────────────────────
cols_show = ["id","ts","strategy","direction","entry","sl","tp","rr",
             "score","lots","risk_usd","status","outcome","pnl_usd","pnl_r"]
cols_show = [c for c in cols_show if c in dff.columns]
tbl = dff[cols_show].copy()
tbl["ts"]       = tbl["ts"].astype(str).str[:16]
tbl["strategy"] = tbl["strategy"].map(STRATEGY_DISPLAY).fillna(tbl["strategy"])
for col in ["entry","sl","tp","rr","score","pnl_usd","pnl_r"]:
    if col in tbl.columns:
        tbl[col] = tbl[col].round(2)

def color_direction(v):
    return "color:#26d17a" if v=="long" else "color:#e05555"
def color_outcome(v):
    if v=="WIN":  return "color:#26d17a"
    if v=="LOSS": return "color:#e05555"
    return "color:#f0a500"
def color_pnl(v):
    try:
        f = float(v)
        return "color:#26d17a" if f>0 else "color:#e05555" if f<0 else ""
    except Exception:
        return ""

styled = tbl.style\
    .map(color_direction, subset=["direction"])\
    .map(color_outcome,   subset=["outcome"] if "outcome" in tbl.columns else [])\
    .map(color_pnl,       subset=["pnl_usd","pnl_r"] if "pnl_usd" in tbl.columns else [])\
    .set_properties(**{
        "font-family": "IBM Plex Mono,monospace",
        "font-size":   "10px",
        "background":  "#0d111a",
        "color":       "#c8d0e0",
    })\
    .set_table_styles([{
        "selector": "th",
        "props": [("background","#06080c"),("color","#f0a500"),
                  ("font-size","9px"),("text-transform","uppercase"),
                  ("letter-spacing","1px"),("border-bottom","1px solid #1e2736")]
    }])

st.dataframe(styled, width='stretch', height=480, hide_index=True)

# ── EXPORT ────────────────────────────────────────────────────────────────────
st.download_button(
    "⬇  EXPORT CSV",
    dff.to_csv(index=False),
    f"xauusd_signals_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.csv",
    "text/csv"
)
