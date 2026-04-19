"""
FX Trading Assistant — Full Edition
Multi-pair scanner · Signal expiry · Platform mockups · Screenshot confirmation
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time, datetime, subprocess, platform, io, base64
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── platform guards ──────────────────────────────────────────────────────────
IS_MAC = platform.system() == "Darwin"
try:
    import mss as _mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

try:
    import ollama as _ollama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False

try:
    from PIL import Image as _PIL
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import kaleido  # noqa
    HAS_KALEIDO = True
except Exception:
    HAS_KALEIDO = False

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FX Pro Trader",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── global CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
  html,body,[class*="css"]{ font-family:'Inter',sans-serif; }
  .stApp{ background:#0a0e1a; color:#e2e8f0; }
  .stTabs [data-baseweb="tab-list"]{ gap:4px; background:#111827; padding:6px; border-radius:12px; }
  .stTabs [data-baseweb="tab"]{ border-radius:8px; padding:8px 20px; color:#94a3b8; font-weight:500; }
  .stTabs [aria-selected="true"]{ background:linear-gradient(135deg,#3b82f6,#8b5cf6)!important; color:#fff!important; }
  .sig-buy{background:linear-gradient(135deg,#064e3b,#065f46);border:1px solid #10b981;border-radius:14px;padding:16px 20px;margin:6px 0;}
  .sig-sell{background:linear-gradient(135deg,#4c0519,#881337);border:1px solid #f43f5e;border-radius:14px;padding:16px 20px;margin:6px 0;}
  .sig-wait{background:linear-gradient(135deg,#1e1b4b,#2e1065);border:1px solid #6366f1;border-radius:14px;padding:16px 20px;margin:6px 0;}
  .sig-scan{background:linear-gradient(135deg,#1c1917,#292524);border:1px solid #78716c;border-radius:14px;padding:16px 20px;margin:6px 0;animation:pulse 1.5s infinite;}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.6}}
  .metric-box{background:#111827;border:1px solid #1f2937;border-radius:12px;padding:14px 18px;text-align:center;}
  .metric-val{font-size:1.6rem;font-weight:700;}
  .metric-lbl{font-size:.75rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em;}
  .cd-badge{display:inline-block;background:#1f2937;border:1px solid #374151;border-radius:20px;padding:3px 12px;font-size:.78rem;color:#94a3b8;}
  .mt4-header{background:#1a237e;color:#fff;padding:8px 14px;border-radius:8px 8px 0 0;font-size:.85rem;font-weight:600;}
  .tv-header{background:#131722;color:#b2b5be;padding:8px 14px;border-radius:8px 8px 0 0;font-size:.85rem;font-weight:600;}
  .ig-header{background:#0e4c8a;color:#fff;padding:8px 14px;border-radius:8px 8px 0 0;font-size:.85rem;font-weight:600;}
  .confirm-ok{background:#052e16;border:2px solid #22c55e;border-radius:12px;padding:18px;margin:12px 0;}
  .confirm-fail{background:#450a0a;border:2px solid #ef4444;border-radius:12px;padding:18px;margin:12px 0;}
  ::-webkit-scrollbar{width:6px;height:6px}
  ::-webkit-scrollbar-track{background:#111827}
  ::-webkit-scrollbar-thumb{background:#374151;border-radius:3px}
</style>
""", unsafe_allow_html=True)

# ── constants ────────────────────────────────────────────────────────────────
PAIRS = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "GBP/JPY": "GBPJPY=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "USDCAD=X",
    "USD/CHF": "USDCHF=X",
    "NZD/USD": "NZDUSD=X",
    "EUR/GBP": "EURGBP=X",
    "EUR/JPY": "EURJPY=X",
}

TIMEFRAMES = {
    "1-min  (scalping)":      ("1m",  "5d",  60),
    "5-min  ✦ recommended":   ("5m",  "5d", 300),
    "15-min (swing prep)":    ("15m", "5d", 900),
    "1-hour (swing)":         ("1h", "30d", 3600),
}

LEVERAGE_MAP = {
    "No leverage (1:1)":  1,
    "Low  (1:10)":       10,
    "Medium (1:30)":     30,
    "High  (1:100)":    100,
    "Very high (1:500)":500,
}

TP_PIPS = {"Conservative (20 pips)": 20, "Standard (35 pips)": 35, "Aggressive (60 pips)": 60}
SL_PIPS = {"Tight (15 pips)": 15, "Standard (25 pips)": 25, "Wide (40 pips)": 40}

# ── session state ─────────────────────────────────────────────────────────────
for _k, _v in [("signals", {}), ("scan_running", False),
               ("last_scan", 0), ("selected_pair", "EUR/USD")]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── helpers ───────────────────────────────────────────────────────────────────
