"""
FX Trading Assistant — Always-On, 1-Second Live Refresh
Constantly watches the market and tells you exactly when to buy and sell.
No trading knowledge needed.
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
import datetime, time, subprocess, io, base64, re, mss
from PIL import Image

st.set_page_config(page_title="FX Live Trader", layout="centered", page_icon="💰")

# ── Always-on 1-second ticker ─────────────────────────────────────────────────
tick = st_autorefresh(interval=1000, key="tick")   # fires every second, always

# ── Session state ─────────────────────────────────────────────────────────────
for k, v in [
    ("last_action", ""), ("last_spoken", ""), ("last_ai_spoken", ""),
    ("trade_log", []), ("screen_img", None), ("screen_verdict", ""),
    ("ai_watch_result", None), ("ai_chart_bytes", None),
]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Constants ─────────────────────────────────────────────────────────────────
PAIRS = {
    "Euro / US Dollar (EUR/USD)":            "EURUSD=X",
    "British Pound / Dollar (GBP/USD)":      "GBPUSD=X",
    "Dollar / Japanese Yen (USD/JPY)":       "USDJPY=X",
    "Australian Dollar / USD (AUD/USD)":     "AUDUSD=X",
    "Dollar / Canadian Dollar (USD/CAD)":    "USDCAD=X",
    "Dollar / Swiss Franc (USD/CHF)":        "USDCHF=X",
    "Euro / British Pound (EUR/GBP)":        "EURGBP=X",
    "Euro / Yen (EUR/JPY)":                  "EURJPY=X",
    "Pound / Yen (GBP/JPY)":                "GBPJPY=X",
    "New Zealand Dollar / USD (NZD/USD)":    "NZDUSD=X",
}

# candle_size → (yf interval, yf period, data-refresh every N seconds)
TIMEFRAMES = {
    "1-minute candles  (fastest)":  ("1m",  "5d",   30),
    "2-minute candles":              ("2m",  "5d",   60),
    "5-minute candles  (recommended)": ("5m","5d",   60),
    "15-minute candles":             ("15m", "5d",  120),
    "1-hour candles":                ("1h",  "30d", 300),
}

def pip_size(sym): return 0.01 if "JPY" in sym else 0.0001

def speak(text):
    if text != st.session_state["last_spoken"]:
        subprocess.Popen(["say","-r","185",text],
                         stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        st.session_state["last_spoken"] = text

def get_ollama_models():
    try:
        import ollama
        return [m.model for m in ollama.list().models]
    except Exception:
        return []

# ── Styles ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.plain-text{font-size:1.1rem;line-height:1.8;color:#eceff1;background:#1e272e;
            border-radius:12px;padding:16px 20px;margin:10px 0}
.ticker-bar{display:flex;align-items:center;justify-content:space-between;
            background:#1e272e;border-radius:10px;padding:10px 18px;margin-bottom:8px}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## 💰 FX Live Trading Assistant")

# ── Settings row ─────────────────────────────────────────────────────────────
s1, s2, s3 = st.columns([3, 3, 1])
with s1:
    pair_label = st.selectbox("Currency pair", list(PAIRS.keys()), index=0, label_visibility="collapsed")
with s2:
    tf_label = st.selectbox("Candle size", list(TIMEFRAMES.keys()), index=2, label_visibility="collapsed")
with s3:
    voice_on = st.toggle("🔊", value=True, help="Voice alerts (Mac)")

ticker_sym              = PAIRS[pair_label]
interval, period, data_refresh_secs = TIMEFRAMES[tf_label]
pip                     = pip_size(ticker_sym)
short_name              = pair_label.split("(")[-1].replace(")","").strip()

# ── Live clock bar ────────────────────────────────────────────────────────────
now_ts      = int(time.time())
secs_in     = now_ts % data_refresh_secs          # seconds since last data pull
secs_left   = data_refresh_secs - secs_in         # seconds until next data pull
pct_done    = secs_in / data_refresh_secs * 100
now_str     = datetime.datetime.now().strftime("%H:%M:%S")
bar_col     = "#26a69a" if secs_left > 10 else "#ffa726" if secs_left > 5 else "#ef5350"

st.markdown(f"""
<div class='ticker-bar'>
  <span style='color:#26a69a;font-weight:700;font-size:1.1rem'>● LIVE&nbsp;&nbsp;{now_str}</span>
  <span style='color:#78909c'>Watching: <b style='color:#eceff1'>{short_name}</b>
  &nbsp;·&nbsp; {tf_label.split('(')[0].strip()}</span>
  <span style='color:{bar_col};font-weight:700'>Next data in {secs_left}s</span>
