"""
FX Pro Trader — Apple Edition v3
- Zero-blink: every dynamic section runs inside @st.fragment
- All 10 pairs: parallel scan with retry + graceful fallback
- 9-indicator AI engine: RSI · MACD · Bollinger · EMA · Stochastic · ADX ·
  Candlestick patterns · Volume · News sentiment
- Interactive Plotly charts that refresh in-place without flash
- Always-on: LaunchAgent local + GitHub Actions keep-alive
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time, datetime, subprocess, platform, requests
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from zoneinfo import ZoneInfo

# ── UK timezone (auto-handles GMT ↔ BST switchover) ──────────────────────────
UK_TZ = ZoneInfo("Europe/London")

# ── platform guards ───────────────────────────────────────────────────────────
IS_MAC = platform.system() == "Darwin"
try:    import mss as _mss;     HAS_MSS     = True
except: HAS_MSS = False  # noqa
try:    import ollama as _ol;   HAS_OLLAMA  = True
except: HAS_OLLAMA = False  # noqa
try:    import kaleido;         HAS_KALEIDO = True  # noqa
except: HAS_KALEIDO = False  # noqa

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="FX Pro", page_icon="◈",
                   layout="wide", initial_sidebar_state="collapsed")

# ══════════════════════════════════════════════════════════════════════════════
#  DESIGN SYSTEM — Apple-grade CSS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
*{box-sizing:border-box;}
html,body,[class*="css"]{
  font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display','Inter','Helvetica Neue',sans-serif;
  -webkit-font-smoothing:antialiased;
}
.stApp{background:#000000!important;color:#ffffff;}
.block-container{padding:0 2rem 4rem!important;max-width:1440px!important;}
section[data-testid="stSidebar"],div[data-testid="stToolbar"],
#MainMenu,footer,header{display:none!important;visibility:hidden!important;}

/* tabs */
.stTabs [data-baseweb="tab-list"]{gap:3px;background:rgba(255,255,255,.05);padding:5px;border-radius:14px;border:1px solid rgba(255,255,255,.07);}
.stTabs [data-baseweb="tab"]{border-radius:10px;padding:9px 22px;color:rgba(255,255,255,.45);font-weight:500;font-size:.87rem;letter-spacing:.01em;}
.stTabs [aria-selected="true"]{background:rgba(255,255,255,.11)!important;color:#fff!important;}
/* remove tab underline flash */
.stTabs [data-baseweb="tab-highlight"]{display:none!important;}

/* expander */
.streamlit-expanderHeader{background:rgba(255,255,255,.04)!important;border:1px solid rgba(255,255,255,.08)!important;border-radius:12px!important;color:rgba(255,255,255,.65)!important;font-size:.86rem;}
.streamlit-expanderContent{background:rgba(255,255,255,.02)!important;border:1px solid rgba(255,255,255,.06)!important;border-top:none!important;border-radius:0 0 12px 12px!important;}

/* buttons */
.stButton>button{background:rgba(255,255,255,.09)!important;border:1px solid rgba(255,255,255,.14)!important;border-radius:12px!important;color:#fff!important;font-weight:500!important;transition:all .18s!important;}
.stButton>button:hover{background:rgba(255,255,255,.16)!important;transform:translateY(-1px)!important;}
.stButton>button[kind="primary"]{background:linear-gradient(135deg,#0a84ff,#5e5ce6)!important;border:none!important;}
.stButton>button[kind="primary"]:hover{opacity:.88!important;box-shadow:0 6px 24px rgba(10,132,255,.32)!important;}

/* inputs */
.stSelectbox>div>div,.stNumberInput input{background:rgba(255,255,255,.06)!important;border:1px solid rgba(255,255,255,.1)!important;border-radius:10px!important;color:#fff!important;}
.stSelectbox [data-baseweb="select"] *{background:#1c1c1e!important;color:#fff!important;}
.stSelectbox [data-baseweb="popover"] *{background:#1c1c1e!important;}
[data-testid="stFileUploader"]{background:rgba(255,255,255,.03)!important;border:2px dashed rgba(255,255,255,.11)!important;border-radius:16px!important;}

/* plotly charts — prevent flash on re-render */
.js-plotly-plot .plotly{transition:none!important;}
iframe{border:none!important;}

/* scrollbar */
::-webkit-scrollbar{width:4px;height:4px}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,.12);border-radius:4px}

hr{border:none;border-top:1px solid rgba(255,255,255,.06)!important;margin:1.5rem 0!important;}

/* ── HERO ── */
.hero{background:linear-gradient(155deg,rgba(28,28,30,.97),rgba(44,44,46,.65));
  backdrop-filter:blur(40px);-webkit-backdrop-filter:blur(40px);
  border:1px solid rgba(255,255,255,.09);border-radius:26px;
  padding:40px 44px;position:relative;overflow:hidden;margin-bottom:1.5rem;}
.hero::after{content:'';position:absolute;inset:0;border-radius:26px;
  background:linear-gradient(145deg,rgba(255,255,255,.04),transparent 55%);pointer-events:none;}
.hero-buy{border-color:rgba(48,209,88,.28)!important;box-shadow:0 0 60px rgba(48,209,88,.07)!important;}
.hero-sell{border-color:rgba(255,69,58,.28)!important;box-shadow:0 0 60px rgba(255,69,58,.07)!important;}
.hero-wait{border-color:rgba(255,214,10,.18)!important;}
.hero-eyebrow{font-size:.68rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:rgba(255,255,255,.35);margin-bottom:10px;}
.hero-action{font-size:4.2rem;font-weight:900;letter-spacing:-.04em;line-height:1;}
.action-buy{color:#30d158;} .action-sell{color:#ff453a;} .action-wait{color:#ffd60a;}
.hero-pair{font-size:1.45rem;font-weight:700;color:#fff;margin-top:6px;}
.hero-why{font-size:.85rem;color:rgba(255,255,255,.5);margin-top:10px;line-height:1.65;max-width:580px;}
.hero-stats{display:flex;gap:28px;margin-top:22px;flex-wrap:wrap;}
.hstat{display:flex;flex-direction:column;gap:3px;}
.hstat-val{font-size:1.1rem;font-weight:700;color:#fff;font-variant-numeric:tabular-nums;}
.hstat-lbl{font-size:.68rem;color:rgba(255,255,255,.3);text-transform:uppercase;letter-spacing:.08em;}
.conf-badge{position:absolute;top:22px;right:24px;border-radius:20px;padding:5px 14px;font-size:.77rem;font-weight:700;}
.conf-buy{background:rgba(48,209,88,.14);border:1px solid rgba(48,209,88,.28);color:#30d158;}
.conf-sell{background:rgba(255,69,58,.14);border:1px solid rgba(255,69,58,.28);color:#ff453a;}
.conf-wait{background:rgba(255,214,10,.1);border:1px solid rgba(255,214,10,.2);color:#ffd60a;}

/* ── SIGNAL CARDS ── */
.scard{background:rgba(28,28,30,.78);backdrop-filter:blur(16px);
  border:1px solid rgba(255,255,255,.07);border-radius:18px;
  padding:18px 20px;margin-bottom:10px;position:relative;overflow:hidden;}
.scard::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;border-radius:18px 18px 0 0;}
.scard-buy{border-color:rgba(48,209,88,.18);} .scard-buy::before{background:linear-gradient(90deg,#30d158,transparent);}
.scard-sell{border-color:rgba(255,69,58,.18);} .scard-sell::before{background:linear-gradient(90deg,#ff453a,transparent);}
.scard-wait{border-color:rgba(255,214,10,.12);} .scard-wait::before{background:linear-gradient(90deg,#ffd60a,transparent);}
.scard-dead{opacity:.42;}
.sact-buy{font-size:1.7rem;font-weight:900;color:#30d158;letter-spacing:-.02em;}
.sact-sell{font-size:1.7rem;font-weight:900;color:#ff453a;letter-spacing:-.02em;}
.sact-wait{font-size:1.7rem;font-weight:900;color:#ffd60a;letter-spacing:-.02em;}
.spair{font-size:.95rem;font-weight:700;color:#fff;}
.sbar-bg{background:rgba(255,255,255,.07);height:3px;border-radius:3px;overflow:hidden;margin:8px 0;}
.sbar-buy{background:#30d158;height:3px;border-radius:3px;}
.sbar-sell{background:#ff453a;height:3px;border-radius:3px;}
.sbar-wait{background:#ffd60a;height:3px;border-radius:3px;}
.stg{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:10px;}
.stg-i{background:rgba(255,255,255,.04);border-radius:10px;padding:8px 10px;}
.stg-v{font-size:.82rem;font-weight:700;color:#fff;font-variant-numeric:tabular-nums;}
.stg-l{font-size:.65rem;color:rgba(255,255,255,.3);text-transform:uppercase;letter-spacing:.06em;margin-top:2px;}
.pill{display:inline-block;border-radius:20px;padding:2px 9px;font-size:.7rem;font-weight:600;margin-right:3px;}
.pill-bull{background:rgba(48,209,88,.12);color:#30d158;border:1px solid rgba(48,209,88,.22);}
.pill-bear{background:rgba(255,69,58,.12);color:#ff453a;border:1px solid rgba(255,69,58,.22);}
.pill-neu{background:rgba(255,255,255,.07);color:rgba(255,255,255,.45);border:1px solid rgba(255,255,255,.1);}
.cd{display:inline-flex;align-items:center;gap:4px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.09);border-radius:16px;padding:2px 9px;font-size:.7rem;color:rgba(255,255,255,.45);}

/* ── TICKER STRIP ── */
.tstrip{display:flex;gap:20px;overflow-x:auto;padding:10px 16px;
  background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);
  border-radius:12px;margin-bottom:20px;white-space:nowrap;scrollbar-width:none;}
.tstrip::-webkit-scrollbar{display:none;}
.ti{display:inline-flex;flex-direction:column;gap:1px;min-width:78px;}
.ti-sym{font-size:.68rem;color:rgba(255,255,255,.3);font-weight:600;letter-spacing:.04em;}
.ti-pr{font-size:.9rem;font-weight:700;color:#fff;font-variant-numeric:tabular-nums;}
.ti-up{font-size:.68rem;color:#30d158;font-weight:600;}
.ti-dn{font-size:.68rem;color:#ff453a;font-weight:600;}

/* ── NEWS ── */
.ncard{background:rgba(28,28,30,.55);border:1px solid rgba(255,255,255,.06);border-radius:14px;padding:14px 16px;margin-bottom:7px;}
.ntitle{font-size:.87rem;font-weight:600;color:#fff;line-height:1.45;}
.nmeta{font-size:.69rem;color:rgba(255,255,255,.3);margin-top:5px;}

/* ── EVENTS ── */
.ev{background:rgba(255,255,255,.03);border-left:3px solid;border-radius:0 12px 12px 0;padding:9px 13px;margin-bottom:7px;}
.ev-hi{border-color:#ff453a;} .ev-me{border-color:#ff9f0a;} .ev-lo{border-color:rgba(255,255,255,.18);}
.ev-t{font-size:.85rem;font-weight:600;color:#fff;}
.ev-m{font-size:.69rem;color:rgba(255,255,255,.35);margin-top:3px;}

/* ── PLATFORM GUIDE ── */
.ph{border-radius:12px 12px 0 0;padding:11px 16px;font-size:.83rem;font-weight:700;letter-spacing:.02em;}
.ph-mt{background:#1c237e;color:#82b1ff;}
.ph-tv{background:#131722;color:#b2b5be;border-top:1px solid rgba(255,255,255,.1);}
.ph-ig{background:#003087;color:#5b9bd5;}
.steps{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);border-radius:0 0 12px 12px;padding:16px 18px;}
.step{display:flex;gap:12px;margin-bottom:12px;align-items:flex-start;}
.snum{min-width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.74rem;font-weight:700;flex-shrink:0;}
.snum-mt{background:rgba(130,177,255,.2);color:#82b1ff;}
.snum-tv{background:rgba(38,166,154,.2);color:#26a69a;}
.snum-ig{background:rgba(91,155,213,.2);color:#5b9bd5;}
.stxt{font-size:.84rem;color:rgba(255,255,255,.72);line-height:1.55;}
.pt{display:inline-block;border-radius:5px;padding:1px 6px;font-family:monospace;font-size:.82rem;font-weight:600;}
.pt-e{background:rgba(255,214,10,.12);color:#ffd60a;}
.pt-tp{background:rgba(48,209,88,.14);color:#30d158;}
.pt-sl{background:rgba(255,69,58,.14);color:#ff453a;}

/* ── CONFIRM ── */
.cok{background:rgba(48,209,88,.07);border:1px solid rgba(48,209,88,.28);border-radius:14px;padding:18px;}
.cfail{background:rgba(255,69,58,.07);border:1px solid rgba(255,69,58,.28);border-radius:14px;padding:18px;}

/* ── METRIC CARDS ── */
.mc{background:rgba(28,28,30,.8);border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:14px 16px;text-align:center;}
.mc-v{font-size:1.4rem;font-weight:800;letter-spacing:-.02em;}
.mc-l{font-size:.68rem;color:rgba(255,255,255,.3);text-transform:uppercase;letter-spacing:.06em;margin-top:4px;}

/* ── INTEL ── */
.intel{background:rgba(10,132,255,.07);border:1px solid rgba(10,132,255,.2);border-radius:14px;padding:14px 16px;margin-bottom:10px;}
.intel-lbl{font-size:.67rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#0a84ff;margin-bottom:6px;}

/* ── NO opacity/visibility animations — they cause visible blink on fragment refresh ── */
.scanning{color:rgba(255,255,255,.45);}
.fade{opacity:1;}
/* live dot — static glow, no flicker */
.ldot{display:inline-block;width:7px;height:7px;border-radius:50%;
      background:#30d158;box-shadow:0 0 7px rgba(48,209,88,.55);margin-right:5px;}

/* ── chart toolbar ── */
.chart-toolbar{display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap;}
.ct-label{font-size:.7rem;color:rgba(255,255,255,.28);text-transform:uppercase;letter-spacing:.08em;margin-right:4px;}

/* ── section headings ── */
.eyebrow{font-size:.67rem;font-weight:700;letter-spacing:.13em;text-transform:uppercase;color:rgba(255,255,255,.28);margin-bottom:5px;}
.stitle{font-size:1.55rem;font-weight:800;letter-spacing:-.03em;color:#fff;margin-bottom:3px;}
.ssub{font-size:.87rem;color:rgba(255,255,255,.38);margin-bottom:18px;}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
PAIRS = {
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X", "GBP/JPY": "GBPJPY=X",
    "AUD/USD": "AUDUSD=X", "USD/CAD": "USDCAD=X",
    "USD/CHF": "USDCHF=X", "NZD/USD": "NZDUSD=X",
    "EUR/GBP": "EURGBP=X", "EUR/JPY": "EURJPY=X",
}
TIMEFRAMES = {
    "1 min  · Scalping":     ("1m",  "5d",   60),
    "5 min  · Recommended":  ("5m",  "5d",  300),
    "15 min · Swing Prep":   ("15m", "5d",  900),
    "1 hour · Swing":        ("1h", "30d", 3600),
}
LEVERAGE_MAP = {
    "1:1  No leverage":   1, "1:10  Low":      10,
    "1:30  Medium":      30, "1:100  High":   100, "1:500  Very high": 500,
}
TP_PIPS = {"20 pips  Conservative": 20, "35 pips  Standard": 35, "60 pips  Aggressive": 60}
SL_PIPS = {"15 pips  Tight": 15, "25 pips  Standard": 25, "40 pips  Wide": 40}

# currency → which pairs it most influences
CURRENCY_PAIRS = {
    "USD": ["EUR/USD","GBP/USD","USD/JPY","AUD/USD","USD/CAD","USD/CHF","NZD/USD"],
    "EUR": ["EUR/USD","EUR/GBP","EUR/JPY"],
    "GBP": ["GBP/USD","GBP/JPY","EUR/GBP"],
    "JPY": ["USD/JPY","GBP/JPY","EUR/JPY"],
    "AUD": ["AUD/USD"], "CAD": ["USD/CAD"],
    "CHF": ["USD/CHF"], "NZD": ["NZD/USD"],
}
NEWS_FEEDS = [
    "https://www.forexlive.com/feed/",
    "https://www.fxstreet.com/rss/news",
    "https://feeds.feedburner.com/forexlive/UDcL",
]
ECON_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

BULL_WORDS = {
    "rise","rises","rose","gain","gains","gained","rally","rallied","surge","surged",
    "jump","jumped","bull","bullish","strong","strengthen","high","higher","growth",
    "beat","exceeded","boost","hawkish","hike","optimism","recovery","expansion",
    "above forecast","better than expected","robust","buying","demand","confidence",
}
BEAR_WORDS = {
    "fall","falls","fell","drop","drops","dropped","decline","declined","plunge","plunged",
    "bear","bearish","weak","weaken","low","lower","recession","miss","missed",
    "disappoint","cut","dovish","slowdown","contraction","concern","uncertainty",
    "below forecast","worse than expected","selling","caution","fear","worry","crisis",
}

# ══════════════════════════════════════════════════════════════════════════════
#  SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
for _k, _v in [("signals",{}),("last_scan",0),("trigger_scan",False),
               ("rev_hero",0),("rev_mt",0),("rev_tv",0),("rev_ig",0),
               ("drag_hero","pan"),("drag_mt","pan"),("drag_tv","pan"),("drag_ig","pan"),
               ("voice_muted", False)]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def pip_size(sym):
    return 0.01 if "JPY" in sym else 0.0001

def calc_profit(amount, lev, pips, ps, price):
    pos = amount * lev
    return (pos * pips * ps / price) if ps == 0.01 else (pos * pips * ps)

def speak(key, text):
    if not IS_MAC: return
    if st.session_state.get("voice_muted", False): return
    if text != st.session_state.get(f"_spoke_{key}", ""):
        st.session_state[f"_spoke_{key}"] = text
        try:
            subprocess.Popen(["say", "-r", "175", text],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception: pass

def fmt_cd(issued_at, valid_secs):
    rem = max(0, valid_secs - (time.time() - issued_at))
    if rem == 0: return "Expired"
    m, s = divmod(int(rem), 60)
    return f"{m}m {s:02d}s" if m else f"{s}s"

def expired(issued_at, valid_secs):
    return (time.time() - issued_at) >= valid_secs

def sent_score(text):
    t = text.lower()
    b = sum(1 for w in BULL_WORDS if w in t)
    s = sum(1 for w in BEAR_WORDS if w in t)
    return min(5, max(-5, b - s))

# ══════════════════════════════════════════════════════════════════════════════
#  INTERNET INTELLIGENCE  (cached)
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300, show_spinner=False)
def fetch_news():
    arts = []
    for url in NEWS_FEEDS:
        try:
            r = requests.get(url, timeout=6,
                             headers={"User-Agent": "FXProTrader/3.0"})
            root = ET.fromstring(r.text)
            for item in list(root.iter("item"))[:8]:
                t = item.findtext("title","").strip()
                d = item.findtext("description","").strip()[:180]
                if t:
                    arts.append({
                        "title": t, "desc": d,
                        "source": url.split("/")[2].replace("www.",""),
                        "score": sent_score(t+" "+d),
                    })
        except Exception:
            pass
    # yfinance news as bonus source
    try:
        for n in (yf.Ticker("EURUSD=X").news or [])[:5]:
            ti = n.get("title",""); s = n.get("summary","")
            if ti:
                arts.append({"title":ti,"desc":s[:180],"source":"Yahoo Finance",
                             "score":sent_score(ti+" "+s)})
    except Exception:
        pass
    seen, out = set(), []
    for a in arts:
        k = a["title"][:40]
        if k not in seen: seen.add(k); out.append(a)
    return out[:22]

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_calendar():
    try:
        r = requests.get(ECON_URL, timeout=8,
                         headers={"User-Agent":"FXProTrader/3.0"})
        now    = datetime.datetime.now(datetime.timezone.utc)
        evs    = []
        for ev in r.json():
            try:
                # parse as UTC, then convert to UK time (GMT or BST)
                dt_utc = datetime.datetime.fromisoformat(
                    ev.get("date","").replace("Z","")
                ).replace(tzinfo=datetime.timezone.utc)
                dt = dt_utc.astimezone(UK_TZ)
                if dt_utc >= now - datetime.timedelta(hours=2):
                    tz_lbl = dt.strftime("%Z")   # "GMT" or "BST"
                    evs.append({
                        "time": f"{dt.strftime('%H:%M')} {tz_lbl}",
                        "currency": ev.get("country","").upper(),
                        "event": ev.get("title",""),
                        "impact": ev.get("impact","low").lower(),
                        "forecast": ev.get("forecast",""),
                        "previous": ev.get("previous",""),
                        "dt": dt,
                    })
            except Exception: pass
        return sorted(evs, key=lambda x: x["dt"])[:15]
    except Exception:
        return []

def build_pair_sentiment(news):
    scores = {p: 0.0 for p in PAIRS}
    for a in news:
        text = (a["title"]+" "+a["desc"]).upper()
        sc   = a["score"]
        for ccy, pairs in CURRENCY_PAIRS.items():
            if ccy in text:
                for p in pairs:
                    # USD bearish → EUR/USD bullish (USD is quote on EUR/USD)
                    base, quote = p.split("/")
                    if ccy == base:   scores[p] += sc
                    elif ccy == quote: scores[p] -= sc * 0.7
    return {p: round(max(-5, min(5, v)), 1) for p, v in scores.items()}

# ══════════════════════════════════════════════════════════════════════════════
#  MARKET DATA  (cached)
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=55, show_spinner=False)
def fetch_df(yf_sym, interval, period):
    """Fetch OHLCV with 1 retry on failure."""
    for attempt in range(2):
        try:
            df = yf.download(yf_sym, interval=interval, period=period,
                             auto_adjust=True, progress=False, timeout=15)
            if df.empty or len(df) < 40:
                time.sleep(1)
                continue
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            df = df[["Open","High","Low","Close","Volume"]].dropna()
            if len(df) >= 40:
                return df
        except Exception:
            time.sleep(1)
    return None

@st.cache_data(ttl=20, show_spinner=False)
def live_price(yf_sym):
    try:
        fi = yf.Ticker(yf_sym).fast_info
        p = float(fi.last_price)
        c = float(getattr(fi, "regular_market_change_percent", 0) or 0)
        return p, c
    except Exception:
        return None, None

# ══════════════════════════════════════════════════════════════════════════════
#  9-INDICATOR AI ENGINE
# ══════════════════════════════════════════════════════════════════════════════
def detect_candle_patterns(df):
    """Recognise the 6 most reliable candlestick reversal patterns."""
    patterns, score = [], 0
    o = df["Open"]; h = df["High"]; l = df["Low"]; c = df["Close"]
    if len(df) < 3: return patterns, score

    o1,h1,lo1,c1 = float(o.iloc[-2]),float(h.iloc[-2]),float(l.iloc[-2]),float(c.iloc[-2])
    o2,h2,lo2,c2 = float(o.iloc[-1]),float(h.iloc[-1]),float(l.iloc[-1]),float(c.iloc[-1])
    body1, body2 = abs(c1-o1), abs(c2-o2)
    lo_wick2 = min(o2,c2)-lo2
    hi_wick2 = h2-max(o2,c2)

    # Bullish engulfing
    if c1<o1 and c2>o2 and o2<=c1 and c2>=o1:
        patterns.append("Bullish engulfing"); score+=2
    # Bearish engulfing
    elif c1>o1 and c2<o2 and o2>=c1 and c2<=o1:
        patterns.append("Bearish engulfing"); score-=2
    # Hammer (bullish reversal)
    if lo_wick2>2*max(body2,0.0001) and hi_wick2<body2*0.6 and c2>o2:
        patterns.append("Hammer"); score+=1
    # Shooting star (bearish reversal)
    if hi_wick2>2*max(body2,0.0001) and lo_wick2<body2*0.6 and c2<o2:
        patterns.append("Shooting star"); score-=1
    # Bullish Doji at low (indecision → possible reversal up)
    if body2 < (h2-lo2)*0.12 and lo2==min(float(l.iloc[-3]),lo1,lo2):
        patterns.append("Doji at low"); score+=1
    # Bearish Doji at high
    if body2 < (h2-lo2)*0.12 and h2==max(float(h.iloc[-3]),h1,h2):
        patterns.append("Doji at high"); score-=1

    return patterns, max(-3, min(3, score))

def calc_adx(df, period=14):
    """Average Directional Index — measures trend strength (0-100)."""
    h,l,c = df["High"],df["Low"],df["Close"]
    tr  = pd.concat([(h-l),(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    dmp = h.diff().clip(lower=0)
    dmn = (-l.diff()).clip(lower=0)
    dmp = dmp.where(dmp>(-l.diff()).clip(lower=0),0)
    dmn = dmn.where(dmn>(h.diff()).clip(lower=0),0)
    atr_s = tr.rolling(period).mean().replace(0,np.nan)
    dip   = 100*dmp.rolling(period).mean()/atr_s
    din   = 100*dmn.rolling(period).mean()/atr_s
    dx    = 100*(dip-din).abs()/(dip+din).replace(0,np.nan)
    adx   = dx.rolling(period).mean()
    v = float(adx.iloc[-1]) if not np.isnan(adx.iloc[-1]) else 18
    return max(0, min(100, v))

def score_technicals(df, sym):
    """
    9-indicator engine.  Returns a score in [-10, +10], action, reasons, etc.

    Indicators  (max raw contribution):
      1. RSI-14              ±3
      2. MACD crossover       ±3
      3. Bollinger Bands      ±2
      4. EMA stack 20/50/200  ±2
      5. Stochastic K/D       ±2
      6. Candlestick patterns ±3
      7. Volume confirmation  ±1
      8. ADX strength multiplier (1.0–1.35)
      9. Price-action (HH/LL) ±1
    """
    c, h, lo = df["Close"], df["High"], df["Low"]
    raw, reasons = 0, []

    # ── 1. RSI ────────────────────────────────────────────────────────────────
    delta = c.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rsi_s = gain / loss.replace(0, np.nan)
    rsi   = 100 - 100/(1+rsi_s)
    rsi_v = float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else 50
    if   rsi_v < 28: raw+=3; reasons.append(f"RSI deeply oversold ({rsi_v:.0f})")
    elif rsi_v < 38: raw+=2; reasons.append(f"RSI oversold ({rsi_v:.0f})")
    elif rsi_v < 46: raw+=1
    elif rsi_v > 72: raw-=3; reasons.append(f"RSI deeply overbought ({rsi_v:.0f})")
    elif rsi_v > 62: raw-=2; reasons.append(f"RSI overbought ({rsi_v:.0f})")
    elif rsi_v > 55: raw-=1

    # ── 2. MACD ───────────────────────────────────────────────────────────────
    ema12 = c.ewm(span=12,adjust=False).mean()
    ema26 = c.ewm(span=26,adjust=False).mean()
    macd  = ema12 - ema26
    sig9  = macd.ewm(span=9,adjust=False).mean()
    hist  = macd - sig9
    if len(macd)>=2:
        cross_up   = macd.iloc[-1]>sig9.iloc[-1] and macd.iloc[-2]<=sig9.iloc[-2]
        cross_down = macd.iloc[-1]<sig9.iloc[-1] and macd.iloc[-2]>=sig9.iloc[-2]
        if   cross_up:   raw+=3; reasons.append("MACD bullish crossover")
        elif cross_down: raw-=3; reasons.append("MACD bearish crossover")
        elif macd.iloc[-1]>sig9.iloc[-1] and float(hist.iloc[-1])>float(hist.iloc[-2]):
            raw+=1; reasons.append("MACD histogram growing")
        elif macd.iloc[-1]<sig9.iloc[-1] and float(hist.iloc[-1])<float(hist.iloc[-2]):
            raw-=1; reasons.append("MACD histogram shrinking")

    # ── 3. Bollinger Bands ────────────────────────────────────────────────────
    sma20 = c.rolling(20).mean()
    std20 = c.rolling(20).std()
    bup   = sma20+2*std20; bdn = sma20-2*std20
    price = float(c.iloc[-1])
    bup_v = float(bup.iloc[-1]); bdn_v = float(bdn.iloc[-1])
    bw    = (bup_v - bdn_v) / float(sma20.iloc[-1])   # band width
    if   bdn_v>0 and price<=bdn_v:  raw+=2; reasons.append("Price at lower Bollinger Band")
    elif bup_v>0 and price>=bup_v:  raw-=2; reasons.append("Price at upper Bollinger Band")
    # squeeze then break — higher confidence
    if bw < 0.01 and price>float(sma20.iloc[-1]): raw+=1
    elif bw < 0.01 and price<float(sma20.iloc[-1]): raw-=1

    # ── 4. EMA stack ──────────────────────────────────────────────────────────
    e20  = float(c.ewm(span=20, adjust=False).mean().iloc[-1])
    e50  = float(c.ewm(span=50, adjust=False).mean().iloc[-1])
    e200 = float(c.ewm(span=200,adjust=False).mean().iloc[-1])
    if   e20>e50>e200: raw+=2; reasons.append("EMA uptrend (20>50>200)")
    elif e20>e50>0:    raw+=1
    elif e20<e50<e200: raw-=2; reasons.append("EMA downtrend (20<50<200)")
    elif e20<e50:      raw-=1
    # price vs EMA200 — long-term bias
    if   price>e200*1.001: raw+=1
    elif price<e200*0.999: raw-=1

    # ── 5. Stochastic K/D ─────────────────────────────────────────────────────
    low14  = lo.rolling(14).min()
    high14 = h.rolling(14).max()
    denom  = (high14-low14).replace(0,np.nan)
    k_line = 100*(c-low14)/denom
    d_line = k_line.rolling(3).mean()
    try:
        kv = float(k_line.iloc[-1]); dv = float(d_line.iloc[-1])
        kv_prev = float(k_line.iloc[-2]); dv_prev = float(d_line.iloc[-2])
    except Exception:
        kv=dv=kv_prev=dv_prev=50
    if   kv<20 and dv<20 and kv>kv_prev: raw+=2; reasons.append("Stochastic oversold crossover")
    elif kv<25:                           raw+=1
    elif kv>80 and dv>80 and kv<kv_prev: raw-=2; reasons.append("Stochastic overbought crossover")
    elif kv>75:                           raw-=1

    # ── 6. Candlestick patterns ───────────────────────────────────────────────
    pats, pat_score = detect_candle_patterns(df)
    raw += pat_score
    if pats: reasons.extend(pats)

    # ── 7. Volume confirmation ────────────────────────────────────────────────
    try:
        vol    = df["Volume"].replace(0, np.nan)
        vol_ma = float(vol.rolling(20).mean().iloc[-1])
        vol_v  = float(vol.iloc[-1])
        last_bull = float(c.iloc[-1]) > float(df["Open"].iloc[-1])
        if vol_v > vol_ma*1.5:
            if last_bull:  raw+=1; reasons.append("High volume on bullish candle")
            else:          raw-=1; reasons.append("High volume on bearish candle")
    except Exception: pass

    # ── 8. ADX — trend strength multiplier ───────────────────────────────────
    adx_v = calc_adx(df)
    if   adx_v>35: mult=1.35; reasons.append(f"Strong trend (ADX {adx_v:.0f})")
    elif adx_v>25: mult=1.15
    elif adx_v<18: mult=0.80  # ranging market, reduce conviction
    else:          mult=1.0

    # ── 9. Price action (higher highs / lower lows over last 5 candles) ───────
    try:
        last5_h = df["High"].iloc[-5:].values
        last5_l = df["Low"].iloc[-5:].values
        if all(last5_h[i]>=last5_h[i-1] for i in range(1,5)): raw+=1; reasons.append("5-candle HH streak")
        elif all(last5_l[i]<=last5_l[i-1] for i in range(1,5)): raw-=1; reasons.append("5-candle LL streak")
    except Exception: pass

    # ── normalise ─────────────────────────────────────────────────────────────
    raw_f = raw * mult
    score = int(max(-10, min(10, raw_f)))

    # ── ATR-based dynamic TP/SL ───────────────────────────────────────────────
    tr   = pd.concat([(h-lo),(h-c.shift()).abs(),(lo-c.shift()).abs()],axis=1).max(axis=1)
    atr  = float(tr.rolling(14).mean().iloc[-1])
    ps   = pip_size(sym)
    tp_p = max(15, min(90, round(atr/ps * 1.6)))
    sl_p = max(10, min(55, round(atr/ps * 1.0)))

    if   score>=4:  action="BUY";  tp=price+tp_p*ps; sl=price-sl_p*ps
    elif score<=-4: action="SELL"; tp=price-tp_p*ps; sl=price+sl_p*ps
    else:           action="WAIT"; tp=price+tp_p*ps; sl=price-sl_p*ps

    return action, score, price, tp, sl, tp_p, sl_p, rsi_v, reasons, adx_v

def scan_one(pair, yf_sym, interval, period, valid_secs, tf_label, news_sent):
    df = fetch_df(yf_sym, interval, period)
    if df is None:
        return pair, None
    action, tech, entry, tp, sl, tp_p, sl_p, rsi_v, reasons, adx_v = \
        score_technicals(df, pair)
    ns  = news_sent.get(pair, 0)
    # news adds max ±2 to final score
    combined = max(-10, min(10, tech + round(ns * 0.4)))
    if   combined>=4:  final="BUY"
    elif combined<=-4: final="SELL"
    else:              final="WAIT"
    # confidence: how many indicators agree? scale to 40–97%
    conf = min(97, max(40, int(abs(combined)/10*57 + 40)))
    return pair, {
        "action":final,"tech":tech,"news_score":ns,"combined":combined,
        "confidence":conf,"entry":entry,"tp":tp,"sl":sl,
        "tp_pips":tp_p,"sl_pips":sl_p,"rsi":rsi_v,"adx":adx_v,
        "reasons":reasons,"issued_at":time.time(),
        "valid_secs":valid_secs,"tf_label":tf_label,"df":df,
    }

# ══════════════════════════════════════════════════════════════════════════════
#  CHART BUILDER — interactive Plotly, platform themes
# ══════════════════════════════════════════════════════════════════════════════
def build_chart(df, pair, action, entry, tp, sl, theme="dark", uirev="1", dragmode="pan"):
    palettes = {
        "dark":        dict(bg="#000000",bg2="rgba(0,0,0,0.82)",
                            grid="#1a1a1a",up="#30d158",dn="#ff453a",
                            tp_c="#30d158",sl_c="#ff453a",en_c="#ffd60a",txt="#ffffff"),
        "metatrader":  dict(bg="#131722",bg2="rgba(19,23,34,0.88)",
                            grid="#1e2230",up="#26a69a",dn="#ef5350",
                            tp_c="#26a69a",sl_c="#ef5350",en_c="#2962ff",txt="#b2b5be"),
        "tradingview": dict(bg="#131722",bg2="rgba(19,23,34,0.88)",
                            grid="#1e222d",up="#26a69a",dn="#ef5350",
                            tp_c="#26a69a",sl_c="#ef5350",en_c="#2962ff",txt="#b2b5be"),
        "ig":          dict(bg="#0d1b2e",bg2="rgba(13,27,46,0.88)",
                            grid="#1a2d45",up="#00b386",dn="#e63946",
                            tp_c="#00b386",sl_c="#e63946",en_c="#5b9bd5",txt="#cce4ff"),
    }
    t = palettes.get(theme, palettes["dark"])
    last = df.tail(80).copy()
    fig  = make_subplots(rows=2, cols=1, shared_xaxes=True,
                         row_heights=[0.76, 0.24], vertical_spacing=0.012)

    # candles
    fig.add_trace(go.Candlestick(
        x=last.index, open=last["Open"], high=last["High"],
        low=last["Low"], close=last["Close"],
        increasing_fillcolor=t["up"], increasing_line_color=t["up"],
        decreasing_fillcolor=t["dn"], decreasing_line_color=t["dn"],
        name="Price", line_width=1), row=1, col=1)

    # EMA lines
    ema20  = last["Close"].ewm(span=20, adjust=False).mean()
    ema50  = last["Close"].ewm(span=50, adjust=False).mean()
    for ema_s, ema_c, ema_n in [(ema20,"rgba(255,214,10,0.55)","EMA 20"),
                                  (ema50,"rgba(94,92,230,0.55)","EMA 50")]:
        fig.add_trace(go.Scatter(x=last.index, y=ema_s, line=dict(color=ema_c,width=1),
                                 name=ema_n, showlegend=False), row=1, col=1)

    # TP / SL / Entry horizontal lines + labels (NO row/col on add_annotation)
    x0, x1 = last.index[0], last.index[-1]
    for pv, clr, lbl, dash in [
        (tp,    t["tp_c"], f"TP {tp:.5f}",     "dash"),
        (sl,    t["sl_c"], f"SL {sl:.5f}",     "dash"),
        (entry, t["en_c"], f"Entry {entry:.5f}", "dot"),
    ]:
        fig.add_shape(type="line", x0=x0, x1=x1, y0=pv, y1=pv,
                      line=dict(color=clr, width=1.5, dash=dash),
                      row=1, col=1)
        fig.add_annotation(
            x=x1, y=pv,
            xref="x", yref="y",          # subplot-1 refs
            text=f"<b>{lbl}</b>",
            showarrow=False,
            xanchor="right", yanchor="middle",
            font=dict(color=clr, size=10),
            bgcolor=t["bg2"],
            borderpad=3,
            opacity=0.92,
        )

    # shaded zone
    zone = "rgba(48,209,88,0.06)" if action=="BUY" else "rgba(255,69,58,0.06)"
    fig.add_shape(type="rect", x0=x0, x1=x1,
                  y0=min(sl,entry), y1=max(tp,entry),
                  fillcolor=zone, line_width=0, row=1, col=1)

    # volume bars
    vol_c = [t["up"] if float(c)>=float(o) else t["dn"]
             for c,o in zip(last["Close"],last["Open"])]
    fig.add_trace(go.Bar(x=last.index, y=last["Volume"],
                         marker_color=vol_c, marker_opacity=0.55,
                         showlegend=False), row=2, col=1)

    ac = {"BUY":t["tp_c"],"SELL":t["sl_c"]}.get(action, t["en_c"])
    ts = datetime.datetime.now(UK_TZ).strftime("%H:%M %Z")
    fig.update_layout(
        title=dict(text=f"<b>{pair}</b>  ·  {action}  <span style='font-size:11px;color:{t['txt']}88'>updated {ts}</span>",
                   font=dict(color=ac, size=14)),
        height=450, paper_bgcolor=t["bg"], plot_bgcolor=t["bg"],
        xaxis_rangeslider_visible=False,
        font=dict(color=t["txt"], size=10,
                  family="-apple-system,'Inter',sans-serif"),
        margin=dict(l=8, r=8, t=46, b=8),
        hovermode="x unified",
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        transition=dict(duration=0),
        uirevision=str(uirev),
        dragmode=dragmode,   # "pan" = drag to move · "zoom" = drag to zoom box
    )
    # spike props are only valid on xaxis, NOT yaxis — keep them separate
    base_style = dict(gridcolor=t["grid"], gridwidth=1,
                      zerolinecolor=t["grid"],
                      tickfont=dict(color=t["txt"]), showgrid=True)
    x_style = dict(**base_style,
                   spikesnap="cursor", spikemode="across",
                   spikethickness=1, spikecolor="rgba(255,255,255,0.25)")
    fig.update_layout(xaxis=x_style, xaxis2=x_style,
                      yaxis=base_style, yaxis2=base_style)
    return fig

# ══════════════════════════════════════════════════════════════════════════════
#  PREDICTION CHART — historical + projected future candles
# ══════════════════════════════════════════════════════════════════════════════
def build_prediction_chart(df, pair, action, entry, tp, sl, tp_pips, sl_pips, issued_at=0):
    """
    Builds a Plotly chart showing historical candles + AI-projected future path.

    Historical: last 50 real candles.
    Projected : 20 forward candles drifting in signal direction using ATR
                volatility + momentum decay (uncertainty grows over time).
    Overlays  : TP / SL / Entry lines, shaded expected-path corridor.
    """
    t = dict(bg="#000000", bg2="rgba(0,0,0,0.85)", grid="#1a1a1a",
             up="#30d158", dn="#ff453a", tp_c="#30d158", sl_c="#ff453a",
             en_c="#ffd60a", txt="#ffffff")

    last = df.tail(50).copy()
    ps   = pip_size(pair)

    # ATR for realistic volatility
    h, lo, c = last["High"], last["Low"], last["Close"]
    tr_s  = pd.concat([(h - lo),
                        (h - c.shift()).abs(),
                        (lo - c.shift()).abs()], axis=1).max(axis=1)
    atr = float(tr_s.rolling(14).mean().iloc[-1])
    if np.isnan(atr) or atr <= 0:
        atr = tp_pips * ps * 0.5

    # candle time-delta
    td = (last.index[-1] - last.index[-2]) if len(last.index) >= 2 else pd.Timedelta(minutes=5)

    last_close = float(last["Close"].iloc[-1])
    last_time  = last.index[-1]
    n_proj     = 20

    # deterministic RNG per signal so projection doesn't flicker on every refresh
    rng = np.random.default_rng(int(issued_at) % (2**31))

    # drift: aim to reach TP by ~75 % of projected bars, decaying as uncertainty grows
    total_drift   = tp - last_close
    drift_per_bar = total_drift / (n_proj * 0.75)

    proj_times  = [last_time + td * (i + 1) for i in range(n_proj)]
    proj_opens, proj_closes, proj_highs, proj_lows = [], [], [], []

    cur = last_close
    for i in range(n_proj):
        fade  = max(0.25, 1.0 - i / n_proj)          # confidence decays further out
        noise = float(rng.normal(0, atr * 0.55))
        o     = cur + float(rng.normal(0, atr * 0.07))
        cl    = o + drift_per_bar * fade + noise
        # soft-clamp: don't project more than 10 % beyond TP or SL
        if action == "BUY":
            cl = max(sl * 0.999, min(tp * 1.01, cl))
        else:
            cl = min(sl * 1.001, max(tp * 0.99, cl))
        hi  = max(o, cl) + abs(float(rng.normal(0, atr * 0.22)))
        lo_ = min(o, cl) - abs(float(rng.normal(0, atr * 0.22)))
        proj_opens.append(o);  proj_closes.append(cl)
        proj_highs.append(hi); proj_lows.append(lo_)
        cur = cl

    # ── build figure ──────────────────────────────────────────────────────────
    fig = make_subplots(rows=1, cols=1)

    # historical candles
    fig.add_trace(go.Candlestick(
        x=last.index, open=last["Open"], high=last["High"],
        low=last["Low"],  close=last["Close"],
        increasing_fillcolor=t["up"], increasing_line_color=t["up"],
        decreasing_fillcolor=t["dn"], decreasing_line_color=t["dn"],
        name="Historical", line_width=1))

    # projected candles (translucent)
    p_up = "rgba(48,209,88,0.50)"  if action == "BUY" else "rgba(255,69,58,0.50)"
    p_dn = "rgba(255,69,58,0.50)"  if action == "BUY" else "rgba(48,209,88,0.50)"
    fig.add_trace(go.Candlestick(
        x=proj_times,
        open=proj_opens, high=proj_highs,
        low=proj_lows,   close=proj_closes,
        increasing_fillcolor=p_up, increasing_line_color=p_up,
        decreasing_fillcolor=p_dn, decreasing_line_color=p_dn,
        name="Projected path", line_width=1, opacity=0.55))

    # shaded expected-path corridor
    env_top = [max(h_, c_) + atr * 0.18 for h_, c_ in zip(proj_highs, proj_closes)]
    env_bot = [min(l_, c_) - atr * 0.18 for l_, c_ in zip(proj_lows,  proj_closes)]
    zone_f  = "rgba(48,209,88,0.07)"  if action == "BUY" else "rgba(255,69,58,0.07)"
    zone_l  = "rgba(48,209,88,0.18)"  if action == "BUY" else "rgba(255,69,58,0.18)"
    fig.add_trace(go.Scatter(
        x=proj_times + proj_times[::-1],
        y=env_top    + env_bot[::-1],
        fill="toself", fillcolor=zone_f,
        line=dict(color=zone_l, width=0.8),
        showlegend=False, hoverinfo="skip"))

    # vertical "NOW" divider
    fig.add_shape(type="line", x0=last_time, x1=last_time,
                  y0=0, y1=1, yref="paper",
                  line=dict(color="rgba(255,255,255,0.22)", width=1, dash="dot"))
    fig.add_annotation(x=last_time, y=0.98, xref="x", yref="paper",
                       text="<b>NOW</b>", showarrow=False,
                       yanchor="top",
                       font=dict(color="rgba(255,255,255,0.32)", size=9),
                       bgcolor="rgba(0,0,0,0)", borderpad=2)

    # TP / SL / Entry horizontal lines (only over projected area)
    x_end = proj_times[-1]
    for pv, clr, lbl in [
        (tp,    t["tp_c"], f"TP  {tp:.5f}  (+{tp_pips}p)"),
        (sl,    t["sl_c"], f"SL  {sl:.5f}  (\u2212{sl_pips}p)"),
        (entry, t["en_c"], f"Entry  {entry:.5f}"),
    ]:
        fig.add_shape(type="line", x0=last_time, x1=x_end, y0=pv, y1=pv,
                      line=dict(color=clr, width=1.4, dash="dash"))
        fig.add_annotation(
            x=x_end, y=pv, xref="x", yref="y",
            text=f"<b>{lbl}</b>", showarrow=False,
            xanchor="right", yanchor="middle",
            font=dict(color=clr, size=10),
            bgcolor=t["bg2"], borderpad=3, opacity=0.92)

    ac  = t["tp_c"] if action == "BUY" else t["sl_c"]
    ts  = datetime.datetime.now(UK_TZ).strftime("%H:%M %Z")
    fig.update_layout(
        title=dict(
            text=(f"<b>{pair}</b>  \u00b7  {action}  \u00b7  Projected path"
                  f"  <span style='font-size:11px;color:{t['txt']}88'>{ts}</span>"),
            font=dict(color=ac, size=14)),
        height=500, paper_bgcolor=t["bg"], plot_bgcolor=t["bg"],
        xaxis_rangeslider_visible=False,
        font=dict(color=t["txt"], size=10,
                  family="-apple-system,'Inter',sans-serif"),
        margin=dict(l=8, r=8, t=46, b=8),
        hovermode="x unified",
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        transition=dict(duration=0),
        uirevision=f"pred_{pair}_{int(issued_at)}",
        dragmode="pan",
    )
    base_style = dict(gridcolor=t["grid"], gridwidth=1, zerolinecolor=t["grid"],
                      tickfont=dict(color=t["txt"]), showgrid=True)
    x_style    = dict(**base_style, spikesnap="cursor", spikemode="across",
                      spikethickness=1, spikecolor="rgba(255,255,255,0.25)")
    fig.update_layout(xaxis=x_style, yaxis=base_style)
    return fig


# ══════════════════════════════════════════════════════════════════════════════
#  AI SCREENSHOT CONFIRM
# ══════════════════════════════════════════════════════════════════════════════
def chart_toolbar(drag_key: str, rev_key: str):
    """
    Renders the Move / Zoom toggle + Reset button above a chart.
    Returns the current dragmode string ("pan" or "zoom").
    Must be called inside a fragment so buttons only rerun the fragment.
    """
    drag_col, zoom_col, reset_col, spacer = st.columns([1.4, 1.4, 0.9, 6])

    current = st.session_state.get(drag_key, "pan")
    is_pan  = current == "pan"

    with drag_col:
        # Active button gets a different background via inline style injected via markdown trick;
        # Streamlit buttons don't support conditional classes directly so we use two buttons.
        if is_pan:
            st.markdown(
                "<div style='background:rgba(48,209,88,.18);border:1px solid rgba(48,209,88,.4);"
                "border-radius:10px;padding:6px 0;text-align:center;font-size:.82rem;"
                "font-weight:600;color:#30d158;cursor:default;'>🤚 Move</div>",
                unsafe_allow_html=True)
        else:
            if st.button("🤚 Move", key=f"pan_{drag_key}", use_container_width=True,
                         help="Drag to move the chart freely"):
                st.session_state[drag_key] = "pan"
                st.rerun()

    with zoom_col:
        if not is_pan:
            st.markdown(
                "<div style='background:rgba(10,132,255,.18);border:1px solid rgba(10,132,255,.4);"
                "border-radius:10px;padding:6px 0;text-align:center;font-size:.82rem;"
                "font-weight:600;color:#0a84ff;cursor:default;'>🔍 Zoom</div>",
                unsafe_allow_html=True)
        else:
            if st.button("🔍 Zoom", key=f"zoom_{drag_key}", use_container_width=True,
                         help="Drag to zoom into an area"):
                st.session_state[drag_key] = "zoom"
                st.rerun()

    with reset_col:
        if st.button("↺", key=f"reset_{drag_key}", use_container_width=True,
                     help="Reset chart zoom & pan to original view"):
            st.session_state[rev_key] += 1

    return st.session_state.get(drag_key, "pan")


def ai_confirm(img_bytes, pair, action, entry, tp, sl):
    if not HAS_OLLAMA:
        return "⚠ Ollama not installed. Visit ollama.com → install → run: ollama pull moondream:latest"
    prompt = (
        f"Trading platform screenshot for {pair}. "
        f"Expected: {action}, Entry≈{entry:.5f}, TP≈{tp:.5f}, SL≈{sl:.5f}. "
        "Is it correctly set up? Are TP and SL lines visible and correct? "
        "What needs fixing if anything? "
        "Start with ✅ CONFIRMED or ❌ NOT CORRECT."
    )
    try:
        import ollama
        return ollama.chat(model="moondream:latest",
            messages=[{"role":"user","content":prompt,"images":[img_bytes]}]
        )["message"]["content"]
    except Exception as e:
        return f"⚠ Vision AI error: {e}"

# ══════════════════════════════════════════════════════════════════════════════
#  PAGE LAYOUT
# ══════════════════════════════════════════════════════════════════════════════

# ── header ────────────────────────────────────────────────────────────────────
hl, hm, hr = st.columns([4, 0.55, 1.45])
with hl:
    st.markdown("""
