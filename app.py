
import streamlit as st
import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

st.set_page_config(
    page_title="XIGA Trading",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed"
)

def init_state():
    defaults = {
        "history": [],
        "signals": 0,
        "wins": 0,
        "losses": 0,
        "result": {
            "signal": "READY",
            "strength": 0,
            "description": "Select an asset and start analysis.",
            "success": False,
        },
        "page": "Trade",
        "analysis_pending": None,
        "trade_pending": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_state()

ASSETS_FALLBACK = {
    "Forex": {"EUR/USD":"EURUSD","GBP/USD":"GBPUSD","USD/JPY":"USDJPY","AUD/USD":"AUDUSD","USD/CAD":"USDCAD","USD/CHF":"USDCHF","NZD/USD":"NZDUSD","EUR/JPY":"EURJPY","EUR/GBP":"EURGBP","GBP/JPY":"GBPJPY"},
    "Stocks": {"Apple (AAPL)":"AAPL","Microsoft (MSFT)":"MSFT","Tesla (TSLA)":"TSLA","Amazon (AMZN)":"AMZN","NVIDIA (NVDA)":"NVDA","Netflix (NFLX)":"NFLX","Meta (META)":"META","Visa (V)":"V","Boeing (BA)":"BA","Palantir (PLTR)":"PLTR","AMD":"AMD","Coinbase (COIN)":"COIN"},
    "Crypto": {"Bitcoin (BTCUSD)":"BTCUSD","Ethereum (ETHUSD)":"ETHUSD","Solana (SOLUSD)":"SOLUSD","Dogecoin (DOGEUSD)":"DOGEUSD","Cardano (ADAUSD)":"ADAUSD","BNB (BNBUSD)":"BNBUSD","Chainlink (LINKUSD)":"LINKUSD","Litecoin (LTCUSD)":"LTCUSD","XRP (XRPUSD)":"XRPUSD"},
    "Commodities": {"Gold (XAUUSD)":"XAUUSD","Silver (XAGUSD)":"XAGUSD","WTI Oil (USOIL)":"USOIL","Brent Oil (UKOIL)":"UKOIL","Natural Gas (NATGAS)":"NATGAS"},
    "Indices": {"S&P 500 (US500)":"US500","NASDAQ 100 (USTEC)":"USTEC","Dow Jones (US30)":"US30","DAX (DE40)":"DE40","FTSE 100 (UK100)":"UK100","Nikkei 225 (JP225)":"JP225"},
}
TIMEFRAMES = {"1 MIN": "1", "5 MIN": "5"}

def get_secret(name):
    try:
        return str(st.secrets[name]).strip()
    except Exception:
        return ""

# Market data is supplied by BiQuote. Its public read API requires no API key.
BIQUOTE_BASE = "https://biquote.io/api"

# Multi-user cache settings: identical market requests are shared across sessions.
# These short TTLs reduce duplicate API calls without making the UI feel stale.
CANDLE_CACHE_SECONDS = 10
TICK_CACHE_SECONDS = 2
NEWS_CACHE_SECONDS = 600

@st.cache_data(ttl=900, show_spinner=False)
def get_symbol_catalog():
    try:
        r = requests.get(f"{BIQUOTE_BASE}/symbols", params={"quotedWithinDays": 7}, timeout=20)
        if r.status_code != 200:
            return ASSETS_FALLBACK, f"CATALOG ERROR {r.status_code} • USING FALLBACK"
        payload = r.json()
        items = payload if isinstance(payload, list) else (payload.get("symbols") or payload.get("items") or payload.get("data") or [])
        if not isinstance(items, list):
            return ASSETS_FALLBACK, "CATALOG FORMAT ERROR • USING FALLBACK"
        grouped = {"Forex":{},"Stocks":{},"Crypto":{},"Commodities":{},"Indices":{},"Other":{}}
        for item in items:
            if not isinstance(item, dict): continue
            name = str(item.get("name") or item.get("symbol") or "").strip()
            if not name: continue
            desc = str(item.get("description") or "").strip()
            kind = str(item.get("type") or "Other").lower()
            category = {"forex":"Forex","stock":"Stocks","crypto":"Crypto","commodity":"Commodities","index":"Indices"}.get(kind,"Other")
            label = f"{desc} ({name})" if desc and desc.upper()!=name.upper() else name
            grouped[category][label] = name
        grouped = {k:v for k,v in grouped.items() if v}
        return grouped or ASSETS_FALLBACK, f"CATALOG OK • {len(items)} INSTRUMENTS"
    except requests.exceptions.Timeout:
        return ASSETS_FALLBACK, "CATALOG TIMEOUT • USING FALLBACK"
    except requests.exceptions.RequestException:
        return ASSETS_FALLBACK, "CATALOG NETWORK ERROR • USING FALLBACK"
    except Exception as exc:
        return ASSETS_FALLBACK, f"CATALOG ERROR • USING FALLBACK: {exc}"

@st.cache_data(ttl=CANDLE_CACHE_SECONDS, show_spinner=False)
def get_candles_cached(provider_symbol, resolution):
    interval = "1m" if resolution == "1" else "5m"
    try:
        response = requests.get(f"{BIQUOTE_BASE}/{provider_symbol}/ohlc", params={"interval": interval, "limit": 150}, timeout=15)
        if response.status_code != 200:
            try: message = response.json().get("message") or response.json().get("error")
            except Exception: message = None
            if response.status_code == 404: return [], f"BIQUOTE SYMBOL NOT FOUND: {provider_symbol}"
            if response.status_code == 429: return [], "BIQUOTE RATE LIMIT — PLEASE RETRY"
            return [], f"BIQUOTE ERROR {response.status_code}" + (f": {message}" if message else "")
        bars = response.json().get("bars", [])
        candles=[]
        for bar in reversed(bars):
            try:
                candles.append({"open":float(bar["open"]),"high":float(bar["high"]),"low":float(bar["low"]),"close":float(bar["close"]),"datetime":str(bar["openTime"]),"is_open":bool(bar.get("isOpen",False))})
            except (KeyError,TypeError,ValueError): pass
        if len(candles)<60: return [], f"NOT ENOUGH DATA ({len(candles)} CANDLES)"
        return candles, "BIQUOTE MARKET DATA CONNECTED"
    except requests.exceptions.Timeout: return [], "BIQUOTE MARKET DATA TIMEOUT"
    except requests.exceptions.RequestException: return [], "BIQUOTE NETWORK ERROR"
    except Exception as exc: return [], f"BIQUOTE DATA ERROR: {exc}"

def get_candles(symbol, resolution, fresh=False):
    # Keep the shared cache intact. Clearing a global Streamlit cache here would
    # invalidate data for every connected user at once. A short TTL provides
    # fresh market data while allowing identical requests from many users to
    # reuse the same BiQuote response.
    return get_candles_cached(symbol, resolution)

@st.cache_data(ttl=TICK_CACHE_SECONDS, show_spinner=False)
def get_latest_tick(provider_symbol):
    try:
        r=requests.get(f"{BIQUOTE_BASE}/{provider_symbol}",timeout=10)
        if r.status_code!=200: return None, f"BIQUOTE TICK ERROR {r.status_code}"
        data=r.json(); price=data.get("mid")
        if price is None: price=data.get("last") or data.get("bid") or data.get("ask")
        if price is None: return None,"NO LIVE PRICE"
        return {"price":float(price),"timestamp":data.get("timestamp"),"market_state":data.get("marketState"),"stale":bool(data.get("stale",False))},"BIQUOTE LIVE PRICE CONNECTED"
    except requests.exceptions.RequestException: return None,"BIQUOTE TICK NETWORK ERROR"
    except Exception as exc: return None,f"BIQUOTE TICK ERROR: {exc}"

def get_marketaux_key():
    try:
        return st.secrets.get("MARKETAUX_API_KEY", "")
    except Exception:
        return ""

NEWS_SYMBOLS = {
    "EUR/USD": "EUR", "GBP/USD": "GBP", "USD/JPY": "JPY",
    "AUD/USD": "AUD", "USD/CAD": "CAD", "USD/CHF": "CHF",
    "NZD/USD": "NZD", "EUR/JPY": "EUR", "EUR/GBP": "EUR",
    "GBP/JPY": "GBP", "XAU/USD": "XAU", "XAG/USD": "XAG",
    "WTI/USD": "WTI", "BRENT/USD": "BRENT", "NATGAS/USD": "NATGAS",
}

@st.cache_data(ttl=NEWS_CACHE_SECONDS, show_spinner=False)
def get_market_news(symbol):
    key = get_marketaux_key()
    if not key:
        return {
            "sentiment": 0.0,
            "articles": 0,
            "status": "MARKETAUX KEY NOT FOUND",
        }

    params = (
        {"symbols": symbol}
        if "/" not in symbol
        else {"search": NEWS_SYMBOLS.get(symbol, symbol.replace("/", " "))}
    )
    params.update({
        "api_token": key,
        "language": "en",
        "limit": 3,
        "filter_entities": "true",
        "published_after": (
            datetime.now(timezone.utc) - timedelta(hours=12)
        ).strftime("%Y-%m-%dT%H:%M"),
    })

    try:
        response = requests.get(
            "https://api.marketaux.com/v1/news/all",
            params=params,
            timeout=15,
        )
        if response.status_code != 200:
            return {
                "sentiment": 0.0,
                "articles": 0,
                "status": f"MARKETAUX ERROR {response.status_code}",
            }

        data = response.json()
        articles = data.get("data", [])
        if not articles:
            return {
                "sentiment": 0.0,
                "articles": 0,
                "status": "NO RECENT NEWS",
            }

        sentiments = []
        for article in articles:
            for entity in article.get("entities", []):
                value = entity.get("sentiment_score")
                if value is not None:
                    try:
                        sentiments.append(float(value))
                    except (TypeError, ValueError):
                        pass

        average = sum(sentiments) / len(sentiments) if sentiments else 0.0
        return {
            "sentiment": average,
            "articles": len(articles),
            "status": "NEWS ANALYSIS CONNECTED",
        }

    except requests.exceptions.Timeout:
        return {"sentiment": 0.0, "articles": 0, "status": "NEWS TIMEOUT"}
    except requests.exceptions.RequestException:
        return {"sentiment": 0.0, "articles": 0, "status": "NEWS NETWORK ERROR"}
    except Exception:
        return {"sentiment": 0.0, "articles": 0, "status": "NEWS ANALYSIS ERROR"}

def ema(values, period):
    if len(values) < period:
        return None
    multiplier = 2 / (period + 1)
    current = sum(values[:period]) / period
    for value in values[period:]:
        current = ((value - current) * multiplier) + current
    return current

def rsi(values, period=14):
    if len(values) < period + 1:
        return None

    gains, losses = [], []
    for i in range(1, len(values)):
        diff = values[i] - values[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def macd(values):
    if len(values) < 35:
        return None, None

    fast = ema(values, 12)
    slow = ema(values, 26)
    previous_fast = ema(values[:-1], 12)
    previous_slow = ema(values[:-1], 26)

    if fast is None or slow is None:
        return None, None

    current = fast - slow
    previous = None
    if previous_fast is not None and previous_slow is not None:
        previous = previous_fast - previous_slow
    return current, previous

def parse_candle_time(value):
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                pass
    return None

def candle_is_completed(candle, interval):
    # Use the candle's timestamp as the authoritative close test.
    # BiQuote exposes isOpen, but a cached/open flag can briefly lag the clock.
    dt = parse_candle_time(candle.get("datetime"))
    if dt is not None:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        duration = timedelta(minutes=1 if interval == "1" else 5)
        if datetime.now(dt.tzinfo) >= dt + duration:
            return True
        return False
    if "is_open" in candle:
        return not bool(candle.get("is_open"))
    return False

def completed_candles(candles, interval):
    return [c for c in candles if candle_is_completed(c, interval)]

def analyze_market(symbol, timeframe):
    resolution = TIMEFRAMES.get(timeframe)
    if resolution is None:
        return {
            "success": False,
            "signal": "NO TRADE",
            "strength": 0,
            "description": "Use 1 MIN or 5 MIN.",
            "status": "TIMEFRAME UNAVAILABLE",
        }

    candles, market_status = get_candles(symbol, resolution)
    if len(candles) < 61:
        return {
            "success": False,
            "signal": "NO TRADE",
            "strength": 0,
            "description": market_status,
            "status": market_status,
        }

    closed = completed_candles(candles, resolution)
    if len(closed) < 60:
        return {
            "success": False,
            "signal": "NO TRADE",
            "strength": 0,
            "description": "WAITING FOR ENOUGH COMPLETED CANDLES",
            "status": market_status,
        }

    closes = [c["close"] for c in closed]
    current = closes[-1]
    ema9 = ema(closes, 9)
    ema21 = ema(closes, 21)
    ema50 = ema(closes, 50)
    rsi_value = rsi(closes, 14)
    macd_value, previous_macd = macd(closes)

    score = 0
    reasons = []

    if ema9 is not None and ema21 is not None:
        if ema9 > ema21:
            score += 1
            reasons.append("EMA 9 is above EMA 21")
        elif ema9 < ema21:
            score -= 1
            reasons.append("EMA 9 is below EMA 21")

    if ema21 is not None and ema50 is not None:
        if ema21 > ema50:
            score += 1
            reasons.append("Medium-term trend is bullish")
        elif ema21 < ema50:
            score -= 1
            reasons.append("Medium-term trend is bearish")

    if ema21 is not None:
        if current > ema21:
            score += 1
            reasons.append("Price is above EMA 21")
        elif current < ema21:
            score -= 1
            reasons.append("Price is below EMA 21")

    if rsi_value is not None:
        if rsi_value >= 55:
            score += 1
            reasons.append(f"RSI bullish ({rsi_value:.1f})")
        elif rsi_value <= 45:
            score -= 1
            reasons.append(f"RSI bearish ({rsi_value:.1f})")
        else:
            reasons.append(f"RSI neutral ({rsi_value:.1f})")

    if macd_value is not None:
        if macd_value > 0:
            score += 1
            reasons.append("MACD is positive")
        elif macd_value < 0:
            score -= 1
            reasons.append("MACD is negative")

        if previous_macd is not None:
            if macd_value > previous_macd:
                reasons.append("MACD momentum is rising")
            elif macd_value < previous_macd:
                reasons.append("MACD momentum is falling")

    if len(closes) >= 6:
        momentum = closes[-1] - closes[-6]
        if momentum > 0:
            score += 1
            reasons.append("Recent momentum is bullish")
        elif momentum < 0:
            score -= 1
            reasons.append("Recent momentum is bearish")

    news = get_market_news(symbol)
    sentiment = float(news.get("sentiment", 0.0))
    news_count = int(news.get("articles", 0))

    if news_count:
        if sentiment >= 0.15:
            score += 1
            reasons.append("Financial news sentiment is bullish")
        elif sentiment <= -0.15:
            score -= 1
            reasons.append("Financial news sentiment is bearish")
        else:
            reasons.append("Financial news sentiment is neutral")

    if score >= 3:
        signal = "CALL"
        description = (
            f"Bullish confirmation. Score {score:+d}. "
            f"News sentiment {sentiment:+.2f}. Analysis only."
        )
    elif score <= -3:
        signal = "PUT"
        description = (
            f"Bearish confirmation. Score {score:+d}. "
            f"News sentiment {sentiment:+.2f}. Analysis only."
        )
    else:
        signal = "NO TRADE"
        description = (
            f"Mixed conditions. Score {score:+d}. "
            f"News sentiment {sentiment:+.2f}. "
            "Waiting for stronger confirmation."
        )

    # Current-trade probability estimate. This is a model estimate derived
    # from the strength and agreement of the indicators above; it is NOT a
    # guaranteed probability and is never taken from previous trade results.
    # Map the composite score to a bounded estimate for display.
    probability = min(95, max(50, int(50 + abs(score) * 6)))
    if signal == "NO TRADE":
        probability = max(50, min(60, int(50 + abs(score) * 2)))

    return {
        "success": True,
        "signal": signal,
        "strength": min(5, max(1, abs(score))),
        "probability": probability,
        "score": score,
        "price": current,
        "entry_candle_time": closed[-1]["datetime"],
        "rsi": rsi_value,
        "macd": macd_value,
        "news_sentiment": sentiment,
        "news_count": news_count,
        "description": description,
        "status": market_status,
        "news_status": news.get("status", "NO NEWS"),
        "reasons": reasons,
    }

def calculate_outcome(signal, entry_price, result_price):
    entry_price = float(entry_price)
    result_price = float(result_price)

    if signal == "CALL":
        if result_price > entry_price:
            return "WIN"
        if result_price < entry_price:
            return "LOSS"
        return "DRAW"

    if signal == "PUT":
        if result_price < entry_price:
            return "WIN"
        if result_price > entry_price:
            return "LOSS"
        return "DRAW"

    return None

def update_win_loss_totals():
    st.session_state.wins = sum(1 for item in st.session_state.history if item.get("status") == "WIN")
    st.session_state.losses = sum(1 for item in st.session_state.history if item.get("status") == "LOSS")

def format_countdown(seconds):
    if seconds is None: return "—"
    minutes, secs = divmod(max(0, int(seconds)), 60)
    return f"{minutes:02d}:{secs:02d}"

def seconds_until(iso_value):
    target = parse_candle_time(iso_value) if iso_value else None
    if target is None: return 0
    if target.tzinfo is None: target = target.replace(tzinfo=timezone.utc)
    return max(0, int((target - datetime.now(timezone.utc)).total_seconds()))

def resolve_trade_if_ready():
    pending = st.session_state.get("trade_pending")
    if not pending or seconds_until(pending.get("complete_at")) > 0: return
    tick, status = get_latest_tick(pending["symbol"])
    if tick:
        result_price = float(tick["price"])
    else:
        candles, candle_status = get_candles(pending["symbol"], TIMEFRAMES[pending["timeframe"]])
        if not candles:
            pending["state"] = "RESULT ERROR"; pending["error"] = f"{status}; {candle_status}"; return
        closed = completed_candles(candles, TIMEFRAMES[pending["timeframe"]])
        if not closed:
            pending["state"] = "RESULT ERROR"; pending["error"] = f"{status}; NO CLOSED RESULT CANDLE"; return
        result_price = float(closed[-1]["close"])
    outcome = calculate_outcome(pending["signal"], pending["entry_price"], result_price)
    checked = datetime.now(ZoneInfo("Asia/Karachi")).strftime("%Y-%m-%d %H:%M:%S PKT")
    for item in st.session_state.history:
        if item.get("id") == pending.get("id"):
            item["status"] = outcome; item["result_price"] = result_price; item["checked_at"] = checked; break
    st.session_state.result["status"] = outcome
    st.session_state.result["result_price"] = result_price
    st.session_state.result["checked_at"] = checked
    st.session_state.result["description"] = f"Individual signal result: {outcome}. Entry {pending['entry_price']:.6g} → result {result_price:.6g}."
    st.session_state.trade_pending = None
    update_win_loss_totals()

ASSETS, catalog_status = get_symbol_catalog()

st.markdown("""
<style>
html,body,[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 50% -10%,#173957 0%,#0a1c30 25%,#030914 62%,#020711 100%) !important}
[data-testid="stHeader"]{background:transparent !important}
[data-testid="stMainBlockContainer"]{max-width:500px !important;padding-top:12px !important;padding-left:12px !important;padding-right:12px !important}
.block-container{padding-bottom:25px !important}
.xiga-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}.xiga-menu{width:42px;height:42px;border-radius:13px;display:flex;align-items:center;justify-content:center;background:rgba(11,30,49,.88);border:1px solid #214967;color:#dceeff;font-size:21px}.xiga-brand{text-align:center;flex:1}.xiga-title{color:#fff;font-size:25px;font-weight:900;letter-spacing:1px}.xiga-title span{color:#28f3a5}.xiga-subtitle{margin-top:4px;color:#71859d;font-size:8px;letter-spacing:2px}.xiga-pro{min-width:66px;padding:9px 8px;text-align:center;border-radius:12px;background:linear-gradient(135deg,#3d2d0d,#1f1809);border:1px solid #9b741d;color:#ffd76a;font-size:10px;font-weight:800}
.xiga-card{background:linear-gradient(145deg,rgba(13,34,57,.96),rgba(5,16,29,.97));border:1px solid rgba(32,91,132,.72);border-radius:20px;box-shadow:0 18px 45px rgba(0,0,0,.32),inset 0 1px rgba(255,255,255,.035);padding:12px;margin-bottom:12px}
div[data-testid="stSelectbox"] label{color:#7d93aa !important;font-size:8px !important;letter-spacing:1.4px !important;text-transform:uppercase !important}div[data-baseweb="select"]>div{background:linear-gradient(145deg,rgba(9,39,64,.98),rgba(7,25,43,.98)) !important;border:1px solid #185276 !important;color:white !important;border-radius:12px !important}div[data-baseweb="select"] span{color:white !important}.xiga-market-status{color:#29f4a5;font-size:7px;margin-top:3px}
.xiga-signal{text-align:center;position:relative;overflow:hidden;min-height:560px}.xiga-signal:before{content:"";position:absolute;left:-10%;right:-10%;top:105px;height:190px;opacity:.22;background:repeating-linear-gradient(0deg,transparent 0px,transparent 45px,#226082 46px)}.xiga-signal-label{color:#8ca1b7;font-size:9px;letter-spacing:1.5px;text-transform:uppercase;position:relative}.xiga-asset{color:white;font-size:22px;font-weight:900;position:relative;margin-top:4px}.xiga-time{color:#28f3a5;font-size:9px;letter-spacing:1px;margin-top:4px;position:relative}
.xiga-circle{width:205px;height:205px;border-radius:50%;margin:25px auto 18px;display:flex;align-items:center;justify-content:center;position:relative}.xiga-circle.call{background:radial-gradient(circle,rgba(38,246,165,.43) 0%,rgba(14,74,61,.70) 35%,rgba(3,15,27,.98) 72%);border:3px solid #29f5a6;box-shadow:0 0 11px #29f5a6,0 0 35px rgba(41,245,166,.65),0 0 80px rgba(41,245,166,.22),inset 0 0 32px rgba(41,245,166,.27)}.xiga-circle.put{background:radial-gradient(circle,rgba(255,53,103,.42) 0%,rgba(82,17,41,.72) 35%,rgba(3,15,27,.98) 72%);border:3px solid #ff3d70;box-shadow:0 0 11px #ff3d70,0 0 35px rgba(255,61,112,.65),0 0 80px rgba(255,61,112,.22)}.xiga-circle.neutral{background:radial-gradient(circle,rgba(80,140,180,.28) 0%,rgba(17,46,68,.72) 35%,rgba(3,15,27,.98) 72%);border:3px solid #5e91b5;box-shadow:0 0 11px #5e91b5,0 0 35px rgba(94,145,181,.35)}.xiga-arrow{font-size:76px;font-weight:900;line-height:1}.call-text{color:#35f4a9;text-shadow:0 0 20px rgba(53,244,169,.3)}.put-text{color:#ff416f;text-shadow:0 0 20px rgba(255,65,111,.3)}.neutral-text{color:#8fb4cf}.xiga-signal-title{font-size:29px;font-weight:950;position:relative}.xiga-direction{color:#8597ac;font-size:9px;letter-spacing:2px;margin-top:4px}.xiga-stat{background:linear-gradient(145deg,rgba(7,29,49,.98),rgba(5,17,30,.98));border:1px solid #17557d;border-radius:15px;padding:13px 8px;text-align:center;min-height:100px}.xiga-stat-label{color:#8296ad;font-size:9px;text-transform:uppercase}.xiga-strength{color:#29f5a6;font-size:18px;margin-top:8px;letter-spacing:2px}.xiga-number{color:white;font-size:12px;font-weight:800;margin-top:3px}.xiga-win{color:#29f5a6;font-size:24px;font-weight:900;margin-top:6px;letter-spacing:1px}.xiga-ai{display:flex;gap:11px;align-items:center;margin-top:11px;padding:12px;text-align:left;border-radius:15px;background:linear-gradient(145deg,rgba(7,37,47,.97),rgba(5,19,31,.97));border:1px solid rgba(31,181,150,.55)}.xiga-ai-icon{width:35px;height:35px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#2af5a5;border:1px solid rgba(42,245,165,.48);flex-shrink:0}.xiga-ai-title{color:#2af5a5;font-size:11px;font-weight:900}.xiga-ai-desc{color:#7f92a7;font-size:8px;margin-top:3px}
.stButton>button{width:100%;height:55px;border-radius:16px;border:1px solid #5affaf;background:linear-gradient(100deg,#13ca87,#38f5ad);color:#03130d;font-size:14px;font-weight:900;box-shadow:0 8px 28px rgba(37,245,166,.20)}.stButton>button:hover{border-color:#5affaf;color:#03130d}.xiga-footer{text-align:center;margin-top:9px;color:#4f647a;font-size:7px;letter-spacing:.5px}
div[role="radiogroup"]{display:flex !important;justify-content:center !important;gap:4px !important;flex-wrap:nowrap !important;margin:0 0 12px !important}div[role="radiogroup"] label{color:#8ca1b7 !important;font-size:10px !important;padding:5px 7px !important;white-space:nowrap !important}div[role="radiogroup"] label:has(input:checked){color:#29f5a6 !important}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="xiga-top">
<div class="xiga-menu">☰</div>
<div class="xiga-brand">
<div class="xiga-title"><span>▰</span> XIGA</div>
<div class="xiga-subtitle">TRADING SIGNAL BOT</div>
</div>
<div class="xiga-pro">👑 PRO</div>
</div>
""", unsafe_allow_html=True)

nav_options = ["Trade", "History", "Learn", "Profile"]
selected_page = st.radio(
    "Navigation",
    nav_options,
    index=nav_options.index(st.session_state.page),
    horizontal=True,
    label_visibility="collapsed",
    key="navigation",
)
st.session_state.page = selected_page

if selected_page == "Trade":

    @st.fragment(run_every="1s")
    def trade_page():
        resolve_trade_if_ready()
        category_options = list(ASSETS.keys())
        default_category = st.session_state.get("category", category_options[0])
        if default_category not in category_options:
            default_category = category_options[0]

        st.markdown('<div class="xiga-card">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            category = st.selectbox("Asset", category_options, index=category_options.index(default_category), key="category")
        asset_map = ASSETS.get(category) or {}
        asset_names = list(asset_map.keys())
        if not asset_names:
            st.error("No instruments are currently available in this category.")
            st.markdown("</div>", unsafe_allow_html=True)
            return
        current_asset = st.session_state.get("asset")
        if current_asset not in asset_names:
            current_asset = asset_names[0]
        with col2:
            display_asset = st.selectbox("Market", asset_names, index=asset_names.index(current_asset), key="asset")
        timeframe = st.selectbox("Timeframe", list(TIMEFRAMES.keys()), index=0, key="timeframe")
        st.markdown(f'<div class="xiga-market-status">● LIVE MARKET READY • {catalog_status}</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        result = st.session_state.result
        signal = result.get("signal", "READY")
        if signal == "CALL":
            circle_class, arrow, title = "call", "↗", "BUY (CALL)"
            direction, title_class = "UPWARD SIGNAL", "call-text"
        elif signal == "PUT":
            circle_class, arrow, title = "put", "↘", "SELL (PUT)"
            direction, title_class = "DOWNWARD SIGNAL", "put-text"
        elif signal == "NO TRADE":
            circle_class, arrow, title = "neutral", "—", "NO TRADE"
            direction, title_class = "WAIT FOR STRONGER CONFIRMATION", "neutral-text"
        else:
            circle_class, arrow, title = "neutral", "◇", "AI READY"
            direction, title_class = "WAITING FOR ANALYSIS", "neutral-text"

        clean_asset = display_asset
        strength = int(result.get("strength", 0))
        filled, empty = "● " * strength, "● " * max(0, 5 - strength)
        strength_html = ('<span style="color:#29f5a6">' + filled + '</span><span style="color:#26394c">' + empty + '</span>') if strength else '<span style="color:#26394c">● ● ● ● ●</span>'

        analysis_pending = st.session_state.get("analysis_pending")
        trade_pending = st.session_state.get("trade_pending")
        if analysis_pending:
            remaining = seconds_until(analysis_pending.get("complete_at"))
            win_display = format_countdown(remaining)
            win_status = f'● {analysis_pending.get("timeframe", "1 MIN")} ANALYZING'
            ai_title = "ANALYZING MARKET"
        elif trade_pending:
            remaining = seconds_until(trade_pending.get("complete_at"))
            win_display = f'{int(result.get("probability", 50))}%'
            win_status = f'● TRADE TIME {format_countdown(remaining)}'
            ai_title = "SIGNAL READY • TRADE WINDOW"
        elif result.get("status") in ("WIN", "LOSS", "DRAW"):
            win_display = result.get("status")
            win_status = "● INDIVIDUAL SIGNAL RESULT"
            ai_title = "TRADE WINDOW COMPLETE"
        elif result.get("success") and result.get("signal") in ("CALL", "PUT"):
            win_display = f'{int(result.get("probability", 50))}%'
            win_status = "● CURRENT TRADE PROBABILITY"
            ai_title = "AI ANALYSIS COMPLETE"
        elif result.get("success") and result.get("signal") == "NO TRADE":
            win_display, win_status, ai_title = "—", "● NO STRONG SIGNAL", "ANALYSIS COMPLETE"
        else:
            win_display, win_status, ai_title = "—", "● START ANALYSIS", "AI ENGINE READY"

        if trade_pending:
            tracker_line = f'<div style="color:#6f8499;font-size:7px;margin-top:6px;">TRADE TIMER: {format_countdown(seconds_until(trade_pending.get("complete_at")))} • ENTRY {trade_pending.get("entry_price", "—")} • RESULT AT 00:00</div>'
        elif analysis_pending:
            tracker_line = f'<div style="color:#6f8499;font-size:7px;margin-top:6px;">ANALYSIS TIMER: {format_countdown(seconds_until(analysis_pending.get("complete_at")))}</div>'
        elif result.get("status") in ("WIN", "LOSS", "DRAW"):
            tracker_line = f'<div style="color:#6f8499;font-size:7px;margin-top:6px;">INDIVIDUAL RESULT: {result.get("status")}</div>'
        else:
            tracker_line = ""

        description = result.get("description", "Select an asset and start analysis.")
        st.markdown(f'''
<div class="xiga-card xiga-signal">
<div class="xiga-signal-label">SIGNAL FOR</div>
<div class="xiga-asset">{clean_asset}</div>
<div class="xiga-time">● TIMEFRAME: {timeframe}</div>
<div class="xiga-circle {circle_class}"><div class="xiga-arrow">{arrow}</div></div>
<div class="xiga-signal-title {title_class}">{title}</div>
<div class="xiga-direction">{direction}</div>
<br>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
<div class="xiga-stat"><div class="xiga-stat-label">SIGNAL STRENGTH</div><div class="xiga-strength">{strength_html}</div><div class="xiga-number">{strength}/5</div></div>
<div class="xiga-stat"><div class="xiga-stat-label">WIN PROBABILITY</div><div class="xiga-win">{win_display}</div><div style="color:#29f5a6;font-size:8px;margin-top:3px;">{win_status}</div></div>
</div>
<div class="xiga-ai"><div class="xiga-ai-icon">✓</div><div><div class="xiga-ai-title">{ai_title}</div><div class="xiga-ai-desc">{description}</div>{tracker_line}</div></div>
</div>
''', unsafe_allow_html=True)

        busy = bool(analysis_pending or trade_pending)
        analyze_clicked = st.button("⚡ ANALYZE MARKET", key="analyze_button", use_container_width=True, disabled=busy)
        if analyze_clicked:
            symbol = asset_map[display_asset]
            duration_minutes = 1 if timeframe == "1 MIN" else 5
            now_utc = datetime.now(timezone.utc)
            st.session_state.analysis_pending = {
                "id": now_utc.isoformat(), "asset": clean_asset, "symbol": symbol,
                "timeframe": timeframe, "started_at": now_utc.isoformat(),
                "complete_at": (now_utc + timedelta(minutes=duration_minutes)).isoformat(),
            }
            st.session_state.trade_pending = None
            st.session_state.result = {
                "success": False, "signal": "READY", "strength": 0,
                "probability": None, "status": "ANALYSIS IN PROGRESS",
                "description": f"Analyzing {clean_asset} for {duration_minutes} minute{'s' if duration_minutes != 1 else ''}."
            }
            st.rerun()

        analysis_pending = st.session_state.get("analysis_pending")
        if analysis_pending and seconds_until(analysis_pending.get("complete_at")) <= 0:
            symbol = analysis_pending["symbol"]
            tf = analysis_pending["timeframe"]
            with st.spinner("Finalizing market analysis..."):
                analysis = analyze_market(symbol, tf)
            st.session_state.result = analysis
            st.session_state.analysis_pending = None
            if analysis.get("success"):
                st.session_state.signals += 1

            if analysis.get("success") and analysis.get("signal") in ("CALL", "PUT"):
                entry_tick, entry_status = get_latest_tick(symbol)
                entry_price = float(entry_tick["price"]) if entry_tick else float(analysis.get("price", 0))
                duration_minutes = 1 if tf == "1 MIN" else 5
                start = datetime.now(ZoneInfo("Asia/Karachi"))
                trade_id = analysis_pending["id"]
                st.session_state.trade_pending = {
                    "id": trade_id, "asset": analysis_pending["asset"], "symbol": symbol,
                    "timeframe": tf, "signal": analysis["signal"],
                    "probability": int(analysis.get("probability", 50)), "entry_price": entry_price,
                    "started_at": start.isoformat(), "complete_at": (start + timedelta(minutes=duration_minutes)).isoformat(),
                    "state": "TRADE COUNTDOWN", "error": "",
                }
                st.session_state.history.insert(0, {
                    "id": trade_id, "asset": analysis_pending["asset"], "symbol": symbol,
                    "signal": analysis["signal"], "strength": analysis.get("strength", 0),
                    "probability": analysis.get("probability", 50), "price": entry_price,
                    "timeframe": tf, "time": start.strftime("%Y-%m-%d %H:%M:%S PKT"),
                    "status": "PENDING", "result_price": "—",
                    "analysis_description": analysis.get("description", ""), "entry_status": entry_status,
                })
            st.rerun()

        st.markdown('<div class="xiga-footer">🔒 SECURE • XIGA AI • V5.3 • LIVE ANALYSIS</div>', unsafe_allow_html=True)

    trade_page()

elif selected_page == "History":
    st.markdown('<div class="xiga-card">', unsafe_allow_html=True)
    st.markdown("### 📊 XIGA Trade History")

    if not st.session_state.history:
        st.info("No signals have been generated yet.")
    else:
        for item in st.session_state.history[:30]:
            st.markdown(
                f"""
**{item["asset"]}**

Signal: **{item["signal"]}**

Strength: **{item["strength"]}/5**

Entry Price: `{item["price"]}`

Result Price: `{item.get("result_price", "—")}`

Timeframe: `{item["timeframe"]}`

Signal Time: `{item["time"]}`

Result Candle: `{item.get("result_candle_time", "—")}`

Probability: **{item.get("probability", "—")}%**

Status: **{item.get("status", "PENDING")}**

---
"""
            )

    st.markdown("</div>", unsafe_allow_html=True)

elif selected_page == "Learn":
    st.markdown('<div class="xiga-card">', unsafe_allow_html=True)
    st.markdown(
        """
### 📈 EMA

Moving averages help identify the direction of a market trend.

### 📊 RSI

RSI measures recent price momentum.

### 📉 MACD

MACD compares moving averages to help identify momentum.

### 🟢 CALL

A CALL means the configured indicators currently show stronger bullish conditions.

### 🔴 PUT

A PUT means the configured indicators currently show stronger bearish conditions.

### ⚪ NO TRADE

When the indicators are mixed, XIGA does not force a directional signal.

### ⚠️ Important

Signals are analysis only.
Markets can move unexpectedly and no signal guarantees a winning trade.
"""
    )
    st.markdown("</div>", unsafe_allow_html=True)

elif selected_page == "Profile":
    st.markdown('<div class="xiga-card">', unsafe_allow_html=True)
    st.markdown("### 👤 XIGA Profile")

    st.metric("Total Signals", st.session_state.signals)

    completed = st.session_state.wins + st.session_state.losses
    st.metric("Completed Results", completed)
    if completed:
        st.metric("Observed Signal Win Rate", f"{st.session_state.wins / completed * 100:.1f}%")
    st.caption("The Trade screen probability is a current model estimate for the latest analysis. It is not a guarantee and does not use previous analysis results to display the current signal.")
    st.markdown("</div>", unsafe_allow_html=True)

st.caption(
    "XIGA is a market-analysis assistant. "
    "It does not automatically place trades."
)
