import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.terminal_theme import TERMINAL_CSS, section_header
from core.risk_engine import RiskEngine
from core.data_engine import DataEngine
from core.sr_engine import SREngine
from database.db import Database
from core.config import CONFIG

st.set_page_config(page_title="RISK MANAGER // XAUUSD", layout="wide")
st.markdown(TERMINAL_CSS, unsafe_allow_html=True)

st.markdown("""
<div style="font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;
            color:#f0a500;letter-spacing:2px;border-bottom:1px solid #1e2736;
            padding-bottom:8px;margin-bottom:14px">
◈ RISK MANAGER // LOT SIZING + NEXT LEVELS + MONTHLY PERFORMANCE
</div>
""", unsafe_allow_html=True)

db = Database()

# ── ACCOUNT INPUTS ────────────────────────────────────────────────────────────
st.markdown(section_header("ACCOUNT CONFIGURATION"), unsafe_allow_html=True)
ri1, ri2, ri3, ri4 = st.columns(4)
with ri1:
    balance = st.number_input("Account Balance ($)", value=10000, min_value=100, step=500)
with ri2:
    win_rate_input = st.slider("Estimated Win Rate (%)", 30, 80, 55) / 100
with ri3:
    avg_rr_input = st.slider("Average R:R", 1.0, 4.0, 1.8, 0.1)
with ri4:
    peak = st.number_input("Peak Balance ($)", value=balance, min_value=100, step=500)

re = RiskEngine(balance=balance)
re.peak = peak

# ── LOT SIZE CALCULATOR ────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(section_header("POSITION SIZE CALCULATOR", "FRACTIONAL KELLY 25% — AUTO DRAWDOWN SCALING"), unsafe_allow_html=True)

lc1, lc2, lc3 = st.columns(3)
with lc1:
    entry_price = st.number_input("Entry Price", value=2350.00, step=0.5, format="%.2f")
with lc2:
    sl_price = st.number_input("Stop Loss Price", value=2335.00, step=0.5, format="%.2f")
with lc3:
    tp_price = st.number_input("Take Profit Price", value=2380.00, step=0.5, format="%.2f")

# Auto-detect direction
direction = "long" if tp_price > entry_price else "short"
sl_dist   = abs(entry_price - sl_price)
tp_dist   = abs(tp_price - entry_price)
rr_ratio  = tp_dist / sl_dist if sl_dist > 0 else 0

sizing = re.position_size(entry_price, sl_price, win_rate=win_rate_input, avg_rr=avg_rr_input)

if sizing.get("blocked"):
    st.markdown(f"""
    <div style="background:#280a0a;border:1px solid #e05555;padding:12px;
                font-family:IBM Plex Mono,monospace;color:#e05555;font-size:11px">
      ⚠ TRADE BLOCKED: {sizing.get('reason','')}
    </div>
    """, unsafe_allow_html=True)
else:
    dir_color = "#26d17a" if direction == "long" else "#e05555"
    sl1, sl2, sl3, sl4, sl5, sl6 = st.columns(6)
    for col, (lbl, val, c) in zip(
        [sl1, sl2, sl3, sl4, sl5, sl6],
        [
            ("Direction",   direction.upper(), dir_color),
            ("Lot Size",    f"{sizing['lots']:.2f}", "#f0f4ff"),
            ("Risk ($)",    f"${sizing['risk_usd']:.2f}", "#f0a500"),
            ("Risk (%)",    f"{sizing['risk_pct']:.2f}%", "#f0a500"),
            ("R:R Ratio",   f"{rr_ratio:.1f}", "#26d17a" if rr_ratio >= 1.5 else "#e05555"),
            ("SL (pips)",   f"{sizing['sl_pips']:.0f}", "#c8d0e0"),
        ]
    ):
        col.markdown(f"""
        <div style="background:#0d111a;border:1px solid #1e2736;padding:10px;
                    font-family:IBM Plex Mono,monospace;text-align:center">
          <div style="font-size:8px;color:#4a5568;text-transform:uppercase;letter-spacing:1px">{lbl}</div>
          <div style="font-size:17px;font-weight:600;color:{c};margin-top:3px">{val}</div>
        </div>
        """, unsafe_allow_html=True)

# Risk matrix: show lot sizes for different SL levels
st.markdown("---")
st.markdown(section_header("LOT SIZE MATRIX", "DIFFERENT SL DISTANCES AT CURRENT SETTINGS"), unsafe_allow_html=True)

sl_dists  = [5, 8, 10, 12, 15, 18, 20, 25, 30, 40]
lot_rows  = []
for sld in sl_dists:
    fake_sl = entry_price - sld * 0.1
    sz = re.position_size(entry_price, fake_sl, win_rate=win_rate_input, avg_rr=avg_rr_input)
    lot_rows.append({
        "SL Distance ($)": sld * 0.1,
        "SL Pips": sld,
        "Lots": sz.get("lots", 0),
        "Risk ($)": sz.get("risk_usd", 0),
        "Risk (%)": sz.get("risk_pct", 0),
    })