<div style='padding:26px 0 0'>
  <div style='font-size:.67rem;font-weight:700;letter-spacing:.15em;text-transform:uppercase;color:rgba(255,255,255,.28);margin-bottom:8px;'>◈ FX PRO TRADER</div>
  <div style='font-size:2rem;font-weight:800;letter-spacing:-.04em;color:#fff;line-height:1.15;'>
    Intelligent FX Signals
    <span style='color:rgba(255,255,255,.28);font-weight:300;font-size:1.3rem;display:block;margin-top:3px;'>9-indicator AI · Live news · Always online</span>
  </div>
</div>""", unsafe_allow_html=True)
with hm:
    st.markdown("<div style='height:38px'></div>", unsafe_allow_html=True)
    _muted = st.session_state.get("voice_muted", False)
    _mute_icon = "🔇" if _muted else "🔊"
    _mute_tip  = "Voice muted — click to unmute" if _muted else "Voice alerts on — click to mute"
    if st.button(_mute_icon, key="mute_btn", use_container_width=True, help=_mute_tip):
        st.session_state["voice_muted"] = not _muted
        st.rerun()
    if _muted:
        st.markdown(
            "<div style='text-align:center;font-size:.58rem;color:rgba(255,69,58,.65);"
            "margin-top:2px;letter-spacing:.04em;'>MUTED</div>",
            unsafe_allow_html=True)
with hr:
    @st.fragment(run_every="5s")
    def clock():
        n      = datetime.datetime.now(UK_TZ)          # always UK time
        tz_lbl = n.strftime("%Z")                       # "GMT" or "BST"
        wday   = n.weekday()                            # 0=Mon … 6=Sun
        hr_now = n.hour + n.minute / 60

        # ── Forex sessions in UK time ──────────────────────────────────────
        # Sydney  00:00–09:00 UK  |  Tokyo  00:00–09:00 UK
        # London  08:00–17:00 UK  |  New York 13:00–22:00 UK
        # Overlap (London + NY, highest liquidity) 13:00–17:00 UK
        is_weekday = wday < 5
        in_london  = is_weekday and  8.0 <= hr_now < 17.0
        in_ny      = is_weekday and 13.0 <= hr_now < 22.0
        in_overlap = is_weekday and 13.0 <= hr_now < 17.0
        in_asian   = is_weekday and (hr_now >= 23.0 or hr_now < 9.0)
        any_open   = is_weekday and (6.0 <= hr_now < 22.0)

        if in_overlap:
            session_html = "<span style='color:#30d158;font-weight:700;'>🔥 London+NY Overlap — Peak liquidity</span>"
        elif in_london and in_ny:
            session_html = "<span style='color:#30d158;'>London + New York open</span>"
        elif in_london:
            session_html = "<span style='color:#0a84ff;'>🇬🇧 London session open</span>"
        elif in_ny:
            session_html = "<span style='color:#ffd60a;'>🇺🇸 New York session open</span>"
        elif in_asian:
            session_html = "<span style='color:#8b5cf6;'>🌏 Asian session</span>"
        elif is_weekday:
            session_html = "<span style='color:rgba(255,255,255,.35);'>Between sessions</span>"
        else:
            session_html = "<span style='color:rgba(255,255,255,.25);'>Weekend — markets closed</span>"

        dot_color = "#30d158" if any_open and is_weekday else "#ff453a"

        st.markdown(
            f"<div style='text-align:right;color:rgba(255,255,255,.3);font-size:.78rem;"
            f"padding-top:32px;font-variant-numeric:tabular-nums;line-height:1.9;'>"
            f"<span style='display:inline-block;width:7px;height:7px;border-radius:50%;"
            f"background:{dot_color};box-shadow:0 0 7px {dot_color}88;"
            f"margin-right:5px;'></span>"
            f"<b style='color:#fff'>{n.strftime('%H:%M:%S')}</b> {tz_lbl}<br>"
            f"{n.strftime('%a %d %b %Y')}<br>"
            f"{session_html}"
            f"</div>",
            unsafe_allow_html=True)
    clock()
st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

# ── settings ──────────────────────────────────────────────────────────────────
with st.expander("⚙  Settings", expanded=False):
    c1,c2,c3,c4 = st.columns(4)
    with c1: tf_label  = st.selectbox("Timeframe",list(TIMEFRAMES.keys()),index=1,key="tf_label")
    with c2: lev_label = st.selectbox("Leverage",list(LEVERAGE_MAP.keys()),index=2,key="lev_label")
    with c3: amt_gbp   = st.number_input("Trade amount (£)",1.0,10000.0,20.0,5.0,key="amt_gbp")
    with c4: auto_scan = st.toggle("Auto-rescan on expiry",True,key="auto_rescan")

tf_int, tf_per, tf_val = TIMEFRAMES[tf_label]
leverage = LEVERAGE_MAP[lev_label]
st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

# ── tabs ───────────────────────────────────────────────────────────────────────
T1, T2, T3, T4, T5 = st.tabs([
    "◉  Best Trade Now",
    "◎  Market Intelligence",
    "▦  Platform Guide",
    "◷  Confirm Setup",
    "📈  Price Prediction",
])

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — BEST TRADE NOW
#  EVERYTHING is inside @st.fragment → zero full-page blink
# ══════════════════════════════════════════════════════════════════════════════
with T1:
    # No st.empty() placeholders outside the fragment — those cause a clear→refill blink.
    # Everything renders directly inside the fragment; Streamlit diffs the subtree in place.
    @st.fragment(run_every=30)
    def scanner():
        # ── Scan button lives INSIDE the fragment: clicking it only reruns the fragment
        top_l, top_r = st.columns([2,4])
        with top_l:
            do_scan = st.button("⟳  Scan All 10 Markets", type="primary",
                                use_container_width=True, key="scan_btn")
        with top_r:
            # show scanning status inline — no external placeholder
            scanning_now = False
            now   = time.time()
            sigs  = st.session_state.get("signals", {})
            rescan = bool(do_scan)

            if st.session_state.get("auto_rescan", True):
                if not sigs or (now - st.session_state.get("last_scan",0)) > tf_val:
                    rescan = True
                elif any(s and expired(s["issued_at"],s["valid_secs"]) for s in sigs.values()):
                    rescan = True

            if rescan:
                st.markdown(
                    "<div style='color:rgba(255,255,255,.4);font-size:.78rem;margin-top:8px;'>"
                    "⟳ Scanning…</div>",
                    unsafe_allow_html=True)
                news   = fetch_news()
                pair_s = build_pair_sentiment(news)
                new_sigs = {}
                with ThreadPoolExecutor(max_workers=10) as ex:
                    futs = {ex.submit(scan_one,p,y,tf_int,tf_per,tf_val,tf_label,pair_s):p
                            for p,y in PAIRS.items()}
                    for f in as_completed(futs):
                        p, s = f.result()
                        new_sigs[p] = s
                st.session_state["signals"] = new_sigs
                st.session_state["last_scan"] = now

        sigs = st.session_state.get("signals", {})
        if not sigs:
            st.markdown(
                "<div style='text-align:center;padding:60px;color:rgba(255,255,255,.25);'>"
                "Click <b>Scan All 10 Markets</b> to begin</div>",
                unsafe_allow_html=True)
            return

        def sort_key(item):
            _, s = item
            if s is None: return (3,0)
            return (0,-s["confidence"]) if s["action"] in ("BUY","SELL") else (1,-abs(s["combined"]))

        sorted_sigs = sorted(sigs.items(), key=sort_key)
        best_pair, best = sorted_sigs[0]

        # ── HERO ──────────────────────────────────────────────────────────────
        if best and best["action"] in ("BUY","SELL"):
            act    = best["action"]
            entry  = best["entry"]
            tp     = best["tp"];    sl  = best["sl"]
            ps_v   = pip_size(best_pair)
            profit = calc_profit(amt_gbp, leverage, best["tp_pips"], ps_v, entry)
            loss_v = calc_profit(amt_gbp, leverage, best["sl_pips"], ps_v, entry)
            conf   = best["confidence"]
            cd     = fmt_cd(best["issued_at"], best["valid_secs"])
            exp    = expired(best["issued_at"], best["valid_secs"])
            rr     = profit / max(loss_v, 0.01)
            why    = " · ".join(best.get("reasons",["Signal confirmed"])[:3])
            ns_lbl = ("📰 News confirms" if (best["news_score"]>0 and act=="BUY")
                      or (best["news_score"]<0 and act=="SELL")
                      else "📰 News neutral")
            adx_lbl= f"ADX {best['adx']:.0f}" + (" (strong trend)" if best["adx"]>25 else "")
            hcls   = "hero-buy" if act=="BUY" else "hero-sell"
            acls   = "action-buy" if act=="BUY" else "action-sell"
            bcls   = "conf-buy"  if act=="BUY" else "conf-sell"

            st.markdown(f"""
