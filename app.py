"""
FX Trading Assistant — Plain English, Beginner Friendly
Tells you exactly when to BUY, when to SELL, and how much profit to expect.
No trading knowledge needed.
Deployable on Streamlit Community Cloud — free, public, no API key.
"""
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, EMAIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime, time, subprocess, io, base64, sys, platform, re

st.set_page_config(page_title="FX Trading Assistant", layout="centered", page_icon="💰")

# ── optional imports (not available on cloud) ─────────────────────────────────
try:
    import mss
    from PIL import Image
    SCREEN_CAPTURE = True
except ImportError:
    SCREEN_CAPTURE = False

def get_ollama_models():
    try:
        import ollama
        return [m.model for m in ollama.list().models]
    except Exception:
        return []

IS_MAC = platform.system() == "Darwin"

# ── session state ─────────────────────────────────────────────────────────────
for k, v in [
    ("watching", False), ("last_action", ""), ("last_spoken", ""),
    ("trade_log", []), ("screen_img", None), ("screen_verdict", ""),
    ("ai_watch_result", None), ("ai_chart_bytes", None),
    ("last_ai_spoken", ""),
]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── constants ─────────────────────────────────────────────────────────────────
PAIRS = {
    "Euro / US Dollar (EUR/USD)":          "EURUSD=X",
    "British Pound / Dollar (GBP/USD)":    "GBPUSD=X",
    "Dollar / Japanese Yen (USD/JPY)":     "USDJPY=X",
    "Australian Dollar / USD (AUD/USD)":   "AUDUSD=X",
    "Dollar / Canadian Dollar (USD/CAD)":  "USDCAD=X",
    "Dollar / Swiss Franc (USD/CHF)":      "USDCHF=X",
    "Euro / British Pound (EUR/GBP)":      "EURGBP=X",
    "Euro / Yen (EUR/JPY)":                "EURJPY=X",
    "Pound / Yen (GBP/JPY)":              "GBPJPY=X",
    "New Zealand Dollar / USD (NZD/USD)":  "NZDUSD=X",
}

CHECK_EVERY = {
    "Every 1 minute":   (60_000,   "1m",  "5d"),
    "Every 5 minutes":  (300_000,  "5m",  "5d"),
    "Every 15 minutes": (900_000,  "15m", "5d"),
    "Every 1 hour":     (3_600_000,"1h",  "30d"),
}

def pip_size(symbol: str) -> float:
    return 0.01 if "JPY" in symbol else 0.0001

def speak(text: str):
    if not IS_MAC:
        return
    if text != st.session_state["last_spoken"]:
        subprocess.Popen(["say", "-r", "185", text],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        st.session_state["last_spoken"] = text

# ── Styles ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.plain-text {
    font-size: 1.15rem; line-height: 1.8; color: #eceff1;
    background: #1e272e; border-radius: 12px; padding: 18px 22px; margin: 12px 0;
}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## 💰 FX Trading Assistant")
st.markdown("*I watch the market for you and tell you exactly **when to buy** and **when to sell**.*")
st.markdown("---")

# ── Settings ──────────────────────────────────────────────────────────────────
col1, col2 = st.columns(2)
with col1:
    pair_label  = st.selectbox("Which currency pair?", list(PAIRS.keys()), index=0)
with col2:
    check_label = st.selectbox("How often should I check?", list(CHECK_EVERY.keys()), index=1)

ticker_sym                    = PAIRS[pair_label]
refresh_ms, interval, period  = CHECK_EVERY[check_label]
pip                           = pip_size(ticker_sym)
short_name                    = pair_label.split("(")[-1].replace(")","").strip()

# ── Controls ──────────────────────────────────────────────────────────────────
bc1, bc2, bc3 = st.columns([2, 2, 1])
with bc1:
    if not st.session_state["watching"]:
        if st.button("▶  Start Watching for Me", use_container_width=True, type="primary"):
            st.session_state["watching"] = True
            st.rerun()
    else:
        if st.button("⏹  Stop Watching", use_container_width=True):
            st.session_state["watching"] = False
            st.rerun()
