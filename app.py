"""
FX Pro Trader — Apple Edition
Intelligence-driven signals · Always-online market awareness · Crystal clear trades
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time, datetime, subprocess, platform, requests, json
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── platform guards ──────────────────────────────────────────────────────────
IS_MAC = platform.system() == "Darwin"
try:
    import mss as _mss;  HAS_MSS = True
except ImportError:
    HAS_MSS = False
try:
    import ollama as _ollama;  HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False
try:
    import kaleido;  HAS_KALEIDO = True   # noqa
except Exception:
    HAS_KALEIDO = False

# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="FX Pro", page_icon="◈", layout="wide",
                   initial_sidebar_state="collapsed")

# ── Apple-grade CSS ───────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── base ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
*{box-sizing:border-box;margin:0;padding:0;}
html,body,[class*="css"]{
  font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display','Inter','Helvetica Neue',sans-serif;
  -webkit-font-smoothing:antialiased;
}
.stApp{background:#000!important;color:#fff;}
.block-container{padding:0 2rem 4rem!important;max-width:1400px!important;}
section[data-testid="stSidebar"]{display:none}
div[data-testid="stToolbar"]{display:none}

/* ── hide streamlit chrome ── */
#MainMenu,footer,header{visibility:hidden}

/* ── tabs ── */
.stTabs [data-baseweb="tab-list"]{
  gap:2px;background:rgba(255,255,255,.06);
  padding:5px;border-radius:14px;border:1px solid rgba(255,255,255,.08);
}
.stTabs [data-baseweb="tab"]{
  border-radius:10px;padding:9px 22px;color:rgba(255,255,255,.5);
  font-weight:500;font-size:.88rem;letter-spacing:.01em;transition:all .2s;
}
.stTabs [aria-selected="true"]{
  background:rgba(255,255,255,.12)!important;
  color:#fff!important;
}

/* ── expander ── */
.streamlit-expanderHeader{
  background:rgba(255,255,255,.04)!important;
  border:1px solid rgba(255,255,255,.08)!important;
  border-radius:14px!important;color:rgba(255,255,255,.7)!important;
  font-size:.88rem;
}
.streamlit-expanderContent{
  background:rgba(255,255,255,.02)!important;
  border:1px solid rgba(255,255,255,.06)!important;
  border-top:none!important;border-radius:0 0 14px 14px!important;
}

/* ── buttons ── */
.stButton>button{
  background:rgba(255,255,255,.1)!important;
  border:1px solid rgba(255,255,255,.15)!important;
  border-radius:12px!important;color:#fff!important;
  font-weight:500!important;transition:all .2s!important;
}
.stButton>button:hover{
  background:rgba(255,255,255,.18)!important;
  border-color:rgba(255,255,255,.3)!important;
}
.stButton>button[kind="primary"]{
  background:linear-gradient(135deg,#0a84ff,#5e5ce6)!important;
  border:none!important;
}
.stButton>button[kind="primary"]:hover{
  opacity:.9!important;transform:translateY(-1px)!important;
  box-shadow:0 8px 30px rgba(10,132,255,.35)!important;
}

/* ── inputs & selects ── */
.stSelectbox>div>div,.stNumberInput>div>div>input{
  background:rgba(255,255,255,.06)!important;
  border:1px solid rgba(255,255,255,.1)!important;
  border-radius:10px!important;color:#fff!important;
}
.stSelectbox [data-baseweb="select"] *{background:#1c1c1e!important;color:#fff!important;}

/* ── file uploader ── */
[data-testid="stFileUploader"]{
  background:rgba(255,255,255,.03)!important;
  border:2px dashed rgba(255,255,255,.12)!important;
  border-radius:16px!important;
}

/* ── toggle ── */
.stToggle [data-baseweb="checkbox"]{color:rgba(255,255,255,.7)!important;}

/* ── divider ── */
hr{border:none;border-top:1px solid rgba(255,255,255,.06)!important;margin:2rem 0!important;}

/* ── scrollbar ── */
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,.15);border-radius:3px}

/* ── HERO CARD ── */
.hero-wrap{
  background:linear-gradient(145deg,rgba(28,28,30,.95),rgba(44,44,46,.7));
  backdrop-filter:blur(40px) saturate(200%);
  -webkit-backdrop-filter:blur(40px) saturate(200%);
  border:1px solid rgba(255,255,255,.1);
  border-radius:28px;padding:44px 48px;
  position:relative;overflow:hidden;margin-bottom:2rem;
}
.hero-wrap::before{
  content:'';position:absolute;inset:-1px;border-radius:28px;
  background:linear-gradient(145deg,rgba(255,255,255,.06),transparent 60%);
  pointer-events:none;
}
.hero-buy{border-color:rgba(48,209,88,.3)!important;box-shadow:0 0 80px rgba(48,209,88,.08)!important;}
.hero-sell{border-color:rgba(255,69,58,.3)!important;box-shadow:0 0 80px rgba(255,69,58,.08)!important;}
.hero-wait{border-color:rgba(255,214,10,.2)!important;}
.hero-tag{font-size:.72rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:rgba(255,255,255,.4);margin-bottom:10px;}
.hero-action-buy{font-size:4.5rem;font-weight:900;letter-spacing:-.03em;color:#30d158;line-height:1;}
.hero-action-sell{font-size:4.5rem;font-weight:900;letter-spacing:-.03em;color:#ff453a;line-height:1;}
.hero-action-wait{font-size:4.5rem;font-weight:900;letter-spacing:-.03em;color:#ffd60a;line-height:1;}
.hero-pair{font-size:1.5rem;font-weight:700;color:#fff;margin-top:6px;}
.hero-why{font-size:.88rem;color:rgba(255,255,255,.55);margin-top:10px;line-height:1.6;max-width:600px;}
.hero-stats{display:flex;gap:32px;margin-top:24px;flex-wrap:wrap;}
.hero-stat{display:flex;flex-direction:column;gap:3px;}
.hero-stat-val{font-size:1.15rem;font-weight:700;color:#fff;}
.hero-stat-lbl{font-size:.72rem;color:rgba(255,255,255,.35);text-transform:uppercase;letter-spacing:.08em;}
.hero-badge{
  position:absolute;top:24px;right:28px;
  background:rgba(48,209,88,.15);border:1px solid rgba(48,209,88,.3);
  border-radius:20px;padding:6px 14px;font-size:.78rem;font-weight:600;color:#30d158;
}
.hero-badge-sell{background:rgba(255,69,58,.15)!important;border-color:rgba(255,69,58,.3)!important;color:#ff453a!important;}
.hero-badge-wait{background:rgba(255,214,10,.1)!important;border-color:rgba(255,214,10,.2)!important;color:#ffd60a!important;}

/* ── SIGNAL CARD ── */
.sig-card{
  background:rgba(28,28,30,.8);backdrop-filter:blur(20px);
  -webkit-backdrop-filter:blur(20px);
  border:1px solid rgba(255,255,255,.08);
  border-radius:20px;padding:20px 22px;margin-bottom:10px;
  transition:all .25s;position:relative;overflow:hidden;
}
.sig-card::before{
  content:'';position:absolute;top:0;left:0;right:0;height:2px;
  border-radius:20px 20px 0 0;
}
.sig-buy::before{background:linear-gradient(90deg,#30d158,transparent);}
.sig-sell::before{background:linear-gradient(90deg,#ff453a,transparent);}
.sig-wait::before{background:linear-gradient(90deg,#ffd60a,transparent);}
.sig-expired::before{background:linear-gradient(90deg,rgba(255,255,255,.2),transparent);}
.sig-buy{border-color:rgba(48,209,88,.2);}
.sig-sell{border-color:rgba(255,69,58,.2);}
.sig-wait{border-color:rgba(255,214,10,.15);}
.sig-expired{opacity:.5;}
.sig-pair{font-size:1rem;font-weight:700;color:#fff;}
.sig-action-buy{font-size:1.8rem;font-weight:900;color:#30d158;letter-spacing:-.02em;}
.sig-action-sell{font-size:1.8rem;font-weight:900;color:#ff453a;letter-spacing:-.02em;}
.sig-action-wait{font-size:1.8rem;font-weight:900;color:#ffd60a;letter-spacing:-.02em;}
.sig-bar-fill-buy{background:#30d158;height:4px;border-radius:2px;transition:width .5s;}
.sig-bar-fill-sell{background:#ff453a;height:4px;border-radius:2px;transition:width .5s;}
.sig-bar-fill-wait{background:#ffd60a;height:4px;border-radius:2px;transition:width .5s;}
.sig-bar-bg{background:rgba(255,255,255,.08);height:4px;border-radius:2px;overflow:hidden;margin:8px 0;}
.cd-pill{
  display:inline-flex;align-items:center;gap:5px;
  background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.1);
  border-radius:20px;padding:3px 10px;font-size:.72rem;color:rgba(255,255,255,.5);
}
.news-pill{
  display:inline-block;background:rgba(10,132,255,.15);
  border:1px solid rgba(10,132,255,.25);border-radius:20px;
  padding:2px 10px;font-size:.7rem;color:#0a84ff;margin-right:4px;margin-bottom:4px;
}
.news-pill-bear{background:rgba(255,69,58,.12)!important;border-color:rgba(255,69,58,.25)!important;color:#ff453a!important;}
.news-pill-bull{background:rgba(48,209,88,.12)!important;border-color:rgba(48,209,88,.25)!important;color:#30d158!important;}

/* ── STAT GRID ── */
.stat-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:12px;}
.stat-item{background:rgba(255,255,255,.04);border-radius:12px;padding:10px 12px;}
.stat-val{font-size:.92rem;font-weight:700;color:#fff;}
.stat-lbl{font-size:.68rem;color:rgba(255,255,255,.35);text-transform:uppercase;letter-spacing:.06em;margin-top:2px;}

/* ── NEWS CARD ── */
.news-card{
  background:rgba(28,28,30,.6);border:1px solid rgba(255,255,255,.07);
  border-radius:16px;padding:16px 18px;margin-bottom:8px;
}
.news-title{font-size:.9rem;font-weight:600;color:#fff;line-height:1.45;margin-bottom:6px;}
.news-meta{font-size:.72rem;color:rgba(255,255,255,.35);}
.news-sentiment-bull{color:#30d158;font-weight:700;}
.news-sentiment-bear{color:#ff453a;font-weight:700;}
.news-sentiment-neu{color:rgba(255,255,255,.4);font-weight:600;}

/* ── METRIC ROW ── */
.metric-row{display:flex;gap:12px;margin:16px 0;flex-wrap:wrap;}
.metric-card{
  flex:1;min-width:120px;background:rgba(28,28,30,.8);
  border:1px solid rgba(255,255,255,.08);border-radius:16px;
  padding:16px 18px;text-align:center;
}
.metric-card-val{font-size:1.5rem;font-weight:800;letter-spacing:-.02em;}
.metric-card-lbl{font-size:.72rem;color:rgba(255,255,255,.35);text-transform:uppercase;letter-spacing:.06em;margin-top:4px;}

/* ── PLATFORM GUIDE ── */
.platform-header{
  border-radius:14px 14px 0 0;padding:12px 18px;
  font-size:.85rem;font-weight:700;letter-spacing:.02em;
  display:flex;align-items:center;gap:8px;
}
.platform-mt{background:#1c237e;color:#82b1ff;}
.platform-tv{background:#131722;color:#b2b5be;}
.platform-ig{background:#003087;color:#5b9bd5;}
.step-list{
  background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);
  border-radius:0 0 14px 14px;padding:18px 20px;
}
.step-row{display:flex;gap:12px;margin-bottom:12px;align-items:flex-start;}
.step-num{
  min-width:26px;height:26px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;
  font-size:.75rem;font-weight:700;flex-shrink:0;margin-top:1px;
}
.step-num-mt{background:rgba(130,177,255,.2);color:#82b1ff;}
.step-num-tv{background:rgba(38,166,154,.2);color:#26a69a;}
.step-num-ig{background:rgba(91,155,213,.2);color:#5b9bd5;}
.step-text{font-size:.86rem;color:rgba(255,255,255,.75);line-height:1.55;}
.price-tag{
  display:inline-block;background:rgba(255,255,255,.08);
  border-radius:6px;padding:1px 7px;font-family:monospace;
  font-size:.84rem;color:#fff;font-weight:600;
}
.tp-tag{background:rgba(48,209,88,.15)!important;color:#30d158!important;}
.sl-tag{background:rgba(255,69,58,.15)!important;color:#ff453a!important;}
.entry-tag{background:rgba(255,214,10,.1)!important;color:#ffd60a!important;}

/* ── CONFIRM ── */
.confirm-ok{
  background:rgba(48,209,88,.08);border:1px solid rgba(48,209,88,.3);
  border-radius:16px;padding:20px;margin:12px 0;
}
.confirm-fail{
  background:rgba(255,69,58,.08);border:1px solid rgba(255,69,58,.3);
  border-radius:16px;padding:20px;margin:12px 0;
}

/* ── INTEL SECTION ── */
.intel-card{
  background:rgba(10,132,255,.07);border:1px solid rgba(10,132,255,.2);
  border-radius:16px;padding:16px 18px;margin-bottom:10px;
}
.intel-label{font-size:.7rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#0a84ff;margin-bottom:6px;}
.event-card{
  background:rgba(255,255,255,.04);border-left:3px solid rgba(255,214,10,.5);
  border-radius:0 12px 12px 0;padding:10px 14px;margin-bottom:8px;
}
.event-high{border-left-color:rgba(255,69,58,.6)!important;}
.event-med{border-left-color:rgba(255,159,10,.5)!important;}
.event-low{border-left-color:rgba(255,255,255,.2)!important;}

/* ── CONFIDENCE BAR ── */
.conf-wrap{background:rgba(255,255,255,.08);border-radius:6px;height:8px;overflow:hidden;}
.conf-fill-buy{background:linear-gradient(90deg,#30d158,#34c759);height:8px;border-radius:6px;transition:width .8s cubic-bezier(.16,1,.3,1);}
.conf-fill-sell{background:linear-gradient(90deg,#ff453a,#ff6b6b);height:8px;border-radius:6px;transition:width .8s cubic-bezier(.16,1,.3,1);}
.conf-fill-wait{background:linear-gradient(90deg,#ffd60a,#ff9f0a);height:8px;border-radius:6px;transition:width .8s cubic-bezier(.16,1,.3,1);}

/* ── SECTION HEADERS ── */
.section-eyebrow{font-size:.72rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:rgba(255,255,255,.3);margin-bottom:6px;}
.section-title{font-size:1.6rem;font-weight:800;letter-spacing:-.02em;color:#fff;margin-bottom:4px;}
.section-sub{font-size:.9rem;color:rgba(255,255,255,.4);margin-bottom:20px;}

/* ── TICKER STRIP ── */
.ticker-strip{
  background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07);
  border-radius:12px;padding:10px 18px;
  display:flex;gap:24px;overflow-x:auto;white-space:nowrap;margin-bottom:24px;
}
.ticker-item{display:inline-flex;flex-direction:column;gap:1px;min-width:80px;}
.ticker-sym{font-size:.72rem;color:rgba(255,255,255,.35);font-weight:600;letter-spacing:.04em;}
.ticker-price{font-size:.92rem;font-weight:700;color:#fff;}
.ticker-chg-up{font-size:.72rem;color:#30d158;font-weight:600;}
.ticker-chg-dn{font-size:.72rem;color:#ff453a;font-weight:600;}

/* ── SCANNING PULSE ── */
@keyframes scanPulse{0%,100%{opacity:1}50%{opacity:.4}}
.scanning{animation:scanPulse 1.4s ease-in-out infinite;}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.fade-in{animation:fadeIn .4s ease-out forwards;}

/* ── CLOCK ── */
.live-clock{
  text-align:right;font-size:.82rem;color:rgba(255,255,255,.3);
  font-variant-numeric:tabular-nums;letter-spacing:.02em;
}
.live-dot{
  display:inline-block;width:7px;height:7px;border-radius:50%;
  background:#30d158;margin-right:6px;
  box-shadow:0 0 8px rgba(48,209,88,.6);
}
@keyframes livePulse{0%,100%{opacity:1;box-shadow:0 0 8px rgba(48,209,88,.6)}
  50%{opacity:.6;box-shadow:0 0 4px rgba(48,209,88,.3)}}
.live-dot{animation:livePulse 2s ease-in-out infinite;}
</style>
""", unsafe_allow_html=True)