<div class="hero {hcls}">
  <div class="conf-badge {bcls}">{conf}% confidence</div>
  <div class="hero-eyebrow">◉ STRONGEST SIGNAL RIGHT NOW</div>
  <div class="hero-action {acls}">{act}</div>
  <div class="hero-pair">{best_pair}</div>
  <div class="hero-why">{why}<br>{ns_lbl} · {adx_lbl} · {'⏰ Signal expired — rescanning' if exp else f'⏱ {cd} remaining'}</div>
  <div class="hero-stats">
    <div class="hstat"><div class="hstat-val" style="font-family:monospace">{entry:.5f}</div><div class="hstat-lbl">Entry Price</div></div>
    <div class="hstat"><div class="hstat-val" style="color:#30d158;font-family:monospace">{tp:.5f}</div><div class="hstat-lbl">Take Profit +{best['tp_pips']}p</div></div>
    <div class="hstat"><div class="hstat-val" style="color:#ff453a;font-family:monospace">{sl:.5f}</div><div class="hstat-lbl">Stop Loss −{best['sl_pips']}p</div></div>
    <div class="hstat"><div class="hstat-val" style="color:#30d158">+£{profit:.2f}</div><div class="hstat-lbl">Win (£{amt_gbp:.0f} trade)</div></div>
    <div class="hstat"><div class="hstat-val" style="color:#ff453a">−£{loss_v:.2f}</div><div class="hstat-lbl">Max Loss</div></div>
    <div class="hstat"><div class="hstat-val">{rr:.1f}:1</div><div class="hstat-lbl">Risk/Reward</div></div>
  </div>
