"""
FX Live Trading Assistant
- No page blink: uses st.fragment for in-place updates
- 1-second live clock (fragment)
- Signal + AI refreshes on its own (fragment, data-interval driven)
- Cash profit calculator built in
- Premium dark UI
"""
import streamlit as st, yfinance as yf, pandas as pd, numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, EMAIndicator
from ta.volatility import BollingerBands, AverageTrueRange
import datetime, time, subprocess, io, base64, re, mss
from PIL import Image

st.set_page_config(page_title="FX Live Trader", layout="centered", page_icon="💰")

# ── Premium CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* base */
html,body,[data-testid="stAppViewContainer"]{background:#0a0e1a!important}
[data-testid="stSidebar"]{display:none}
[data-testid="stDecoration"]{display:none}
.block-container{padding-top:1.4rem!important;max-width:860px}

/* cards */
.card{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);
      border-radius:16px;padding:20px 24px;margin:10px 0}

/* live bar */
.live-bar{display:flex;align-items:center;justify-content:space-between;
          background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07);
          border-radius:12px;padding:10px 20px;margin-bottom:6px}
.live-dot{width:8px;height:8px;border-radius:50%;background:#26a69a;
          display:inline-block;margin-right:8px;
          box-shadow:0 0 8px #26a69a;animation:pulse 1.4s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}

/* signal banner */
.banner{border-radius:20px;padding:28px 24px 20px;text-align:center;margin:12px 0}
.banner-title{font-size:3rem;font-weight:900;letter-spacing:-.5px;margin-bottom:4px}
.banner-sub{font-size:1.1rem;opacity:.7}

/* price boxes */
.pbox{border-radius:14px;padding:16px 12px;text-align:center}
.pbox-label{font-size:.75rem;font-weight:600;letter-spacing:.08em;
            text-transform:uppercase;opacity:.65;margin-bottom:6px}
.pbox-value{font-size:1.6rem;font-weight:800;letter-spacing:-.3px}
.pbox-sub{font-size:.8rem;margin-top:4px;opacity:.7}

/* cash card */
.cash-card{background:rgba(255,215,0,.05);border:1px solid rgba(255,215,0,.2);
           border-radius:14px;padding:16px 20px;margin:10px 0}

/* plain text */
.plain{font-size:1.05rem;line-height:1.85;color:#d0d8e8;background:rgba(255,255,255,.03);
       border:1px solid rgba(255,255,255,.06);border-radius:14px;padding:18px 22px;margin:10px 0}

/* log row */
.log-row{background:rgba(255,255,255,.03);border-radius:10px;
         padding:10px 16px;margin-bottom:6px;display:flex;
         align-items:center;justify-content:space-between}

/* metric override */
[data-testid="metric-container"]{background:rgba(255,255,255,.03);
  border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:12px}
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
PAIRS = {
    "Euro / US Dollar (EUR/USD)":           "EURUSD=X",
    "British Pound / Dollar (GBP/USD)":     "GBPUSD=X",
    "Dollar / Japanese Yen (USD/JPY)":      "USDJPY=X",
    "Australian Dollar / USD (AUD/USD)":    "AUDUSD=X",
    "Dollar / Canadian Dollar (USD/CAD)":   "USDCAD=X",
    "Dollar / Swiss Franc (USD/CHF)":       "USDCHF=X",
    "Euro / British Pound (EUR/GBP)":       "EURGBP=X",
    "Euro / Yen (EUR/JPY)":                 "EURJPY=X",
    "Pound / Yen (GBP/JPY)":               "GBPJPY=X",
    "New Zealand Dollar / USD (NZD/USD)":   "NZDUSD=X",
}
TIMEFRAMES = {
    "1-min candles  (scalping)":     ("1m",  "5d",  30),
    "2-min candles":                 ("2m",  "5d",  60),
    "5-min candles  ✦ recommended":  ("5m",  "5d",  60),
    "15-min candles":                ("15m", "5d", 120),
    "1-hour candles  (swing)":       ("1h", "30d", 300),
}
LEVERAGE_MAP = {"No leverage (1:1)":1,"Low (1:10)":10,"Medium (1:30)":30,
                "High (1:100)":100,"Very high (1:500)":500}

def pip_size(sym): return 0.01 if "JPY" in sym else 0.0001

def get_ollama_models():
    try:
        import ollama
        return [m.model for m in ollama.list().models]
    except Exception:
        return []

def speak(key, text):
    if text != st.session_state.get(f"_spoken_{key}",""):
        st.session_state[f"_spoken_{key}"] = text
        subprocess.Popen(["say","-r","185",text],
                         stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

# ── Session state defaults ────────────────────────────────────────────────────
for k,v in [("trade_log",[]),("screen_img",None),("screen_verdict",""),
            ("ai_result",None),("ai_chart",None),("last_action",""),
            ("_prev_cache_key",-1)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("<h2 style='margin-bottom:4px;color:#f0f4f8'>💰 FX Live Trading Assistant</h2>",
            unsafe_allow_html=True)
st.markdown("<p style='color:#8892a0;margin-top:0;font-size:1rem'>"
            "Watches the market every second · Tells you exactly when to trade</p>",
            unsafe_allow_html=True)

# ── Settings ──────────────────────────────────────────────────────────────────
c1,c2 = st.columns(2)
with c1:
    pair_label = st.selectbox("Currency pair",  list(PAIRS.keys()),  index=0, key="sel_pair")
with c2:
    tf_label   = st.selectbox("Candle size",    list(TIMEFRAMES.keys()), index=2, key="sel_tf")

c3,c4,c5 = st.columns([2,2,1])
with c3:
    trade_amount = st.number_input("Your trade amount (£)", min_value=1.0, max_value=100000.0,
                                   value=20.0, step=5.0, key="trade_amount",
                                   help="How much money you plan to trade with")
with c4:
    leverage_label = st.selectbox("Leverage", list(LEVERAGE_MAP.keys()),
                                  index=2, key="sel_leverage",
                                  help="UK regulated brokers default to 1:30")
with c5:
    voice_on = st.toggle("🔊", value=True, key="voice_on", help="Voice alerts")

ticker_sym = PAIRS[pair_label]
interval, period, data_refresh_secs = TIMEFRAMES[tf_label]
leverage   = LEVERAGE_MAP[leverage_label]
pip        = pip_size(ticker_sym)
short_name = pair_label.split("(")[-1].replace(")","").strip()

# ── Cash profit helper ────────────────────────────────────────────────────────
def calc_profit(amount_gbp, leverage, pips, pip_s, price):
    """Approximate profit in GBP for a given pip move."""
    position = amount_gbp * leverage
    if pip_s == 0.01:          # JPY pairs
        return position * pips * pip_s / price
    else:                      # Most major pairs
        return position * pips * pip_s

# ═══════════════════════════════════════════════════════════════════════════════
# FRAGMENT 1 — Live clock bar  (updates every 1 second, zero blink)
# ═══════════════════════════════════════════════════════════════════════════════
@st.fragment(run_every="1s")
def live_clock():
    now_ts    = int(time.time())
    secs_in   = now_ts % data_refresh_secs
    secs_left = data_refresh_secs - secs_in
    pct       = secs_in / data_refresh_secs * 100
    now_str   = datetime.datetime.now().strftime("%H:%M:%S")
    bar_col   = "#26a69a" if secs_left>10 else "#ffa726" if secs_left>4 else "#ef5350"
    lbl       = tf_label.split("(")[0].split("✦")[0].strip()
    st.markdown(f"""
    <div class='live-bar'>
      <span style='color:#eceff1;font-weight:700;font-size:1rem'>
        <span class='live-dot'></span>LIVE &nbsp; {now_str}
      </span>
      <span style='color:#8892a0'>{short_name} &nbsp;·&nbsp; {lbl}</span>
      <span style='color:{bar_col};font-weight:700;font-size:.9rem'>
        Data refreshes in {secs_left}s
      </span>
    </div>
    <div style='background:rgba(255,255,255,.06);border-radius:3px;height:3px;margin-bottom:14px'>
      <div style='width:{pct:.1f}%;background:{bar_col};height:100%;
           border-radius:3px;transition:width .9s linear'></div>
    </div>""", unsafe_allow_html=True)

live_clock()

# ═══════════════════════════════════════════════════════════════════════════════
# FRAGMENT 2 — Signal + Cash Calculator + AI  (updates on data-refresh cadence)
# ═══════════════════════════════════════════════════════════════════════════════
@st.fragment(run_every=data_refresh_secs)
def signal_panel():
    # ── Fetch data ────────────────────────────────────────────────────────────
    @st.cache_data(ttl=data_refresh_secs)
    def get_data(sym, iv, per, _k):
        for _ in range(3):
            try:
                df = yf.download(sym, interval=iv, period=per,
                                 auto_adjust=True, progress=False)
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                df.dropna(inplace=True)
                if not df.empty: return df
            except Exception: time.sleep(1)
        return pd.DataFrame()

    ck = int(time.time()) // data_refresh_secs
    df = get_data(ticker_sym, interval, period, ck)
    if df.empty:
        st.warning("⏳ Waiting for market data…")
        return

    # ── Indicators ────────────────────────────────────────────────────────────
    cl,hi,lo = df["Close"],df["High"],df["Low"]
    df = df.copy()
    df["RSI"]      = RSIIndicator(cl,14).rsi()
    mo             = MACD(cl,26,12,9)
    df["MACD"]     = mo.macd()
    df["MACD_sig"] = mo.macd_signal()
    df["MACD_hist"]= mo.macd_diff()
    bb             = BollingerBands(cl,20,2)
    df["BB_upper"] = bb.bollinger_hband()
    df["BB_lower"] = bb.bollinger_lband()
    df["EMA20"]    = EMAIndicator(cl,20).ema_indicator()
    df["EMA50"]    = EMAIndicator(cl,50).ema_indicator()
    df["ATR"]      = AverageTrueRange(hi,lo,cl,14).average_true_range()
    df["StochK"]   = StochasticOscillator(hi,lo,cl,14,3).stoch()

    last=df.iloc[-1]; prev=df.iloc[-2]

    # ── Score ─────────────────────────────────────────────────────────────────
    score=0; reasons=[]
    rsi=float(last["RSI"])
    if rsi<32:   score+=3; reasons.append("market is oversold — likely to bounce up")
    elif rsi>68: score-=3; reasons.append("market is overbought — likely to drop soon")
    elif rsi<48: score+=1
    elif rsi>52: score-=1
    if float(prev["MACD"])<float(prev["MACD_sig"]) and float(last["MACD"])>float(last["MACD_sig"]):
        score+=3; reasons.append("momentum just flipped upward — strong buy signal")
    elif float(prev["MACD"])>float(prev["MACD_sig"]) and float(last["MACD"])<float(last["MACD_sig"]):
        score-=3; reasons.append("momentum just flipped downward — strong sell signal")
    elif float(last["MACD_hist"])>0: score+=1
    else: score-=1
    cp=float(last["Close"])
    if cp<float(last["BB_lower"]):   score+=2; reasons.append("price hit a low bounce zone")
    elif cp>float(last["BB_upper"]): score-=2; reasons.append("price hit a high reversal zone")
    if float(last["EMA20"])>float(last["EMA50"]): score+=1.5; reasons.append("short-term trend is up")
    else: score-=1.5; reasons.append("short-term trend is down")
    sk=float(last["StochK"])
    if sk<22:   score+=1.5; reasons.append("price in a deep low zone — buyers step in here")
    elif sk>78: score-=1.5; reasons.append("price in a high zone — sellers come in here")
    atr=float(last["ATR"])

    # ── Decision ──────────────────────────────────────────────────────────────
    if score>=4.0:
        action="BUY"; tp=round(cp+2.5*atr,5); sl=round(cp-1.2*atr,5)
        pp=round((tp-cp)/pip); pr=round((cp-sl)/pip)
    elif score<=-4.0:
        action="SELL"; tp=round(cp-2.5*atr,5); sl=round(cp+1.2*atr,5)
        pp=round((cp-tp)/pip); pr=round((sl-cp)/pip)
    else:
        action="WAIT"; tp=None; sl=round(cp-1.2*atr,5); pp=0; pr=0

    # ── New signal → voice + log ──────────────────────────────────────────────
    if action != "WAIT" and action != st.session_state["last_action"]:
        st.session_state["last_action"] = action
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        st.session_state["trade_log"].append(
            {"time":ts,"action":action,"price":cp,"tp":tp,"sl":sl,
             "pips":pp,"amount":trade_amount,"leverage":leverage})
        if len(st.session_state["trade_log"])>40:
            st.session_state["trade_log"].pop(0)
        if voice_on:
            profit_est = calc_profit(trade_amount, leverage, pp, pip, cp)
            speak("signal",
                  f"{'Buy' if action=='BUY' else 'Sell'} {short_name} now "
                  f"at {cp:.4f}. Target {tp:.4f}. "
                  f"Stop at {sl:.4f}. Estimated profit £{profit_est:.2f}.")
    elif action=="WAIT":
        st.session_state["last_action"] = "WAIT"

    # ── Banner ────────────────────────────────────────────────────────────────
    if action=="BUY":
        bg="#0d2818"; bc="#00e676"; ico="🟢"; hl="BUY NOW"
        glow="0 0 40px rgba(0,230,118,.15)"
    elif action=="SELL":
        bg="#2a0a0a"; bc="#ff1744"; ico="🔴"; hl="SELL NOW"
        glow="0 0 40px rgba(255,23,68,.15)"
    else:
        bg="#111827"; bc="#4b5563"; ico="⏳"; hl="WAIT — DO NOTHING"
        glow="none"

    st.markdown(f"""
    <div class='banner' style='background:{bg};border:2px solid {bc}22;box-shadow:{glow}'>
      <div class='banner-title' style='color:{bc}'>{ico}&nbsp;&nbsp;{hl}</div>
      <div class='banner-sub' style='color:#8892a0'>
        {short_name} &nbsp;·&nbsp; <span style='color:#eceff1;font-weight:600'>{cp:.5f}</span>
        &nbsp;·&nbsp; {datetime.datetime.now().strftime("%H:%M:%S")}
      </div>
    </div>""", unsafe_allow_html=True)

    # ── Price + Cash boxes ────────────────────────────────────────────────────
    if action != "WAIT":
        profit_gbp = calc_profit(trade_amount, leverage, pp, pip, cp)
        loss_gbp   = calc_profit(trade_amount, leverage, pr, pip, cp)

        b1,b2,b3 = st.columns(3)
        act_lbl = "BUY AT" if action=="BUY" else "SELL AT"
        with b1:
            st.markdown(f"""
            <div class='pbox' style='background:rgba(255,255,255,.04);
                 border:1px solid rgba(255,255,255,.1)'>
              <div class='pbox-label' style='color:#8892a0'>{act_lbl}</div>
              <div class='pbox-value' style='color:#f0f4f8'>{cp:.5f}</div>
              <div class='pbox-sub'>Enter trade here</div>
            </div>""", unsafe_allow_html=True)
        with b2:
            st.markdown(f"""
            <div class='pbox' style='background:rgba(0,230,118,.07);
                 border:1px solid rgba(0,230,118,.25)'>
              <div class='pbox-label' style='color:#a5d6a7'>💰 TAKE PROFIT</div>
              <div class='pbox-value' style='color:#00e676'>{tp:.5f}</div>
              <div class='pbox-sub' style='color:#a5d6a7'>+{pp} pips</div>
            </div>""", unsafe_allow_html=True)
        with b3:
            st.markdown(f"""
            <div class='pbox' style='background:rgba(255,23,68,.07);
                 border:1px solid rgba(255,23,68,.25)'>
              <div class='pbox-label' style='color:#ef9a9a'>🛑 STOP LOSS</div>
              <div class='pbox-value' style='color:#ff5252'>{sl:.5f}</div>
              <div class='pbox-sub' style='color:#ef9a9a'>-{pr} pips max</div>
            </div>""", unsafe_allow_html=True)

        # ── Cash profit card ──────────────────────────────────────────────────
        st.markdown(f"""
        <div class='cash-card'>
          <div style='color:#ffd700;font-weight:700;font-size:.85rem;
               letter-spacing:.08em;text-transform:uppercase;margin-bottom:10px'>
            💷 If you trade £{trade_amount:,.0f} with {leverage_label}
          </div>
          <div style='display:flex;gap:20px;flex-wrap:wrap'>
            <div style='flex:1;min-width:140px'>
              <div style='color:#8892a0;font-size:.8rem'>If the trade wins ✅</div>
              <div style='color:#00e676;font-size:1.7rem;font-weight:800'>
                +£{profit_gbp:,.2f}
              </div>
              <div style='color:#a5d6a7;font-size:.8rem'>
                ({pp} pips × £{profit_gbp/pp:.4f}/pip)
              </div>
            </div>
            <div style='width:1px;background:rgba(255,255,255,.08)'></div>
            <div style='flex:1;min-width:140px'>
              <div style='color:#8892a0;font-size:.8rem'>If stop loss hits ❌</div>
              <div style='color:#ff5252;font-size:1.7rem;font-weight:800'>
                -£{loss_gbp:,.2f}
              </div>
              <div style='color:#ef9a9a;font-size:.8rem'>
                ({pr} pips × £{loss_gbp/pr:.4f}/pip)
              </div>
            </div>
            <div style='width:1px;background:rgba(255,255,255,.08)'></div>
            <div style='flex:1;min-width:140px'>
              <div style='color:#8892a0;font-size:.8rem'>Your position size</div>
              <div style='color:#f0f4f8;font-size:1.7rem;font-weight:800'>
                £{trade_amount*leverage:,.0f}
              </div>
              <div style='color:#8892a0;font-size:.8rem'>
                £{trade_amount:,.0f} × {leverage}× leverage
              </div>
            </div>
          </div>
          <div style='margin-top:8px;color:#6b7280;font-size:.75rem'>
            ⚠ Approximate estimate. Actual profit depends on your broker's pip value and currency conversion.
          </div>
        </div>""", unsafe_allow_html=True)

    # ── Plain English ─────────────────────────────────────────────────────────
    why = ", ".join(reasons[:3]) if reasons else "mixed signals"
    if action=="BUY":
        plain=(f"✅ <b>Right now is a good time to BUY {short_name}.</b><br><br>"
               f"The price is at <b>{cp:.5f}</b> and the market looks like it's going <b>UP</b> "
               f"because {why}.<br><br>"
               f"<b>What to do:</b><br>"
               f"🟢 <b>BUY</b> at <b>{cp:.5f}</b><br>"
               f"💰 <b>Close for profit</b> when price hits <b>{tp:.5f}</b> "
               f"— you'd make roughly <b>+£{calc_profit(trade_amount,leverage,pp,pip,cp):,.2f}</b><br>"
               f"🛑 <b>Exit immediately</b> if price drops to <b>{sl:.5f}</b> "
               f"— limits your loss to about <b>-£{calc_profit(trade_amount,leverage,pr,pip,cp):,.2f}</b>")
    elif action=="SELL":
        plain=(f"🔴 <b>Right now is a good time to SELL {short_name}.</b><br><br>"
               f"The price is at <b>{cp:.5f}</b> and the market looks like it's going <b>DOWN</b> "
               f"because {why}.<br><br>"
               f"<b>What to do:</b><br>"
               f"🔴 <b>SELL</b> at <b>{cp:.5f}</b><br>"
               f"💰 <b>Close for profit</b> when price hits <b>{tp:.5f}</b> "
               f"— you'd make roughly <b>+£{calc_profit(trade_amount,leverage,pp,pip,cp):,.2f}</b><br>"
               f"🛑 <b>Exit immediately</b> if price rises to <b>{sl:.5f}</b> "
               f"— limits your loss to about <b>-£{calc_profit(trade_amount,leverage,pr,pip,cp):,.2f}</b>")
    else:
        plain=(f"⏳ <b>Don't trade right now — wait.</b><br><br>"
               f"The price is at <b>{cp:.5f}</b> but it's not safe to trade yet "
               f"because {why}.<br><br>"
               f"✋ <b>Do nothing.</b> Keep your money safe. I'm checking every second "
               f"and will alert you the moment there's a clear signal.")

    st.markdown(f"<div class='plain'>{plain}</div>", unsafe_allow_html=True)

    # ── AI Auto-Watch ─────────────────────────────────────────────────────────
    st.markdown("<hr style='border:none;border-top:1px solid rgba(255,255,255,.07);margin:18px 0'>",
                unsafe_allow_html=True)
    st.markdown("<p style='color:#8892a0;font-size:.85rem;margin-bottom:8px'>"
                "🧠 <b style='color:#eceff1'>AI Auto-Watch</b> — builds a live chart, "
                "reads it visually, gives its own prediction</p>", unsafe_allow_html=True)

    models      = get_ollama_models()
    text_models = [m for m in models if not any(v in m.lower()
                   for v in ["llava","moondream","vision","minicpm"])]
    vis_models  = [m for m in models if any(v in m.lower()
                   for v in ["moondream","llava","vision"])]

    def build_chart(df, name):
        d = df.tail(100).copy()
        fig = make_subplots(rows=3,cols=1,shared_xaxes=True,row_heights=[.6,.2,.2],
                            vertical_spacing=.035,
                            subplot_titles=(f"{name}","RSI","MACD"))
        fig.add_trace(go.Candlestick(x=d.index,open=d["Open"],high=d["High"],
            low=d["Low"],close=d["Close"],name="Price",
            increasing_line_color="#26a69a",decreasing_line_color="#ef5350",
            increasing_fillcolor="#26a69a",decreasing_fillcolor="#ef5350"),row=1,col=1)
        fig.add_trace(go.Scatter(x=d.index,y=d["BB_upper"],name="BB+",
            line=dict(color="#5c6bc0",width=1,dash="dash")),row=1,col=1)
        fig.add_trace(go.Scatter(x=d.index,y=d["BB_lower"],name="BB-",
            line=dict(color="#5c6bc0",width=1,dash="dash"),
            fill="tonexty",fillcolor="rgba(92,107,192,.06)"),row=1,col=1)
        fig.add_trace(go.Scatter(x=d.index,y=d["EMA20"],name="EMA20",
            line=dict(color="#ffb300",width=1.5)),row=1,col=1)
        fig.add_trace(go.Scatter(x=d.index,y=d["EMA50"],name="EMA50",
            line=dict(color="#ff7043",width=1.5)),row=1,col=1)
        fig.add_trace(go.Scatter(x=d.index,y=d["RSI"],name="RSI",
            line=dict(color="#ab47bc",width=1.5)),row=2,col=1)
        for lvl,lc in [(70,"#ef5350"),(50,"#37474f"),(30,"#26a69a")]:
            fig.add_hline(y=lvl,line_color=lc,line_dash="dot",line_width=1,row=2,col=1)
        bc2=["#26a69a" if v>=0 else "#ef5350" for v in d["MACD_hist"]]
        fig.add_trace(go.Bar(x=d.index,y=d["MACD_hist"],marker_color=bc2,opacity=.7),row=3,col=1)
        fig.add_trace(go.Scatter(x=d.index,y=d["MACD"],name="MACD",
            line=dict(color="#42a5f5",width=1.5)),row=3,col=1)
        fig.add_trace(go.Scatter(x=d.index,y=d["MACD_sig"],name="Sig",
            line=dict(color="#ff7043",width=1.5)),row=3,col=1)
        fig.update_layout(template="plotly_dark",height=520,width=1000,
            margin=dict(t=36,b=8,l=50,r=12),xaxis_rangeslider_visible=False,
            paper_bgcolor="#0a0e1a",plot_bgcolor="#0a0e1a",showlegend=False,
            font=dict(size=10,color="#8892a0"))
        fig.update_yaxes(showgrid=True,gridcolor="#1a2030",gridwidth=.5)
        fig.update_xaxes(showgrid=True,gridcolor="#1a2030",gridwidth=.5)
        try: return fig.to_image(format="png",scale=1.5)
        except Exception: return None

    # auto-run when cache key rolls over
    cache_key_now = int(time.time()) // data_refresh_secs
    is_fresh = (cache_key_now != st.session_state["_prev_cache_key"])
    st.session_state["_prev_cache_key"] = cache_key_now

    ac1,ac2 = st.columns([3,1])
    with ac2:
        run_ai = st.button("🔍 Analyse Now", use_container_width=True, key="btn_ai")
    with ac1:
        auto_ai = st.toggle("Auto-analyse on refresh", value=True, key="tog_ai")

    if (run_ai or (auto_ai and is_fresh)) and models:
        import ollama as _oll
        with st.spinner("Building chart…"):
            cb = build_chart(df, short_name)
            if cb: st.session_state["ai_chart"] = cb
        with st.spinner("AI is reading the chart…"):
            visual=""
            if vis_models and st.session_state["ai_chart"]:
                try:
                    r=_oll.chat(model=vis_models[0],messages=[{"role":"user",
                        "content":"Describe this trading chart in 2 sentences. Is the trend UP or DOWN? Start with UP or DOWN.",
                        "images":[base64.standard_b64encode(st.session_state["ai_chart"]).decode()]}],
                        options={"temperature":.1,"num_predict":100})
                    visual=r.message.content.strip()
                except Exception: pass
            if text_models:
                rsi_lbl="oversold—likely UP" if rsi<32 else "overbought—likely DOWN" if rsi>68 else "neutral"
                tr="UP" if float(last["EMA20"])>float(last["EMA50"]) else "DOWN"
                prompt=(f"Trading coach for a beginner. {short_name} at {cp:.5f}. "
                        f"RSI {rsi:.1f} ({rsi_lbl}). Trend {tr}. "
                        f"Reasons: {', '.join(reasons[:3])}. Signal: {action}. "
                        f"TP {tp} (+{pp} pips = ~£{calc_profit(trade_amount,leverage,pp,pip,cp):.2f}). "
                        f"SL {sl}. {f'Chart: {visual}' if visual else ''}\n\n"
                        f"Write 4 plain sentences (no jargon): "
                        f"1.What market is doing 2.Why {action} 3.What to do with prices "
                        f"4.When to exit if wrong")
                try:
                    r=_oll.chat(model=text_models[0],messages=[{"role":"user","content":prompt}],
                                options={"temperature":.2,"num_predict":320})
                    plain_ai=re.sub(r"<think>.*?</think>","",r.message.content,flags=re.DOTALL).strip()
                    st.session_state["ai_result"]={
                        "verdict":action,"plain":plain_ai,"visual":visual,
                        "entry":cp,"tp":tp,"sl":sl,"model":text_models[0],
                        "vis_model":vis_models[0] if vis_models else None,
                        "time":datetime.datetime.now().strftime("%H:%M:%S")}
                except Exception as e:
                    st.session_state["ai_result"]={"verdict":action,"plain":f"AI error: {e}",
                        "visual":visual,"entry":cp,"tp":tp,"sl":sl}
                if (voice_on and st.session_state["ai_result"]["verdict"] in ("BUY","SELL")):
                    v=st.session_state["ai_result"]["verdict"]
                    speak("ai",f"AI confirms: {'buy' if v=='BUY' else 'sell'} {short_name}.")

    res=st.session_state.get("ai_result")
    chart_c, pred_c = st.columns([3,2])
    with chart_c:
        st.markdown("<p style='color:#8892a0;font-size:.8rem;margin-bottom:4px'>"
                    "Live chart — same as what you'd see on any trading platform</p>",
                    unsafe_allow_html=True)
        if st.session_state.get("ai_chart"):
            st.image(st.session_state["ai_chart"], use_container_width=True)
        else:
            st.markdown("<div style='background:rgba(255,255,255,.02);border:1px dashed "
                        "rgba(255,255,255,.1);border-radius:12px;height:160px;display:flex;"
                        "align-items:center;justify-content:center;color:#4b5563'>"
                        "Press 🔍 Analyse Now</div>",unsafe_allow_html=True)
    with pred_c:
        if res:
            v=res["verdict"]
            vc={"BUY":"#00e676","SELL":"#ff1744","WAIT":"#4b5563"}.get(v,"#4b5563")
            bg2={"BUY":"rgba(0,230,118,.08)","SELL":"rgba(255,23,68,.08)",
                 "WAIT":"rgba(255,255,255,.03)"}.get(v,"rgba(255,255,255,.03)")
            ico={"BUY":"🟢","SELL":"🔴","WAIT":"⏳"}.get(v,"⏳")
            st.markdown(f"""
            <div style='background:{bg2};border:1.5px solid {vc}44;border-radius:14px;
                 padding:16px;text-align:center;margin-bottom:10px'>
              <div style='font-size:1.7rem;font-weight:900;color:{vc}'>{ico} {v}</div>
              <div style='color:#8892a0;font-size:.8rem'>
                {res['entry']:.5f} · {res.get('time','')}
              </div>
            </div>""",unsafe_allow_html=True)
            if res.get("tp"):
                m1,m2=st.columns(2)
                m1.metric("💰 Target",f"{res['tp']:.5f}")
                m2.metric("🛑 Stop",  f"{res['sl']:.5f}")
            if res.get("visual"):
                st.markdown(f"<p style='color:#8892a0;font-size:.85rem;margin:8px 0 2px'>"
                            f"👁 What AI sees:</p>"
                            f"<p style='color:#d0d8e8;font-style:italic;font-size:.9rem'>"
                            f"{res['visual']}</p>",unsafe_allow_html=True)
            if res.get("plain"):
                st.markdown(f"<div style='background:rgba(255,255,255,.03);border-radius:10px;"
                            f"padding:12px 14px;color:#d0d8e8;font-size:.9rem;line-height:1.75'>"
                            f"{res['plain']}</div>",unsafe_allow_html=True)
            models_used=[]
            if res.get("vis_model"): models_used.append(res["vis_model"])
            if res.get("model"):     models_used.append(res["model"])
            if models_used:
                st.caption(" · ".join(models_used)+" · free & local · no API key")
        else:
            st.markdown("<div style='background:rgba(255,255,255,.02);border:1px dashed "
                        "rgba(255,255,255,.1);border-radius:12px;height:160px;display:flex;"
                        "align-items:center;justify-content:center;color:#4b5563;text-align:center'>"
                        "AI prediction appears here</div>",unsafe_allow_html=True)

    # ── Advanced details ──────────────────────────────────────────────────────
    with st.expander("🔬 View the signals (advanced)", expanded=False):
        st.dataframe(pd.DataFrame({
            "Signal":  ["RSI","MACD","Bollinger","EMA Trend","Stochastic","Score"],
            "Value":   [f"{rsi:.1f}",
                        "↑ Bullish" if float(last["MACD"])>float(last["MACD_sig"]) else "↓ Bearish",
                        ("Below low zone 🟢" if cp<float(last["BB_lower"])
                         else "Above high zone 🔴" if cp>float(last["BB_upper"]) else "Normal range"),
                        "↑ Uptrend" if float(last["EMA20"])>float(last["EMA50"]) else "↓ Downtrend",
                        ("Oversold 🟢" if sk<22 else "Overbought 🔴" if sk>78 else "Neutral"),
                        f"{score:+.1f} / ±10"],
            "Meaning": ["<30=buy, >70=sell","Crossed up=buy, down=sell",
                        "Bottom zone=price likely goes up","Short above long=going up",
                        "<20=going up, >80=going down","≥+4=BUY · ≤-4=SELL · else=WAIT"],
        }),use_container_width=True,hide_index=True)

# ── Run fragment ──────────────────────────────────────────────────────────────
signal_panel()

# ── Screen capture (static, outside fragment) ────────────────────────────────
st.markdown("<hr style='border:none;border-top:1px solid rgba(255,255,255,.07);margin:20px 0'>",
            unsafe_allow_html=True)
with st.expander("🖥️  Show my live trading screen (optional)", expanded=False):
    models_all = get_ollama_models()
    vis = [m for m in models_all if any(v in m.lower() for v in ["moondream","llava","vision"])]
    sc1,sc2 = st.columns([3,1])
    with sc2:
        if st.button("📸 Capture", key="btn_cap"):
            try:
                with mss.mss() as sct:
                    shot=sct.grab(sct.monitors[1])
                img=Image.frombytes("RGB",shot.size,shot.bgra,"raw","BGRX")
                st.session_state["screen_img"]=img
                if vis:
                    import ollama as _o
                    buf=io.BytesIO()
                    img.resize((1024,int(1024*img.height/img.width)),Image.LANCZOS).save(buf,format="JPEG",quality=70)
                    r=_o.chat(model=vis[0],messages=[{"role":"user",
                        "content":"One sentence starting UP or DOWN: direction of price on this chart?",
                        "images":[base64.standard_b64encode(buf.getvalue()).decode()]}],
                        options={"temperature":.1,"num_predict":60})
                    st.session_state["screen_verdict"]=r.message.content.strip()
            except Exception as e:
                st.error(f"Screen capture error: {e}")
    with sc1:
        if st.session_state["screen_img"]:
            st.image(st.session_state["screen_img"],use_container_width=True)
            v=st.session_state.get("screen_verdict","")
            if v:
                vc2="#00e676" if v.upper().startswith("UP") else "#ff5252"
                st.markdown(f"<div style='background:rgba(0,0,0,.3);border:1.5px solid {vc2};"
                            f"border-radius:8px;padding:8px;text-align:center;"
                            f"color:{vc2};font-weight:700'>{v}</div>",unsafe_allow_html=True)
        else:
            st.markdown("<div style='background:rgba(255,255,255,.02);border:1px dashed "
                        "rgba(255,255,255,.1);border-radius:12px;height:130px;display:flex;"
                        "align-items:center;justify-content:center;color:#4b5563'>"
                        "Click 📸 Capture</div>",unsafe_allow_html=True)

# ── Trade log ─────────────────────────────────────────────────────────────────
st.markdown("<hr style='border:none;border-top:1px solid rgba(255,255,255,.07);margin:20px 0'>",
            unsafe_allow_html=True)
st.markdown("<h4 style='color:#f0f4f8;margin-bottom:12px'>📋 Trading Calls Log</h4>",
            unsafe_allow_html=True)
log = list(reversed(st.session_state["trade_log"]))
if log:
    for e in log:
        c = "#00e676" if e["action"]=="BUY" else "#ff1744"
        amt = e.get("amount", trade_amount)
        lev = e.get("leverage", leverage)
        est = calc_profit(amt, lev, e["pips"], pip_size(ticker_sym), e["price"])
        st.markdown(f"""
        <div class='log-row' style='border-left:3px solid {c}'>
          <div>
            <span style='color:{c};font-weight:700'>
              {'🟢' if e['action']=='BUY' else '🔴'} {e['action']}
            </span>
            <span style='color:#8892a0'> at </span>
            <span style='color:#eceff1;font-weight:600'>{e['price']:.5f}</span>
          </div>
          <div style='text-align:center'>
            <span style='color:#a5d6a7;font-size:.9rem'>
              Target {e['tp']:.5f}
            </span>
            <span style='color:#4b5563'> / </span>
            <span style='color:#ef9a9a;font-size:.9rem'>
              Stop {e['sl']:.5f}
            </span>
          </div>
          <div style='text-align:right'>
            <span style='color:#00e676;font-weight:700'>+£{est:.2f}</span>
            <span style='color:#4b5563;font-size:.8rem'> est · {e['time']}</span>
          </div>
        </div>""", unsafe_allow_html=True)
else:
    st.markdown("<div style='background:rgba(255,255,255,.02);border:1px dashed "
                "rgba(255,255,255,.08);border-radius:12px;padding:20px;text-align:center;"
                "color:#4b5563'>No signals yet — the app is watching and will log every call automatically</div>",
                unsafe_allow_html=True)

st.markdown("<p style='color:#374151;font-size:.75rem;text-align:center;margin-top:16px'>"
            "⚠ Educational tool only · All trading carries risk · "
            "Never trade money you cannot afford to lose</p>",
            unsafe_allow_html=True)