df_matrix = pd.DataFrame(lot_rows)
st.dataframe(
    df_matrix.style.set_properties(**{
        "font-family": "IBM Plex Mono,monospace",
        "font-size":   "11px",
        "background":  "#0d111a",
        "color":       "#c8d0e0",
    }).set_table_styles([
        {"selector": "th", "props": [
            ("background", "#06080c"), ("color", "#f0a500"),
            ("font-size", "9px"), ("text-transform", "uppercase"),
            ("letter-spacing", "1px"), ("border-bottom", "1px solid #1e2736"),
        ]}
    ]),
    width='stretch', height=250
)

# ── NEXT BUY/SELL LEVELS ──────────────────────────────────────────────────────
st.markdown("---")
st.markdown(section_header("NEXT BUY / SELL PRICE LEVELS", "FROM LIVE S/R DETECTION"), unsafe_allow_html=True)

@st.cache_data(ttl=900, show_spinner=False)
def get_live_levels():
    de = DataEngine()
    de.fetch_all()
    sre = SREngine()
    df_1h = de.get("1H")
    if df_1h.empty:
        return None, None, None
    current = float(df_1h["close"].iloc[-1])
    sr_all  = sre.detect_all_tf(de.data, de)
    sup, res = sre.nearest(sr_all, current, n=5)
    return current, sup, res

with st.spinner("FETCHING LIVE S/R LEVELS..."):
    current_price, sup_levels, res_levels = get_live_levels()