</div>""", unsafe_allow_html=True)

            speak(f"hero_{best_pair}_{best['issued_at']:.0f}",
                  f"Top trade: {act} {best_pair.replace('/','')} — {conf} percent confidence.")

            # ── hero chart ────────────────────────────────────────────────────
            drag_mode = chart_toolbar("drag_hero", "rev_hero")
            fig = build_chart(best["df"], best_pair, act, entry, tp, sl,
                              uirev=st.session_state["rev_hero"],
                              dragmode=drag_mode)
            st.plotly_chart(fig, use_container_width=True, key="hero_chart",
                            config={"displayModeBar":True,"scrollZoom":True,
                                    "modeBarButtonsToRemove":["select2d","lasso2d"]})

        # ── TICKER STRIP ──────────────────────────────────────────────────────
        strip_html = '<div class="tstrip">'
        for pair in list(PAIRS.keys())[:10]:
            pr, chg = live_price(PAIRS[pair])
            if pr:
                chg_c = "ti-up" if (chg or 0)>=0 else "ti-dn"
                sgn   = "+" if (chg or 0)>=0 else ""
                strip_html += (f'<div class="ti"><div class="ti-sym">{pair}</div>'
                               f'<div class="ti-pr">{pr:.5f}</div>'
                               f'<div class="{chg_c}">{sgn}{chg:.3f}%</div></div>')
        strip_html += '</div>'
        st.markdown(strip_html, unsafe_allow_html=True)

        # ── ALL PAIRS GRID ─────────────────────────────────────────────────────
        if True:
            st.markdown("""