with bc2:
    if st.button("🔍  Check Right Now", use_container_width=True):
        st.cache_data.clear()
        st.session_state["force_check"] = True
with bc3:
    voice_on = st.toggle("🔊", value=True, help="Voice alerts (Mac only)")

if st.session_state["watching"]:
    st_autorefresh(interval=refresh_ms, key="watcher")

# ── Fetch data ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=max(30, refresh_ms // 1000))
def get_data(symbol, interval, period, _ts):
    for _ in range(3):
        try:
            df = yf.download(symbol, interval=interval, period=period,
                             auto_adjust=True, progress=False)
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            df.dropna(inplace=True)
            if not df.empty:
                return df
        except Exception:
            time.sleep(1)
    return pd.DataFrame()

cache_ts = int(time.time() * 1000) // refresh_ms

with st.spinner("Checking the market…"):
    df = get_data(ticker_sym, interval, period, cache_ts)

if df.empty:
    st.error("Couldn't get market data right now. I'll try again shortly.")
    st.stop()

# ── Compute indicators ────────────────────────────────────────────────────────
cl, hi, lo = df["Close"], df["High"], df["Low"]
df = df.copy()
df["RSI"]      = RSIIndicator(cl, 14).rsi()
macd_obj       = MACD(cl, 26, 12, 9)
df["MACD"]     = macd_obj.macd()
df["MACD_sig"] = macd_obj.macd_signal()
df["MACD_hist"]= macd_obj.macd_diff()
bb             = BollingerBands(cl, 20, 2)
df["BB_upper"] = bb.bollinger_hband()
df["BB_lower"] = bb.bollinger_lband()
df["EMA20"]    = EMAIndicator(cl, 20).ema_indicator()
df["EMA50"]    = EMAIndicator(cl, 50).ema_indicator()
df["ATR"]      = AverageTrueRange(hi, lo, cl, 14).average_true_range()
st_obj         = StochasticOscillator(hi, lo, cl, 14, 3)
df["StochK"]   = st_obj.stoch()

# ── Signal scoring ────────────────────────────────────────────────────────────
def compute_signal(df):
    last = df.iloc[-1]; prev = df.iloc[-2]
    score = 0; reasons = []

    rsi = float(last["RSI"])
    if rsi < 32:
        score += 3; reasons.append("the market is oversold and likely to bounce back up")
    elif rsi > 68:
        score -= 3; reasons.append("the market is overbought and likely to drop")
    elif rsi < 48:
        score += 1
    elif rsi > 52:
        score -= 1

    if (float(prev["MACD"]) < float(prev["MACD_sig"]) and
            float(last["MACD"]) > float(last["MACD_sig"])):
        score += 3; reasons.append("momentum just flipped upward — a common buy signal")
    elif (float(prev["MACD"]) > float(prev["MACD_sig"]) and
            float(last["MACD"]) < float(last["MACD_sig"])):
        score -= 3; reasons.append("momentum just flipped downward — a common sell signal")
    elif float(last["MACD_hist"]) > 0:
        score += 1
    else:
        score -= 1

    cp = float(last["Close"])
    if cp < float(last["BB_lower"]):
        score += 2; reasons.append("the price just hit a historically low zone and tends to bounce")
    elif cp > float(last["BB_upper"]):
        score -= 2; reasons.append("the price just hit a historically high zone and tends to drop")

    if float(last["EMA20"]) > float(last["EMA50"]):
        score += 1.5; reasons.append("the short-term trend is pointing upward")
    else:
        score -= 1.5; reasons.append("the short-term trend is pointing downward")

    sk = float(last["StochK"])
    if sk < 22:
        score += 1.5; reasons.append("the price is in a deep low zone — buyers often step in here")
    elif sk > 78:
        score -= 1.5; reasons.append("the price is in a high zone where sellers usually come in")

    return score, reasons, cp, float(last["ATR"])

score, reasons, current_price, atr = compute_signal(df)