if current_price and sup_levels:
    nb1, nb2 = st.columns(2)
    with nb1:
        st.markdown(f"""
        <div style="background:#0d111a;border:1px solid #1e2736;padding:14px;
                    font-family:IBM Plex Mono,monospace">
          <div style="font-size:9px;color:#26d17a;letter-spacing:1.5px;text-transform:uppercase;
                      margin-bottom:10px;border-bottom:1px solid #1e2736;padding-bottom:4px">
            NEXT BUY LEVELS (SUPPORT)
          </div>
        """, unsafe_allow_html=True)
        for i, lvl in enumerate(sup_levels[:5]):
            dist = abs(current_price - lvl.price)
            dist_pct = dist / current_price * 100
            bg   = "#0a2818" if i == 0 else "#0d111a"
            st.markdown(f"""
          <div style="background:{bg};padding:6px 8px;margin-bottom:2px;
                      display:flex;justify-content:space-between">
            <span style="color:#26d17a;font-size:13px;font-weight:{'600' if i==0 else '400'}">
              {lvl.price:.2f}
            </span>
            <span style="font-size:9px;color:#4a5568;background:#111520;padding:1px 6px">{lvl.timeframe}</span>
            <span style="color:#4a5568;font-size:10px">{dist:.1f} pts ({dist_pct:.2f}%)</span>
            <span style="color:#4a5568;font-size:9px">{"●"*min(lvl.touches,4)}</span>
          </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with nb2:
        st.markdown(f"""
        <div style="background:#0d111a;border:1px solid #1e2736;padding:14px;
                    font-family:IBM Plex Mono,monospace">
          <div style="font-size:9px;color:#e05555;letter-spacing:1.5px;text-transform:uppercase;
                      margin-bottom:10px;border-bottom:1px solid #1e2736;padding-bottom:4px">
            NEXT SELL LEVELS (RESISTANCE)
          </div>
        """, unsafe_allow_html=True)
        for i, lvl in enumerate(res_levels[:5]):
            dist = abs(current_price - lvl.price)
            dist_pct = dist / current_price * 100
            bg   = "#280a0a" if i == 0 else "#0d111a"
            st.markdown(f"""
          <div style="background:{bg};padding:6px 8px;margin-bottom:2px;
                      display:flex;justify-content:space-between">
            <span style="color:#e05555;font-size:13px;font-weight:{'600' if i==0 else '400'}">
              {lvl.price:.2f}
            </span>
            <span style="font-size:9px;color:#4a5568;background:#111520;padding:1px 6px">{lvl.timeframe}</span>
            <span style="color:#4a5568;font-size:10px">{dist:.1f} pts ({dist_pct:.2f}%)</span>
            <span style="color:#4a5568;font-size:9px">{"●"*min(lvl.touches,4)}</span>
          </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Current price reference
    st.markdown(f"""
    <div style="background:#1a1500;border:1px solid #5a3800;padding:8px 14px;
                font-family:IBM Plex Mono,monospace;display:flex;justify-content:space-between;
                align-items:center;margin-top:8px">
      <span style="font-size:9px;color:#4a5568;letter-spacing:1px">CURRENT XAUUSD</span>
      <span style="font-size:18px;font-weight:600;color:#f0a500">{current_price:,.2f}</span>
      <span style="font-size:9px;color:#4a5568">LIVE PRICE</span>
    </div>
    """, unsafe_allow_html=True)

# ── DRAWDOWN CIRCUIT BREAKERS ─────────────────────────────────────────────────
st.markdown("---")
st.markdown(section_header("DRAWDOWN CIRCUIT BREAKERS", "KELLY SCALING RULES"), unsafe_allow_html=True)

dd_pct = (peak - balance) / peak * 100 if peak > 0 else 0
mult   = re.size_mult()
kill, kreason = re.kill_switch()

da1, da2, da3, da4 = st.columns(4)
for col, (lbl, val, c, sub) in zip(
    [da1, da2, da3, da4],
    [
        ("Current DD",    f"{dd_pct:.2f}%", "#26d17a" if dd_pct<5 else "#f0a500" if dd_pct<10 else "#e05555", f"Peak ${peak:,.0f}"),
        ("Size Mult",     f"{mult:.2f}×",   "#26d17a" if mult==1.0 else "#f0a500" if mult==0.5 else "#e05555", "Kelly scale factor"),
        ("Daily Loss",    f"{re.daily_loss():.1f}%", "#26d17a", f"Limit {CONFIG['risk']['max_daily_loss_pct']}%"),
        ("Kill Switch",   "ON" if kill else "OFF", "#e05555" if kill else "#26d17a", kreason if kill else "All clear"),
    ]
):
    col.markdown(f"""
    <div style="background:#0d111a;border:1px solid #1e2736;padding:10px;
                font-family:IBM Plex Mono,monospace;text-align:center">
      <div style="font-size:8px;color:#4a5568;text-transform:uppercase;letter-spacing:1px">{lbl}</div>
      <div style="font-size:18px;font-weight:600;color:{c};margin-top:3px">{val}</div>
      <div style="font-size:8px;color:#4a5568;margin-top:2px">{sub}</div>
    </div>
    """, unsafe_allow_html=True)

# Visual DD gauge
fig_dd = go.Figure(go.Indicator(
    mode="gauge+number",
    value=dd_pct,
    title={"text": "DRAWDOWN %", "font": {"family": "IBM Plex Mono", "color": "#c8d0e0", "size": 11}},
    gauge={
        "axis":  {"range": [0, 20], "tickfont": {"size": 9, "color": "#4a5568"},
                  "tickcolor": "#1e2736"},
        "bar":   {"color": "#f0a500"},
        "steps": [
            {"range": [0, 5],  "color": "#0a2818"},
            {"range": [5, 10], "color": "#2a1a00"},
            {"range": [10, 20],"color": "#280a0a"},
        ],
        "threshold": {"line": {"color": "#e05555", "width": 2}, "value": 15},
    },
    number={"suffix": "%", "font": {"family": "IBM Plex Mono", "color": "#f0a500", "size": 24}},
))
fig_dd.update_layout(
    height=200, margin=dict(l=20, r=20, t=40, b=10),
    plot_bgcolor="#0a0c10", paper_bgcolor="#0a0c10",
    font=dict(family="IBM Plex Mono", color="#c8d0e0"),
)
st.plotly_chart(fig_dd, width='stretch', config={"displayModeBar": False})

# ── MONTHLY PROFIT % FROM DATABASE ────────────────────────────────────────────
st.markdown("---")
st.markdown(section_header("LIVE TRADE MONTHLY PROFIT %", "FROM CLOSED SIGNALS IN DATABASE"), unsafe_allow_html=True)

signals_df = db.get_signals(limit=1000)
if not signals_df.empty and "pnl_r" in signals_df.columns:
    monthly_pnl = re.monthly_profit_pct(signals_df)
    if monthly_pnl:
        months  = list(monthly_pnl.keys())
        vals    = [monthly_pnl[m] for m in months]
        pnl_usd = [v * balance * 0.01 for v in vals]

        fig_mp = go.Figure()
        fig_mp.add_trace(go.Bar(
            x=months, y=[v * 100 for v in vals],
            marker_color=["#26d17a" if v >= 0 else "#e05555" for v in vals],
            text=[f"{v*100:+.1f}%" for v in vals],
            textfont=dict(family="IBM Plex Mono", size=9, color="#c8d0e0"),
            textposition="outside",
            name="Monthly P&L %"
        ))
        fig_mp.add_hline(y=0, line_color="#4a5568", line_width=0.5)
        fig_mp.update_layout(
            height=220, plot_bgcolor="#0a0c10", paper_bgcolor="#0a0c10",
            font=dict(family="IBM Plex Mono", color="#c8d0e0", size=10),
            margin=dict(l=40, r=20, t=10, b=30),
            xaxis=dict(gridcolor="#1e2736", tickfont=dict(size=9)),
            yaxis=dict(gridcolor="#1e2736", tickfont=dict(size=9), ticksuffix="%"),
        )
        st.plotly_chart(fig_mp, width='stretch', config={"displayModeBar": False})
    else:
        st.markdown("""
        <div style="background:#0d111a;border:1px solid #1e2736;padding:16px;text-align:center;
                    font-family:IBM Plex Mono,monospace;font-size:10px;color:#4a5568">
          NO CLOSED TRADES YET — RUN LIVE CYCLES TO POPULATE MONTHLY DATA
        </div>
        """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div style="background:#0d111a;border:1px solid #1e2736;padding:16px;text-align:center;
                font-family:IBM Plex Mono,monospace;font-size:10px;color:#4a5568">
      NO SIGNAL DATA — RUN CYCLES FROM DASHBOARD FIRST
    </div>
    """, unsafe_allow_html=True)