<div style='margin:4px 0 14px'>
  <div class='eyebrow'>ALL 10 MARKETS</div>
  <div style='font-size:1.2rem;font-weight:800;letter-spacing:-.02em;color:#fff;'>Ranked by signal strength</div>
</div>""", unsafe_allow_html=True)

            col_a, col_b = st.columns(2)
            for i, (pair, sig) in enumerate(sorted_sigs):
                with (col_a if i%2==0 else col_b):
                    if sig is None:
                        st.markdown(
                            f'<div class="scard scard-dead">'
                            f'<div class="spair">⚠ {pair}</div>'
                            f'<div style="font-size:.78rem;color:rgba(255,255,255,.25);margin-top:4px;">Data unavailable — will retry on next scan</div>'
                            f'</div>', unsafe_allow_html=True)
                        continue

                    act   = sig["action"]
                    exp   = expired(sig["issued_at"], sig["valid_secs"])
                    cd    = fmt_cd(sig["issued_at"], sig["valid_secs"])
                    conf  = sig["confidence"]
                    ps_v  = pip_size(pair)
                    win   = calc_profit(amt_gbp, leverage, sig["tp_pips"], ps_v, sig["entry"])
                    lose  = calc_profit(amt_gbp, leverage, sig["sl_pips"], ps_v, sig["entry"])
                    pct   = abs(sig["combined"])/10*100
                    ns    = sig["news_score"]

                    cc    = {"BUY":"scard-buy","SELL":"scard-sell"}.get(act,"scard-wait") + (" scard-dead" if exp else "")
                    ac    = {"BUY":"sact-buy","SELL":"sact-sell"}.get(act,"sact-wait")
                    bc    = {"BUY":"sbar-buy","SELL":"sbar-sell"}.get(act,"sbar-wait")
                    ni    = ('<span class="pill pill-bull">📰 Bullish news</span>' if ns>0.5
                             else '<span class="pill pill-bear">📰 Bearish news</span>' if ns<-0.5
                             else '<span class="pill pill-neu">📰 Neutral</span>')
                    cd_txt = "Rescanning…" if exp else cd
                    adx_lbl = f"ADX {sig['adx']:.0f}" + ("▲" if sig["adx"]>25 else "")

                    st.markdown(f"""
