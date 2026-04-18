# 💰 FX Trading Assistant

**A plain-English trading signal app for beginners. No trading knowledge needed.**

It watches the market for you and tells you exactly **when to BUY**, **when to SELL**, and **how much profit to expect** — all in simple everyday language.

## 🚀 Live App

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app-url.streamlit.app)

## What it does

- ✅ Watches any FX currency pair automatically (every 1 min → 1 hour)
- 🟢 Shows a giant **BUY NOW** or 🔴 **SELL NOW** when the time is right
- 💰 Gives you the exact entry price, take-profit price, and stop-loss price
- 🗣️ Speaks the alert out loud (Mac)
- 📋 Logs every trading call so you can track its performance
- 🤖 Optional local AI explanation using Ollama (free, no API key)
- 🖥️ Optional live screen capture of your trading platform

## How to use it

1. Pick a currency pair (e.g. EUR/USD)
2. Pick how often to check (e.g. Every 5 minutes)
3. Press **▶ Start Watching for Me**
4. Wait — the app alerts you when to trade

That's it. No charts to read. No numbers to understand.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Cloud (free)

1. Fork this repo
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click **New app** → select this repo → set main file to `app.py`
4. Deploy — your app is live in 2 minutes

## Supported currency pairs

EUR/USD · GBP/USD · USD/JPY · AUD/USD · USD/CAD · USD/CHF · EUR/GBP · EUR/JPY · GBP/JPY · NZD/USD

## Signals used (hidden from main view)

- RSI (momentum)
- MACD (trend flip)
- Bollinger Bands (price zone)
- EMA 20/50 (trend direction)
- Stochastic (overbought/oversold)
- ATR (stop-loss / take-profit sizing)

---

> ⚠️ **Disclaimer:** This app is for educational purposes only. All trading carries risk. Never trade money you cannot afford to lose.
