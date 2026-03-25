import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.terminal_theme import TERMINAL_CSS, section_header
from core.data_engine import DataEngine
from core.sr_engine import SREngine
from core.regime import RegimeClassifier

st.set_page_config(page_title="S/R CHART // XAUUSD", layout="wide")
st.markdown(TERMINAL_CSS, unsafe_allow_html=True)

st.markdown("""
<div style="font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;
            color:#f0a500;letter-spacing:2px;border-bottom:1px solid #1e2736;
            padding-bottom:8px;margin-bottom:14px">
◈ S/R CHART // LIVE XAUUSD — FRACTAL PIVOTS + ZONE FLIP + VOLUME PROFILE
</div>
""", unsafe_allow_html=True)

# Controls
cc1, cc2, cc3, cc4 = st.columns(4)
with cc1:
    tf = st.selectbox("Chart Timeframe", ["1H", "4H", "15M", "1D"], key="chart_tf")
with cc2:
    bars = st.slider("Bars to display", 50, 300, 120, 10, key="chart_bars")
with cc3:
    show_tfs = st.multiselect(
        "S/R from timeframes",
        ["15M", "1H", "4H", "1D"],
        default=["1H", "4H", "1D"],
        key="chart_sr_tfs"
    )
with cc4:
    refresh = st.button("↺  REFRESH DATA", width='stretch')

@st.cache_data(ttl=600, show_spinner=False)
def load_chart_data(timeframe):
    de = DataEngine()
    de.fetch_all()
    return de

with st.spinner("LOADING MARKET DATA..."):
    de = load_chart_data(tf)

df_chart = de.get(tf)
if df_chart.empty:
    st.error("Could not fetch chart data. Check connection.")
    st.stop()

df_plot = df_chart.tail(bars).copy()
current_price = float(df_plot["close"].iloc[-1])

# Detect S/R from selected timeframes
sre   = SREngine()
rc    = RegimeClassifier()
sr_by_tf = {}
all_sr   = []
for t in show_tfs:
    df_t = de.get(t)
    if not df_t.empty:
        levels = sre.detect(df_t, t)
        sr_by_tf[t] = levels
        all_sr.extend(levels)

regime = rc.classify(de.get("1H"))

# ── BUILD CHART ───────────────────────────────────────────────────────────────
atr_val = float(df_plot["atr"].iloc[-1]) if "atr" in df_plot.columns else 0
adx_val = float(df_plot["adx"].iloc[-1]) if "adx" in df_plot.columns else 0
rsi_val = float(df_plot["rsi"].iloc[-1]) if "rsi" in df_plot.columns else 50

fig = make_subplots(
    rows=4, cols=1,
    shared_xaxes=True,
    row_heights=[0.55, 0.15, 0.15, 0.15],
    vertical_spacing=0.015,
    subplot_titles=["", "", "", ""]
)

# Candlestick
fig.add_trace(go.Candlestick(
    x=df_plot.index,
    open=df_plot["open"], high=df_plot["high"],
    low=df_plot["low"],   close=df_plot["close"],
    increasing_line_color="#26d17a",  decreasing_line_color="#e05555",
    increasing_fillcolor="#0a2010",   decreasing_fillcolor="#200a0a",
    name="XAUUSD", showlegend=False,
), row=1, col=1)

# EMAs
ema_cfg = [("ema_fast","#f0a500","EMA20",1.0),
           ("ema_med", "#4da8f0","EMA50",1.0),
           ("ema_slow","#e05555","EMA200",0.8)]
for col_n, color, name, width in ema_cfg:
    if col_n in df_plot.columns:
        fig.add_trace(go.Scatter(
            x=df_plot.index, y=df_plot[col_n],
            line=dict(width=width, color=color),
            name=name, showlegend=True,
        ), row=1, col=1)

# S/R Levels with TF color coding
tf_colors = {
    "15M": "rgba(100,100,200,0.5)",
    "1H":  "rgba(240,165,0,0.55)",
    "4H":  "rgba(77,168,240,0.55)",
    "1D":  "rgba(168,85,247,0.65)",
}
sup_levels, res_levels = sre.nearest(all_sr, current_price, n=6)

for lvl in res_levels:
    c = tf_colors.get(lvl.timeframe, "rgba(200,100,100,0.5)")
    fig.add_hline(
        y=lvl.price, line_dash="dash",
        line_color=c, line_width=1,
        annotation_text=f"  RES {lvl.price:.0f} [{lvl.timeframe}] {lvl.touches}t",
        annotation_font_size=8,
        annotation_font_color=c,
        row=1, col=1
    )