<div class="scard {cc}">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;">
    <div>
      <div class="spair">{pair}</div>
      <div class="{ac}">{act}</div>
    </div>
    <div style="text-align:right;">
      <div class="cd">{"⏰" if exp else "⏱"} {cd_txt}</div>
      <div style="font-size:.68rem;color:rgba(255,255,255,.28);margin-top:4px;">{conf}% conf · {adx_lbl}</div>
    </div>
  </div>
  <div class="sbar-bg"><div class="{bc}" style="width:{pct:.0f}%"></div></div>
  <div class="stg">
    <div class="stg-i"><div class="stg-v" style="font-family:monospace;font-size:.78rem">{sig['entry']:.5f}</div><div class="stg-l">Entry</div></div>
    <div class="stg-i"><div class="stg-v" style="color:#30d158;font-family:monospace;font-size:.78rem">{sig['tp']:.5f}</div><div class="stg-l">TP +{sig['tp_pips']}p</div></div>
    <div class="stg-i"><div class="stg-v" style="color:#ff453a;font-family:monospace;font-size:.78rem">{sig['sl']:.5f}</div><div class="stg-l">SL −{sig['sl_pips']}p</div></div>
  </div>
  <div style="display:flex;gap:12px;margin-top:10px;font-size:.78rem;flex-wrap:wrap;align-items:center;">
    <span>💰 <b style="color:#30d158">+£{win:.2f}</b></span>
    <span>🛡 <b style="color:#ff453a">−£{lose:.2f}</b></span>
    <span style="color:rgba(255,255,255,.35)">RSI {sig['rsi']:.0f}</span>
    {ni}
  </div>
</div>""", unsafe_allow_html=True)

                    if act in ("BUY","SELL") and not exp:
                        speak(f"{pair}_{sig['issued_at']:.0f}",
                              f"{pair.replace('/','')} {act}.")

    scanner()

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 2 — MARKET INTELLIGENCE
# ══════════════════════════════════════════════════════════════════════════════
with T2:
    @st.fragment(run_every=300)
    def intel():
        st.markdown("""
<div style='margin-bottom:18px;'>
  <div class='eyebrow'>LIVE MARKET INTELLIGENCE</div>
  <div class='stitle'>What the market is doing right now</div>
  <div class='ssub'>Live news · Economic calendar · Sentiment — all feeding your signals</div>
</div>""", unsafe_allow_html=True)

        with st.spinner("Fetching live market intelligence…"):
            news  = fetch_news()
            evs   = fetch_calendar()
            p_s   = build_pair_sentiment(news)

        # sentiment grid
        st.markdown("<div class='eyebrow' style='margin-bottom:10px;'>NEWS SENTIMENT BY PAIR</div>",
                    unsafe_allow_html=True)
        rows = [list(PAIRS.keys())[:5], list(PAIRS.keys())[5:]]
        for row in rows:
            cs = st.columns(5)
            for ci, pair in enumerate(row):
                with cs[ci]:
                    s   = p_s.get(pair, 0)
                    clr = "#30d158" if s>0.4 else ("#ff453a" if s<-0.4 else "#ffd60a")
                    lbl = "Bullish" if s>0.4 else ("Bearish" if s<-0.4 else "Neutral")
                    st.markdown(
                        f'<div class="mc"><div class="mc-v" style="color:{clr};font-size:1rem;">{lbl}</div>'
                        f'<div style="font-size:.72rem;color:rgba(255,255,255,.28);margin-top:4px;">{pair}</div>'
                        f'<div style="font-size:.68rem;color:{clr};margin-top:2px;">{s:+.1f} score</div></div>',
                        unsafe_allow_html=True)

        st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
        n_col, e_col = st.columns([3,2])

        with n_col:
            st.markdown("<div class='eyebrow' style='margin-bottom:10px;'>LATEST FX NEWS</div>",
                        unsafe_allow_html=True)
            if news:
                for a in news[:14]:
                    s   = a["score"]
                    sc  = "#30d158" if s>0 else ("#ff453a" if s<0 else "rgba(255,255,255,.35)")
                    lbl = "▲ Bullish" if s>0 else ("▼ Bearish" if s<0 else "— Neutral")
                    src = a.get("source","")
                    st.markdown(
                        f'<div class="ncard"><div class="ntitle">{a["title"][:115]}</div>'
                        f'<div class="nmeta"><span style="color:{sc};font-weight:600">{lbl}</span>'
                        f' · {src}</div></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="intel"><div class="intel-lbl">STATUS</div>No news loaded — check internet connection.</div>',
                            unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:.67rem;color:rgba(255,255,255,.18);margin-top:6px;'>"
                        f"🔄 Auto-refreshes every 5 min · {datetime.datetime.now(UK_TZ).strftime('%H:%M %Z')}</div>",
                        unsafe_allow_html=True)

        with e_col:
            st.markdown("<div class='eyebrow' style='margin-bottom:10px;'>ECONOMIC CALENDAR</div>",
                        unsafe_allow_html=True)
            if evs:
                for ev in evs[:10]:
                    imp = ev.get("impact","low")
                    ec  = {"high":"ev-hi","medium":"ev-me"}.get(imp,"ev-lo")
                    ic  = {"high":"🔴","medium":"🟠"}.get(imp,"⚪")
                    fc  = f" · Forecast: {ev['forecast']}" if ev.get("forecast") else ""
                    pr  = f" · Prev: {ev['previous']}" if ev.get("previous") else ""
                    st.markdown(
                        f'<div class="ev {ec}"><div class="ev-t">{ic} {ev["event"][:52]}</div>'
                        f'<div class="ev-m">🕐 {ev["time"]} · {ev["currency"]}{fc}{pr}</div></div>',
                        unsafe_allow_html=True)
            else:
                st.markdown('<div class="intel"><div class="intel-lbl">CALENDAR</div>No upcoming events found.</div>',
                            unsafe_allow_html=True)

            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
            st.markdown("""
<div class="intel">
  <div class="intel-lbl">HOW SIGNALS ARE CALCULATED</div>
  <div style="font-size:.82rem;color:rgba(255,255,255,.65);line-height:1.8;">
    <b style="color:#fff">9 Technical Indicators</b><br>
    RSI · MACD · Bollinger · EMA stack · Stochastic · ADX · Candlestick patterns · Volume · Price action<br><br>
    <b style="color:#0a84ff">+ Live News Sentiment</b> (scraped every 5 min)<br>
    <b style="color:#ffd60a">+ Economic Calendar</b> (high-impact events)<br>
    = <b style="color:#30d158">Confidence-weighted final signal</b>
  </div>
</div>""", unsafe_allow_html=True)

    intel()

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 3 — PLATFORM GUIDE  (chart refreshes inside fragment)
# ══════════════════════════════════════════════════════════════════════════════
with T3:
    st.markdown("""
<div style='margin-bottom:18px;'>
  <div class='eyebrow'>PLATFORM GUIDE</div>
  <div class='stitle'>Exactly what to do — step by step</div>
  <div class='ssub'>Live annotated chart + click-by-click instructions for your platform</div>
</div>""", unsafe_allow_html=True)

    g1,g2,g3 = st.columns(3)
    with g1: guide_pair = st.selectbox("Pair", list(PAIRS.keys()), key="guide_pair")
    with g2: tp_label   = st.selectbox("Take Profit", list(TP_PIPS.keys()), index=1, key="tp_label")
    with g3: sl_label   = st.selectbox("Stop Loss",   list(SL_PIPS.keys()), index=1, key="sl_label")

    @st.fragment(run_every=60)
    def guide():
        sig = st.session_state.get("signals",{}).get(guide_pair)
        if sig is None:
            st.markdown('<div style="padding:40px;text-align:center;color:rgba(255,255,255,.25);">⟳ Run scanner first (◉ Best Trade Now tab)</div>',
                        unsafe_allow_html=True)
            return
        df     = sig.get("df")
        # always re-fetch for freshest chart data
        fresh  = fetch_df(PAIRS[guide_pair], tf_int, tf_per)
        if fresh is not None and len(fresh)>40: df = fresh

        act    = sig["action"]
        entry  = sig["entry"]
        tp_p   = TP_PIPS[tp_label]; sl_p = SL_PIPS[sl_label]
        ps     = pip_size(guide_pair)
        tp     = entry+tp_p*ps if act!="SELL" else entry-tp_p*ps
        sl     = entry-sl_p*ps if act!="SELL" else entry+sl_p*ps
        profit = calc_profit(amt_gbp, leverage, tp_p, ps, entry)
        loss_v = calc_profit(amt_gbp, leverage, sl_p, ps, entry)
        rr     = profit/max(loss_v,0.01)
        ac_c   = "#30d158" if act=="BUY" else ("#ff453a" if act=="SELL" else "#ffd60a")
        bsw    = "Buy" if act=="BUY" else ("Sell" if act=="SELL" else "Wait — no clear signal")

        # summary bar
        st.markdown(f"""