def pip_size(sym: str) -> float:
    return 0.01 if "JPY" in sym else 0.0001

def calc_profit(amount_gbp: float, leverage: int, pips: float, pip_s: float, price: float) -> float:
    pos = amount_gbp * leverage
    if pip_s == 0.01:
        return pos * pips * pip_s / price
    return pos * pips * pip_s

def speak(key: str, text: str):
    if not IS_MAC:
        return
    if text != st.session_state.get(f"_spoken_{key}", ""):
        st.session_state[f"_spoken_{key}"] = text
        try:
            subprocess.Popen(["say", "-r", "185", text],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        except Exception:
            pass

def fmt_countdown(issued_at: float, valid_secs: int) -> str:
    rem = max(0, valid_secs - (time.time() - issued_at))
    if rem == 0:
        return "⏰ EXPIRED"
    m, s = divmod(int(rem), 60)
    return f"⏱ {m}m {s:02d}s left" if m else f"⏱ {s}s left"

def is_expired(issued_at: float, valid_secs: int) -> bool:
    return (time.time() - issued_at) >= valid_secs

# ── data fetch ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def fetch_data(yf_sym: str, interval: str, period: str):
    try:
        df = yf.download(yf_sym, interval=interval, period=period,
                         auto_adjust=True, progress=False)
        if df.empty or len(df) < 30:
            return None
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        return df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    except Exception:
        return None

# ── signal scoring ────────────────────────────────────────────────────────────
def score_pair(df: pd.DataFrame, sym: str):
    c, h, lo = df["Close"], df["High"], df["Low"]
    score = 0

    # RSI
    delta = c.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rsi   = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    rsi_v = float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else 50
    if rsi_v < 35:   score += 3
    elif rsi_v < 45: score += 1
    elif rsi_v > 65: score -= 3
    elif rsi_v > 55: score -= 1

    # MACD
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    macd  = ema12 - ema26
    sig9  = macd.ewm(span=9, adjust=False).mean()
    if len(macd) >= 2:
        if   macd.iloc[-1] > sig9.iloc[-1] and macd.iloc[-2] <= sig9.iloc[-2]: score += 3
        elif macd.iloc[-1] < sig9.iloc[-1] and macd.iloc[-2] >= sig9.iloc[-2]: score -= 3
        elif macd.iloc[-1] > sig9.iloc[-1]: score += 1
        else: score -= 1

    # Bollinger Bands
    sma20 = c.rolling(20).mean()
    std20 = c.rolling(20).std()
    b_up  = sma20 + 2*std20
    b_dn  = sma20 - 2*std20
    price = float(c.iloc[-1])
    if float(b_dn.iloc[-1]) > 0 and price <= float(b_dn.iloc[-1]): score += 2
    elif float(b_up.iloc[-1]) > 0 and price >= float(b_up.iloc[-1]): score -= 2

    # EMA trend
    ema20  = float(c.ewm(span=20,  adjust=False).mean().iloc[-1])
    ema50  = float(c.ewm(span=50,  adjust=False).mean().iloc[-1])
    ema200 = float(c.ewm(span=200, adjust=False).mean().iloc[-1])
    if ema20 > ema50 > ema200:  score += 2
    elif ema20 < ema50 < ema200: score -= 2

    # Stochastic
    low14  = lo.rolling(14).min()
    high14 = h.rolling(14).max()
    k_v    = float(100 * (c - low14) / (high14 - low14).replace(0, np.nan)).iloc[-1] if True else 50
    try:
        k_v = float((100 * (c - low14) / (high14 - low14).replace(0, np.nan)).iloc[-1])
    except Exception:
        k_v = 50
    if k_v < 25:   score += 1
    elif k_v > 75: score -= 1

    score = max(-10, min(10, score))

    # ATR for dynamic TP/SL
    tr = pd.concat([
        h - lo,
        (h - c.shift()).abs(),
        (lo - c.shift()).abs()
    ], axis=1).max(axis=1)
    atr      = float(tr.rolling(14).mean().iloc[-1])
    ps       = pip_size(sym)
    atr_pips = atr / ps
    tp_pips  = max(15, min(80, round(atr_pips * 1.5)))
    sl_pips  = max(10, min(50, round(atr_pips * 1.0)))

    if score >= 4:
        action = "BUY"
        tp = price + tp_pips * ps
        sl = price - sl_pips * ps
    elif score <= -4:
        action = "SELL"
        tp = price - tp_pips * ps
        sl = price + sl_pips * ps
    else:
        action = "WAIT"
        tp = price + tp_pips * ps
        sl = price - sl_pips * ps

    return action, score, price, tp, sl, tp_pips, sl_pips, rsi_v

def scan_one(pair_name, yf_sym, interval, period, valid_secs, tf_label):
    df = fetch_data(yf_sym, interval, period)
    if df is None:
        return pair_name, None
    action, score, entry, tp, sl, tp_pips, sl_pips, rsi_v = score_pair(df, pair_name)
    return pair_name, {
        "action": action, "score": score, "entry": entry,
        "tp": tp, "sl": sl, "tp_pips": tp_pips, "sl_pips": sl_pips,
        "rsi": rsi_v, "issued_at": time.time(), "valid_secs": valid_secs,
        "tf_label": tf_label, "df": df,
    }

# ── chart builder ─────────────────────────────────────────────────────────────
def build_chart(df, pair, action, entry, tp, sl, theme="generic"):
    themes = {
        "metatrader": dict(bg="#1a1a2e", grid="#16213e", up="#00e676", dn="#ff1744",
                           tp_c="#00e676", sl_c="#ff1744", entry_c="#ffea00", text_c="#e0e0e0"),
        "tradingview": dict(bg="#131722", grid="#1e222d", up="#26a69a", dn="#ef5350",
                            tp_c="#26a69a", sl_c="#ef5350", entry_c="#2962ff", text_c="#b2b5be"),
        "ig":          dict(bg="#f8f9fa", grid="#e9ecef", up="#00897b", dn="#e53935",
                            tp_c="#00897b", sl_c="#e53935", entry_c="#0d47a1", text_c="#212529"),
        "generic":     dict(bg="#0a0e1a", grid="#1f2937", up="#10b981", dn="#f43f5e",
                            tp_c="#10b981", sl_c="#f43f5e", entry_c="#fbbf24", text_c="#e2e8f0"),
    }
    t = themes.get(theme, themes["generic"])
    last = df.tail(60)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.78, 0.22], vertical_spacing=0.02)

    fig.add_trace(go.Candlestick(
        x=last.index, open=last["Open"], high=last["High"],
        low=last["Low"], close=last["Close"],
        increasing_fillcolor=t["up"], increasing_line_color=t["up"],
        decreasing_fillcolor=t["dn"], decreasing_line_color=t["dn"],
        name="Price"), row=1, col=1)

    x0, x1 = last.index[0], last.index[-1]
    for pv, clr, lbl, dash in [
        (tp,    t["tp_c"],    f"TP  {tp:.5f}",     "dash"),
        (sl,    t["sl_c"],    f"SL  {sl:.5f}",     "dash"),
        (entry, t["entry_c"], f"Entry {entry:.5f}", "dot"),
    ]:
        fig.add_shape(type="line", x0=x0, x1=x1, y0=pv, y1=pv,
                      line=dict(color=clr, width=2, dash=dash), row=1, col=1)
        fig.add_annotation(x=x1, y=pv, text=lbl, showarrow=False,
                           xanchor="right", font=dict(color=clr, size=11),
                           bgcolor=t["bg"], row=1, col=1)

    zone_c = "rgba(0,230,118,0.07)" if action == "BUY" else "rgba(255,23,68,0.07)"
    fig.add_shape(type="rect", x0=x0, x1=x1,
                  y0=min(sl, entry), y1=max(tp, entry),
                  fillcolor=zone_c, line_width=0, row=1, col=1)

    colors_vol = [t["up"] if c >= o else t["dn"]
                  for c, o in zip(last["Close"], last["Open"])]
    fig.add_trace(go.Bar(x=last.index, y=last["Volume"],
                         marker_color=colors_vol, showlegend=False), row=2, col=1)

    action_color = t["tp_c"] if action == "BUY" else (t["sl_c"] if action == "SELL" else t["entry_c"])
    fig.update_layout(
        title=dict(text=f"{pair}  ●  {action}", font=dict(color=action_color, size=16)),
        height=460, paper_bgcolor=t["bg"], plot_bgcolor=t["bg"],
        xaxis_rangeslider_visible=False,
        font=dict(color=t["text_c"], size=11),
        margin=dict(l=10, r=10, t=50, b=10),
    )
    for ax in ["xaxis", "xaxis2", "yaxis", "yaxis2"]:
        fig.update_layout(**{ax: dict(gridcolor=t["grid"], gridwidth=1,
                                      zerolinecolor=t["grid"],
                                      tickfont=dict(color=t["text_c"]))})
    return fig