# ── Decision ──────────────────────────────────────────────────────────────────
if score >= 4.0:
    action      = "BUY"
    take_profit = round(current_price + 2.5 * atr, 5)
    stop_loss   = round(current_price - 1.2 * atr, 5)
    pips_profit = round((take_profit - current_price) / pip)
    pips_risk   = round((current_price - stop_loss) / pip)
elif score <= -4.0:
    action      = "SELL"
    take_profit = round(current_price - 2.5 * atr, 5)
    stop_loss   = round(current_price + 1.2 * atr, 5)
    pips_profit = round((current_price - take_profit) / pip)
    pips_risk   = round((stop_loss - current_price) / pip)
else:
    action      = "WAIT"
    take_profit = None
    stop_loss   = round(current_price - 1.2 * atr, 5)
    pips_profit = 0
    pips_risk   = 0

# ── Plain-English explanation ─────────────────────────────────────────────────
def plain_english(action, short_name, price, tp, sl, pp, pr, reasons):
    top = reasons[:3]
    why = ", ".join(top) if top else "the signals are mixed right now"
    if action == "BUY":
        return (
            f"✅ **Right now is a good time to BUY {short_name}.**\n\n"
            f"The price is at **{price:.5f}** and my signals show the price is likely going **UP** because {why}.\n\n"
            f"**Here is exactly what to do:**\n"
            f"- 🟢 **BUY** {short_name} at **{price:.5f}**\n"
            f"- 💰 **Close the trade (take your profit)** when the price reaches **{tp:.5f}** "
            f"— that's **+{pp} pips** of profit\n"
            f"- 🛑 **Close the trade immediately (cut your loss)** if the price drops to **{sl:.5f}** "
            f"— that keeps your loss to just {pr} pips\n\n"
            f"I'm watching every {check_label.lower().replace('every ','')} and will tell you when to close."
        )
    elif action == "SELL":
        return (
            f"🔴 **Right now is a good time to SELL {short_name}.**\n\n"
            f"The price is at **{price:.5f}** and my signals show the price is likely going **DOWN** because {why}.\n\n"
            f"**Here is exactly what to do:**\n"
            f"- 🔴 **SELL** {short_name} at **{price:.5f}**\n"
            f"- 💰 **Close the trade (take your profit)** when the price reaches **{tp:.5f}** "
            f"— that's **+{pp} pips** of profit\n"
            f"- 🛑 **Close the trade immediately (cut your loss)** if the price rises to **{sl:.5f}** "
            f"— that keeps your loss to just {pr} pips\n\n"
            f"I'm watching every {check_label.lower().replace('every ','')} and will tell you when to close."
        )
    else:
        return (
            f"⏳ **Don't trade right now. Just wait.**\n\n"
            f"The price is at **{price:.5f}** but the signals are not clear enough to trade safely "
            f"because {why}.\n\n"
            f"**What to do:**\n"
            f"- ✋ **Do nothing** — keep your money safe\n"
            f"- I'm watching the market automatically and will shout when it's time\n"
            f"- A good setup is coming — patience always pays in trading"
        )

plain_text = plain_english(action, short_name, current_price, take_profit, stop_loss,
                            pips_profit, pips_risk, reasons)

# ── New signal alert ──────────────────────────────────────────────────────────
if action != st.session_state["last_action"] and action != "WAIT":
    st.session_state["last_action"] = action
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    st.session_state["trade_log"].append({
        "time": ts, "action": action, "price": current_price,
        "tp": take_profit, "sl": stop_loss, "pips": pips_profit,
    })
    if len(st.session_state["trade_log"]) > 30:
        st.session_state["trade_log"].pop(0)
    if voice_on and IS_MAC:
        if action == "BUY":
            speak(f"Buy {short_name} now at {current_price:.4f}. "
                  f"Take profit at {take_profit:.4f}. Stop loss at {stop_loss:.4f}.")
        elif action == "SELL":
            speak(f"Sell {short_name} now at {current_price:.4f}. "
                  f"Take profit at {take_profit:.4f}. Stop loss at {stop_loss:.4f}.")