<div style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:18px 22px;margin-bottom:20px;display:flex;flex-wrap:wrap;gap:24px;align-items:center;">
  <div><div style="font-size:.65rem;color:rgba(255,255,255,.28);text-transform:uppercase;letter-spacing:.08em;margin-bottom:3px;">Signal</div>
       <div style="font-size:1.5rem;font-weight:900;color:{ac_c};letter-spacing:-.02em;">{act} {guide_pair}</div></div>
  <div><div style="font-size:.65rem;color:rgba(255,255,255,.28);text-transform:uppercase;letter-spacing:.08em;margin-bottom:3px;">Entry</div>
       <div style="font-size:1rem;font-weight:700;font-family:monospace;">{entry:.5f}</div></div>
  <div><div style="font-size:.65rem;color:rgba(255,255,255,.28);text-transform:uppercase;letter-spacing:.08em;margin-bottom:3px;">Take Profit</div>
       <div style="font-size:1rem;font-weight:700;color:#30d158;font-family:monospace;">{tp:.5f} <span style="font-size:.75rem;color:rgba(48,209,88,.55)">+{tp_p}p</span></div></div>
  <div><div style="font-size:.65rem;color:rgba(255,255,255,.28);text-transform:uppercase;letter-spacing:.08em;margin-bottom:3px;">Stop Loss</div>
       <div style="font-size:1rem;font-weight:700;color:#ff453a;font-family:monospace;">{sl:.5f} <span style="font-size:.75rem;color:rgba(255,69,58,.55)">−{sl_p}p</span></div></div>
  <div><div style="font-size:.65rem;color:rgba(255,255,255,.28);text-transform:uppercase;letter-spacing:.08em;margin-bottom:3px;">Win / Lose</div>
       <div style="font-size:1rem;font-weight:700;"><span style="color:#30d158">+£{profit:.2f}</span> <span style="color:rgba(255,255,255,.2)">/</span> <span style="color:#ff453a">−£{loss_v:.2f}</span></div></div>
  <div><div style="font-size:.65rem;color:rgba(255,255,255,.28);text-transform:uppercase;letter-spacing:.08em;margin-bottom:3px;">R/R</div>
       <div style="font-size:1rem;font-weight:700;">{rr:.1f}:1</div></div>
</div>""", unsafe_allow_html=True)

        pt_mt, pt_tv, pt_ig = st.tabs(["MetaTrader 4/5","TradingView","IG Broker"])

        def make_steps(items, nc):
            s = '<div class="steps">'
            for i,(txt,) in enumerate([(x,) for x in items],1):
                s += f'<div class="step"><div class="snum {nc}">{i}</div><div class="stxt">{txt}</div></div>'
            return s+'</div>'

        # ── MetaTrader ──────────────────────────────────────────────────────
        with pt_mt:
            if df is not None:
                drag_mode = chart_toolbar("drag_mt", "rev_mt")
                fig = build_chart(df, guide_pair, act, entry, tp, sl, "metatrader",
                                  uirev=st.session_state["rev_mt"],
                                  dragmode=drag_mode)
                fig.update_layout(title=dict(text=f"MetaTrader · {guide_pair} · {act}",
                                             font=dict(color="#82b1ff",size=13)))
                st.plotly_chart(fig, use_container_width=True, key="mt_chart",
                                config={"displayModeBar":True,"scrollZoom":True})
            st.markdown('<div class="ph ph-mt">📊 MetaTrader 4 / 5 — Step by step</div>', unsafe_allow_html=True)
            steps = [
                f"Open MetaTrader and locate <b>{guide_pair}</b> in <i>Market Watch</i> (Ctrl+M if hidden).",
                f"Right-click the chart → <b>Timeframe</b> → select <b>{tf_int.upper()}</b>.",
                f"Press <b>F9</b> or click <b>New Order</b> in the toolbar.",
                f"Direction: <b>{bsw}</b>. TP field: <span class='pt pt-tp'>{tp:.5f}</span>. SL field: <span class='pt pt-sl'>{sl:.5f}</span>.",
                f"Click <b>{bsw} by Market</b> to place.",
                f"Check <b>Terminal → Trade</b>: green line at <span class='pt pt-tp'>{tp:.5f}</span>, red at <span class='pt pt-sl'>{sl:.5f}</span>.",
            ]
            st.markdown(make_steps(steps,"snum-mt"), unsafe_allow_html=True)

        # ── TradingView ─────────────────────────────────────────────────────
        with pt_tv:
            if df is not None:
                drag_mode = chart_toolbar("drag_tv", "rev_tv")
                fig = build_chart(df, guide_pair, act, entry, tp, sl, "tradingview",
                                  uirev=st.session_state["rev_tv"],
                                  dragmode=drag_mode)
                fig.update_layout(title=dict(text=f"TradingView · {guide_pair} · {act}",
                                             font=dict(color="#26a69a",size=13)))
                st.plotly_chart(fig, use_container_width=True, key="tv_chart",
                                config={"displayModeBar":True,"scrollZoom":True})
            st.markdown('<div class="ph ph-tv">◼ TradingView — Step by step</div>', unsafe_allow_html=True)
            steps = [
                f"Go to <b>tradingview.com</b> and search <b>{guide_pair.replace('/','')}</b>.",
                f"Set timeframe: click interval buttons → <b>{tf_int.upper()}</b>.",
                f"Use <b>Long/Short Position tool</b> (toolbar left, or Shift+F): click at entry <span class='pt pt-e'>{entry:.5f}</span>.",
                f"Drag TP to <span class='pt pt-tp'>{tp:.5f}</span> and SL to <span class='pt pt-sl'>{sl:.5f}</span>. Position tool shows R/R {rr:.1f}:1.",
                f"Via connected broker: click <b>Trading Panel</b> → <b>{bsw}</b> → TP <span class='pt pt-tp'>{tp:.5f}</span> SL <span class='pt pt-sl'>{sl:.5f}</span>.",
                f"Profit zone (teal) should extend {tp_p} pips {'above' if act=='BUY' else 'below'} entry.",
            ]
            st.markdown(make_steps(steps,"snum-tv"), unsafe_allow_html=True)

        # ── IG Broker ───────────────────────────────────────────────────────
        with pt_ig:
            if df is not None:
                drag_mode = chart_toolbar("drag_ig", "rev_ig")
                fig = build_chart(df, guide_pair, act, entry, tp, sl, "ig",
                                  uirev=st.session_state["rev_ig"],
                                  dragmode=drag_mode)
                fig.update_layout(title=dict(text=f"IG Broker · {guide_pair} · {act}",
                                             font=dict(color="#5b9bd5",size=13)))
                st.plotly_chart(fig, use_container_width=True, key="ig_chart",
                                config={"displayModeBar":True,"scrollZoom":True})
            st.markdown('<div class="ph ph-ig">🔵 IG Broker — Step by step</div>', unsafe_allow_html=True)
            steps = [
                f"Log into <b>web.ig.com</b> or the IG app. Search <b>{guide_pair}</b>.",
                f"Click <b>{bsw}</b> to open the deal ticket.",
                f"<b>Limit (TP)</b>: <span class='pt pt-tp'>{tp:.5f}</span> — locks in <b style='color:#30d158'>+£{profit:.2f}</b> when hit.",
                f"<b>Stop (SL)</b>: <span class='pt pt-sl'>{sl:.5f}</span> — limits loss to <b style='color:#ff453a'>−£{loss_v:.2f}</b>.",
                f"IG pip view: TP is <b>{tp_p} pips</b> away, SL is <b>{sl_p} pips</b> away — verify these match.",
                f"Click <b>Place deal</b>. Position shows in <b>My IG → Positions</b> with lines on chart.",
            ]
            st.markdown(make_steps(steps,"snum-ig"), unsafe_allow_html=True)

        # ── P&L CALCULATOR ───────────────────────────────────────────────────
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        st.markdown("""
<div style='border-top:1px solid rgba(255,255,255,.07);margin:8px 0 18px;'></div>
<div style='margin-bottom:14px;'>
  <div class='eyebrow'>💰 PROFIT / LOSS CALCULATOR</div>
  <div style='font-size:1.1rem;font-weight:800;letter-spacing:-.02em;color:#fff;'>
    How much will you make or lose on this trade?
  </div>
  <div style='font-size:.82rem;color:rgba(255,255,255,.35);margin-top:2px;'>
    Enter any amount and leverage — calculated against the current signal for {gp}
  </div>
</div>""".replace("{gp}", guide_pair), unsafe_allow_html=True)

        cc1, cc2 = st.columns(2)
        with cc1:
            calc_amt = st.number_input(
                "Your trade amount (£)", min_value=1.0, max_value=100000.0,
                value=float(st.session_state.get("amt_gbp", 20.0)),
                step=10.0, key="calc_amt")
        with cc2:
            calc_lev_lbl = st.selectbox(
                "Leverage", list(LEVERAGE_MAP.keys()), index=2, key="calc_lev_lbl")
            calc_lev = LEVERAGE_MAP[calc_lev_lbl]

        calc_ps   = pip_size(guide_pair)
        calc_win  = calc_profit(calc_amt, calc_lev, tp_p, calc_ps, entry)
        calc_lose = calc_profit(calc_amt, calc_lev, sl_p, calc_ps, entry)
        calc_rr   = calc_win / max(calc_lose, 0.01)
        rr_col    = "#30d158" if calc_rr >= 1.5 else ("#ffd60a" if calc_rr >= 1.0 else "#ff453a")
        rr_lbl    = "Good ratio" if calc_rr >= 1.5 else ("Acceptable" if calc_rr >= 1.0 else "Poor ratio")
        rr_icon   = "✅" if calc_rr >= 1.5 else ("⚠️" if calc_rr >= 1.0 else "❌")
        pos_size  = calc_amt * calc_lev

        mc1, mc2, mc3, mc4 = st.columns(4)
        with mc1:
            st.markdown(
                f'<div class="mc" style="border-color:rgba(255,255,255,.1);">'
                f'<div class="mc-v" style="color:#fff;font-size:1.6rem;">£{pos_size:,.0f}</div>'
                f'<div class="mc-l">Position size</div>'
                f'<div style="font-size:.69rem;color:rgba(255,255,255,.25);margin-top:5px;">'
                f'£{calc_amt:.0f} &times; {calc_lev}x leverage</div></div>',
                unsafe_allow_html=True)
        with mc2:
            st.markdown(
                f'<div class="mc" style="border-color:rgba(48,209,88,.2);background:rgba(48,209,88,.05);">'
                f'<div class="mc-v" style="color:#30d158;font-size:1.6rem;">+£{calc_win:.2f}</div>'
                f'<div class="mc-l">If Take Profit hit</div>'
                f'<div style="font-size:.69rem;color:rgba(48,209,88,.45);margin-top:5px;">'
                f'+{tp_p} pips &nbsp;·&nbsp; {tp:.5f}</div></div>',
                unsafe_allow_html=True)
        with mc3:
            st.markdown(
                f'<div class="mc" style="border-color:rgba(255,69,58,.2);background:rgba(255,69,58,.05);">'
                f'<div class="mc-v" style="color:#ff453a;font-size:1.6rem;">&minus;£{calc_lose:.2f}</div>'
                f'<div class="mc-l">If Stop Loss hit</div>'
                f'<div style="font-size:.69rem;color:rgba(255,69,58,.45);margin-top:5px;">'
                f'&minus;{sl_p} pips &nbsp;·&nbsp; {sl:.5f}</div></div>',
                unsafe_allow_html=True)
        with mc4:
            st.markdown(
                f'<div class="mc" style="border-color:rgba(255,255,255,.1);">'
                f'<div class="mc-v" style="color:{rr_col};font-size:1.6rem;">{calc_rr:.1f}:1</div>'
                f'<div class="mc-l">Risk / Reward</div>'
                f'<div style="font-size:.69rem;color:{rr_col};opacity:.7;margin-top:5px;">'
                f'{rr_icon} {rr_lbl}</div></div>',
                unsafe_allow_html=True)

    guide()

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 4 — CONFIRM SETUP
# ══════════════════════════════════════════════════════════════════════════════
with T4:
    st.markdown("""
<div style='margin-bottom:18px;'>
  <div class='eyebrow'>SETUP CONFIRMATION</div>
  <div class='stitle'>AI checks your screenshot</div>
  <div class='ssub'>Upload a photo of your platform — AI confirms ✅ or tells you exactly what to fix ❌</div>