# ── AI helpers ────────────────────────────────────────────────────────────────
def ai_confirm_screenshot(img_bytes, pair, action, entry, tp, sl):
    if not HAS_OLLAMA:
        return "⚠ Ollama not installed. Visit https://ollama.com to install it, then run: ollama pull moondream:latest"
    prompt = (
        f"The user uploaded a screenshot of their trading platform for {pair}. "
        f"Expected setup: {action} trade, Entry ≈ {entry:.5f}, "
        f"Take Profit ≈ {tp:.5f}, Stop Loss ≈ {sl:.5f}. "
        "Does this screenshot match? Are TP and SL lines visible and correct? "
        "If anything is wrong, say exactly what to fix. "
        "Start with ✅ CONFIRMED if correct, or ❌ NOT CORRECT if needs fixing."
    )
    try:
        import ollama
        resp = ollama.chat(
            model="moondream:latest",
            messages=[{"role": "user", "content": prompt, "images": [img_bytes]}])
        return resp["message"]["content"]
    except Exception as e:
        return f"⚠ Vision AI error: {e}"

# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────
col_l, col_r = st.columns([3, 1])
with col_l:
    st.markdown("## 📈 FX Pro Trader")
    st.markdown("<p style='color:#64748b;margin-top:-10px;font-size:.9rem;'>"
                "Live signals · Platform guides · Setup confirmation</p>",
                unsafe_allow_html=True)