elif action == "WAIT" and st.session_state["last_action"] != "WAIT":
    st.session_state["last_action"] = "WAIT"

# ── Big signal banner ─────────────────────────────────────────────────────────
if action == "BUY":
    bg, border, emoji, headline = "#1b5e20", "#00e676", "🟢", "BUY NOW"
elif action == "SELL":
    bg, border, emoji, headline = "#b71c1c", "#ff1744", "🔴", "SELL NOW"
else:
    bg, border, emoji, headline = "#1c2833", "#546e7a", "⏳", "WAIT — DO NOTHING"

st.markdown(f"""
<div style='background:{bg};border:3px solid {border};border-radius:18px;
     padding:28px 20px 18px;text-align:center;margin:10px 0 6px'>
  <div style='font-size:3.5rem;font-weight:900;color:{border}'>{emoji}&nbsp;&nbsp;{headline}</div>
  <div style='font-size:1.2rem;color:#eceff1;margin-top:8px'>{short_name} &nbsp;·&nbsp; {current_price:.5f}</div>
</div>""", unsafe_allow_html=True)

# ── Price boxes ───────────────────────────────────────────────────────────────
if action != "WAIT":
    p1, p2, p3 = st.columns(3)
    with p1:
        lbl = "BUY AT" if action == "BUY" else "SELL AT"
        st.markdown(f"""<div style='background:#263238;border:2px solid #546e7a;
            border-radius:10px;padding:14px;text-align:center'>
            <div style='color:#90a4ae;font-size:0.85rem'>{lbl}</div>
            <div style='color:#eceff1;font-size:1.6rem;font-weight:700'>{current_price:.5f}</div>
            </div>""", unsafe_allow_html=True)
    with p2:
        st.markdown(f"""<div style='background:#1b5e20;border:2px solid #00e676;
            border-radius:10px;padding:14px;text-align:center'>
            <div style='color:#a5d6a7;font-size:0.85rem'>💰 TAKE PROFIT AT</div>
            <div style='color:#00e676;font-size:1.6rem;font-weight:700'>{take_profit:.5f}</div>
            <div style='color:#a5d6a7;font-size:0.85rem'>+{pips_profit} pips profit</div>
            </div>""", unsafe_allow_html=True)
    with p3:
        st.markdown(f"""<div style='background:#b71c1c22;border:2px solid #ff5252;
            border-radius:10px;padding:14px;text-align:center'>
            <div style='color:#ef9a9a;font-size:0.85rem'>🛑 GET OUT IF IT HITS</div>
            <div style='color:#ff5252;font-size:1.6rem;font-weight:700'>{stop_loss:.5f}</div>
            <div style='color:#ef9a9a;font-size:0.85rem'>-{pips_risk} pips max loss</div>
            </div>""", unsafe_allow_html=True)

# ── Plain-English block ───────────────────────────────────────────────────────
st.markdown(f"<div class='plain-text'>{plain_text.replace(chr(10),'<br>')}</div>",
            unsafe_allow_html=True)

# ── Status ────────────────────────────────────────────────────────────────────
now = datetime.datetime.now()
if st.session_state["watching"]:
    nxt = now + datetime.timedelta(milliseconds=refresh_ms)
    st.markdown(f"<div style='text-align:center;color:#78909c;margin:6px 0'>"
                f"✅ Watching {short_name} · Next check at "
                f"<b style='color:#eceff1'>{nxt.strftime('%H:%M:%S')}</b></div>",
                unsafe_allow_html=True)
else:
    st.markdown("<div style='text-align:center;color:#78909c;margin:6px 0'>"
                "⏸ Not watching. Press <b>▶ Start Watching</b> to get automatic alerts.</div>",
                unsafe_allow_html=True)

# ── Local AI explanation (only when Ollama is available) ─────────────────────
models     = get_ollama_models()
text_models = [m for m in models if not any(v in m.lower()
               for v in ["llava","moondream","vision","minicpm"])]