</div>""", unsafe_allow_html=True)

    cf1,cf2 = st.columns(2)
    with cf1: c_pair = st.selectbox("Pair", list(PAIRS.keys()), key="c_pair")
    with cf2: c_plat = st.selectbox("Platform", ["MetaTrader 4/5","TradingView","IG Broker"], key="c_plat")

    uploaded = st.file_uploader("Drop your screenshot (PNG or JPG)",
                                type=["png","jpg","jpeg"], key="upload")

    if uploaded:
        img_bytes = uploaded.read()
        st.image(img_bytes, use_container_width=True)
        sig_c = st.session_state.get("signals",{}).get(c_pair)
        if sig_c is None:
            st.markdown('<div class="intel"><div class="intel-lbl">RUN SCANNER FIRST</div>Scanner provides the expected values to check against.</div>',
                        unsafe_allow_html=True)
        else:
            act = sig_c["action"]; ent = sig_c["entry"]
            tp_p2 = TP_PIPS.get(st.session_state.get("tp_label","35 pips  Standard"),35)
            sl_p2 = SL_PIPS.get(st.session_state.get("sl_label","25 pips  Standard"),25)
            ps2   = pip_size(c_pair)
            tp2   = ent+tp_p2*ps2 if act!="SELL" else ent-tp_p2*ps2
            sl2   = ent-sl_p2*ps2 if act!="SELL" else ent+sl_p2*ps2

            st.markdown(f'<div style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:14px 18px;margin:10px 0;font-size:.84rem;">'
                        f'Checking against: {act} {c_pair} · Entry <span class="pt pt-e">{ent:.5f}</span> · TP <span class="pt pt-tp">{tp2:.5f}</span> · SL <span class="pt pt-sl">{sl2:.5f}</span>'
                        f'</div>', unsafe_allow_html=True)

            if st.button("◎  Check with AI Vision", type="primary"):
                if not HAS_OLLAMA:
                    st.markdown('<div class="cfail">⚠ <b>Ollama not found.</b><br>Install from ollama.com then run: <code>ollama pull moondream:latest</code></div>',
                                unsafe_allow_html=True)
                else:
                    with st.spinner("AI reading your screenshot…"):
                        result = ai_confirm(img_bytes, c_pair, act, ent, tp2, sl2)
                    ok = ("✅" in result or
                          ("confirmed" in result.lower() and "not confirmed" not in result.lower()) or
                          ("correct" in result.lower() and "not correct" not in result.lower()
                           and "incorrect" not in result.lower()))
                    if ok:
                        st.markdown(f'<div class="cok">✅ <b style="color:#30d158">CONFIRMED — looks correct!</b><br><br>{result}</div>',
                                    unsafe_allow_html=True)
                        st.success("🎉 Setup confirmed — go ahead and execute the trade.")
                    else:
                        st.markdown(f'<div class="cfail">❌ <b style="color:#ff453a">NEEDS ADJUSTMENT</b><br><br>{result}</div>',
                                    unsafe_allow_html=True)
    else:
        st.markdown("""
<div style="background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:18px;padding:30px 34px;">
  <div style="font-size:1rem;font-weight:700;color:#fff;margin-bottom:18px;">How to use</div>
  <div style="display:flex;flex-direction:column;gap:14px;">""" +
  "".join([f'<div style="display:flex;gap:14px;align-items:flex-start;">'
           f'<div style="min-width:28px;height:28px;border-radius:50%;background:rgba(10,132,255,.2);color:#0a84ff;font-weight:700;font-size:.8rem;display:flex;align-items:center;justify-content:center;flex-shrink:0;">{n}</div>'
           f'<div style="font-size:.85rem;color:rgba(255,255,255,.62);line-height:1.55;">{t}</div></div>'
           for n,t in [
               ("1","Open the <b style='color:#fff'>Platform Guide</b> tab and note the exact TP and SL values."),
               ("2","Set up your trade on MetaTrader / TradingView / IG exactly as shown."),
               ("3","Screenshot: <b style='color:#fff'>Mac</b> Cmd+Shift+4 · <b style='color:#fff'>Windows</b> Win+Shift+S"),
               ("4","Upload it above → click <b style='color:#fff'>Check with AI Vision</b> → get ✅ CONFIRMED or ❌ fix instructions."),
           ]]) +
  '</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    st.markdown("<div class='eyebrow' style='margin-bottom:10px;'>MANUAL CHECKLIST</div>",
                unsafe_allow_html=True)
    sig_m = st.session_state.get("signals",{}).get(c_pair)
    if sig_m:
        ps_m  = pip_size(c_pair)
        tp_m2 = TP_PIPS.get(st.session_state.get("tp_label","35 pips  Standard"),35)
        sl_m2 = SL_PIPS.get(st.session_state.get("sl_label","25 pips  Standard"),25)
        tp_mc = sig_m["entry"]+tp_m2*ps_m if sig_m["action"]!="SELL" else sig_m["entry"]-tp_m2*ps_m
        sl_mc = sig_m["entry"]-sl_m2*ps_m if sig_m["action"]!="SELL" else sig_m["entry"]+sl_m2*ps_m
        for j,lbl in enumerate([
            f"Correct pair: **{c_pair}**",
            f"Direction: **{sig_m['action']}**",
            f"Entry near `{sig_m['entry']:.5f}`",
            f"Take Profit at `{tp_mc:.5f}` (+{tp_m2} pips)",
            f"Stop Loss at `{sl_mc:.5f}` (−{sl_m2} pips)",
            f"Timeframe: **{tf_int.upper()}**",
        ]): st.checkbox(lbl, key=f"chk_{j}")
    else:
        st.markdown('<div style="color:rgba(255,255,255,.25);font-size:.83rem;">Run scanner to load values.</div>',
                    unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  TAB 5 — PRICE PREDICTION
# ══════════════════════════════════════════════════════════════════════════════
with T5:
    @st.fragment(run_every=60)
    def prediction_tab():
        st.markdown("""
<div style='margin-bottom:18px;'>
  <div class='eyebrow'>AI PRICE PREDICTION</div>
  <div class='stitle'>Where price may go next</div>
  <div class='ssub'>Projected path based on momentum, ATR volatility &amp; signal direction — TP and SL zones clearly marked</div>
</div>""", unsafe_allow_html=True)

        sigs = st.session_state.get("signals", {})
        if not sigs:
            st.markdown(
                "<div style='text-align:center;padding:60px;color:rgba(255,255,255,.25);'>"
                "⟳ Run the scanner first (◉ Best Trade Now tab)</div>",
                unsafe_allow_html=True)
            return

        pred_pair = st.selectbox("Select pair to predict", list(PAIRS.keys()), key="pred_pair")
        sig = sigs.get(pred_pair)

        if sig is None:
            st.markdown(
                "<div style='padding:30px;text-align:center;color:rgba(255,255,255,.25);'>"
                "⟳ No signal for this pair — run scanner again.</div>",
                unsafe_allow_html=True)
            return

        act     = sig["action"]
        entry   = sig["entry"]
        tp      = sig["tp"];       sl      = sig["sl"]
        tp_pips = sig["tp_pips"];  sl_pips = sig["sl_pips"]
        conf    = sig["confidence"]
        df      = sig.get("df")

        # try to get fresh data for a sharper chart
        fresh = fetch_df(PAIRS[pred_pair], tf_int, tf_per)
        if fresh is not None and len(fresh) > 40:
            df = fresh

        if df is None or len(df) < 20:
            st.warning("Not enough historical data to generate a prediction for this pair.")
            return

        ac_c = "#30d158" if act == "BUY" else ("#ff453a" if act == "SELL" else "#ffd60a")

        # ── summary card ──────────────────────────────────────────────────────
        st.markdown(f"""
<div style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.09);
border-radius:16px;padding:18px 22px;margin-bottom:18px;display:flex;
flex-wrap:wrap;gap:28px;align-items:center;">

  <div>
    <div style="font-size:.63rem;color:rgba(255,255,255,.28);text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px;">Predicted direction</div>
    <div style="font-size:2.2rem;font-weight:900;color:{ac_c};letter-spacing:-.04em;">{act}</div>
    <div style="font-size:.8rem;color:rgba(255,255,255,.35);">{pred_pair}</div>
  </div>

  <div>
    <div style="font-size:.63rem;color:rgba(255,255,255,.28);text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px;">Entry price</div>
    <div style="font-size:1.1rem;font-weight:700;font-family:monospace;">{entry:.5f}</div>
  </div>

  <div>
    <div style="font-size:.63rem;color:rgba(255,255,255,.28);text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px;">Take Profit target</div>
    <div style="font-size:1.1rem;font-weight:700;color:#30d158;font-family:monospace;">{tp:.5f}</div>
    <div style="font-size:.72rem;color:rgba(48,209,88,.5);">+{tp_pips} pips</div>
  </div>

  <div>
    <div style="font-size:.63rem;color:rgba(255,255,255,.28);text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px;">Stop Loss</div>
    <div style="font-size:1.1rem;font-weight:700;color:#ff453a;font-family:monospace;">{sl:.5f}</div>
    <div style="font-size:.72rem;color:rgba(255,69,58,.5);">&#8722;{sl_pips} pips</div>
  </div>

  <div style="margin-left:auto;text-align:right;">
    <div style="font-size:.63rem;color:rgba(255,255,255,.28);text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px;">AI confidence</div>
    <div style="font-size:1.9rem;font-weight:900;color:{ac_c};">{conf}%</div>
  </div>

</div>""", unsafe_allow_html=True)

        # ── prediction chart ──────────────────────────────────────────────────
        fig = build_prediction_chart(
            df, pred_pair, act, entry, tp, sl,
            tp_pips, sl_pips,
            issued_at=sig.get("issued_at", 0))
        st.plotly_chart(fig, use_container_width=True, key="pred_chart",
                        config={"displayModeBar": True, "scrollZoom": True,
                                "modeBarButtonsToRemove": ["select2d", "lasso2d"]})

        # ── legend + reasoning ────────────────────────────────────────────────
        dir_word = "upward" if act == "BUY" else "downward"
        reasons_html = "<br>".join(
            f"&bull; {r}" for r in sig.get("reasons", ["Signal confirmed"])[:5])

        st.markdown(f"""
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px;">

  <div style="background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);
  border-radius:14px;padding:16px 18px;">
    <div style="font-size:.68rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;
    color:#0a84ff;margin-bottom:10px;">📊 How to read this chart</div>
    <div style="font-size:.83rem;color:rgba(255,255,255,.62);line-height:1.82;">
      <b style="color:#fff">Solid candles</b> — real historical price data<br>
      <b style="color:{ac_c}">Faded candles</b> — AI projected {dir_word} path<br>
      <b style="color:rgba(255,255,255,.38)">Shaded corridor</b> — expected ATR volatility range<br>
      <b style="color:#ffd60a">Dotted vertical line</b> — current moment (NOW)<br>
      <b style="color:#30d158">Dashed green line</b> — take profit target (TP)<br>
      <b style="color:#ff453a">Dashed red line</b> — stop loss level (SL)
    </div>
  </div>

  <div style="background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);
  border-radius:14px;padding:16px 18px;">
    <div style="font-size:.68rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;
    color:#ffd60a;margin-bottom:10px;">⚡ Why {act} — signal reasons</div>
    <div style="font-size:.83rem;color:rgba(255,255,255,.62);line-height:1.82;">
      {reasons_html}
    </div>
  </div>

</div>

<div style="margin-top:12px;padding:11px 15px;background:rgba(255,214,10,.05);
border:1px solid rgba(255,214,10,.15);border-radius:10px;font-size:.75rem;
color:rgba(255,255,255,.4);line-height:1.7;">
  ⚠&nbsp; This projection is a <b>technical estimate</b> based on current momentum,
  ATR volatility and indicator alignment. Markets can move against any signal at any time.
  Always use your stop loss. This is not financial advice.
</div>""", unsafe_allow_html=True)

    prediction_tab()

# ── footer ────────────────────────────────────────────────────────────────────
st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)
st.markdown("""
<div style="text-align:center;padding:18px 0;border-top:1px solid rgba(255,255,255,.05);">
  <div style="font-size:.74rem;color:rgba(255,255,255,.18);letter-spacing:.04em;">
    FX PRO TRADER · 9-Indicator AI Engine · Live news via RSS · Economic calendar via ForexFactory
    · Local AI via Ollama · Not financial advice — always manage your risk
  </div>
</div>""", unsafe_allow_html=True)