with col_r:
    clock_ph = st.empty()

@st.fragment(run_every="1s")
def live_clock():
    clock_ph.markdown(
        f"<div style='text-align:right;color:#475569;font-size:.85rem;padding-top:10px;'>"
        f"{datetime.datetime.now().strftime('%H:%M:%S')} &nbsp;|&nbsp; "
        f"{datetime.datetime.now().strftime('%a %d %b %Y')}</div>",
        unsafe_allow_html=True)

live_clock()
st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# SETTINGS BAR
# ─────────────────────────────────────────────────────────────────────────────
with st.expander("⚙️  Settings", expanded=False):
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        tf_label = st.selectbox("Timeframe", list(TIMEFRAMES.keys()), index=1, key="tf_label")
    with s2:
        lev_label = st.selectbox("Leverage", list(LEVERAGE_MAP.keys()), index=2, key="lev_label")
    with s3:
        amt_gbp = st.number_input("Trade amount (£)", min_value=1.0, max_value=10000.0,
                                   value=20.0, step=5.0, key="amt_gbp")
    with s4:
        auto_rescan = st.toggle("Auto-rescan on expiry", value=True, key="auto_rescan")

tf_interval, tf_period, tf_valid = TIMEFRAMES[tf_label]
leverage = LEVERAGE_MAP[lev_label]

# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────
tab_scanner, tab_guide, tab_confirm = st.tabs([
    "🔍  Signal Scanner",
    "🖥️  Platform Trade Guide",
    "📸  Confirm My Setup",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — SIGNAL SCANNER
# ══════════════════════════════════════════════════════════════════════════════
with tab_scanner:
    st.markdown("### 🌐 All Pairs — Live Signals")
    st.markdown("<p style='color:#64748b;font-size:.85rem;'>Signals auto-expire when the candle window closes, "
                "then a fresh scan runs automatically.</p>", unsafe_allow_html=True)

    col_btn, col_status = st.columns([2, 3])
    with col_btn:
        do_scan = st.button("🔄  Scan All Pairs Now", use_container_width=True, type="primary")
    with col_status:
        status_ph = st.empty()

    st.markdown("")
    grid_ph = st.empty()

    @st.fragment(run_every=30)
    def scanner_fragment():
        now      = time.time()
        signals  = st.session_state.get("signals", {})
        rescan   = bool(do_scan)

        if st.session_state.get("auto_rescan", True):
            for sig in signals.values():
                if sig and is_expired(sig["issued_at"], sig["valid_secs"]):
                    rescan = True
                    break
            if not signals or (now - st.session_state.get("last_scan", 0)) > tf_valid:
                rescan = True

        if rescan:
            status_ph.info("🔍  Scanning all 10 pairs — please wait…")
            new_sigs = {}
            with ThreadPoolExecutor(max_workers=10) as ex:
                futs = {
                    ex.submit(scan_one, pn, ys, tf_interval, tf_period, tf_valid, tf_label): pn
                    for pn, ys in PAIRS.items()
                }
                for f in as_completed(futs):
                    pn, sig = f.result()
                    new_sigs[pn] = sig
            st.session_state["signals"] = new_sigs
            st.session_state["last_scan"] = now
            status_ph.empty()

        signals = st.session_state.get("signals", {})
        if not signals:
            grid_ph.info("Click **Scan All Pairs Now** to begin.")
            return

        def sort_key(item):
            _, s = item
            if s is None: return (2, 0)
            if s["action"] in ("BUY", "SELL"): return (0, -abs(s["score"]))
            return (1, -abs(s["score"]))

        sorted_sigs = sorted(signals.items(), key=sort_key)

        with grid_ph.container():
            cols = st.columns(2)
            for i, (pair, sig) in enumerate(sorted_sigs):
                with cols[i % 2]:
                    if sig is None:
                        st.markdown(
                            f'<div class="sig-scan"><b>{pair}</b><br>'
                            f'<span style="color:#78716c">⚠ No data available</span></div>',
                            unsafe_allow_html=True)
                        continue

                    expired = is_expired(sig["issued_at"], sig["valid_secs"])
                    cd      = "🔄 RESCANNING…" if expired else fmt_countdown(sig["issued_at"], sig["valid_secs"])
                    action  = sig["action"]
                    cls     = {"BUY": "sig-buy", "SELL": "sig-sell"}.get(action, "sig-wait") if not expired else "sig-scan"
                    icon    = {"BUY": "🟢", "SELL": "🔴"}.get(action, "🟡")
                    bar     = "▓" * abs(sig["score"]) + "░" * (10 - abs(sig["score"]))
                    ps      = pip_size(pair)
                    profit  = calc_profit(amt_gbp, leverage, sig["tp_pips"], ps, sig["entry"])
                    loss_v  = calc_profit(amt_gbp, leverage, sig["sl_pips"], ps, sig["entry"])

                    st.markdown(f"""
<div class="{cls}">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
    <span style="font-size:1.05rem;font-weight:700;">{icon} {pair}</span>
    <span class="cd-badge">{cd}</span>
  </div>
  <div style="font-size:1.7rem;font-weight:800;letter-spacing:.05em;">{action}</div>
  <div style="font-size:.78rem;color:#94a3b8;margin:4px 0;">
    Signal strength: <code>{bar}</code> {sig['score']:+d}/10
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-top:8px;font-size:.82rem;">
    <div><span style="color:#64748b">Entry</span><br><b>{sig['entry']:.5f}</b></div>
    <div><span style="color:#10b981">Take Profit</span><br><b>{sig['tp']:.5f}</b>
         <br><span style="color:#10b981;font-size:.75rem">+{sig['tp_pips']} pips</span></div>
    <div><span style="color:#f43f5e">Stop Loss</span><br><b>{sig['sl']:.5f}</b>
         <br><span style="color:#f43f5e;font-size:.75rem">-{sig['sl_pips']} pips</span></div>
  </div>
  <div style="margin-top:10px;display:flex;gap:12px;font-size:.82rem;">
    <span>💰 Win: <b style="color:#10b981">£{profit:.2f}</b></span>
    <span>💸 Lose: <b style="color:#f43f5e">-£{loss_v:.2f}</b></span>
    <span>📊 RSI: {sig['rsi']:.0f}</span>
  </div>
</div>""", unsafe_allow_html=True)

                    if action in ("BUY", "SELL") and not expired:
                        speak(f"{pair}_{sig['issued_at']:.0f}",
                              f"{pair.replace('/', ' ')} — {action} now!")

    scanner_fragment()

    # ── deep-dive ─────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🔎 Pair Deep-Dive")
    detail_pair = st.selectbox("Choose a pair to inspect", list(PAIRS.keys()), key="detail_pair")
    detail_ph   = st.empty()

    @st.fragment(run_every=60)
    def detail_fragment():
        sig = st.session_state.get("signals", {}).get(detail_pair)
        if sig is None:
            detail_ph.info("Run the scanner first to see this pair's signal.")
            return
        df = sig.get("df")
        if df is None or df.empty:
            detail_ph.warning("No chart data available.")
            return
        with detail_ph.container():
            fig = build_chart(df, detail_pair, sig["action"],
                              sig["entry"], sig["tp"], sig["sl"])
            st.plotly_chart(fig, use_container_width=True)

            m1, m2, m3, m4, m5 = st.columns(5)
            ps     = pip_size(detail_pair)
            profit = calc_profit(amt_gbp, leverage, sig["tp_pips"], ps, sig["entry"])
            loss_v = calc_profit(amt_gbp, leverage, sig["sl_pips"], ps, sig["entry"])
            rr     = profit / max(loss_v, 0.01)

            for col, val, lbl, clr in [
                (m1, sig["action"],     "Signal",      "#3b82f6"),
                (m2, f"{sig['score']:+d}/10", "Strength","#8b5cf6"),
                (m3, f"£{profit:.2f}", "If Win",       "#10b981"),
                (m4, f"-£{loss_v:.2f}","If Lose",      "#f43f5e"),
                (m5, f"{rr:.1f}:1",    "Risk/Reward",  "#fbbf24"),
            ]:
                col.markdown(
                    f'<div class="metric-box">'
                    f'<div class="metric-val" style="color:{clr}">{val}</div>'
                    f'<div class="metric-lbl">{lbl}</div></div>',
                    unsafe_allow_html=True)

    detail_fragment()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — PLATFORM TRADE GUIDE
# ══════════════════════════════════════════════════════════════════════════════
with tab_guide:
    st.markdown("### 🖥️ Platform Trade Guide")
    st.markdown("<p style='color:#64748b;font-size:.85rem;'>See exactly what your chart should look like "
                "on each platform, with step-by-step instructions.</p>", unsafe_allow_html=True)

    gp1, gp2, gp3 = st.columns(3)
    with gp1:
        guide_pair = st.selectbox("Pair", list(PAIRS.keys()), key="guide_pair")
    with gp2:
        tp_label = st.selectbox("Take Profit target", list(TP_PIPS.keys()), index=1, key="tp_label")
    with gp3:
        sl_label = st.selectbox("Stop Loss", list(SL_PIPS.keys()), index=1, key="sl_label")

    guide_ph = st.empty()

    @st.fragment(run_every=120)
    def guide_fragment():
        sig = st.session_state.get("signals", {}).get(guide_pair)
        if sig is None:
            guide_ph.info("⏳ Run the **Signal Scanner** tab first to get live data for this pair.")
            return
        df = sig.get("df")
        if df is None or df.empty:
            guide_ph.warning("No chart data for this pair yet.")
            return

        action = sig["action"]
        entry  = sig["entry"]
        tp_p   = TP_PIPS[tp_label]
        sl_p   = SL_PIPS[sl_label]
        ps     = pip_size(guide_pair)
        tp     = entry + tp_p*ps if action != "SELL" else entry - tp_p*ps
        sl     = entry - sl_p*ps if action != "SELL" else entry + sl_p*ps
        profit = calc_profit(amt_gbp, leverage, tp_p, ps, entry)
        loss_v = calc_profit(amt_gbp, leverage, sl_p, ps, entry)
        action_color = "#10b981" if action == "BUY" else ("#f43f5e" if action == "SELL" else "#fbbf24")

        with guide_ph.container():
            st.markdown(
                f"<div style='background:#111827;border:1px solid #1f2937;border-radius:12px;"
                f"padding:16px;margin-bottom:16px;'>"
                f"<b style='font-size:1.1rem;color:{action_color}'>{action} {guide_pair}</b>"
                f"&nbsp;&nbsp;|&nbsp;&nbsp;"
                f"Entry: <code>{entry:.5f}</code> &nbsp; "
                f"TP: <code style='color:#10b981'>{tp:.5f}</code> &nbsp; "
                f"SL: <code style='color:#f43f5e'>{sl:.5f}</code> &nbsp; "
                f"💰 Win: <b style='color:#10b981'>£{profit:.2f}</b> &nbsp; "
                f"💸 Lose: <b style='color:#f43f5e'>-£{loss_v:.2f}</b>"
                f"</div>",
                unsafe_allow_html=True)

            pt1, pt2, pt3 = st.tabs(["🟦 MetaTrader 4/5", "⬛ TradingView", "🔵 IG Broker"])

            # ── MetaTrader ──────────────────────────────────────────────────
            with pt1:
                st.markdown('<div class="mt4-header">MetaTrader 4 / 5  —  Annotated Chart Preview</div>',
                            unsafe_allow_html=True)
                fig_mt = build_chart(df, guide_pair, action, entry, tp, sl, theme="metatrader")
                fig_mt.update_layout(title=dict(
                    text=f"MetaTrader: {guide_pair}  {action}  |  TP {tp:.5f}  SL {sl:.5f}",
                    font=dict(color="#00e676", size=13)))
                st.plotly_chart(fig_mt, use_container_width=True, key="mt_chart")

                buy_sell_word = "Buy" if action == "BUY" else ("Sell" if action == "SELL" else "Wait — no clear signal")
                st.markdown(f"""
**📋 Step-by-step — MetaTrader 4 / 5:**

1. Open MetaTrader and find **{guide_pair}** in the *Market Watch* panel (press **Ctrl+M** if hidden).
2. Right-click the chart → **Timeframe** → select `{tf_interval.upper()}`.
3. Press **F9** (or click **New Order** in the toolbar) to open the order window.
4. Fill in:
   - **Type**: Market Execution
   - **Direction**: `{buy_sell_word}`
   - **Take Profit (TP)**: `{tp:.5f}` — type this exactly in the TP field
   - **Stop Loss (SL)**: `{sl:.5f}` — type this exactly in the SL field
5. Click the blue **{buy_sell_word} by Market** button.
6. Your trade appears in **Terminal → Trade** tab.

**📐 What your chart should look like:**
- 🟡 Dotted yellow line = your entry at `{entry:.5f}`
- 🟢 Dashed green line at `{tp:.5f}` = Take Profit — you collect **£{profit:.2f}** when price hits this
- 🔴 Dashed red line at `{sl:.5f}` = Stop Loss — you lose max **£{loss_v:.2f}** if price hits this
- Green shaded zone = profit area to reach TP
""")

            # ── TradingView ─────────────────────────────────────────────────
            with pt2:
                st.markdown('<div class="tv-header">TradingView  —  Annotated Chart Preview</div>',
                            unsafe_allow_html=True)
                fig_tv = build_chart(df, guide_pair, action, entry, tp, sl, theme="tradingview")
                fig_tv.update_layout(title=dict(
                    text=f"TradingView: {guide_pair}  {action}  |  TP {tp:.5f}  SL {sl:.5f}",
                    font=dict(color="#26a69a", size=13)))
                st.plotly_chart(fig_tv, use_container_width=True, key="tv_chart")

                st.markdown(f"""
**📋 Step-by-step — TradingView:**

1. Go to [tradingview.com](https://tradingview.com) and search **{guide_pair.replace('/','')}** in the top search bar.
2. Set the timeframe by clicking the interval buttons at the top → choose `{tf_interval.upper()}`.
3. To draw the trade on your chart, select the **Long/Short Position** tool from the left toolbar (or press **Shift+F**):
   - Click at entry price `{entry:.5f}`
   - Drag the TP line up to `{tp:.5f}` (for BUY) or down (for SELL)
   - The SL line auto-calculates — adjust to `{sl:.5f}`
4. To place a real trade (if your broker is connected via TV):
   - Click **Trading Panel** → **{"Buy" if action == "BUY" else "Sell" if action == "SELL" else "Wait"}**
   - Enter TP: `{tp:.5f}` and SL: `{sl:.5f}` in the order form
   - Click **Place Market Order**

**📐 What your chart should look like:**
- 🔵 Blue horizontal line = entry `{entry:.5f}`
- 🟢 Teal shaded zone above entry = profit area (target: `{tp:.5f}`)
- 🔴 Red shaded zone below entry = risk zone (limit: `{sl:.5f}`)
- Bottom left of the position tool shows: **Risk £{loss_v:.2f}  Reward £{profit:.2f}  R/R {profit/max(loss_v,0.01):.1f}:1**
""")

            # ── IG Broker ───────────────────────────────────────────────────
            with pt3:
                st.markdown('<div class="ig-header">IG Broker  —  Annotated Chart Preview</div>',
                            unsafe_allow_html=True)
                fig_ig = build_chart(df, guide_pair, action, entry, tp, sl, theme="ig")
                fig_ig.update_layout(title=dict(
                    text=f"IG: {guide_pair}  {action}  |  TP {tp:.5f}  SL {sl:.5f}",
                    font=dict(color="#0d47a1", size=13)))
                st.plotly_chart(fig_ig, use_container_width=True, key="ig_chart")

                st.markdown(f"""
**📋 Step-by-step — IG Broker:**

1. Log in to **IG Web** (web.ig.com) or the IG mobile app.
2. Search for **{guide_pair}** in the search box at the top.
3. Click **{"Buy" if action == "BUY" else "Sell" if action == "SELL" else "No trade yet — wait for a clearer signal"}** to open the deal ticket.
4. In the deal ticket, fill in:
   - **Order**: Market (executes immediately at current price near `{entry:.5f}`)
   - **Limit (Take Profit)**: `{tp:.5f}` — locks in your **£{profit:.2f}** gain
   - **Stop (Stop Loss)**: `{sl:.5f}` — limits your loss to **£{loss_v:.2f}**
   - **Size**: based on your £{amt_gbp:.0f} at {leverage}x leverage
5. Click **Place deal** and confirm.
6. Your trade appears in **My IG → Positions**.

**📐 What it should look like on IG:**
- Deal ticket: green **Limit** field showing `{tp:.5f}`
- Deal ticket: red **Stop** field showing `{sl:.5f}`
- On the IG chart: two horizontal lines — green above (TP) and red below (SL) entry
- **💡 IG tip:** IG also shows distances in pips — your TP is **{tp_p} pips** away and SL is **{sl_p} pips** away.
""")

    guide_fragment()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — CONFIRM MY SETUP
# ══════════════════════════════════════════════════════════════════════════════
with tab_confirm:
    st.markdown("### 📸 Confirm My Setup")
    st.markdown("<p style='color:#64748b;font-size:.85rem;'>"
                "Upload a screenshot of your platform. AI checks if TP/SL match the signal.</p>",
                unsafe_allow_html=True)

    cc1, cc2 = st.columns(2)
    with cc1:
        confirm_pair = st.selectbox("Which pair?", list(PAIRS.keys()), key="confirm_pair")
    with cc2:
        confirm_platform = st.selectbox("Which platform?",
                                        ["MetaTrader 4/5", "TradingView", "IG Broker"],
                                        key="confirm_platform")

    uploaded = st.file_uploader(
        "📤 Drop your screenshot here (PNG or JPG)",
        type=["png", "jpg", "jpeg"],
        key="screenshot_upload")

    if uploaded:
        img_bytes = uploaded.read()
        st.image(img_bytes, caption="Your uploaded screenshot", use_column_width=True)

        sig_c = st.session_state.get("signals", {}).get(confirm_pair)
        if sig_c is None:
            st.info("⏳ Please run the **Signal Scanner** first so I know what values to check against.")
        else:
            action = sig_c["action"]
            entry  = sig_c["entry"]
            tp_p   = TP_PIPS.get(st.session_state.get("tp_label", "Standard (35 pips)"), 35)
            sl_p   = SL_PIPS.get(st.session_state.get("sl_label", "Standard (25 pips)"), 25)
            ps     = pip_size(confirm_pair)
            tp     = entry + tp_p*ps if action != "SELL" else entry - tp_p*ps
            sl     = entry - sl_p*ps if action != "SELL" else entry + sl_p*ps

            st.markdown(
                f"**Expected:** {action} `{confirm_pair}` | "
                f"Entry `{entry:.5f}` | TP `{tp:.5f}` | SL `{sl:.5f}`")

            if st.button("🤖  Check My Screenshot with AI", type="primary"):
                if not HAS_OLLAMA:
                    st.error(
                        "⚠ Ollama is not installed on this machine. "
                        "The screenshot checker uses local AI and needs Ollama running. "
                        "Install from https://ollama.com then run: `ollama pull moondream:latest`")
                else:
                    with st.spinner("🔍 AI is reading your screenshot…"):
                        result = ai_confirm_screenshot(img_bytes, confirm_pair,
                                                       action, entry, tp, sl)

                    confirmed = (
                        "✅" in result or
                        "confirmed" in result.lower() or
                        ("correct" in result.lower() and "not correct" not in result.lower())
                    )
                    if confirmed:
                        st.markdown(
                            f'<div class="confirm-ok">✅ <b>CONFIRMED — looks correct!</b><br><br>{result}</div>',
                            unsafe_allow_html=True)
                        st.success("🎉 Your setup matches! Go ahead and execute the trade.")
                    else:
                        st.markdown(
                            f'<div class="confirm-fail">❌ <b>NOT QUITE — please adjust</b><br><br>{result}</div>',
                            unsafe_allow_html=True)
                        st.warning("⚠ Fix the highlighted issues before trading.")
    else:
        st.markdown("""
<div style="background:#111827;border:1px solid #1f2937;border-radius:12px;padding:20px;margin-top:8px;">

**How to use this tab:**

1. Go to the **Platform Trade Guide** tab — note the exact TP and SL values.
2. Open your trading platform (MetaTrader / TradingView / IG) and set up the trade exactly as shown.
3. Take a screenshot:
   - **Mac**: Press **Cmd + Shift + 4** then drag to capture the chart
   - **Windows**: Press **Win + Shift + S** then drag to capture
4. Upload it above and click **Check My Screenshot with AI**.
5. The AI reads your screenshot and tells you:
   - ✅ **CONFIRMED** — setup is correct, execute the trade
   - ❌ **NOT CORRECT** — exactly what needs adjusting

**Why bother?** One misplaced TP or SL turns a winning trade into a loss. This check takes 10 seconds.
</div>
""", unsafe_allow_html=True)

    # manual checklist
    st.markdown("---")
    st.markdown("#### ✅ Quick Manual Checklist")
    sig_m = st.session_state.get("signals", {}).get(confirm_pair)
    if sig_m:
        ps_m   = pip_size(confirm_pair)
        tp_p_m = TP_PIPS.get(st.session_state.get("tp_label","Standard (35 pips)"), 35)
        sl_p_m = SL_PIPS.get(st.session_state.get("sl_label","Standard (25 pips)"), 25)
        tp_m   = sig_m["entry"] + tp_p_m*ps_m if sig_m["action"] != "SELL" else sig_m["entry"] - tp_p_m*ps_m
        sl_m   = sig_m["entry"] - sl_p_m*ps_m if sig_m["action"] != "SELL" else sig_m["entry"] + sl_p_m*ps_m
        checks = [
            f"Correct pair selected: **{confirm_pair}**",
            f"Direction is **{sig_m['action']}**",
            f"Entry price near **{sig_m['entry']:.5f}**",
            f"Take Profit set to **{tp_m:.5f}** (+{tp_p_m} pips)",
            f"Stop Loss set to **{sl_m:.5f}** (-{sl_p_m} pips)",
            f"Timeframe set to **{tf_interval.upper()}**",
        ]
        for j, label in enumerate(checks):
            st.checkbox(label, key=f"chk_{j}")
    else:
        st.info("Run the scanner first to generate expected values for this pair.")


# ─────────────────────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<p style='text-align:center;color:#374151;font-size:.8rem;'>"
    "FX Pro Trader · Live data via yfinance · AI via Ollama (local, free) · "
    "Not financial advice — always manage your risk</p>",
    unsafe_allow_html=True)