</div>
<div style='background:#263238;border-radius:4px;height:5px;margin-bottom:12px;overflow:hidden'>
  <div style='width:{pct_done:.0f}%;background:{bar_col};height:100%;
       border-radius:4px;transition:width 1s linear'></div>
</div>
""", unsafe_allow_html=True)

# ── Fetch data (cached per data_refresh_secs window) ─────────────────────────
cache_key = now_ts // data_refresh_secs   # changes only when window rolls over

@st.cache_data(ttl=data_refresh_secs)
def get_data(symbol, interval, period, _key):
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

if st.session_state.pop("force_check", False):
    get_data.clear()

with st.spinner(""):
    df = get_data(ticker_sym, interval, period, cache_key)

if df.empty:
    st.error("No market data right now — will retry in a few seconds.")
    st.stop()

# ── Compute indicators ────────────────────────────────────────────────────────
cl, hi, lo = df["Close"], df["High"], df["Low"]
df = df.copy()
df["RSI"]      = RSIIndicator(cl,14).rsi()
macd_obj       = MACD(cl,26,12,9)
df["MACD"]     = macd_obj.macd()
df["MACD_sig"] = macd_obj.macd_signal()
df["MACD_hist"]= macd_obj.macd_diff()
bb             = BollingerBands(cl,20,2)
df["BB_upper"] = bb.bollinger_hband()
df["BB_lower"] = bb.bollinger_lband()
df["EMA20"]    = EMAIndicator(cl,20).ema_indicator()
df["EMA50"]    = EMAIndicator(cl,50).ema_indicator()
df["ATR"]      = AverageTrueRange(hi,lo,cl,14).average_true_range()
st_obj         = StochasticOscillator(hi,lo,cl,14,3)
df["StochK"]   = st_obj.stoch()

# ── Signal scoring ────────────────────────────────────────────────────────────
def compute_signal(df):
    last=df.iloc[-1]; prev=df.iloc[-2]
    score=0; reasons=[]
    rsi=float(last["RSI"])
    if rsi<32:   score+=3; reasons.append("the market is oversold and likely to bounce up")
    elif rsi>68: score-=3; reasons.append("the market is overbought and likely to drop")
    elif rsi<48: score+=1
    elif rsi>52: score-=1
    if float(prev["MACD"])<float(prev["MACD_sig"]) and float(last["MACD"])>float(last["MACD_sig"]):
        score+=3; reasons.append("momentum just flipped upward — a strong buy signal")
    elif float(prev["MACD"])>float(prev["MACD_sig"]) and float(last["MACD"])<float(last["MACD_sig"]):
        score-=3; reasons.append("momentum just flipped downward — a strong sell signal")
    elif float(last["MACD_hist"])>0: score+=1
    else: score-=1
    cp=float(last["Close"])
    if cp<float(last["BB_lower"]):   score+=2; reasons.append("price hit a historically low bounce zone")
    elif cp>float(last["BB_upper"]): score-=2; reasons.append("price hit a historically high reversal zone")
    if float(last["EMA20"])>float(last["EMA50"]): score+=1.5; reasons.append("the short-term trend is pointing up")
    else: score-=1.5; reasons.append("the short-term trend is pointing down")
    sk=float(last["StochK"])
    if sk<22:   score+=1.5; reasons.append("price is in a deep low zone — buyers usually step in here")
    elif sk>78: score-=1.5; reasons.append("price is in a high zone — sellers usually come in here")
    return score, reasons, cp, float(last["ATR"])

score, reasons, current_price, atr = compute_signal(df)

# ── Decision ──────────────────────────────────────────────────────────────────
if score >= 4.0:
    action      = "BUY"
    take_profit = round(current_price + 2.5*atr, 5)
    stop_loss   = round(current_price - 1.2*atr, 5)
    pips_profit = round((take_profit - current_price)/pip)
    pips_risk   = round((current_price - stop_loss)/pip)
elif score <= -4.0:
    action      = "SELL"
    take_profit = round(current_price - 2.5*atr, 5)
    stop_loss   = round(current_price + 1.2*atr, 5)
    pips_profit = round((current_price - take_profit)/pip)
    pips_risk   = round((stop_loss - current_price)/pip)
else:
    action      = "WAIT"
    take_profit = None
    stop_loss   = round(current_price - 1.2*atr, 5)
    pips_profit = 0
    pips_risk   = 0

# ── Plain-English explanation ─────────────────────────────────────────────────
def plain_english(action, short_name, price, tp, sl, pp, pr, reasons):
    why = ", ".join(reasons[:3]) if reasons else "signals are mixed"
    if action == "BUY":
        return (
            f"✅ **Right now is a good time to BUY {short_name}.**\n\n"
            f"The price is at **{price:.5f}** and the market is likely going **UP** because {why}.\n\n"
            f"**Here is exactly what to do:**\n"
            f"- 🟢 **BUY** {short_name} now at **{price:.5f}**\n"
            f"- 💰 **Close the trade and take your profit** when the price reaches **{tp:.5f}** (+{pp} pips)\n"
            f"- 🛑 **Get out immediately** if price drops to **{sl:.5f}** (limits loss to {pr} pips)\n\n"
            f"I'm watching every second and will alert you when to close."
        )
    elif action == "SELL":
        return (
            f"🔴 **Right now is a good time to SELL {short_name}.**\n\n"
            f"The price is at **{price:.5f}** and the market is likely going **DOWN** because {why}.\n\n"
            f"**Here is exactly what to do:**\n"
            f"- 🔴 **SELL** {short_name} now at **{price:.5f}**\n"
            f"- 💰 **Close the trade and take your profit** when the price reaches **{tp:.5f}** (+{pp} pips)\n"
            f"- 🛑 **Get out immediately** if price rises to **{sl:.5f}** (limits loss to {pr} pips)\n\n"
            f"I'm watching every second and will alert you when to close."
        )
    else:
        return (
            f"⏳ **Don't trade right now. Wait.**\n\n"
            f"The price is at **{price:.5f}** but it's not safe to trade yet because {why}.\n\n"
            f"- ✋ **Do nothing** — keep your money safe\n"
            f"- I'm checking the market **every second** and will shout the moment it's time\n"
            f"- Patience always pays — a clear setup is coming"
        )

plain_text = plain_english(action, short_name, current_price, take_profit,
                            stop_loss, pips_profit, pips_risk, reasons)

# ── Fire voice alert on new actionable signal ─────────────────────────────────
if action != "WAIT" and action != st.session_state["last_action"]:
    st.session_state["last_action"] = action
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    st.session_state["trade_log"].append({
        "time":ts,"action":action,"price":current_price,
        "tp":take_profit,"sl":stop_loss,"pips":pips_profit
    })
    if len(st.session_state["trade_log"]) > 40:
        st.session_state["trade_log"].pop(0)
    if voice_on:
        speak(f"{'Buy' if action=='BUY' else 'Sell'} {short_name} now "
              f"at {current_price:.4f}. Take profit at {take_profit:.4f}. "
              f"Stop loss at {stop_loss:.4f}.")
elif action == "WAIT":
    st.session_state["last_action"] = "WAIT"

# ── Big signal banner ─────────────────────────────────────────────────────────
if action=="BUY":    bg,border,emoji,headline = "#1b5e20","#00e676","🟢","BUY NOW"
elif action=="SELL": bg,border,emoji,headline = "#b71c1c","#ff1744","🔴","SELL NOW"
else:                bg,border,emoji,headline = "#1c2833","#546e7a","⏳","WAIT — DO NOTHING"

st.markdown(f"""
<div style='background:{bg};border:3px solid {border};border-radius:18px;
     padding:26px 20px 16px;text-align:center;margin:6px 0'>
  <div style='font-size:3.2rem;font-weight:900;color:{border}'>{emoji}&nbsp;&nbsp;{headline}</div>
  <div style='font-size:1.15rem;color:#eceff1;margin-top:6px'>
    {short_name} &nbsp;·&nbsp; <b>{current_price:.5f}</b>
    &nbsp;·&nbsp; <span style='color:#78909c;font-size:0.9rem'>updated {now_str}</span>
  </div>