for lvl in sup_levels:
    c = tf_colors.get(lvl.timeframe, "rgba(50,200,100,0.5)")
    fig.add_hline(
        y=lvl.price, line_dash="dash",
        line_color=c, line_width=1,
        annotation_text=f"  SUP {lvl.price:.0f} [{lvl.timeframe}] {lvl.touches}t",
        annotation_font_size=8,
        annotation_font_color=c,
        row=1, col=1
    )

# Current price line
fig.add_hline(
    y=current_price, line_dash="solid",
    line_color="#f0a500", line_width=1,
    annotation_text=f"  ◈ {current_price:.2f}",
    annotation_font_color="#f0a500",
    annotation_font_size=10,
    row=1, col=1
)

# Volume
vol_c = ["#0a2010" if c >= o else "#200a0a"
         for c, o in zip(df_plot["close"], df_plot["open"])]
fig.add_trace(go.Bar(
    x=df_plot.index, y=df_plot["volume"],
    marker_color=vol_c, name="Volume", showlegend=False,
), row=2, col=1)

# Volume MA
if "vol_ma" in df_plot.columns:
    fig.add_trace(go.Scatter(
        x=df_plot.index, y=df_plot["vol_ma"],
        line=dict(color="#f0a500", width=0.8),
        name="Vol MA", showlegend=False,
    ), row=2, col=1)

# RSI
if "rsi" in df_plot.columns:
    fig.add_trace(go.Scatter(
        x=df_plot.index, y=df_plot["rsi"],
        line=dict(color="#a855f7", width=1),
        name="RSI", showlegend=False,
    ), row=3, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="rgba(224,85,85,0.4)", row=3, col=1)
    fig.add_hline(y=50, line_dash="dot", line_color="rgba(100,100,100,0.4)", row=3, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="rgba(38,209,122,0.4)", row=3, col=1)

# ADX
if "adx" in df_plot.columns:
    adx_color = [("#26d17a" if v > 40 else "#f0a500" if v > 25 else "#4a5568")
                 for v in df_plot["adx"].fillna(0)]
    fig.add_trace(go.Bar(
        x=df_plot.index, y=df_plot["adx"],
        marker_color=adx_color, name="ADX", showlegend=False,
    ), row=4, col=1)
    fig.add_hline(y=25, line_dash="dot", line_color="rgba(240,165,0,0.4)", row=4, col=1)
    fig.add_hline(y=40, line_dash="dot", line_color="rgba(38,209,122,0.4)", row=4, col=1)

fig.update_layout(
    height=680,
    plot_bgcolor="#0a0c10",
    paper_bgcolor="#0a0c10",
    font=dict(family="IBM Plex Mono", color="#c8d0e0", size=9),
    xaxis_rangeslider_visible=False,
    margin=dict(l=60, r=80, t=15, b=15),
    legend=dict(
        orientation="h", y=1.01, x=0,
        font=dict(size=9), bgcolor="rgba(0,0,0,0)",
        bordercolor="#1e2736",
    ),
)
for i in range(1, 5):
    fig.update_xaxes(
        gridcolor="#111827", showgrid=True,
        zeroline=False, tickfont=dict(size=8),
        row=i, col=1,
    )
    fig.update_yaxes(
        gridcolor="#111827", showgrid=True,
        zeroline=False, tickfont=dict(size=8),
        row=i, col=1,
    )

st.plotly_chart(fig, width='stretch', config={
    "displayModeBar": True,
    "modeBarButtonsToRemove": ["pan2d","lasso2d","select2d","autoScale2d"],
    "displaylogo": False,
})

# ── S/R TABLE ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(section_header("ALL ACTIVE S/R LEVELS", f"{len(all_sr)} DETECTED"), unsafe_allow_html=True)