# ── constants ─────────────────────────────────────────────────────────────────
PAIRS = {
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X", "GBP/JPY": "GBPJPY=X",
    "AUD/USD": "AUDUSD=X", "USD/CAD": "USDCAD=X",
    "USD/CHF": "USDCHF=X", "NZD/USD": "NZDUSD=X",
    "EUR/GBP": "EURGBP=X", "EUR/JPY": "EURJPY=X",
}
TIMEFRAMES = {
    "1 min  · Scalping":        ("1m",  "5d",   60),
    "5 min  · Recommended ✦":   ("5m",  "5d",  300),
    "15 min · Swing Prep":      ("15m", "5d",  900),
    "1 hour · Swing":           ("1h", "30d", 3600),
}
LEVERAGE_MAP = {
    "1:1  No leverage":   1,
    "1:10  Low":         10,
    "1:30  Medium":      30,
    "1:100  High":      100,
    "1:500  Very high": 500,
}
TP_PIPS = {"20 pips  Conservative": 20, "35 pips  Standard": 35, "60 pips  Aggressive": 60}
SL_PIPS = {"15 pips  Tight": 15, "25 pips  Standard": 25, "40 pips  Wide": 40}

# Currency → which pairs it affects
CURRENCY_PAIRS = {
    "USD": ["EUR/USD","GBP/USD","USD/JPY","AUD/USD","USD/CAD","USD/CHF","NZD/USD","GBP/JPY","EUR/JPY"],
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
ECON_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

BULLISH_WORDS = {
    "rise","rises","rose","up","gain","gains","gained","bull","bullish","strong","strengthen",
    "rally","rallied","surge","surged","jump","jumped","high","higher","growth","positive",
    "beat","exceeded","exceed","boost","boosted","hawkish","hike","raised rate",
    "optimism","recovery","expansion","strong data","better than expected","above forecast",
    "robust","momentum","support","buying","bought","demand","confidence",
}
BEARISH_WORDS = {
    "fall","falls","fell","down","drop","dropped","drops","bear","bearish","weak","weaken",
    "decline","declined","plunge","plunged","dive","dived","low","lower","recession",
    "miss","missed","disappoint","disappointed","cut","dovish","rate cut","slowdown",
    "contraction","concern","uncertainty","risk off","worse than expected","below forecast",
    "pressure","selling","sold","supply","caution","fear","worry","crisis","slowdown",
}

# ── session state ─────────────────────────────────────────────────────────────
_defaults = {
    "signals": {}, "last_scan": 0,
    "news_cache": [], "news_fetched_at": 0,
    "econ_cache": [], "econ_fetched_at": 0,
    "pair_sentiment": {},
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── helpers ───────────────────────────────────────────────────────────────────
def pip_size(sym): return 0.01 if "JPY" in sym else 0.0001

def calc_profit(amount, leverage, pips, ps, price):
    pos = amount * leverage
    return (pos * pips * ps / price) if ps == 0.01 else (pos * pips * ps)

def speak(key, text):
    if not IS_MAC: return
    if text != st.session_state.get(f"_spoken_{key}", ""):
        st.session_state[f"_spoken_{key}"] = text
        try:
            subprocess.Popen(["say", "-r", "175", text],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception: pass

def fmt_countdown(issued_at, valid_secs):
    rem = max(0, valid_secs - (time.time() - issued_at))
    if rem == 0: return "Expired"
    m, s = divmod(int(rem), 60)
    return f"{m}m {s:02d}s" if m else f"{s}s"

def is_expired(issued_at, valid_secs):
    return (time.time() - issued_at) >= valid_secs

def sentiment_score_text(text):
    t = text.lower()
    bull = sum(1 for w in BULLISH_WORDS if w in t)
    bear = sum(1 for w in BEARISH_WORDS if w in t)
    return min(5, max(-5, bull - bear))

# ── internet news fetch ───────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)   # 5-min cache
def fetch_fx_news():
    """Fetch FX news from multiple free RSS feeds + yfinance."""
    articles = []

    # 1) RSS feeds
    for url in NEWS_FEEDS:
        try:
            r = requests.get(url, timeout=6,
                             headers={"User-Agent": "Mozilla/5.0 FXProTrader/1.0"})
            root = ET.fromstring(r.text)
            for item in list(root.iter("item"))[:8]:
                title = item.findtext("title", "").strip()
                desc  = item.findtext("description", "").strip()
                link  = item.findtext("link", "").strip()
                pub   = item.findtext("pubDate", "").strip()
                if title:
                    articles.append({
                        "title": title, "desc": desc[:200],
                        "link": link, "pub": pub, "source": url.split("/")[2],
                        "score": sentiment_score_text(title + " " + desc),
                    })
        except Exception:
            pass

    # 2) yfinance news for EUR/USD (broad market coverage)
    try:
        t = yf.Ticker("EURUSD=X")
        for n in (t.news or [])[:6]:
            title = n.get("title", "")
            desc  = n.get("summary", "")
            if title:
                articles.append({
                    "title": title, "desc": desc[:200],
                    "link": n.get("link", ""), "pub": "",
                    "source": "Yahoo Finance",
                    "score": sentiment_score_text(title + " " + desc),
                })
    except Exception:
        pass

    # dedupe by title prefix
    seen, unique = set(), []
    for a in articles:
        key = a["title"][:40]
        if key not in seen:
            seen.add(key)
            unique.append(a)

    return unique[:20]

@st.cache_data(ttl=1800, show_spinner=False)  # 30-min cache
def fetch_econ_calendar():
    """Fetch this week's economic calendar from ForexFactory."""
    try:
        r = requests.get(ECON_CALENDAR_URL, timeout=8,
                         headers={"User-Agent": "Mozilla/5.0"})
        data = r.json()
        events = []
        now = datetime.datetime.utcnow()
        for ev in data:
            try:
                ev_dt = datetime.datetime.fromisoformat(ev.get("date","").replace("Z",""))
                if ev_dt >= now - datetime.timedelta(hours=2):
                    events.append({
                        "time":     ev_dt.strftime("%H:%M UTC"),
                        "currency": ev.get("country","").upper(),
                        "event":    ev.get("title",""),
                        "impact":   ev.get("impact","").lower(),
                        "forecast": ev.get("forecast",""),
                        "previous": ev.get("previous",""),
                        "dt":       ev_dt,
                    })
            except Exception:
                pass
        return sorted(events, key=lambda x: x["dt"])[:15]
    except Exception:
        return []

def build_pair_sentiment(news_articles):
    """Map news sentiment onto each FX pair."""
    pair_scores = {p: 0 for p in PAIRS}
    for art in news_articles:
        text = (art["title"] + " " + art["desc"]).upper()
        for currency, affected_pairs in CURRENCY_PAIRS.items():
            if currency in text:
                s = art["score"]
                for p in affected_pairs:
                    # if USD is bullish, USD pairs (EUR/USD) go down — invert for non-USD base
                    if currency == "USD":
                        pair_scores[p] += -s if p.startswith("USD") else s
                    else:
                        pair_scores[p] += s if p.startswith(currency.replace("USD","").strip("/")) else -s/2
    return {p: max(-5, min(5, round(v, 1))) for p, v in pair_scores.items()}

# ── market data ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def fetch_data(yf_sym, interval, period):
    try:
        df = yf.download(yf_sym, interval=interval, period=period,
                         auto_adjust=True, progress=False)
        if df.empty or len(df) < 30: return None
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        return df[["Open","High","Low","Close","Volume"]].dropna()
    except Exception:
        return None

@st.cache_data(ttl=30, show_spinner=False)
def fetch_live_price(yf_sym):
    try:
        t = yf.Ticker(yf_sym)
        info = t.fast_info
        return float(info.last_price), float(getattr(info, "regular_market_change_percent", 0) or 0)
    except Exception:
        return None, None

# ── signal scoring ────────────────────────────────────────────────────────────
def score_technicals(df, sym):
    c, h, lo = df["Close"], df["High"], df["Low"]
    score = 0
    reasons = []

    # RSI
    delta = c.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rsi   = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    rsi_v = float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else 50
    if rsi_v < 30:
        score += 3; reasons.append("RSI oversold (buy pressure)")
    elif rsi_v < 42:
        score += 1; reasons.append("RSI leaning bullish")
    elif rsi_v > 70:
        score -= 3; reasons.append("RSI overbought (sell pressure)")
    elif rsi_v > 58:
        score -= 1; reasons.append("RSI leaning bearish")

    # MACD
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    macd  = ema12 - ema26
    sig9  = macd.ewm(span=9, adjust=False).mean()
    if len(macd) >= 2:
        cross_up   = macd.iloc[-1] > sig9.iloc[-1] and macd.iloc[-2] <= sig9.iloc[-2]
        cross_down = macd.iloc[-1] < sig9.iloc[-1] and macd.iloc[-2] >= sig9.iloc[-2]
        if cross_up:    score += 3; reasons.append("MACD bullish crossover")
        elif cross_down: score -= 3; reasons.append("MACD bearish crossover")
        elif macd.iloc[-1] > sig9.iloc[-1]: score += 1
        else: score -= 1

    # Bollinger Bands
    sma20 = c.rolling(20).mean()
    std20 = c.rolling(20).std()
    price = float(c.iloc[-1])
    b_up, b_dn = float((sma20 + 2*std20).iloc[-1]), float((sma20 - 2*std20).iloc[-1])
    if b_dn > 0 and price <= b_dn:
        score += 2; reasons.append("Price at lower Bollinger Band")
    elif b_up > 0 and price >= b_up:
        score -= 2; reasons.append("Price at upper Bollinger Band")

    # EMA trend
    e20  = float(c.ewm(span=20,  adjust=False).mean().iloc[-1])
    e50  = float(c.ewm(span=50,  adjust=False).mean().iloc[-1])
    e200 = float(c.ewm(span=200, adjust=False).mean().iloc[-1])
    if e20 > e50 > e200:
        score += 2; reasons.append("EMA uptrend (20>50>200)")
    elif e20 < e50 < e200:
        score -= 2; reasons.append("EMA downtrend (20<50<200)")

    # Stochastic
    low14  = lo.rolling(14).min()
    high14 = h.rolling(14).max()
    try:
        k_v = float((100 * (c - low14) / (high14 - low14).replace(0, np.nan)).iloc[-1])
    except Exception:
        k_v = 50
    if k_v < 20:    score += 1; reasons.append("Stochastic oversold")
    elif k_v > 80:  score -= 1; reasons.append("Stochastic overbought")

    # ATR
    tr    = pd.concat([(h-lo), (h-c.shift()).abs(), (lo-c.shift()).abs()], axis=1).max(axis=1)
    atr   = float(tr.rolling(14).mean().iloc[-1])
    ps    = pip_size(sym)
    tp_p  = max(15, min(80, round(atr / ps * 1.5)))
    sl_p  = max(10, min(50, round(atr / ps * 1.0)))

    score = max(-10, min(10, score))

    if score >= 4:
        action = "BUY"
        tp, sl = price + tp_p*ps, price - sl_p*ps
    elif score <= -4:
        action = "SELL"
        tp, sl = price - tp_p*ps, price + sl_p*ps
    else:
        action = "WAIT"
        tp, sl = price + tp_p*ps, price - sl_p*ps

    return action, score, price, tp, sl, tp_p, sl_p, rsi_v, reasons

def scan_one(pair, yf_sym, interval, period, valid_secs, tf_label, news_sentiment):
    df = fetch_data(yf_sym, interval, period)
    if df is None:
        return pair, None
    action, tech_score, entry, tp, sl, tp_pips, sl_pips, rsi_v, reasons = score_technicals(df, pair)
    news_s  = news_sentiment.get(pair, 0)
    combined = max(-10, min(10, tech_score + round(news_s * 0.5)))
    if combined >= 4:   final_action = "BUY"
    elif combined <= -4: final_action = "SELL"
    else:               final_action = "WAIT"
    confidence = min(99, max(30, int(abs(combined) / 10 * 65 + 35)))

    return pair, {
        "action": final_action, "tech_score": tech_score,
        "news_score": news_s, "combined": combined,
        "confidence": confidence,
        "entry": entry, "tp": tp, "sl": sl,
        "tp_pips": tp_pips, "sl_pips": sl_pips,
        "rsi": rsi_v, "reasons": reasons,
        "issued_at": time.time(), "valid_secs": valid_secs,
        "tf_label": tf_label, "df": df,
    }

# ── chart builder ─────────────────────────────────────────────────────────────
def build_chart(df, pair, action, entry, tp, sl, theme="dark"):
    palettes = {
        "dark":        dict(bg="#000000",    grid="#1a1a1a", up="#30d158", dn="#ff453a",
                            tp_c="#30d158",  sl_c="#ff453a", en_c="#ffd60a", txt="#ffffff"),
        "metatrader":  dict(bg="#131722",    grid="#1e2230", up="#26a69a", dn="#ef5350",
                            tp_c="#26a69a",  sl_c="#ef5350", en_c="#2962ff", txt="#b2b5be"),
        "tradingview": dict(bg="#131722",    grid="#1e222d", up="#26a69a", dn="#ef5350",
                            tp_c="#26a69a",  sl_c="#ef5350", en_c="#2962ff", txt="#b2b5be"),
        "ig":          dict(bg="#0d1b2e",    grid="#1a2d45", up="#00b386", dn="#e63946",
                            tp_c="#00b386",  sl_c="#e63946", en_c="#5b9bd5", txt="#cce4ff"),
    }
    t = palettes.get(theme, palettes["dark"])
    last = df.tail(80)
    fig  = make_subplots(rows=2, cols=1, shared_xaxes=True,
                         row_heights=[0.78, 0.22], vertical_spacing=0.015)

    fig.add_trace(go.Candlestick(
        x=last.index, open=last["Open"], high=last["High"],
        low=last["Low"], close=last["Close"],
        increasing_fillcolor=t["up"], increasing_line_color=t["up"],
        decreasing_fillcolor=t["dn"], decreasing_line_color=t["dn"],
        name="Price", line_width=1), row=1, col=1)

    x0, x1 = last.index[0], last.index[-1]
    # annotation bg: always use rgba() so it works in every Plotly version
    ann_bg = "rgba(0,0,0,0.75)" if t["bg"] in ("#000000","#000") else "rgba(19,23,34,0.85)"
    for pv, clr, lbl, dash, w in [
        (tp,    t["tp_c"], f"TP  {tp:.5f}",      "dash", 1.5),
        (sl,    t["sl_c"], f"SL  {sl:.5f}",      "dash", 1.5),
        (entry, t["en_c"], f"Entry  {entry:.5f}", "dot",  1.5),
    ]:
        fig.add_shape(type="line", x0=x0, x1=x1, y0=pv, y1=pv,
                      line=dict(color=clr, width=w, dash=dash), row=1, col=1)
        # add_annotation does NOT accept row/col — annotations are layout-level
        fig.add_annotation(x=x1, y=pv, text=f"<b>{lbl}</b>", showarrow=False,
                           xref="x", yref="y",
                           xanchor="right", yanchor="middle",
                           font=dict(color=clr, size=10),
                           bgcolor=ann_bg, borderpad=3, bordercolor=clr,
                           borderwidth=0, opacity=0.9)

    zone_c = "rgba(48,209,88,0.06)" if action == "BUY" else "rgba(255,69,58,0.06)"
    fig.add_shape(type="rect", x0=x0, x1=x1,
                  y0=min(sl, entry), y1=max(tp, entry),
                  fillcolor=zone_c, line_width=0, row=1, col=1)

    vol_colors = [t["up"] if c >= o else t["dn"]
                  for c, o in zip(last["Close"], last["Open"])]
    fig.add_trace(go.Bar(x=last.index, y=last["Volume"],
                         marker_color=vol_colors, showlegend=False,
                         marker_opacity=0.6), row=2, col=1)

    ac = {"BUY": t["tp_c"], "SELL": t["sl_c"]}.get(action, t["en_c"])
    fig.update_layout(
        title=dict(text=f"<b>{pair}</b>  ·  {action}", font=dict(color=ac, size=15)),
        height=440, paper_bgcolor=t["bg"], plot_bgcolor=t["bg"],
        xaxis_rangeslider_visible=False,
        font=dict(color=t["txt"], size=10, family="-apple-system,'Inter',sans-serif"),
        margin=dict(l=8, r=8, t=48, b=8),
        legend_bgcolor=t["bg"],
    )
    for ax in ["xaxis","xaxis2","yaxis","yaxis2"]:
        fig.update_layout(**{ax: dict(
            gridcolor=t["grid"], gridwidth=1, zerolinecolor=t["grid"],
            tickfont=dict(color=t["txt"]), showgrid=True,
        )})
    return fig

# ── AI confirm ────────────────────────────────────────────────────────────────
def ai_confirm_screenshot(img_bytes, pair, action, entry, tp, sl):
    if not HAS_OLLAMA:
        return "⚠ Ollama is not installed. Visit ollama.com, install it, then run: ollama pull moondream:latest"
    prompt = (
        f"This is a screenshot of a trading platform for {pair}. "
        f"The correct trade setup is: {action}, "
        f"Entry ≈ {entry:.5f}, Take Profit ≈ {tp:.5f}, Stop Loss ≈ {sl:.5f}. "
        "Check: 1) Is the correct pair shown? 2) Is the direction (buy/sell) correct? "
        "3) Are TP and SL lines set roughly to the right levels? "
        "4) What, if anything, is wrong or missing? "
        "Be specific. Start your reply with ✅ CONFIRMED if everything looks correct, "
        "or ❌ NOT CORRECT followed by exactly what to fix."
    )
    try:
        import ollama
        resp = ollama.chat(model="moondream:latest",
                           messages=[{"role":"user","content":prompt,"images":[img_bytes]}])
        return resp["message"]["content"]
    except Exception as e:
        return f"⚠ Vision AI error: {e}"

# ══════════════════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════════════════

# ── HEADER ────────────────────────────────────────────────────────────────────
h_left, h_right = st.columns([4, 2])
with h_left:
    st.markdown("""
<div style='padding:28px 0 0'>
  <div style='font-size:.72rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:rgba(255,255,255,.3);margin-bottom:8px;'>
    ◈ FX PRO TRADER
  </div>
  <div style='font-size:2.2rem;font-weight:800;letter-spacing:-.04em;color:#fff;line-height:1.1;'>
    Intelligent FX Signals<br>
    <span style='color:rgba(255,255,255,.3);font-weight:300;font-size:1.6rem;'>powered by live market intelligence</span>
  </div>
</div>""", unsafe_allow_html=True)
with h_right:
    clock_ph = st.empty()

@st.fragment(run_every="1s")
def live_clock():
    now = datetime.datetime.now()
    market_open = now.weekday() < 5 and 6 <= now.hour < 22
    clock_ph.markdown(
        f"<div class='live-clock' style='padding-top:38px;'>"
        f"<span class='live-dot'></span>"
        f"{'MARKETS OPEN' if market_open else 'MARKETS CLOSED'}"
        f"<br>{now.strftime('%H:%M:%S')} · {now.strftime('%a %d %b %Y')}</div>",
        unsafe_allow_html=True)

live_clock()
st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)

# ── SETTINGS ─────────────────────────────────────────────────────────────────
with st.expander("⚙  Settings", expanded=False):
    c1, c2, c3, c4 = st.columns(4)
    with c1: tf_label   = st.selectbox("Timeframe", list(TIMEFRAMES.keys()), index=1, key="tf_label")
    with c2: lev_label  = st.selectbox("Leverage",  list(LEVERAGE_MAP.keys()), index=2, key="lev_label")
    with c3: amt_gbp    = st.number_input("Trade amount (£)", 1.0, 10000.0, 20.0, 5.0, key="amt_gbp")
    with c4: auto_scan  = st.toggle("Auto-rescan on expiry", True, key="auto_rescan")

tf_interval, tf_period, tf_valid = TIMEFRAMES[tf_label]
leverage = LEVERAGE_MAP[lev_label]
st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ── TABS ──────────────────────────────────────────────────────────────────────
T_scan, T_intel, T_guide, T_confirm = st.tabs([
    "◉  Best Trade Now",
    "◎  Market Intelligence",
    "▦  Platform Guide",
    "◷  Confirm Setup",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — BEST TRADE NOW
# ══════════════════════════════════════════════════════════════════════════════
with T_scan:
    scan_btn_col, scan_status_col = st.columns([2, 4])
    with scan_btn_col:
        do_scan = st.button("⟳  Scan All Markets", use_container_width=True, type="primary")
    with scan_status_col:
        scan_status_ph = st.empty()

    hero_ph  = st.empty()
    strip_ph = st.empty()
    grid_ph  = st.empty()

    @st.fragment(run_every=30)
    def scanner_frag():
        now     = time.time()
        sigs    = st.session_state.get("signals", {})
        rescan  = bool(do_scan)

        if st.session_state.get("auto_rescan", True):
            if not sigs or (now - st.session_state.get("last_scan", 0)) > tf_valid:
                rescan = True
            else:
                for s in sigs.values():
                    if s and is_expired(s["issued_at"], s["valid_secs"]):
                        rescan = True; break

        # ── fetch news & sentiment ───────────────────────────────────────────
        news_articles = fetch_fx_news()
        pair_sentiment = build_pair_sentiment(news_articles)

        if rescan:
            scan_status_ph.markdown(
                "<div class='scanning' style='color:rgba(255,255,255,.5);font-size:.85rem;'>"
                "⟳ Scanning 10 markets — fetching live prices, news & signals…</div>",
                unsafe_allow_html=True)
            new_sigs = {}
            with ThreadPoolExecutor(max_workers=10) as ex:
                futs = {
                    ex.submit(scan_one, p, y, tf_interval, tf_period,
                              tf_valid, tf_label, pair_sentiment): p
                    for p, y in PAIRS.items()
                }
                for f in as_completed(futs):
                    p, s = f.result()
                    new_sigs[p] = s
            st.session_state["signals"] = new_sigs
            st.session_state["last_scan"] = now
            scan_status_ph.empty()

        sigs = st.session_state.get("signals", {})
        if not sigs:
            hero_ph.markdown(
                "<div style='text-align:center;padding:60px;color:rgba(255,255,255,.3);'>"
                "Click <b>Scan All Markets</b> to find the best trade</div>",
                unsafe_allow_html=True)
            return

        # ── sort: strongest actionable first ────────────────────────────────
        def sort_key(item):
            _, s = item
            if s is None: return (3, 0)
            if s["action"] in ("BUY","SELL"): return (0, -s["confidence"])
            return (1, -abs(s["combined"]))

        sorted_sigs = sorted(sigs.items(), key=sort_key)
        best_pair, best_sig = sorted_sigs[0]

        # ── HERO: THE best trade ─────────────────────────────────────────────
        with hero_ph.container():
            if best_sig and best_sig["action"] in ("BUY","SELL"):
                action  = best_sig["action"]
                entry   = best_sig["entry"]
                tp      = best_sig["tp"]
                sl      = best_sig["sl"]
                profit  = calc_profit(amt_gbp, leverage, best_sig["tp_pips"],
                                      pip_size(best_pair), entry)
                loss_v  = calc_profit(amt_gbp, leverage, best_sig["sl_pips"],
                                      pip_size(best_pair), entry)
                conf    = best_sig["confidence"]
                cd      = fmt_countdown(best_sig["issued_at"], best_sig["valid_secs"])
                expired = is_expired(best_sig["issued_at"], best_sig["valid_secs"])
                hero_cls = "hero-buy" if action=="BUY" else "hero-sell"
                a_cls    = "hero-action-buy" if action=="BUY" else "hero-action-sell"
                badge_c  = "" if action=="BUY" else "hero-badge-sell"
                rr_ratio = profit / max(loss_v, 0.01)
                why_txt  = " · ".join(best_sig.get("reasons",["Strong signal"])[:3])
                news_lbl = "📰 News confirms" if best_sig["news_score"] > 0 and action=="BUY" \
                      else ("📰 News confirms" if best_sig["news_score"] < 0 and action=="SELL" \
                      else "📰 News neutral")

                st.markdown(f"""
<div class="hero-wrap {hero_cls} fade-in">
  <div class="hero-badge {badge_c}">{conf}% confidence</div>
  <div class="hero-tag">◉ STRONGEST SIGNAL RIGHT NOW</div>
  <div class="{a_cls}">{action}</div>
  <div class="hero-pair">{best_pair}</div>
  <div class="hero-why">Technical: {why_txt}<br>{news_lbl} · {cd} remaining on this signal</div>
  <div class="hero-stats">
    <div class="hero-stat">
      <div class="hero-stat-val" style="font-family:monospace">{entry:.5f}</div>
      <div class="hero-stat-lbl">Entry Price</div>
    </div>
    <div class="hero-stat">
      <div class="hero-stat-val" style="color:#30d158;font-family:monospace">{tp:.5f}</div>
      <div class="hero-stat-lbl">Take Profit</div>
    </div>
    <div class="hero-stat">
      <div class="hero-stat-val" style="color:#ff453a;font-family:monospace">{sl:.5f}</div>
      <div class="hero-stat-lbl">Stop Loss</div>
    </div>
    <div class="hero-stat">
      <div class="hero-stat-val" style="color:#30d158">+£{profit:.2f}</div>
      <div class="hero-stat-lbl">If you win (£{amt_gbp:.0f} trade)</div>
    </div>
    <div class="hero-stat">
      <div class="hero-stat-val" style="color:#ff453a">-£{loss_v:.2f}</div>
      <div class="hero-stat-lbl">If stopped out</div>
    </div>
    <div class="hero-stat">
      <div class="hero-stat-val">{rr_ratio:.1f}:1</div>
      <div class="hero-stat-lbl">Risk / Reward</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

                speak(f"hero_{best_pair}_{best_sig['issued_at']:.0f}",
                      f"Best trade now. {action} {best_pair.replace('/','')}. "
                      f"Confidence {conf} percent.")

                # chart
                fig = build_chart(best_sig["df"], best_pair, action, entry, tp, sl)
                st.plotly_chart(fig, use_container_width=True, key="hero_chart")

        # ── price ticker strip ───────────────────────────────────────────────
        with strip_ph.container():
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            strip_items = ""
            for pair in list(PAIRS.keys())[:8]:
                price, chg = fetch_live_price(PAIRS[pair])
                if price:
                    chg_cls  = "ticker-chg-up" if (chg or 0) >= 0 else "ticker-chg-dn"
                    chg_sign = "+" if (chg or 0) >= 0 else ""
                    strip_items += f"""
<div class="ticker-item">
  <div class="ticker-sym">{pair}</div>
  <div class="ticker-price">{price:.5f}</div>
  <div class="{chg_cls}">{chg_sign}{chg:.3f}%</div>
</div>"""
            st.markdown(f'<div class="ticker-strip">{strip_items}</div>',
                        unsafe_allow_html=True)

        # ── ALL PAIRS GRID ────────────────────────────────────────────────────
        with grid_ph.container():
            st.markdown("""
<div style='margin-bottom:16px;'>
  <div class='section-eyebrow'>ALL MARKETS</div>
  <div class='section-title' style='font-size:1.3rem;'>Every pair — ranked by signal strength</div>
</div>""", unsafe_allow_html=True)

            cols = st.columns(2)
            for i, (pair, sig) in enumerate(sorted_sigs):
                with cols[i % 2]:
                    if sig is None:
                        st.markdown(
                            f'<div class="sig-card sig-expired">'
                            f'<div class="sig-pair">⚠ {pair}</div>'
                            f'<div style="font-size:.8rem;color:rgba(255,255,255,.3);margin-top:4px;">No data</div>'
                            f'</div>', unsafe_allow_html=True)
                        continue

                    action  = sig["action"]
                    expired = is_expired(sig["issued_at"], sig["valid_secs"])
                    cd      = fmt_countdown(sig["issued_at"], sig["valid_secs"])
                    conf    = sig["confidence"]
                    ps      = pip_size(pair)
                    profit  = calc_profit(amt_gbp, leverage, sig["tp_pips"], ps, sig["entry"])
                    loss_v  = calc_profit(amt_gbp, leverage, sig["sl_pips"], ps, sig["entry"])
                    bar_pct = abs(sig["combined"]) / 10 * 100
                    card_cls= {"BUY":"sig-buy","SELL":"sig-sell"}.get(action,"sig-wait")
                    if expired: card_cls = "sig-expired"
                    act_cls = {"BUY":"sig-action-buy","SELL":"sig-action-sell"}.get(action,"sig-action-wait")
                    bar_cls = {"BUY":"sig-bar-fill-buy","SELL":"sig-bar-fill-sell"}.get(action,"sig-bar-fill-wait")
                    news_s  = sig["news_score"]
                    news_indicator = (
                        f'<span class="news-pill news-pill-bull">📰 News bullish</span>' if news_s > 0
                        else f'<span class="news-pill news-pill-bear">📰 News bearish</span>' if news_s < 0
                        else '<span class="news-pill">📰 News neutral</span>'
                    )
                    cd_txt = "🔄 Rescanning…" if expired else cd

                    st.markdown(f"""
<div class="sig-card {card_cls}">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;">
    <div>
      <div class="sig-pair">{pair}</div>
      <div class="{act_cls}">{action}</div>
    </div>
    <div style="text-align:right;">
      <div class="cd-pill">{"⏰" if expired else "⏱"} {cd_txt}</div>
      <div style="font-size:.72rem;color:rgba(255,255,255,.3);margin-top:5px;">{conf}% confidence</div>
    </div>
  </div>
  <div class="sig-bar-bg"><div class="{bar_cls}" style="width:{bar_pct}%"></div></div>
  <div class="stat-grid">
    <div class="stat-item">
      <div class="stat-val" style="font-family:monospace;font-size:.82rem;">{sig['entry']:.5f}</div>
      <div class="stat-lbl">Entry</div>
    </div>
    <div class="stat-item">
      <div class="stat-val" style="color:#30d158;font-family:monospace;font-size:.82rem;">{sig['tp']:.5f}</div>
      <div class="stat-lbl">TP · +{sig['tp_pips']}p</div>
    </div>
    <div class="stat-item">
      <div class="stat-val" style="color:#ff453a;font-family:monospace;font-size:.82rem;">{sig['sl']:.5f}</div>
      <div class="stat-lbl">SL · -{sig['sl_pips']}p</div>
    </div>
  </div>
  <div style="display:flex;gap:14px;margin-top:12px;font-size:.8rem;flex-wrap:wrap;align-items:center;">
    <span>💰 <b style="color:#30d158">+£{profit:.2f}</b></span>
    <span>🛡 <b style="color:#ff453a">-£{loss_v:.2f}</b></span>
    <span style="color:rgba(255,255,255,.4)">RSI {sig['rsi']:.0f}</span>
    {news_indicator}
  </div>
</div>""", unsafe_allow_html=True)

    scanner_frag()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — MARKET INTELLIGENCE
# ══════════════════════════════════════════════════════════════════════════════
with T_intel:
    intel_ph = st.empty()

    @st.fragment(run_every=300)   # refresh every 5 min
    def intel_frag():
        with intel_ph.container():
            st.markdown("""
<div style='margin-bottom:20px;'>
  <div class='section-eyebrow'>LIVE MARKET INTELLIGENCE</div>
  <div class='section-title'>What the market is doing right now</div>
  <div class='section-sub'>News · Economic calendar · Market sentiment — all feeding your signals</div>
</div>""", unsafe_allow_html=True)

            with st.spinner("Fetching latest market intelligence…"):
                news_articles = fetch_fx_news()
                econ_events   = fetch_econ_calendar()
                pair_sent     = build_pair_sentiment(news_articles)

            # ── sentiment overview ──────────────────────────────────────────
            st.markdown("<div class='section-eyebrow' style='margin-bottom:10px;'>MARKET SENTIMENT BY PAIR</div>",
                        unsafe_allow_html=True)
            sent_cols = st.columns(5)
            pair_list = list(PAIRS.keys())
            for i, pair in enumerate(pair_list[:5]):
                with sent_cols[i]:
                    s = pair_sent.get(pair, 0)
                    clr = "#30d158" if s > 0.5 else ("#ff453a" if s < -0.5 else "#ffd60a")
                    lbl = "Bullish" if s > 0.5 else ("Bearish" if s < -0.5 else "Neutral")
                    st.markdown(
                        f'<div class="metric-card">'
                        f'<div class="metric-card-val" style="color:{clr};font-size:1.1rem;">{lbl}</div>'
                        f'<div style="font-size:.75rem;color:rgba(255,255,255,.3);margin-top:4px;">{pair}</div>'
                        f'<div style="font-size:.72rem;color:{clr};margin-top:2px;">{s:+.1f} news score</div>'
                        f'</div>', unsafe_allow_html=True)
            sent_cols2 = st.columns(5)
            for i, pair in enumerate(pair_list[5:10]):
                with sent_cols2[i]:
                    s = pair_sent.get(pair, 0)
                    clr = "#30d158" if s > 0.5 else ("#ff453a" if s < -0.5 else "#ffd60a")
                    lbl = "Bullish" if s > 0.5 else ("Bearish" if s < -0.5 else "Neutral")
                    st.markdown(
                        f'<div class="metric-card">'
                        f'<div class="metric-card-val" style="color:{clr};font-size:1.1rem;">{lbl}</div>'
                        f'<div style="font-size:.75rem;color:rgba(255,255,255,.3);margin-top:4px;">{pair}</div>'
                        f'<div style="font-size:.72rem;color:{clr};margin-top:2px;">{s:+.1f} news score</div>'
                        f'</div>', unsafe_allow_html=True)

            st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

            # ── two-column: news + calendar ─────────────────────────────────
            nc_left, nc_right = st.columns([3, 2])

            with nc_left:
                st.markdown("<div class='section-eyebrow' style='margin-bottom:12px;'>LATEST FX NEWS</div>",
                            unsafe_allow_html=True)
                if news_articles:
                    for art in news_articles[:12]:
                        s = art["score"]
                        sent_html = (
                            f"<span class='news-sentiment-bull'>▲ Bullish</span>" if s > 0
                            else f"<span class='news-sentiment-bear'>▼ Bearish</span>" if s < 0
                            else f"<span class='news-sentiment-neu'>— Neutral</span>"
                        )
                        title_clean = art["title"][:120]
                        source = art.get("source","").replace("www.","")
                        st.markdown(f"""
<div class="news-card fade-in">
  <div class="news-title">{title_clean}</div>
  <div class="news-meta">{sent_html} &nbsp;·&nbsp; {source}</div>
</div>""", unsafe_allow_html=True)
                else:
                    st.markdown(
                        '<div class="intel-card"><div class="intel-label">STATUS</div>'
                        'No news articles loaded yet — check your internet connection.</div>',
                        unsafe_allow_html=True)

                # refresh note
                st.markdown(
                    "<div style='font-size:.72rem;color:rgba(255,255,255,.2);margin-top:8px;'>"
                    f"🔄 News refreshes every 5 minutes · Last check: {datetime.datetime.now().strftime('%H:%M')}</div>",
                    unsafe_allow_html=True)

            with nc_right:
                st.markdown("<div class='section-eyebrow' style='margin-bottom:12px;'>ECONOMIC CALENDAR</div>",
                            unsafe_allow_html=True)
                if econ_events:
                    for ev in econ_events[:10]:
                        impact    = ev.get("impact","low")
                        ev_cls    = {"high":"event-high","medium":"event-med"}.get(impact,"event-low")
                        impact_ic = {"high":"🔴","medium":"🟠","low":"⚪"}.get(impact,"⚪")
                        forecast  = f"  Forecast: {ev['forecast']}" if ev.get("forecast") else ""
                        prev      = f"  Prev: {ev['previous']}" if ev.get("previous") else ""
                        st.markdown(f"""
<div class="event-card {ev_cls}">
  <div style="font-size:.88rem;font-weight:600;color:#fff;">{impact_ic} {ev['event'][:50]}</div>
  <div style="font-size:.72rem;color:rgba(255,255,255,.4);margin-top:4px;">
    🕐 {ev['time']} &nbsp;·&nbsp; {ev['currency']}{forecast}{prev}
  </div>
</div>""", unsafe_allow_html=True)
                else:
                    st.markdown(
                        '<div class="intel-card"><div class="intel-label">CALENDAR</div>'
                        'No upcoming high-impact events found for this week.</div>',
                        unsafe_allow_html=True)

                st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

                # ── how signals are calculated ──────────────────────────────
                st.markdown("<div class='section-eyebrow' style='margin-bottom:12px;'>HOW YOUR SIGNALS WORK</div>",
                            unsafe_allow_html=True)
                st.markdown("""
<div class="intel-card">
  <div class="intel-label">SIGNAL FORMULA</div>
  <div style="font-size:.84rem;color:rgba(255,255,255,.7);line-height:1.8;">
    <b style="color:#fff;">Technical Analysis</b> (RSI, MACD, Bollinger, EMA, Stochastic)
    <br>+ <b style="color:#0a84ff;">Live News Sentiment</b> (FX headlines scraped every 5 min)
    <br>+ <b style="color:#ffd60a;">Economic Calendar</b> (upcoming events that move markets)
    <br>= <b style="color:#30d158;">Combined Confidence Score</b>
    <br><br>
    Signals only show <b style="color:#30d158;">BUY</b> or <b style="color:#ff453a;">SELL</b>
    when score exceeds ±4/10. Below that = WAIT.
  </div>
</div>""", unsafe_allow_html=True)

    intel_frag()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — PLATFORM GUIDE
# ══════════════════════════════════════════════════════════════════════════════
with T_guide:
    st.markdown("""
<div style='margin-bottom:20px;'>
  <div class='section-eyebrow'>PLATFORM GUIDE</div>
  <div class='section-title'>Exactly what to do — step by step</div>
  <div class='section-sub'>See the annotated chart and click-by-click instructions for your platform</div>
</div>""", unsafe_allow_html=True)

    g1, g2, g3 = st.columns(3)
    with g1: guide_pair = st.selectbox("Pair", list(PAIRS.keys()), key="guide_pair")
    with g2: tp_label   = st.selectbox("Take Profit", list(TP_PIPS.keys()), index=1, key="tp_label")
    with g3: sl_label   = st.selectbox("Stop Loss", list(SL_PIPS.keys()), index=1, key="sl_label")

    guide_ph = st.empty()

    @st.fragment(run_every=120)
    def guide_frag():
        sig = st.session_state.get("signals", {}).get(guide_pair)
        if sig is None:
            guide_ph.markdown(
                '<div style="padding:40px;text-align:center;color:rgba(255,255,255,.3);">'
                '⟳ Run the scanner first (◉ Best Trade Now tab)</div>',
                unsafe_allow_html=True)
            return

        df     = sig.get("df")
        action = sig["action"]
        entry  = sig["entry"]
        tp_p   = TP_PIPS[tp_label]
        sl_p   = SL_PIPS[sl_label]
        ps     = pip_size(guide_pair)
        tp     = entry + tp_p*ps if action != "SELL" else entry - tp_p*ps
        sl     = entry - sl_p*ps if action != "SELL" else entry + sl_p*ps
        profit = calc_profit(amt_gbp, leverage, tp_p, ps, entry)
        loss_v = calc_profit(amt_gbp, leverage, sl_p, ps, entry)
        rr     = profit / max(loss_v, 0.01)
        ac     = "#30d158" if action=="BUY" else ("#ff453a" if action=="SELL" else "#ffd60a")

        with guide_ph.container():
            # signal summary bar
            st.markdown(f"""
<div style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);
     border-radius:16px;padding:20px 24px;margin-bottom:24px;display:flex;
     flex-wrap:wrap;gap:28px;align-items:center;">
  <div>
    <div style="font-size:.7rem;color:rgba(255,255,255,.3);text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px;">Signal</div>
    <div style="font-size:1.6rem;font-weight:900;color:{ac};letter-spacing:-.02em;">{action} {guide_pair}</div>
  </div>
  <div>
    <div style="font-size:.7rem;color:rgba(255,255,255,.3);text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px;">Entry</div>
    <div style="font-size:1.1rem;font-weight:700;font-family:monospace;">{entry:.5f}</div>
  </div>
  <div>
    <div style="font-size:.7rem;color:rgba(255,255,255,.3);text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px;">Take Profit</div>
    <div style="font-size:1.1rem;font-weight:700;color:#30d158;font-family:monospace;">{tp:.5f} <span style="font-size:.75rem;color:rgba(48,209,88,.6)">+{tp_p}p</span></div>
  </div>
  <div>
    <div style="font-size:.7rem;color:rgba(255,255,255,.3);text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px;">Stop Loss</div>
    <div style="font-size:1.1rem;font-weight:700;color:#ff453a;font-family:monospace;">{sl:.5f} <span style="font-size:.75rem;color:rgba(255,69,58,.6)">-{sl_p}p</span></div>
  </div>
  <div>
    <div style="font-size:.7rem;color:rgba(255,255,255,.3);text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px;">Win/Lose</div>
    <div style="font-size:1rem;font-weight:700;"><span style="color:#30d158">+£{profit:.2f}</span> <span style="color:rgba(255,255,255,.2)">/</span> <span style="color:#ff453a">-£{loss_v:.2f}</span></div>
  </div>
  <div>
    <div style="font-size:.7rem;color:rgba(255,255,255,.3);text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px;">R/R Ratio</div>
    <div style="font-size:1.1rem;font-weight:700;">{rr:.1f}:1</div>
  </div>
</div>""", unsafe_allow_html=True)

            pt_mt, pt_tv, pt_ig = st.tabs(["MetaTrader 4/5", "TradingView", "IG Broker"])
            bsw = "Buy" if action=="BUY" else ("Sell" if action=="SELL" else "Wait — no clear signal")

            # ── MetaTrader ──────────────────────────────────────────────────
            with pt_mt:
                if df is not None:
                    fig_mt = build_chart(df, guide_pair, action, entry, tp, sl, theme="metatrader")
                    fig_mt.update_layout(title=dict(text=f"MetaTrader · {guide_pair} · {action}",
                                                    font=dict(color="#82b1ff",size=13)))
                    st.plotly_chart(fig_mt, use_container_width=True, key="mt_c")

                st.markdown('<div class="platform-header platform-mt">📊 MetaTrader 4 / 5 — Step by step</div>', unsafe_allow_html=True)
                steps = [
                    (f"Open MetaTrader and find <b>{guide_pair}</b> in the <i>Market Watch</i> panel. Press <b>Ctrl+M</b> if you don't see it.", "step-num-mt"),
                    (f"Right-click the chart → <b>Timeframe</b> → select <b>{tf_interval.upper()}</b>.", "step-num-mt"),
                    (f"Press <b>F9</b> or click <b>New Order</b> in the toolbar to open the order window.", "step-num-mt"),
                    (f"Set direction to <b>{bsw}</b>. In the TP field type <span class='price-tag tp-tag'>{tp:.5f}</span> and in the SL field type <span class='price-tag sl-tag'>{sl:.5f}</span>.", "step-num-mt"),
                    (f"Click <b>{bsw} by Market</b> to place the trade.", "step-num-mt"),
                    (f"Check the <b>Terminal → Trade</b> tab. You should see a green TP line at <span class='price-tag tp-tag'>{tp:.5f}</span> and red SL line at <span class='price-tag sl-tag'>{sl:.5f}</span> on the chart.", "step-num-mt"),
                ]
                steps_html = '<div class="step-list">'
                for i, (txt, num_cls) in enumerate(steps, 1):
                    steps_html += f'<div class="step-row"><div class="step-num {num_cls}">{i}</div><div class="step-text">{txt}</div></div>'
                steps_html += '</div>'
                st.markdown(steps_html, unsafe_allow_html=True)

            # ── TradingView ─────────────────────────────────────────────────
            with pt_tv:
                if df is not None:
                    fig_tv = build_chart(df, guide_pair, action, entry, tp, sl, theme="tradingview")
                    fig_tv.update_layout(title=dict(text=f"TradingView · {guide_pair} · {action}",
                                                    font=dict(color="#26a69a",size=13)))
                    st.plotly_chart(fig_tv, use_container_width=True, key="tv_c")

                st.markdown('<div class="platform-header platform-tv">◼ TradingView — Step by step</div>', unsafe_allow_html=True)
                tv_steps = [
                    (f"Go to <b>tradingview.com</b> and search <b>{guide_pair.replace('/','')}</b> in the top search bar.", "step-num-tv"),
                    (f"Set timeframe: click the interval buttons at the top of the chart and select <b>{tf_interval.upper()}</b>.", "step-num-tv"),
                    (f"Use the <b>Long/Short Position</b> tool (left toolbar, or press <b>Shift+F</b>) to draw the trade: click at entry <span class='price-tag entry-tag'>{entry:.5f}</span>, then drag to set TP at <span class='price-tag tp-tag'>{tp:.5f}</span>.", "step-num-tv"),
                    (f"Adjust the SL line to <span class='price-tag sl-tag'>{sl:.5f}</span>. The shaded zone shows your risk/reward of <b>{rr:.1f}:1</b>.", "step-num-tv"),
                    (f"To place a real trade via a connected broker, click <b>Trading Panel</b> at the bottom → <b>{bsw}</b> → enter TP <span class='price-tag tp-tag'>{tp:.5f}</span> and SL <span class='price-tag sl-tag'>{sl:.5f}</span>.", "step-num-tv"),
                    (f"Your chart should show a <b>teal profit zone</b> above entry and a <b>red risk zone</b> below. Bottom of the position tool shows: Reward £{profit:.2f} / Risk £{loss_v:.2f}.", "step-num-tv"),
                ]
                tv_html = '<div class="step-list">'
                for i, (txt, nc) in enumerate(tv_steps, 1):
                    tv_html += f'<div class="step-row"><div class="step-num {nc}">{i}</div><div class="step-text">{txt}</div></div>'
                tv_html += '</div>'
                st.markdown(tv_html, unsafe_allow_html=True)

            # ── IG Broker ───────────────────────────────────────────────────
            with pt_ig:
                if df is not None:
                    fig_ig = build_chart(df, guide_pair, action, entry, tp, sl, theme="ig")
                    fig_ig.update_layout(title=dict(text=f"IG Broker · {guide_pair} · {action}",
                                                    font=dict(color="#5b9bd5",size=13)))
                    st.plotly_chart(fig_ig, use_container_width=True, key="ig_c")

                st.markdown('<div class="platform-header platform-ig">🔵 IG Broker — Step by step</div>', unsafe_allow_html=True)
                ig_steps = [
                    (f"Log in to <b>web.ig.com</b> or the IG app. Search for <b>{guide_pair}</b> in the search bar.", "step-num-ig"),
                    (f"Click <b>{bsw}</b> to open the deal ticket for {guide_pair}.", "step-num-ig"),
                    (f"In the deal ticket: set <b>Limit (TP)</b> to <span class='price-tag tp-tag'>{tp:.5f}</span>. This locks in your <b style='color:#30d158'>+£{profit:.2f}</b> profit when price reaches it.", "step-num-ig"),
                    (f"Set <b>Stop (SL)</b> to <span class='price-tag sl-tag'>{sl:.5f}</span>. This limits your loss to <b style='color:#ff453a'>-£{loss_v:.2f}</b> maximum.", "step-num-ig"),
                    (f"IG also shows pip distances: your TP is <b>{tp_p} pips</b> away and SL is <b>{sl_p} pips</b> away. Verify these match the fields.", "step-num-ig"),
                    (f"Click <b>Place deal</b> and confirm. Your open position appears in <b>My IG → Positions</b> with both lines on the chart.", "step-num-ig"),
                ]
                ig_html = '<div class="step-list">'
                for i, (txt, nc) in enumerate(ig_steps, 1):
                    ig_html += f'<div class="step-row"><div class="step-num {nc}">{i}</div><div class="step-text">{txt}</div></div>'
                ig_html += '</div>'
                st.markdown(ig_html, unsafe_allow_html=True)

    guide_frag()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — CONFIRM SETUP
# ══════════════════════════════════════════════════════════════════════════════
with T_confirm:
    st.markdown("""
<div style='margin-bottom:20px;'>
  <div class='section-eyebrow'>SETUP CONFIRMATION</div>
  <div class='section-title'>AI checks your screenshot</div>
  <div class='section-sub'>Upload a photo of your platform — AI tells you if it's set up correctly before you trade</div>
</div>""", unsafe_allow_html=True)

    cf1, cf2 = st.columns(2)
    with cf1: confirm_pair = st.selectbox("Pair", list(PAIRS.keys()), key="confirm_pair")
    with cf2: confirm_plat = st.selectbox("Platform", ["MetaTrader 4/5","TradingView","IG Broker"], key="confirm_plat")

    uploaded = st.file_uploader("Upload your screenshot (PNG or JPG)",
                                type=["png","jpg","jpeg"], key="screenshot_upload")

    if uploaded:
        img_bytes = uploaded.read()
        st.image(img_bytes, use_container_width=True)

        sig_c = st.session_state.get("signals",{}).get(confirm_pair)
        if sig_c is None:
            st.markdown(
                '<div class="intel-card"><div class="intel-label">ACTION NEEDED</div>'
                'Run the scanner first so I know what values to check against.</div>',
                unsafe_allow_html=True)
        else:
            action = sig_c["action"]
            entry  = sig_c["entry"]
            tp_p   = TP_PIPS.get(st.session_state.get("tp_label","35 pips  Standard"), 35)
            sl_p   = SL_PIPS.get(st.session_state.get("sl_label","25 pips  Standard"), 25)
            ps     = pip_size(confirm_pair)
            tp     = entry + tp_p*ps if action != "SELL" else entry - tp_p*ps
            sl     = entry - sl_p*ps if action != "SELL" else entry + sl_p*ps

            st.markdown(f"""
<div style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);
     border-radius:14px;padding:16px 20px;margin:12px 0;font-size:.86rem;">
  <b>Checking against:</b> {action} {confirm_pair} &nbsp;·&nbsp;
  Entry <span class="price-tag entry-tag">{entry:.5f}</span> &nbsp;
  TP <span class="price-tag tp-tag">{tp:.5f}</span> &nbsp;
  SL <span class="price-tag sl-tag">{sl:.5f}</span>
</div>""", unsafe_allow_html=True)

            if st.button("◎  Check with AI Vision", type="primary", use_container_width=False):
                if not HAS_OLLAMA:
                    st.markdown(
                        '<div class="confirm-fail">⚠ <b>Ollama not found.</b><br><br>'
                        'This feature needs the free Ollama AI running locally.<br>'
                        '1. Go to <b>ollama.com</b> and install it<br>'
                        '2. Run: <code>ollama pull moondream:latest</code><br>'
                        '3. Come back and try again.</div>',
                        unsafe_allow_html=True)
                else:
                    with st.spinner("AI is reading your screenshot…"):
                        result = ai_confirm_screenshot(img_bytes, confirm_pair,
                                                       action, entry, tp, sl)
                    confirmed = (
                        "✅" in result or
                        ("confirmed" in result.lower() and "not confirmed" not in result.lower()) or
                        ("correct" in result.lower() and "not correct" not in result.lower() and "incorrect" not in result.lower())
                    )
                    if confirmed:
                        st.markdown(
                            f'<div class="confirm-ok">✅ <b style="color:#30d158">CONFIRMED — looks correct</b>'
                            f'<br><br>{result}</div>', unsafe_allow_html=True)
                        st.balloons()
                    else:
                        st.markdown(
                            f'<div class="confirm-fail">❌ <b style="color:#ff453a">NEEDS ADJUSTMENT</b>'
                            f'<br><br>{result}</div>', unsafe_allow_html=True)
    else:
        # how-to panel
        st.markdown("""
<div style="background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);
     border-radius:20px;padding:32px 36px;margin-top:8px;">
  <div style="font-size:1.1rem;font-weight:700;color:#fff;margin-bottom:20px;">How this works</div>
  <div style="display:flex;flex-direction:column;gap:16px;">
    <div style="display:flex;gap:16px;align-items:flex-start;">
      <div style="min-width:32px;height:32px;background:rgba(10,132,255,.2);border-radius:50%;display:flex;align-items:center;justify-content:center;color:#0a84ff;font-weight:700;font-size:.85rem;">1</div>
      <div style="font-size:.88rem;color:rgba(255,255,255,.65);line-height:1.6;">Go to <b style="color:#fff;">Platform Guide</b> tab and note the exact TP and SL values for your chosen pair.</div>
    </div>
    <div style="display:flex;gap:16px;align-items:flex-start;">
      <div style="min-width:32px;height:32px;background:rgba(10,132,255,.2);border-radius:50%;display:flex;align-items:center;justify-content:center;color:#0a84ff;font-weight:700;font-size:.85rem;">2</div>
      <div style="font-size:.88rem;color:rgba(255,255,255,.65);line-height:1.6;">Open your trading platform and set up the trade — entry, TP, and SL exactly as shown.</div>
    </div>
    <div style="display:flex;gap:16px;align-items:flex-start;">
      <div style="min-width:32px;height:32px;background:rgba(10,132,255,.2);border-radius:50%;display:flex;align-items:center;justify-content:center;color:#0a84ff;font-weight:700;font-size:.85rem;">3</div>
      <div style="font-size:.88rem;color:rgba(255,255,255,.65);line-height:1.6;">Take a screenshot: <b style="color:#fff">Mac</b> → Cmd+Shift+4 · <b style="color:#fff">Windows</b> → Win+Shift+S</div>
    </div>
    <div style="display:flex;gap:16px;align-items:flex-start;">
      <div style="min-width:32px;height:32px;background:rgba(10,132,255,.2);border-radius:50%;display:flex;align-items:center;justify-content:center;color:#0a84ff;font-weight:700;font-size:.85rem;">4</div>
      <div style="font-size:.88rem;color:rgba(255,255,255,.65);line-height:1.6;">Upload it above and click <b style="color:#fff">Check with AI Vision</b>. The AI reads your screen and confirms ✅ or tells you exactly what to fix ❌.</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    # ── manual checklist ──────────────────────────────────────────────────────
    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-eyebrow' style='margin-bottom:12px;'>QUICK MANUAL CHECKLIST</div>",
                unsafe_allow_html=True)
    sig_m = st.session_state.get("signals",{}).get(confirm_pair)
    if sig_m:
        ps_m  = pip_size(confirm_pair)
        tp_pm = TP_PIPS.get(st.session_state.get("tp_label","35 pips  Standard"), 35)
        sl_pm = SL_PIPS.get(st.session_state.get("sl_label","25 pips  Standard"), 25)
        tp_m  = sig_m["entry"] + tp_pm*ps_m if sig_m["action"] != "SELL" else sig_m["entry"] - tp_pm*ps_m
        sl_m  = sig_m["entry"] - sl_pm*ps_m if sig_m["action"] != "SELL" else sig_m["entry"] + sl_pm*ps_m
        for j, lbl in enumerate([
            f"Correct pair selected: **{confirm_pair}**",
            f"Direction is **{sig_m['action']}**",
            f"Entry price near `{sig_m['entry']:.5f}`",
            f"Take Profit set to `{tp_m:.5f}` (+{tp_pm} pips)",
            f"Stop Loss set to `{sl_m:.5f}` (-{sl_pm} pips)",
            f"Timeframe set to **{tf_interval.upper()}**",
        ]):
            st.checkbox(lbl, key=f"chk_{j}")
    else:
        st.markdown('<div style="color:rgba(255,255,255,.3);font-size:.85rem;">Run the scanner to populate expected values.</div>',
                    unsafe_allow_html=True)

# ── FOOTER ────────────────────────────────────────────────────────────────────
st.markdown("<div style='height:40px'></div>", unsafe_allow_html=True)
st.markdown("""
<div style="text-align:center;padding:20px 0;border-top:1px solid rgba(255,255,255,.05);">
  <div style="font-size:.78rem;color:rgba(255,255,255,.2);letter-spacing:.04em;">
    FX PRO TRADER &nbsp;·&nbsp; Live data via yfinance &nbsp;·&nbsp;
    News via RSS &nbsp;·&nbsp; AI via Ollama (local, free) &nbsp;·&nbsp;
    Not financial advice — always manage your risk
  </div>
</div>
""", unsafe_allow_html=True)