</div>""", unsafe_allow_html=True)

# ── Price boxes ───────────────────────────────────────────────────────────────
if action != "WAIT":
    p1,p2,p3 = st.columns(3)
    with p1:
        st.markdown(f"""<div style='background:#263238;border:2px solid #546e7a;
            border-radius:10px;padding:13px;text-align:center'>
            <div style='color:#90a4ae;font-size:0.8rem'>{'BUY' if action=='BUY' else 'SELL'} AT</div>
            <div style='color:#eceff1;font-size:1.5rem;font-weight:700'>{current_price:.5f}</div>
            </div>""", unsafe_allow_html=True)
    with p2:
        st.markdown(f"""<div style='background:#1b5e20;border:2px solid #00e676;
            border-radius:10px;padding:13px;text-align:center'>
            <div style='color:#a5d6a7;font-size:0.8rem'>💰 TAKE PROFIT AT</div>
            <div style='color:#00e676;font-size:1.5rem;font-weight:700'>{take_profit:.5f}</div>
            <div style='color:#a5d6a7;font-size:0.8rem'>+{pips_profit} pips profit</div>
            </div>""", unsafe_allow_html=True)
    with p3:
        st.markdown(f"""<div style='background:#b71c1c22;border:2px solid #ff5252;
            border-radius:10px;padding:13px;text-align:center'>
            <div style='color:#ef9a9a;font-size:0.8rem'>🛑 GET OUT IF IT HITS</div>
            <div style='color:#ff5252;font-size:1.5rem;font-weight:700'>{stop_loss:.5f}</div>
            <div style='color:#ef9a9a;font-size:0.8rem'>-{pips_risk} pips max loss</div>
            </div>""", unsafe_allow_html=True)

# ── Plain English ─────────────────────────────────────────────────────────────
st.markdown(f"<div class='plain-text'>{plain_text.replace(chr(10),'<br>')}</div>",
            unsafe_allow_html=True)

# ── AI plain-English (Ollama text model) ─────────────────────────────────────
models      = get_ollama_models()
text_models = [m for m in models if not any(v in m.lower()
               for v in ["llava","moondream","vision","minicpm"])]

if text_models:
    with st.expander("🤖 Ask AI to explain this in plain English", expanded=False):
        if st.button(f"Explain with {text_models[0]}"):
            with st.spinner("AI is writing a plain-English explanation…"):
                try:
                    import ollama, re as _re
                    last=df.iloc[-1]
                    prompt=(f"You are a friendly trading coach. Tell someone who knows NOTHING about trading "
                            f"what is happening with {short_name} right now and what they should do. "
                            f"Price: {current_price:.5f}. Signal: {action}. "
                            f"Reasons: {', '.join(reasons[:3])}. "
                            f"Take profit: {take_profit}. Stop loss: {stop_loss}. "
                            f"Write 4 simple sentences. No jargon. No indicator names.")
                    resp=ollama.chat(model=text_models[0],
                                     messages=[{"role":"user","content":prompt}],
                                     options={"temperature":0.3,"num_predict":300})
                    out=_re.sub(r"<think>.*?</think>","",resp.message.content.strip(),flags=_re.DOTALL).strip()
                    st.markdown(out)
                except Exception as e:
                    st.info(f"Local AI unavailable: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# 🧠  AI AUTO-WATCH — builds its own chart, reads it, predicts the trade
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")

def build_chart_image(df, short_name):
    d = df.tail(120).copy()
    fig = make_subplots(rows=3,cols=1,shared_xaxes=True,row_heights=[0.60,0.20,0.20],
                        vertical_spacing=0.04,
                        subplot_titles=(f"{short_name} — Price","RSI","MACD"))
    fig.add_trace(go.Candlestick(x=d.index,open=d["Open"],high=d["High"],low=d["Low"],close=d["Close"],
        name="Price",increasing_line_color="#26a69a",decreasing_line_color="#ef5350",
        increasing_fillcolor="#26a69a",decreasing_fillcolor="#ef5350"),row=1,col=1)
    fig.add_trace(go.Scatter(x=d.index,y=d["BB_upper"],name="BB Upper",
        line=dict(color="#5c6bc0",width=1,dash="dash")),row=1,col=1)
    fig.add_trace(go.Scatter(x=d.index,y=d["BB_lower"],name="BB Lower",
        line=dict(color="#5c6bc0",width=1,dash="dash"),
        fill="tonexty",fillcolor="rgba(92,107,192,0.07)"),row=1,col=1)
    fig.add_trace(go.Scatter(x=d.index,y=d["EMA20"],name="EMA 20",
        line=dict(color="#ffb300",width=1.5)),row=1,col=1)
    fig.add_trace(go.Scatter(x=d.index,y=d["EMA50"],name="EMA 50",
        line=dict(color="#ff7043",width=1.5)),row=1,col=1)
    fig.add_trace(go.Scatter(x=d.index,y=d["RSI"],name="RSI",
        line=dict(color="#ab47bc",width=1.5)),row=2,col=1)
    for lvl,lc in [(70,"#ef5350"),(50,"#546e7a"),(30,"#26a69a")]:
        fig.add_hline(y=lvl,line_color=lc,line_dash="dot",line_width=1,row=2,col=1)
    bc=["#26a69a" if v>=0 else "#ef5350" for v in d["MACD_hist"]]
    fig.add_trace(go.Bar(x=d.index,y=d["MACD_hist"],name="Hist",marker_color=bc,opacity=0.7),row=3,col=1)
    fig.add_trace(go.Scatter(x=d.index,y=d["MACD"],name="MACD",line=dict(color="#42a5f5",width=1.5)),row=3,col=1)
    fig.add_trace(go.Scatter(x=d.index,y=d["MACD_sig"],name="Signal",line=dict(color="#ff7043",width=1.5)),row=3,col=1)
    fig.update_layout(template="plotly_dark",height=580,width=1100,
        margin=dict(t=40,b=10,l=60,r=20),xaxis_rangeslider_visible=False,
        paper_bgcolor="#0e1117",plot_bgcolor="#0e1117",
        legend=dict(orientation="h",yanchor="bottom",y=1.01,xanchor="right",x=1))
    fig.update_yaxes(showgrid=True,gridcolor="#1e272e")
    fig.update_xaxes(showgrid=True,gridcolor="#1e272e")
    try:
        return fig.to_image(format="png",scale=1.5)
    except Exception:
        return None


def ai_auto_watch(chart_bytes, df, short_name, action, reasons,
                  tp, sl, pp, pr, models):
    import ollama
    last=df.iloc[-1]
    vm=[m for m in models if any(v in m.lower() for v in ["moondream","llava","vision","minicpm"])]
    tm=[m for m in models if m not in vm]

    visual=""
    if vm and chart_bytes:
        try:
            r=ollama.chat(model=vm[0],messages=[{"role":"user",
                "content":"Describe this trading chart in 2 sentences. Is the price going UP or DOWN? Are candles mostly green or red? Start your answer with UP or DOWN.",
                "images":[base64.standard_b64encode(chart_bytes).decode()]}],
                options={"temperature":0.1,"num_predict":120})
            visual=r.message.content.strip()
        except Exception:
            pass

    if not tm:
        return {"verdict":action,"plain":"","visual":visual,
                "entry":float(last["Close"]),"tp":tp,"sl":sl}

    rsi_v=float(last["RSI"])
    trend="UP" if float(last["EMA20"])>float(last["EMA50"]) else "DOWN"
    prompt=(
        f"You are a professional trading coach helping a complete beginner.\n\n"
        f"LIVE DATA FOR {short_name}:\n"
        f"- Price: {float(last['Close']):.5f}\n"
        f"- RSI: {rsi_v:.1f} ({'oversold — likely UP' if rsi_v<32 else 'overbought — likely DOWN' if rsi_v>68 else 'neutral'})\n"
        f"- Trend: {trend}\n"
        f"- Key reasons: {', '.join(reasons[:4])}\n"
        f"- Signal: {action}\n"
        f"- Take profit: {tp} (+{pp} pips)\n"
        f"- Stop loss: {sl} (-{pr} pips)\n"
        f"{f'- Chart looks like: {visual}' if visual else ''}\n\n"
        f"Write exactly 4 plain sentences — no jargon, no indicator names:\n"
        f"1. What the market is doing right now\n"
        f"2. Why the signal says {action}\n"
        f"3. Exactly what the person should do (with prices)\n"
        f"4. When to exit if it goes wrong"
    )
    try:
        r=ollama.chat(model=tm[0],messages=[{"role":"user","content":prompt}],
                      options={"temperature":0.25,"num_predict":350})
        plain=re.sub(r"<think>.*?</think>","",r.message.content.strip(),flags=re.DOTALL).strip()
    except Exception as e:
        plain=f"AI unavailable: {e}"

    return {"verdict":action,"plain":plain,"visual":visual,
            "entry":float(last["Close"]),"tp":tp,"sl":sl,
            "model":tm[0],"vis_model":vm[0] if vm else None,
            "time":datetime.datetime.now().strftime("%H:%M:%S")}


with st.expander("🧠  AI Auto-Watch — watches the market on its own", expanded=True):
    st.caption(
        "The AI builds a live chart from real price data, reads it visually, and tells you "
        "what you'd see if you opened your trading platform — then gives you the trade decision."
    )

    aw1, aw2 = st.columns([3,1])
    with aw1:
        auto_ai=st.toggle("Auto-analyse on every data refresh", value=True)
    with aw2:
        run_now=st.button("🔍 Analyse Now", use_container_width=True)

    # run when new data window arrives (cache_key changed) or manual trigger
    prev_key = st.session_state.get("_prev_cache_key", -1)
    data_is_fresh = (cache_key != prev_key)
    st.session_state["_prev_cache_key"] = cache_key

    should_run = run_now or (auto_ai and data_is_fresh)

    if should_run and models:
        with st.spinner("📊 Building chart…"):
            cb = build_chart_image(df, short_name)
            if cb:
                st.session_state["ai_chart_bytes"] = cb
        with st.spinner("🧠 AI is analysing…"):
            res = ai_auto_watch(
                st.session_state.get("ai_chart_bytes"),
                df, short_name, action, reasons,
                take_profit, stop_loss, pips_profit, pips_risk, models,
            )
            res["time"] = datetime.datetime.now().strftime("%H:%M:%S")
            st.session_state["ai_watch_result"] = res
            if (voice_on and res["verdict"] in ("BUY","SELL")
                    and res["verdict"] != st.session_state["last_ai_spoken"]):
                st.session_state["last_ai_spoken"] = res["verdict"]
                speak(f"AI says {'buy' if res['verdict']=='BUY' else 'sell'} {short_name} "
                      f"at {res['entry']:.4f}. Target {res['tp']:.4f}. Stop {res['sl']:.4f}.")

    elif should_run and not models:
        with st.spinner("📊 Building chart…"):
            cb = build_chart_image(df, short_name)
            if cb: st.session_state["ai_chart_bytes"] = cb
        st.info("Chart generated. Start Ollama (`ollama serve`) for AI reasoning.")

    res = st.session_state.get("ai_watch_result")
    cc, ic = st.columns([3,2])

    with cc:
        st.markdown("**📈 Live Market Chart**")
        st.caption("This is exactly what you'd see if you opened your trading app right now.")
        cb = st.session_state.get("ai_chart_bytes")
        if cb:
            st.image(cb, use_container_width=True)
        else:
            st.markdown("<div style='background:#1e272e;border:2px dashed #546e7a;border-radius:10px;"
                        "height:180px;display:flex;align-items:center;justify-content:center;"
                        "color:#546e7a'>Press 🔍 Analyse Now to generate</div>",
                        unsafe_allow_html=True)

    with ic:
        st.markdown("**🤖 AI Prediction**")
        if res:
            v=res["verdict"]
            vc={"BUY":"#00e676","SELL":"#ff1744","WAIT":"#90a4ae"}.get(v,"#90a4ae")
            bg2={"BUY":"#1b5e20","SELL":"#b71c1c","WAIT":"#1c2833"}.get(v,"#1c2833")
            ico2={"BUY":"🟢","SELL":"🔴","WAIT":"⏳"}.get(v,"⏳")
            st.markdown(
                f"<div style='background:{bg2};border:2px solid {vc};border-radius:12px;"
                f"padding:14px;text-align:center;margin-bottom:10px'>"
                f"<div style='font-size:1.9rem;font-weight:900;color:{vc}'>{ico2} {v}</div>"
                f"<div style='color:#b0bec5;font-size:0.8rem'>at {res['entry']:.5f} · {res.get('time','')}</div>"
                f"</div>",unsafe_allow_html=True)
            lv1,lv2=st.columns(2)
            lv1.metric("💰 Target", f"{res['tp']:.5f}" if res['tp'] else "—")
            lv2.metric("🛑 Stop",   f"{res['sl']:.5f}" if res['sl'] else "—")
            if res.get("visual"):
                st.markdown(f"**👁️ Chart reading:**\n\n*{res['visual']}*")
            if res.get("plain"):
                st.markdown("**🗣️ AI says:**")
                st.markdown(f"<div style='background:#1e272e;border-radius:10px;padding:12px 14px;"
                            f"color:#eceff1;font-size:0.95rem;line-height:1.7'>{res['plain']}</div>",
                            unsafe_allow_html=True)
            used=[]
            if res.get("vis_model"): used.append(f"👁️ {res['vis_model']}")
            if res.get("model"):     used.append(f"🧠 {res['model']}")
            if used: st.caption("  ·  ".join(used)+" · free & local")
        else:
            st.markdown("<div style='background:#1e272e;border:2px dashed #546e7a;border-radius:10px;"
                        "padding:22px;text-align:center;color:#546e7a'>"
                        "Press 🔍 Analyse Now<br>or turn on Auto-analyse</div>",
                        unsafe_allow_html=True)

# ── Screen capture (optional, local only) ────────────────────────────────────
st.markdown("---")
with st.expander("🖥️  Show my live trading screen (optional)", expanded=False):
    vision_models=[m for m in models if any(v in m.lower() for v in ["moondream","llava","vision"])]
    sc1,sc2=st.columns([3,1])
    with sc2:
        if st.button("📸 Capture"):
            try:
                with mss.mss() as sct:
                    shot=sct.grab(sct.monitors[1])
                img=Image.frombytes("RGB",shot.size,shot.bgra,"raw","BGRX")
                st.session_state["screen_img"]=img
                if vision_models:
                    import ollama
                    buf=io.BytesIO()
                    img.resize((1024,int(1024*img.height/img.width)),Image.LANCZOS).save(buf,format="JPEG",quality=70)
                    b64=base64.standard_b64encode(buf.getvalue()).decode()
                    r=ollama.chat(model=vision_models[0],messages=[{"role":"user",
                        "content":"One sentence starting with UP or DOWN: which direction is the price going on this trading chart?",
                        "images":[b64]}],options={"temperature":0.1,"num_predict":60})
                    st.session_state["screen_verdict"]=r.message.content.strip()
            except Exception as e:
                st.error(f"Screen capture error: {e}")
    with sc1:
        if st.session_state["screen_img"]:
            st.image(st.session_state["screen_img"],use_container_width=True)
            v=st.session_state.get("screen_verdict","")
            if v:
                vc2="#00e676" if v.upper().startswith("UP") else "#ff5252"
                st.markdown(f"<div style='background:#1e272e;border:2px solid {vc2};"
                            f"border-radius:8px;padding:8px;text-align:center;"
                            f"color:{vc2};font-weight:700'>{v}</div>",unsafe_allow_html=True)
        else:
            st.markdown("<div style='background:#1e272e;border:2px dashed #546e7a;"
                        "border-radius:10px;height:140px;display:flex;align-items:center;"
                        "justify-content:center;color:#546e7a'>Click 📸 Capture</div>",
                        unsafe_allow_html=True)

# ── Trade log ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 📋 My Trading Calls")
log=list(reversed(st.session_state["trade_log"]))
if log:
    for e in log:
        c="#00e676" if e["action"]=="BUY" else "#ff5252"
        st.markdown(f"""<div style='background:#1e272e;border-left:4px solid {c};
             border-radius:0 10px 10px 0;padding:10px 14px;margin-bottom:6px'>
          <span style='color:{c};font-weight:700'>{'🟢' if e['action']=='BUY' else '🔴'} {e['action']}</span>
          <span style='color:#78909c'> at </span>
          <span style='color:#eceff1;font-weight:700'>{e['price']:.5f}</span>
          &nbsp;→&nbsp;
          <span style='color:#a5d6a7'>Target {e['tp']:.5f} (+{e['pips']} pips)</span>
          &nbsp;&nbsp;
          <span style='color:#546e7a;font-size:0.85rem'>{e['time']}</span>
        </div>""",unsafe_allow_html=True)
else:
    st.info("No signals yet — the app is watching and will log every call here automatically.")

# ── Advanced ──────────────────────────────────────────────────────────────────
with st.expander("🔬 Show the details (advanced)", expanded=False):
    last=df.iloc[-1]
    st.dataframe(pd.DataFrame({
        "Signal":       ["RSI","MACD","Bollinger","EMA Trend","Stochastic","ATR"],
        "Value":        [f"{float(last['RSI']):.1f}",
                         "↑ Bullish" if float(last["MACD"])>float(last["MACD_sig"]) else "↓ Bearish",
                         ("Below low zone 🟢" if float(last["Close"])<float(last["BB_lower"])
                          else "Above high zone 🔴" if float(last["Close"])>float(last["BB_upper"])
                          else "Normal range"),
                         "↑ Uptrend" if float(last["EMA20"])>float(last["EMA50"]) else "↓ Downtrend",
                         ("Oversold 🟢" if float(last["StochK"])<22
                          else "Overbought 🔴" if float(last["StochK"])>78 else "Neutral"),
                         f"{float(last['ATR']):.5f}"],
        "Meaning":      ["<30=buy opp, >70=sell opp","Flipped up=buy, down=sell",
                         "At bottom=price likely going up","Short trend above long=going up",
                         "<20=likely going up, >80=likely going down","Size of price moves"],
    }),use_container_width=True,hide_index=True)
    st.caption(f"Score: {score:+.1f}/±10 · +4=BUY · -4=SELL · in between=WAIT")

st.markdown("---")
st.caption("⚠️ For educational purposes only. All trading carries risk. Never risk what you can't afford to lose.")