ta1, ta2 = st.columns(2)
with ta1:
    st.markdown(f"""
    <div style="font-family:IBM Plex Mono,monospace;font-size:9px;color:#e05555;
                letter-spacing:1.5px;text-transform:uppercase;margin-bottom:6px">
      RESISTANCE LEVELS
    </div>
    """, unsafe_allow_html=True)
    for lvl in sorted(res_levels, key=lambda x: x.price, reverse=True):
        dist     = lvl.price - current_price
        dist_pct = dist / current_price * 100
        tf_c     = {"15M":"#6464c8","1H":"#f0a500","4H":"#4da8f0","1D":"#a855f7"}.get(lvl.timeframe,"#c8d0e0")
        st.markdown(f"""
        <div style="background:#0d111a;border-left:2px solid #e05555;padding:6px 10px;
                    margin-bottom:2px;font-family:IBM Plex Mono,monospace;
                    display:flex;justify-content:space-between;align-items:center">
          <span style="color:#e05555;font-size:13px;font-weight:500">{lvl.price:.2f}</span>
          <span style="background:#111520;color:{tf_c};padding:1px 6px;font-size:9px">{lvl.timeframe}</span>
          <span style="color:#4a5568;font-size:9px">{lvl.touches} touches</span>
          <span style="color:#4a5568;font-size:9px">+{dist:.1f} (+{dist_pct:.2f}%)</span>
          <span style="font-size:9px;color:{'#26d17a' if lvl.strength>0.7 else '#f0a500'}">
            {'★'*max(1,int(lvl.strength*4))}
          </span>
        </div>
        """, unsafe_allow_html=True)

with ta2:
    st.markdown(f"""
    <div style="font-family:IBM Plex Mono,monospace;font-size:9px;color:#26d17a;
                letter-spacing:1.5px;text-transform:uppercase;margin-bottom:6px">
      SUPPORT LEVELS
    </div>
    """, unsafe_allow_html=True)
    for lvl in sorted(sup_levels, key=lambda x: x.price, reverse=True):
        dist     = current_price - lvl.price
        dist_pct = dist / current_price * 100
        tf_c     = {"15M":"#6464c8","1H":"#f0a500","4H":"#4da8f0","1D":"#a855f7"}.get(lvl.timeframe,"#c8d0e0")
        st.markdown(f"""
        <div style="background:#0d111a;border-left:2px solid #26d17a;padding:6px 10px;
                    margin-bottom:2px;font-family:IBM Plex Mono,monospace;
                    display:flex;justify-content:space-between;align-items:center">
          <span style="color:#26d17a;font-size:13px;font-weight:500">{lvl.price:.2f}</span>
          <span style="background:#111520;color:{tf_c};padding:1px 6px;font-size:9px">{lvl.timeframe}</span>
          <span style="color:#4a5568;font-size:9px">{lvl.touches} touches</span>
          <span style="color:#4a5568;font-size:9px">-{dist:.1f} (-{dist_pct:.2f}%)</span>
          <span style="font-size:9px;color:{'#26d17a' if lvl.strength>0.7 else '#f0a500'}">
            {'★'*max(1,int(lvl.strength*4))}
          </span>
        </div>
        """, unsafe_allow_html=True)

# ── REGIME BADGE ──────────────────────────────────────────────────────────────
from core.config import REGIME_LABELS
r_label = REGIME_LABELS.get(regime, regime)
r_color = {"TRENDING BULL":"#26d17a","TRENDING BEAR":"#e05555",
           "RANGING":"#f0a500","HIGH VOL/NEWS":"#e05555","LOW LIQ GRIND":"#4da8f0"}.get(r_label,"#c8d0e0")
st.markdown(f"""
<div style="background:#0d111a;border:1px solid {r_color};padding:8px 14px;margin-top:8px;
            font-family:IBM Plex Mono,monospace;display:flex;gap:24px;align-items:center">
  <span style="font-size:9px;color:#4a5568;letter-spacing:1px">REGIME</span>
  <span style="font-size:13px;font-weight:600;color:{r_color}">{r_label}</span>
  <span style="font-size:9px;color:#4a5568">ATR {atr_val:.1f}</span>
  <span style="font-size:9px;color:{'#26d17a' if adx_val>25 else '#c8d0e0'}">ADX {adx_val:.1f}</span>
  <span style="font-size:9px;color:{'#e05555' if rsi_val>70 else '#26d17a' if rsi_val<30 else '#c8d0e0'}">RSI {rsi_val:.1f}</span>
  <span style="font-size:9px;color:#f0a500;margin-left:auto">
    TF COLOR KEY:
    <span style="color:#f0a500">■ 1H</span>
    <span style="color:#4da8f0;margin-left:6px">■ 4H</span>
    <span style="color:#a855f7;margin-left:6px">■ 1D</span>
    <span style="color:#6464c8;margin-left:6px">■ 15M</span>
  </span>
</div>
""", unsafe_allow_html=True)