if text_models:
    with st.expander("🤖 Ask AI to explain this in plain English", expanded=(action != "WAIT")):
        chosen = text_models[0]
        if st.button(f"Explain with {chosen}"):
            with st.spinner("AI is writing a plain-English explanation…"):
                try:
                    import ollama
                    last = df.iloc[-1]
                    prompt = (
                        f"You are a friendly trading coach. Explain in 4 simple sentences "
                        f"to someone who knows NOTHING about trading: "
                        f"The currency pair is {short_name}. Price is {current_price:.5f}. "
                        f"The signal is {action}. Reasons: {', '.join(reasons[:3])}. "
                        f"Take profit: {take_profit}. Stop loss: {stop_loss}. "
                        f"No jargon. No indicator names. Write like texting a friend."
                    )
                    resp = ollama.chat(
                        model=chosen,
                        messages=[{"role":"user","content":prompt}],
                        options={"temperature":0.3,"num_predict":300}
                    )
                    st.markdown(resp.message.content.strip())
                except Exception as e:
                    st.info(f"Local AI not available: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# 🧠  AI AUTO-WATCH — no screen capture needed
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")

def build_chart_image(df, short_name):
    d = df.tail(120).copy()
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.60, 0.20, 0.20],
        vertical_spacing=0.04,
        subplot_titles=(f"{short_name} — Price", "RSI", "MACD"),
    )
    fig.add_trace(go.Candlestick(
        x=d.index, open=d["Open"], high=d["High"], low=d["Low"], close=d["Close"],
        name="Price",
        increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
        increasing_fillcolor="#26a69a", decreasing_fillcolor="#ef5350",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["BB_upper"], name="BB Upper",
        line=dict(color="#5c6bc0", width=1, dash="dash")), row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["BB_lower"], name="BB Lower",
        line=dict(color="#5c6bc0", width=1, dash="dash"),
        fill="tonexty", fillcolor="rgba(92,107,192,0.07)"), row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["EMA20"], name="EMA 20",
        line=dict(color="#ffb300", width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["EMA50"], name="EMA 50",
        line=dict(color="#ff7043", width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["RSI"], name="RSI",
        line=dict(color="#ab47bc", width=1.5)), row=2, col=1)
    for lvl, lc in [(70,"#ef5350"),(50,"#546e7a"),(30,"#26a69a")]:
        fig.add_hline(y=lvl, line_color=lc, line_dash="dot", line_width=1, row=2, col=1)
    bar_colors = ["#26a69a" if v>=0 else "#ef5350" for v in d["MACD_hist"]]
    fig.add_trace(go.Bar(x=d.index, y=d["MACD_hist"], name="Hist",
        marker_color=bar_colors, opacity=0.7), row=3, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["MACD"], name="MACD",
        line=dict(color="#42a5f5", width=1.5)), row=3, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["MACD_sig"], name="Signal",
        line=dict(color="#ff7043", width=1.5)), row=3, col=1)
    fig.update_layout(
        template="plotly_dark", height=600, width=1100,
        margin=dict(t=40, b=10, l=60, r=20),
        xaxis_rangeslider_visible=False,
        paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
    )
    fig.update_yaxes(showgrid=True, gridcolor="#1e272e")
    fig.update_xaxes(showgrid=True, gridcolor="#1e272e")
    try:
        return fig.to_image(format="png", scale=1.5)
    except Exception:
        return None


