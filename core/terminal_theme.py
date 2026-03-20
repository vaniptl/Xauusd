TERMINAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Mono', monospace !important;
    background-color: #0a0c10 !important;
    color: #c8d0e0 !important;
}

/* Main app background */
.stApp {
    background-color: #0a0c10 !important;
}
.main .block-container {
    background-color: #0a0c10 !important;
    padding: 1rem 2rem !important;
    max-width: 100% !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #06080c !important;
    border-right: 1px solid #1e2736 !important;
}
[data-testid="stSidebar"] * {
    font-family: 'IBM Plex Mono', monospace !important;
    color: #c8d0e0 !important;
}
[data-testid="stSidebar"] .stRadio label {
    font-size: 12px !important;
    letter-spacing: 1px !important;
}

/* Metrics */
[data-testid="stMetric"] {
    background-color: #0d111a !important;
    border: 1px solid #1e2736 !important;
    border-radius: 0 !important;
    padding: 10px 14px !important;
}
[data-testid="stMetricLabel"] {
    font-size: 9px !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    color: #4a5568 !important;
    font-family: 'IBM Plex Mono', monospace !important;
}
[data-testid="stMetricValue"] {
    font-size: 20px !important;
    font-weight: 600 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    color: #f0f4ff !important;
}
[data-testid="stMetricDelta"] {
    font-size: 11px !important;
    font-family: 'IBM Plex Mono', monospace !important;
}