def ai_auto_watch(chart_bytes, df, short_name, action, reasons,
                  take_profit, stop_loss, pips_profit, pips_risk, models):
    import ollama
    last = df.iloc[-1]
    vision_models = [m for m in models if any(v in m.lower()
                     for v in ["moondream","llava","vision","minicpm"])]
    text_models   = [m for m in models if m not in vision_models]

    visual_reading = ""
    if vision_models and chart_bytes:
        b64 = base64.standard_b64encode(chart_bytes).decode()
        try:
            r = ollama.chat(
                model=vision_models[0],
                messages=[{"role":"user",
                    "content": "This is a live trading chart. Describe what you see in 2 sentences: Is the price trending up or down? Are the candles mostly green or red recently? Start with UP or DOWN.",
                    "images":[b64]}],
                options={"temperature":0.1,"num_predict":120},
            )
            visual_reading = r.message.content.strip()
        except Exception:
            pass

    if not text_models:
        return {"verdict":action,"plain":"","visual":visual_reading,
                "entry":float(last["Close"]),"tp":take_profit,"sl":stop_loss}

    rsi_val   = float(last["RSI"])
    trend_dir = "UP" if float(last["EMA20"])>float(last["EMA50"]) else "DOWN"
    why       = ", ".join(reasons[:4])

    prompt = f"""You are a professional trading coach helping a complete beginner.

MARKET DATA FOR {short_name}:
- Current price: {float(last['Close']):.5f}
- RSI: {rsi_val:.1f} ({'oversold — likely to go UP' if rsi_val<32 else 'overbought — likely to go DOWN' if rsi_val>68 else 'neutral'})
- Overall trend direction: {trend_dir}
- Key signals: {why}
- My signal: {action}
- Take-profit: {take_profit} (+{pips_profit} pips)
- Stop-loss: {stop_loss} (-{pips_risk} pips)
{f"- Chart visual reading: {visual_reading}" if visual_reading else ""}

Write 4 plain sentences — no jargon, no indicator names:
1. What the market is doing right now
2. Why the signal says {action}
3. Exactly what the person should do (with prices)
4. When to get out if it goes wrong"""

    try:
        r = ollama.chat(
            model=text_models[0],
            messages=[{"role":"user","content":prompt}],
            options={"temperature":0.25,"num_predict":350},
        )
        plain = re.sub(r"<think>.*?</think>","",r.message.content.strip(),flags=re.DOTALL).strip()
    except Exception as e:
        plain = f"AI reasoning unavailable: {e}"

    return {"verdict":action,"plain":plain,"visual":visual_reading,
            "entry":float(last["Close"]),"tp":take_profit,"sl":stop_loss,
            "model":text_models[0],
            "vis_model":vision_models[0] if vision_models else None,
            "time":datetime.datetime.now().strftime("%H:%M:%S")}


with st.expander("🧠  AI Auto-Watch — sees the market like you would", expanded=True):
    st.markdown(
        "The AI builds its own chart from live data, reads it visually, and tells you "
        "**exactly what you'd see** if you opened your trading platform — then tells you what to do. "
        "**No screen capture needed.**"
    )
    aw1, aw2 = st.columns([3, 1])
    with aw2:
        run_ai_watch = st.button("🔍 Analyse Now", use_container_width=True)
    with aw1:
        auto_ai = st.toggle("Auto-analyse on every refresh", value=True)

    models = get_ollama_models()
    should_run = run_ai_watch or (auto_ai and st.session_state["watching"])

    if should_run and models:
        with st.spinner("📊 Building your chart…"):
            chart_bytes = build_chart_image(df, short_name)
            if chart_bytes:
                st.session_state["ai_chart_bytes"] = chart_bytes
        with st.spinner("🧠 AI is reading the chart and making a prediction…"):
            result = ai_auto_watch(
                st.session_state.get("ai_chart_bytes"),
                df, short_name, action, reasons,
                take_profit, stop_loss, pips_profit, pips_risk, models,
            )
            result["time"] = datetime.datetime.now().strftime("%H:%M:%S")
            st.session_state["ai_watch_result"] = result
            if (IS_MAC and voice_on and result["verdict"] in ("BUY","SELL")
                    and result["verdict"] != st.session_state.get("last_ai_spoken","")):
                st.session_state["last_ai_spoken"] = result["verdict"]
                speak(f"AI says {result['verdict']} {short_name} now at {result['entry']:.4f}. "
                      f"Target {result['tp']:.4f}. Stop at {result['sl']:.4f}.")
    elif should_run:
        st.info("Ollama not running locally. The chart is still generated below — AI reasoning needs `ollama serve`.")
        with st.spinner("📊 Building chart…"):
            chart_bytes = build_chart_image(df, short_name)
            if chart_bytes:
                st.session_state["ai_chart_bytes"] = chart_bytes

    res = st.session_state.get("ai_watch_result")
    chart_col, info_col = st.columns([3, 2])

    with chart_col:
        st.markdown("**📈 What the market looks like right now**")
        st.caption("Same chart you'd see on any trading platform — built live from real price data.")
        cb = st.session_state.get("ai_chart_bytes")
        if cb:
            st.image(cb, use_container_width=True)
        else:
            st.markdown("<div style='background:#1e272e;border:2px dashed #546e7a;border-radius:10px;"
                        "height:200px;display:flex;align-items:center;justify-content:center;"
                        "color:#546e7a'>Press 🔍 Analyse Now to generate the chart</div>",
                        unsafe_allow_html=True)

    with info_col:
        st.markdown("**🤖 AI's Prediction**")
        if res:
            v  = res["verdict"]
            vc = {"BUY":"#00e676","SELL":"#ff1744","WAIT":"#90a4ae"}.get(v,"#90a4ae")
            bg2= {"BUY":"#1b5e20","SELL":"#b71c1c","WAIT":"#1c2833"}.get(v,"#1c2833")
            ico= {"BUY":"🟢","SELL":"🔴","WAIT":"⏳"}.get(v,"⏳")
            st.markdown(
                f"<div style='background:{bg2};border:2px solid {vc};border-radius:12px;"
                f"padding:16px;text-align:center;margin-bottom:12px'>"
                f"<div style='font-size:2rem;font-weight:900;color:{vc}'>{ico} {v}</div>"
                f"<div style='color:#b0bec5;font-size:0.85rem'>at {res['entry']:.5f} · {res.get('time','')}</div>"
                f"</div>", unsafe_allow_html=True)
            lv1, lv2 = st.columns(2)
            lv1.metric("💰 Take Profit", f"{res['tp']:.5f}" if res['tp'] else "—")
            lv2.metric("🛑 Stop Loss",   f"{res['sl']:.5f}" if res['sl'] else "—")
            if res.get("visual"):
                st.markdown(f"**👁️ Chart shows:**\n\n*{res['visual']}*")
            if res.get("plain"):
                st.markdown("**🗣️ AI says:**")
                st.markdown(f"<div style='background:#1e272e;border-radius:10px;padding:14px 16px;"
                            f"color:#eceff1;font-size:1rem;line-height:1.7'>{res['plain']}</div>",
                            unsafe_allow_html=True)
            used = []
            if res.get("vis_model"): used.append(f"👁️ {res['vis_model']}")
            if res.get("model"):     used.append(f"🧠 {res['model']}")
            if used: st.caption("  ·  ".join(used) + " · free & local")
        else:
            st.markdown("<div style='background:#1e272e;border:2px dashed #546e7a;border-radius:10px;"
                        "padding:24px;text-align:center;color:#546e7a'>"
                        "Press 🔍 Analyse Now<br>or turn on Auto-analyse</div>",
                        unsafe_allow_html=True)