/* Headers */
h1, h2, h3 {
    font-family: 'IBM Plex Mono', monospace !important;
    color: #f0a500 !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
}
h1 { font-size: 14px !important; font-weight: 600 !important; }
h2 { font-size: 12px !important; font-weight: 500 !important; }
h3 { font-size: 11px !important; font-weight: 400 !important; color: #7a849a !important; }

/* Buttons */
.stButton button {
    background-color: #0d111a !important;
    color: #f0a500 !important;
    border: 1px solid #f0a500 !important;
    border-radius: 0 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 11px !important;
    letter-spacing: 1px !important;
    text-transform: uppercase !important;
    padding: 4px 16px !important;
}
.stButton button:hover {
    background-color: #1a1500 !important;
    border-color: #f0c040 !important;
}

/* Selectbox */
.stSelectbox > div > div {
    background-color: #0d111a !important;
    border: 1px solid #1e2736 !important;
    border-radius: 0 !important;
    color: #c8d0e0 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 12px !important;
}

/* DataFrames / Tables */
.stDataFrame {
    background-color: #0d111a !important;
    border: 1px solid #1e2736 !important;
}
.stDataFrame table {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 11px !important;
}
.stDataFrame thead th {
    background-color: #111827 !important;
    color: #f0a500 !important;
    font-size: 9px !important;
    letter-spacing: 1px !important;
    text-transform: uppercase !important;
    border-bottom: 1px solid #1e2736 !important;
}
.stDataFrame tbody td {
    color: #c8d0e0 !important;
    border-bottom: 1px solid #0f1420 !important;
}

/* Plotly charts background */
.js-plotly-plot .plotly .bg {
    fill: #0a0c10 !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background-color: #06080c !important;
    border-bottom: 1px solid #1e2736 !important;
    gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background-color: #06080c !important;
    color: #4a5568 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 10px !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    border-radius: 0 !important;
    padding: 6px 16px !important;
    border-right: 1px solid #1e2736 !important;
}
.stTabs [aria-selected="true"] {
    background-color: #0d111a !important;
    color: #f0a500 !important;
    border-bottom: 2px solid #f0a500 !important;
}

/* Sliders */
.stSlider > div > div > div {
    background-color: #f0a500 !important;
}

/* Number input */
.stNumberInput input {
    background-color: #0d111a !important;
    color: #c8d0e0 !important;
    border: 1px solid #1e2736 !important;
    border-radius: 0 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 12px !important;
}

/* Expander */
.streamlit-expanderHeader {
    background-color: #0d111a !important;
    color: #f0a500 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 10px !important;
    letter-spacing: 1px !important;
    text-transform: uppercase !important;
    border: 1px solid #1e2736 !important;
    border-radius: 0 !important;
}
.streamlit-expanderContent {
    background-color: #0a0c10 !important;
    border: 1px solid #1e2736 !important;
    border-top: none !important;
}

/* Progress bar */
.stProgress > div > div > div {
    background-color: #f0a500 !important;
}

/* Divider */
hr {
    border-color: #1e2736 !important;
    margin: 8px 0 !important;
}

/* Spinner */
.stSpinner > div {
    border-top-color: #f0a500 !important;
}

/* Scrollbars */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: #06080c; }
::-webkit-scrollbar-thumb { background: #1e2736; border-radius: 0; }
::-webkit-scrollbar-thumb:hover { background: #2e3a50; }

/* Remove Streamlit branding */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }
</style>
"""

# Reusable HTML components
def section_header(title, subtitle=None):
    sub = f'<div style="font-size:9px;color:#4a5568;letter-spacing:1px;margin-top:2px">{subtitle}</div>' if subtitle else ""
    return f"""
    <div style="border-bottom:1px solid #1e2736;padding-bottom:6px;margin-bottom:12px">
      <div style="font-family:\'IBM Plex Mono\',monospace;font-size:10px;font-weight:600;
                  color:#f0a500;letter-spacing:2px;text-transform:uppercase">{title}</div>
      {sub}
    </div>
    """

def stat_box(label, value, color="#f0f4ff", sub=None):
    sub_html = f'<div style="font-size:9px;color:#4a5568;margin-top:1px">{sub}</div>' if sub else ""
    return f"""
    <div style="background:#0d111a;border:1px solid #1e2736;padding:10px 14px;margin-bottom:4px">
      <div style="font-family:\'IBM Plex Mono\',monospace;font-size:9px;color:#4a5568;
                  text-transform:uppercase;letter-spacing:1px;margin-bottom:3px">{label}</div>
      <div style="font-family:\'IBM Plex Mono\',monospace;font-size:18px;font-weight:600;
                  color:{color}">{value}</div>
      {sub_html}
    </div>
    """

def signal_card(sig, score, sizing=None):
    dir_color = "#26d17a" if sig.direction == "long" else "#e05555"
    dir_bg    = "#0a2818" if sig.direction == "long" else "#280a0a"
    dir_label = "▲ LONG" if sig.direction == "long" else "▼ SHORT"
    lots_str  = f"  {sizing['lots']:.2f} lots  ${sizing['risk_usd']:.0f} risk" if sizing else ""
    bar_w     = int(score * 10)
    return f"""
    <div style="background:#0d111a;border:1px solid #1e2736;border-left:2px solid {dir_color};
                padding:10px 12px;margin-bottom:6px;font-family:\'IBM Plex Mono\',monospace">
      <div style="display:flex;justify-content:space-between;margin-bottom:5px">
        <span style="background:{dir_bg};color:{dir_color};border:1px solid {dir_color};
                     font-size:10px;font-weight:600;padding:1px 8px">{dir_label}</span>
        <span style="font-size:10px;color:#7a849a;text-transform:uppercase;letter-spacing:1px">
          {sig.strategy.replace('_',' ')}
        </span>
        <span style="font-size:12px;font-weight:600;color:#f0a500">{score}/10</span>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;font-size:11px;margin-bottom:5px">
        <div>
          <div style="color:#4a5568;font-size:8px;text-transform:uppercase">Entry</div>
          <div style="color:#f0f4ff;font-weight:500">{sig.entry:.2f}</div>
        </div>
        <div>
          <div style="color:#4a5568;font-size:8px;text-transform:uppercase">SL</div>
          <div style="color:#e05555;font-weight:500">{sig.sl:.2f}</div>
        </div>
        <div>
          <div style="color:#4a5568;font-size:8px;text-transform:uppercase">TP</div>
          <div style="color:#26d17a;font-weight:500">{sig.tp:.2f}</div>
        </div>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:10px;color:#4a5568">
        <span>R:R <span style="color:#c8d0e0">{sig.rr:.1f}</span></span>
        <span>TF <span style="color:#c8d0e0">{sig.timeframe}</span></span>
        <span style="color:#7a849a">{lots_str}</span>
      </div>
      <div style="height:2px;background:#1e2736;margin-top:6px;border-radius:1px">
        <div style="height:2px;width:{bar_w}%;background:#f0a500;border-radius:1px"></div>
      </div>
    </div>
    """

def live_price_bar(price, change, change_pct, session, regime, atr, adx, rsi, utc_time):
    p_color = "#26d17a" if change >= 0 else "#e05555"
    arrow   = "▲" if change >= 0 else "▼"
    return f"""
    <div style="background:#0d111a;border:1px solid #1e2736;border-top:1px solid #f0a500;
                padding:10px 16px;margin-bottom:12px;font-family:\'IBM Plex Mono\',monospace">
      <div style="display:grid;grid-template-columns:auto 1fr repeat(6,auto);gap:24px;align-items:center">
        <div>
          <div style="font-size:8px;color:#4a5568;letter-spacing:1px;text-transform:uppercase">XAUUSD</div>
          <div style="font-size:28px;font-weight:600;color:#f0f4ff;line-height:1">{price:,.2f}</div>
          <div style="font-size:12px;color:{p_color}">{arrow} {abs(change):.2f} ({change_pct:+.2f}%)</div>
        </div>
        <div></div>
        <div style="text-align:right">
          <div style="font-size:8px;color:#4a5568;letter-spacing:1px">SESSION</div>
          <div style="font-size:13px;color:#4da8f0;font-weight:500">{session.upper()}</div>
        </div>
        <div style="text-align:right">
          <div style="font-size:8px;color:#4a5568;letter-spacing:1px">REGIME</div>
          <div style="font-size:11px;color:#f0a500;font-weight:500">{regime}</div>
        </div>
        <div style="text-align:right">
          <div style="font-size:8px;color:#4a5568;letter-spacing:1px">ATR(14)</div>
          <div style="font-size:13px;color:#c8d0e0">{atr:.1f}</div>
        </div>
        <div style="text-align:right">
          <div style="font-size:8px;color:#4a5568;letter-spacing:1px">ADX(14)</div>
          <div style="font-size:13px;color:{'#26d17a' if adx>25 else '#c8d0e0'}">{adx:.1f}</div>
        </div>
        <div style="text-align:right">
          <div style="font-size:8px;color:#4a5568;letter-spacing:1px">RSI(14)</div>
          <div style="font-size:13px;color:{'#e05555' if rsi>70 else '#26d17a' if rsi<30 else '#c8d0e0'}">{rsi:.1f}</div>
        </div>
        <div style="text-align:right">
          <div style="font-size:8px;color:#4a5568;letter-spacing:1px">UTC</div>
          <div style="font-size:12px;color:#4a5568">{utc_time}</div>
        </div>
      </div>
    </div>
    """

def status_footer(data_ok, wfo_ok, tg_ok, db_ok, next_cycle_secs=None):
    def dot(ok):
        color = "#26d17a" if ok else "#e05555"
        return f'<span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:{color};margin-right:4px"></span>'
    cycle = f"NEXT CYCLE: {next_cycle_secs//60}:{next_cycle_secs%60:02d}" if next_cycle_secs else ""
    return f"""
    <div style="display:flex;gap:20px;align-items:center;padding:6px 0;
                border-top:1px solid #1e2736;font-family:\'IBM Plex Mono\',monospace;
                font-size:9px;color:#4a5568;margin-top:8px;flex-wrap:wrap">
      <span>{dot(data_ok)}DATA FEED</span>
      <span>{dot(wfo_ok)}WFO ENGINE</span>
      <span>{dot(tg_ok)}TELEGRAM</span>
      <span>{dot(db_ok)}DATABASE</span>
      {"<span style='margin-left:auto;color:#f0a500'>" + cycle + "</span>" if cycle else ""}
    </div>
    """