# ── Screen monitor (only when running locally with mss) ──────────────────────
if SCREEN_CAPTURE:
    st.markdown("---")
    with st.expander("🖥️  Show my live trading screen", expanded=False):
        vision_models = [m for m in models if any(v in m.lower()
                         for v in ["moondream","llava","vision"])]
        sc1, sc2 = st.columns([3,1])
        with sc2:
            if st.button("📸 Capture Screen"):
                try:
                    with mss.mss() as sct:
                        shot = sct.grab(sct.monitors[1])
                    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                    st.session_state["screen_img"] = img
                    if vision_models:
                        import ollama
                        buf = io.BytesIO()
                        img.resize((1024, int(1024*img.height/img.width)),
                                   Image.LANCZOS).save(buf, format="JPEG", quality=70)
                        b64  = base64.standard_b64encode(buf.getvalue()).decode()
                        resp = ollama.chat(
                            model=vision_models[0],
                            messages=[{"role":"user",
                                       "content":"In one sentence starting with UP or DOWN, describe the direction of this trading chart.",
                                       "images":[b64]}],
                            options={"temperature":0.1,"num_predict":60}
                        )
                        st.session_state["screen_verdict"] = resp.message.content.strip()
                except Exception as e:
                    st.error(f"Screen capture error: {e}")
        with sc1:
            if st.session_state["screen_img"]:
                st.image(st.session_state["screen_img"], use_container_width=True)
                v = st.session_state.get("screen_verdict","")
                if v:
                    vc = "#00e676" if v.upper().startswith("UP") else "#ff5252"
                    st.markdown(f"<div style='background:#1e272e;border:2px solid {vc};"
                                f"border-radius:8px;padding:10px;text-align:center;"
                                f"color:{vc};font-weight:700'>{v}</div>",
                                unsafe_allow_html=True)
            else:
                st.markdown("<div style='background:#1e272e;border:2px dashed #546e7a;"
                            "border-radius:10px;height:160px;display:flex;"
                            "align-items:center;justify-content:center;color:#546e7a'>"
                            "Click 📸 Capture Screen to start</div>", unsafe_allow_html=True)

# ── Trade log ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 📋 My Trading Calls")
log = list(reversed(st.session_state["trade_log"]))
if log:
    for e in log:
        c = "#00e676" if e["action"]=="BUY" else "#ff5252"
        ico = "🟢" if e["action"]=="BUY" else "🔴"
        st.markdown(f"""
        <div style='background:#1e272e;border-left:4px solid {c};
             border-radius:0 10px 10px 0;padding:12px 16px;margin-bottom:8px'>
          <span style='color:{c};font-weight:700;font-size:1.1rem'>{ico} {e['action']}</span>
          <span style='color:#78909c'> at </span>
          <span style='color:#eceff1;font-weight:700'>{e['price']:.5f}</span>
          &nbsp;&nbsp;→&nbsp;&nbsp;
          <span style='color:#a5d6a7'>Target: {e['tp']:.5f} (+{e['pips']} pips)</span>
          &nbsp;&nbsp;&nbsp;
          <span style='color:#546e7a;font-size:0.85rem'>{e['time']}</span>
        </div>""", unsafe_allow_html=True)
else:
    st.info("No signals yet. Press ▶ Start Watching — I'll log every call here.")

# ── Advanced details (hidden) ─────────────────────────────────────────────────
with st.expander("🔬 Show the details (for advanced users)", expanded=False):
    last = df.iloc[-1]
    st.markdown("These are the 6 signals I check. You don't need to understand them — I handle it all.")
    st.dataframe(pd.DataFrame({
        "Signal":        ["RSI","MACD trend","Bollinger zone","EMA trend","Stochastic","ATR"],
        "Current value": [
            f"{float(last['RSI']):.1f}",
            "↑ Bullish" if float(last["MACD"])>float(last["MACD_sig"]) else "↓ Bearish",
            ("Below low zone 🟢" if float(last["Close"])<float(last["BB_lower"])
             else "Above high zone 🔴" if float(last["Close"])>float(last["BB_upper"])
             else "Normal range"),
            "↑ Uptrend" if float(last["EMA20"])>float(last["EMA50"]) else "↓ Downtrend",
            ("Oversold 🟢" if float(last["StochK"])<22
             else "Overbought 🔴" if float(last["StochK"])>78 else "Neutral"),
            f"{float(last['ATR']):.5f}",
        ],
        "What it means": [
            "Below 30 = buy opportunity, above 70 = sell opportunity",
            "Flipped up = buy, flipped down = sell",
            "At bottom = price likely to go up",
            "Short trend above long trend = market going up",
            "Below 20 = likely going up, above 80 = likely going down",
            "How much the price moves per candle",
        ],
    }), use_container_width=True, hide_index=True)
    st.markdown(f"**Score: `{score:+.1f}` / ±10** — needs +4 to BUY, -4 to SELL")

st.markdown("---")
st.caption(
    "Built with ❤️ using Streamlit · Data from Yahoo Finance · "
    "⚠️ For educational purposes only. All trading carries risk."
)
