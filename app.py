
import streamlit as st
import requests
import extra_streamlit_components as stx
import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

st.set_page_config(
    page_title="XIGA Trading",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Browser-persistent encrypted session cookie.
COOKIE_PASSWORD = str(st.secrets.get("COOKIES_PASSWORD", "")).strip()
if not COOKIE_PASSWORD:
    st.error("XIGA PRO is missing the COOKIES_PASSWORD secret. Please add it in Streamlit Secrets.")
    st.stop()

_COOKIE_FERNET_KEY = base64.urlsafe_b64encode(hashlib.sha256(COOKIE_PASSWORD.encode()).digest())
COOKIE_FERNET = Fernet(_COOKIE_FERNET_KEY)
COOKIE_MANAGER = stx.CookieManager(key="xiga-pro-auth")
COOKIE_NAME = "xiga_refresh"
COOKIE_DAYS = 365

def set_persistent_refresh_cookie(refresh_token):
    if not refresh_token:
        return
    encrypted = COOKIE_FERNET.encrypt(refresh_token.encode()).decode()
    COOKIE_MANAGER.set(
        COOKIE_NAME,
        encrypted,
        expires_at=datetime.now() + timedelta(days=COOKIE_DAYS),
        secure=True,
        same_site="lax",
    )

def get_persistent_refresh_cookie():
    try:
        cookies = COOKIE_MANAGER.get_all(key="xiga-refresh-cookie-read")
        value = cookies.get(COOKIE_NAME) if cookies else None
        if not value:
            return ""
        return COOKIE_FERNET.decrypt(str(value).encode()).decode()
    except (InvalidToken, ValueError, TypeError, AttributeError):
        return ""

def delete_persistent_refresh_cookie():
    try:
        COOKIE_MANAGER.delete(COOKIE_NAME)
    except Exception:
        pass

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
        "page": "Dashboard",
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

EXCHANGE_ASSETS = {
    "Binance": {
        "Bitcoin (BTC/USDT)":"BTCUSDT", "Ethereum (ETH/USDT)":"ETHUSDT", "Solana (SOL/USDT)":"SOLUSDT",
        "BNB (BNB/USDT)":"BNBUSDT", "XRP (XRP/USDT)":"XRPUSDT", "Dogecoin (DOGE/USDT)":"DOGEUSDT",
        "Cardano (ADA/USDT)":"ADAUSDT", "Chainlink (LINK/USDT)":"LINKUSDT", "Avalanche (AVAX/USDT)":"AVAXUSDT",
        "Tron (TRX/USDT)":"TRXUSDT", "Sui (SUI/USDT)":"SUIUSDT", "Polkadot (DOT/USDT)":"DOTUSDT",
    },
    "Bitget": {
        "Bitcoin (BTC/USDT)":"BTCUSDT", "Ethereum (ETH/USDT)":"ETHUSDT", "Solana (SOL/USDT)":"SOLUSDT",
        "BNB (BNB/USDT)":"BNBUSDT", "XRP (XRP/USDT)":"XRPUSDT", "Dogecoin (DOGE/USDT)":"DOGEUSDT",
        "Cardano (ADA/USDT)":"ADAUSDT", "Chainlink (LINK/USDT)":"LINKUSDT", "Avalanche (AVAX/USDT)":"AVAXUSDT",
        "Sui (SUI/USDT)":"SUIUSDT", "Polkadot (DOT/USDT)":"DOTUSDT", "Litecoin (LTC/USDT)":"LTCUSDT",
    },
    "OKX": {
        "Bitcoin (BTC/USDT)":"BTC-USDT", "Ethereum (ETH/USDT)":"ETH-USDT", "Solana (SOL/USDT)":"SOL-USDT",
        "BNB (BNB/USDT)":"BNB-USDT", "XRP (XRP/USDT)":"XRP-USDT", "Dogecoin (DOGE/USDT)":"DOGE-USDT",
        "Cardano (ADA/USDT)":"ADA-USDT", "Chainlink (LINK/USDT)":"LINK-USDT", "Avalanche (AVAX/USDT)":"AVAX-USDT",
        "Sui (SUI/USDT)":"SUI-USDT", "Polkadot (DOT/USDT)":"DOT-USDT", "Litecoin (LTC/USDT)":"LTC-USDT",
    },
}

EXCHANGE_PROVIDERS = ["BiQuote", "Binance", "Bitget", "OKX"]

TIMEFRAMES = {"1 MIN": "1", "5 MIN": "5"}

def get_secret(name):
    try:
        return str(st.secrets[name]).strip()
    except Exception:
        return ""
# ==============================
# XIGA PRO SUBSCRIPTION ACCESS
# ==============================

SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = get_secret("SUPABASE_PUBLISHABLE_KEY")
XIGA_FUNCTION_URL = f"{SUPABASE_URL}/functions/v1/xiga-request-activation-key"
XIGA_PRO_URL = "https://xiga-pro.streamlit.app"

def auth_headers(access_token=None):
    headers = {"apikey": SUPABASE_PUBLISHABLE_KEY, "Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers

def save_session(data):
    st.session_state["xiga_access_token"] = data.get("access_token", "")
    st.session_state["xiga_refresh_token"] = data.get("refresh_token", "")
    st.session_state["xiga_email"] = data.get("user", {}).get("email") or st.session_state.get("xiga_email", "")
    refresh_token = data.get("refresh_token")
    if refresh_token:
        set_persistent_refresh_cookie(refresh_token)

def clear_session():
    for key in ("xiga_access_token", "xiga_refresh_token", "xiga_email", "xiga_status", "xiga_subscription_active"):
        st.session_state.pop(key, None)
    delete_persistent_refresh_cookie()

def refresh_access_token(refresh_token):
    try:
        response = requests.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=refresh_token",
            headers=auth_headers(),
            json={"refresh_token": refresh_token},
            timeout=15,
        )
        if response.status_code == 200:
            save_session(response.json())
            return True
    except requests.RequestException:
        pass
    return False

def ensure_session_from_cookie():
    if st.session_state.get("xiga_access_token"):
        return True

    refresh_token = get_persistent_refresh_cookie()
    if refresh_token:
        return bool(refresh_access_token(refresh_token))

    # CookieManager reads asynchronously after a fresh Streamlit session.
    # Give the browser one rerun before showing the login screen.
    if not st.session_state.get("xiga_cookie_checked"):
        st.session_state["xiga_cookie_checked"] = True
        st.stop()

    return False

def get_subscription_status():
    token = st.session_state.get("xiga_access_token")
    if not token:
        return None
    try:
        response = requests.post(
            XIGA_FUNCTION_URL,
            headers=auth_headers(token),
            json={"action": "status"},
            timeout=15,
        )
        if response.status_code == 200:
            data = response.json()
            st.session_state["xiga_status"] = data
            return data
        if response.status_code in (401, 403):
            refresh_token = st.session_state.get("xiga_refresh_token") or get_persistent_refresh_cookie()
            if refresh_token and refresh_access_token(refresh_token):
                return get_subscription_status()
    except requests.RequestException:
        return None
    return None

def call_xiga_function(action, key=None):
    token = st.session_state.get("xiga_access_token")
    payload = {"action": action}
    if key is not None:
        payload["key"] = key
    try:
        response = requests.post(
            XIGA_FUNCTION_URL,
            headers=auth_headers(token),
            json=payload,
            timeout=15,
        )
        try:
            data = response.json()
        except ValueError:
            data = {}
        return response.status_code, data
    except requests.RequestException:
        return 0, {"error": "Unable to connect to XIGA subscription service."}

def render_auth_styles():
    st.markdown("""
<style>
html,body,[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 50% -15%,#173957 0%,#0a1c30 28%,#030914 65%,#020711 100%) !important}
[data-testid="stHeader"]{display:none !important}
[data-testid="stMainBlockContainer"]{max-width:500px !important;padding-top:0 !important;padding-left:12px !important;padding-right:12px !important}
.block-container{padding-top:0 !important;padding-bottom:24px !important}
.xiga-auth-topbar{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;width:100%;margin:0 0 22px;padding:10px 0 8px}
.xiga-auth-brand{text-align:center;color:#fff;font-size:26px;font-weight:950;letter-spacing:1.5px;white-space:nowrap}.xiga-auth-brand span{color:#28f3a5}.xiga-auth-pro-wrap{display:flex;justify-content:flex-end}.xiga-auth-pro{min-width:70px;padding:9px 10px;text-align:center;border-radius:12px;background:linear-gradient(135deg,#3d2d0d,#1f1809);border:1px solid #9b741d;color:#ffd76a;font-size:11px;font-weight:900}
.xiga-auth-title{color:#fff;font-size:30px;font-weight:950;letter-spacing:.5px;margin-top:0}.xiga-auth-title span{color:#28f3a5}.xiga-auth-sub{color:#8ca1b7;font-size:11px;line-height:1.6;margin:7px 0 18px}
div[role="radiogroup"]{display:flex !important;justify-content:center !important;gap:2px !important;flex-wrap:nowrap !important;margin:0 0 14px !important}div[role="radiogroup"] label{color:#8ca1b7 !important;font-size:10px !important;padding:6px 6px !important;white-space:nowrap !important}div[role="radiogroup"] label:has(input:checked){color:#29f5a6 !important}
div[data-testid="stTextInput"] label{color:#dceeff !important;font-size:12px !important}div[data-testid="stTextInput"] input{background:linear-gradient(145deg,rgba(9,39,64,.98),rgba(7,25,43,.98)) !important;border:1px solid #185276 !important;border-radius:13px !important;color:#fff !important;min-height:48px !important}
.xiga-auth-card{background:linear-gradient(145deg,rgba(13,34,57,.96),rgba(5,16,29,.97));border:1px solid rgba(32,91,132,.72);border-radius:20px;padding:16px;margin-top:4px;box-shadow:0 18px 45px rgba(0,0,0,.32),inset 0 1px rgba(255,255,255,.035)}
.stButton>button,[data-testid="stFormSubmitButton"] button{height:52px;border-radius:15px;border:1px solid #5affaf;background:linear-gradient(100deg,#13ca87,#38f5ad);color:#03130d;font-size:14px;font-weight:900;box-shadow:0 8px 28px rgba(37,245,166,.20)}
footer,#MainMenu{display:none !important}
</style>
""", unsafe_allow_html=True)

def xiga_subscription_login():
    render_auth_styles()
    if not SUPABASE_URL or not SUPABASE_PUBLISHABLE_KEY:
        st.error("XIGA PRO subscription settings are missing.")
        st.stop()

    if ensure_session_from_cookie():
        status = get_subscription_status()
        if status is None:
            st.error("Unable to verify your XIGA PRO subscription right now.")
            st.stop()
        st.session_state["xiga_email"] = st.session_state.get("xiga_email") or status.get("email", "")
        if status.get("active"):
            st.session_state["xiga_subscription_active"] = True
            return True

        st.session_state["xiga_subscription_active"] = False
        st.markdown("## XIGA PRO SUBSCRIPTION")
        st.warning("Your XIGA PRO subscription is not active.")
        expires = status.get("subscription_expires_at")
        if expires:
            st.info(f"Previous subscription expiry: {expires}")
        request_key = st.button("GENERATE KEY", key="generate_activation_key", use_container_width=True)
        if request_key:
            code, data = call_xiga_function("request")
            if code == 200:
                st.success("Key request sent. Please contact the XIGA owner for your key.")
            else:
                st.error(data.get("error", "Unable to request a key."))
        with st.form("xiga_activate_key"):
            activation_key = st.text_input("ACTIVATION KEY", placeholder="Enter the key provided to your account")
            activate = st.form_submit_button("ACTIVATE KEY")
        if activate:
            if not activation_key.strip():
                st.error("Please enter your activation key.")
                st.stop()
            code, data = call_xiga_function("activate", activation_key.strip())
            if code == 200:
                st.success("Subscription activated for 1 year. Opening XIGA PRO...")
                st.rerun()
            else:
                st.error(data.get("error", "Activation failed."))
        if st.button("LOG OUT", key="expired_logout", use_container_width=True):
            clear_session()
            st.rerun()
        st.stop()

    st.markdown('<div class="xiga-auth-topbar"><div></div><div class="xiga-auth-brand"><span>▰</span> XIGA</div><div class="xiga-auth-pro-wrap"><div class="xiga-auth-pro">👑 PRO</div></div></div>', unsafe_allow_html=True)
    st.markdown('<div class="xiga-auth-title">XIGA <span>PRO</span><br>SECURE ACCESS</div>', unsafe_allow_html=True)
    st.markdown('<div class="xiga-auth-sub">Use your XIGA account to access the XIGA PRO trading app.</div>', unsafe_allow_html=True)
    mode = st.radio("Access", ["LOGIN", "SIGN UP"], horizontal=True, label_visibility="collapsed", key="access_mode")

    if mode == "LOGIN":
        with st.form("xiga_pro_login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            login = st.form_submit_button("LOGIN")
        if login:
            if not email or not password:
                st.error("Please enter your email and password.")
                st.stop()
            try:
                response = requests.post(
                    f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
                    headers=auth_headers(),
                    json={"email": email.strip(), "password": password},
                    timeout=15,
                )
                if response.status_code != 200:
                    st.error("Invalid email or password. If you just signed up, confirm your email first.")
                    st.stop()
                save_session(response.json())
                st.rerun()
            except requests.RequestException:
                st.error("Unable to connect to XIGA account service.")
                st.stop()

    elif mode == "SIGN UP":
        with st.form("xiga_pro_signup"):
            full_name = st.text_input("Full name")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            confirm = st.text_input("Confirm password", type="password")
            signup = st.form_submit_button("CREATE ACCOUNT")
        if signup:
            if not email or not password:
                st.error("Email and password are required.")
                st.stop()
            if len(password) < 6:
                st.error("Password must be at least 6 characters.")
                st.stop()
            if password != confirm:
                st.error("Passwords do not match.")
                st.stop()
            try:
                response = requests.post(
                    f"{SUPABASE_URL}/auth/v1/signup",
                    headers=auth_headers(),
                    json={"email": email.strip(), "password": password, "data": {"full_name": full_name.strip()}},
                    timeout=15,
                )
                if response.status_code in (200, 201):
                    data = response.json()
                    if data.get("access_token"):
                        save_session(data)
                        st.rerun()
                    st.success("Account created. Please check your email, confirm your account, then log in.")
                else:
                    try:
                        error_data = response.json()
                        message = error_data.get("msg") or error_data.get("error_description") or error_data.get("message")
                    except ValueError:
                        message = None
                    st.error(message or "Unable to create the account.")
            except requests.RequestException:
                st.error("Unable to connect to XIGA account service.")

    st.stop()

xiga_subscription_login()

# Market data providers. Public read-only market data is used; no trading API keys are needed.
BIQUOTE_BASE = "https://biquote.io/api"
BINANCE_BASE = "https://data-api.binance.vision"
BITGET_BASE = "https://api.bitget.com"
OKX_BASE = "https://www.okx.com"

# Multi-user cache settings: identical market requests are shared across sessions.
# Short TTLs reduce duplicate requests for ~50 simultaneous users while keeping prices fresh.
CANDLE_CACHE_SECONDS = 10
TICK_CACHE_SECONDS = 2
NEWS_CACHE_SECONDS = 600
BACKTEST_STANDARD_CANDLES = 5000
BACKTEST_DEEP_CANDLES = 10000
BACKTEST_CACHE_SECONDS = 900

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

def _parse_exchange_candles(provider, raw, resolution):
    candles=[]
    try:
        if provider == "Binance":
            rows = raw
            for row in reversed(rows):
                candles.append({"open":float(row[1]),"high":float(row[2]),"low":float(row[3]),"close":float(row[4]),"datetime":datetime.fromtimestamp(row[0]/1000, tz=timezone.utc).isoformat(),"is_open":datetime.now(timezone.utc).timestamp()*1000 < row[6]})
        elif provider == "Bitget":
            rows = raw.get("data", [])
            for row in reversed(rows):
                candles.append({"open":float(row[1]),"high":float(row[2]),"low":float(row[3]),"close":float(row[4]),"datetime":datetime.fromtimestamp(int(row[0])/1000, tz=timezone.utc).isoformat(),"is_open":False})
        elif provider == "OKX":
            rows = raw.get("data", [])
            for row in reversed(rows):
                candles.append({"open":float(row[1]),"high":float(row[2]),"low":float(row[3]),"close":float(row[4]),"datetime":datetime.fromtimestamp(int(row[0])/1000, tz=timezone.utc).isoformat(),"is_open":str(row[8]) != "1" if len(row)>8 else False})
    except (TypeError, ValueError, IndexError, KeyError):
        return []
    return candles

@st.cache_data(ttl=CANDLE_CACHE_SECONDS, show_spinner=False)
def get_candles_cached(provider, provider_symbol, resolution, _fresh_key="cached"):
    interval = "1m" if resolution == "1" else "5m"
    try:
        if provider == "BiQuote":
            response = requests.get(f"{BIQUOTE_BASE}/{provider_symbol}/ohlc", params={"interval":interval,"limit":300}, timeout=15)
            if response.status_code != 200:
                return [], f"BIQUOTE ERROR {response.status_code}"
            bars=response.json().get("bars",[])
            candles=[]
            for bar in reversed(bars):
                try:
                    candles.append({"open":float(bar["open"]),"high":float(bar["high"]),"low":float(bar["low"]),"close":float(bar["close"]),"datetime":str(bar["openTime"]),"is_open":bool(bar.get("isOpen",False))})
                except (KeyError,TypeError,ValueError): pass
            if len(candles)<60: return [], f"NOT ENOUGH DATA ({len(candles)} CANDLES)"
            return candles, "BIQUOTE MARKET DATA CONNECTED"

        if provider == "Binance":
            r=requests.get(f"{BINANCE_BASE}/api/v3/klines",params={"symbol":provider_symbol,"interval":interval,"limit":300},timeout=15)
        elif provider == "Bitget":
            r=requests.get(f"{BITGET_BASE}/api/v3/market/candles",params={"category":"SPOT","symbol":provider_symbol,"interval":interval,"limit":300},timeout=15)
        elif provider == "OKX":
            r=requests.get(f"{OKX_BASE}/api/v5/market/candles",params={"instId":provider_symbol,"bar":interval,"limit":300},timeout=15)
        else:
            return [], "UNKNOWN MARKET PROVIDER"
        if r.status_code != 200:
            return [], f"{provider.upper()} ERROR {r.status_code}"
        raw=r.json()
        candles=_parse_exchange_candles(provider,raw,resolution)
        if len(candles)<60: return [], f"NOT ENOUGH {provider.upper()} CANDLES ({len(candles)})"
        return candles, f"{provider.upper()} MARKET DATA CONNECTED"
    except requests.exceptions.Timeout:
        return [], f"{provider.upper()} MARKET DATA TIMEOUT"
    except requests.exceptions.RequestException:
        return [], f"{provider.upper()} NETWORK ERROR"
    except Exception as exc:
        return [], f"{provider.upper()} DATA ERROR: {exc}"

def get_candles(provider, symbol, resolution, fresh=False):
    if fresh:
        # Cache-bust only at the decision point so the app remains efficient
        # for multiple simultaneous users.
        return get_candles_cached(provider, symbol, resolution, _fresh_key=datetime.now(timezone.utc).replace(second=0, microsecond=0).isoformat())
    return get_candles_cached(provider, symbol, resolution, _fresh_key="cached")

@st.cache_data(ttl=BACKTEST_CACHE_SECONDS, show_spinner=False)
def get_backtest_candles(provider, provider_symbol, resolution, target_count):
    """Fetch enough historical COMPLETED candles for the XIGA backtest.

    Each provider has different pagination rules, so this function walks
    backward until it has target_count completed candles instead of assuming
    one request can return the whole history.
    """
    target_count = int(max(BACKTEST_STANDARD_CANDLES, min(BACKTEST_DEEP_CANDLES, target_count)))
    interval = "1m" if resolution == "1" else "5m"
    interval_ms = 60_000 if resolution == "1" else 300_000
    # Fetch a small buffer so the currently-open candle can be discarded.
    fetch_target = target_count + 3
    all_candles = []

    def add_rows(rows, parser_provider):
        if not rows:
            return
        raw = rows if parser_provider == "Binance" else {"data": rows}
        all_candles.extend(_parse_exchange_candles(parser_provider, raw, resolution))

    try:
        if provider == "BiQuote":
            # BiQuote documents a maximum of 1000 bars per request and supports
            # the `to` range parameter. Walk backward using the oldest bar.
            cursor_to = datetime.now(timezone.utc)
            safety = 0
            while len(all_candles) < fetch_target and safety < 30:
                safety += 1
                need = min(1000, fetch_target - len(all_candles))
                params = {
                    "interval": interval,
                    "limit": need,
                    "to": cursor_to.isoformat().replace("+00:00", "Z"),
                }
                r = requests.get(f"{BIQUOTE_BASE}/{provider_symbol}/ohlc", params=params, timeout=30)
                if r.status_code != 200:
                    return [], f"BIQUOTE BACKTEST ERROR {r.status_code}"
                bars = r.json().get("bars", [])
                if not bars:
                    break
                for bar in bars:
                    try:
                        all_candles.append({
                            "open": float(bar["open"]),
                            "high": float(bar["high"]),
                            "low": float(bar["low"]),
                            "close": float(bar["close"]),
                            "datetime": str(bar["openTime"]),
                            "is_open": bool(bar.get("isOpen", False)),
                        })
                    except (KeyError, TypeError, ValueError):
                        continue
                times = [parse_candle_time(str(b.get("openTime"))) for b in bars if b.get("openTime")]
                oldest_dt = min((t for t in times if t), default=None)
                if oldest_dt is None or len(bars) < need:
                    break
                cursor_to = oldest_dt - timedelta(milliseconds=interval_ms)

        elif provider == "Binance":
            # Binance klines allow up to 1000 rows. Use endTime to page backward.
            end_time = int(datetime.now(timezone.utc).timestamp() * 1000)
            safety = 0
            while len(all_candles) < fetch_target and safety < 30:
                safety += 1
                need = min(1000, fetch_target - len(all_candles))
                r = requests.get(
                    f"{BINANCE_BASE}/api/v3/klines",
                    params={
                        "symbol": provider_symbol,
                        "interval": interval,
                        "limit": need,
                        "endTime": end_time,
                    },
                    timeout=20,
                )
                if r.status_code != 200:
                    return [], f"BINANCE BACKTEST ERROR {r.status_code}"
                rows = r.json()
                if not rows:
                    break
                add_rows(rows, "Binance")
                oldest = int(rows[0][0])
                if oldest <= 0 or len(rows) < need:
                    break
                end_time = oldest - 1

        elif provider == "Bitget":
            # Bitget's spot candles endpoint supports up to 1000 rows. Supplying
            # both startTime and endTime makes each backward page deterministic.
            end_time = int(datetime.now(timezone.utc).timestamp() * 1000)
            safety = 0
            while len(all_candles) < fetch_target and safety < 30:
                safety += 1
                need = min(1000, fetch_target - len(all_candles))
                start_time = max(0, end_time - interval_ms * (need + 2))
                r = requests.get(
                    f"{BITGET_BASE}/api/v3/market/candles",
                    params={
                        "category": "SPOT",
                        "symbol": provider_symbol,
                        "interval": interval,
                        "startTime": str(start_time),
                        "endTime": str(end_time),
                        "limit": need,
                    },
                    timeout=20,
                )
                if r.status_code != 200:
                    return [], f"BITGET BACKTEST ERROR {r.status_code}"
                raw = r.json()
                rows = raw.get("data", [])
                if not rows:
                    break
                add_rows(rows, "Bitget")
                row_times = []
                for row in rows:
                    try:
                        row_times.append(int(row[0]))
                    except (TypeError, ValueError, IndexError):
                        pass
                oldest = min(row_times) if row_times else 0
                if oldest <= 0 or oldest >= end_time or len(rows) < need:
                    break
                end_time = oldest - 1

        elif provider == "OKX":
            # OKX market candles support up to 300 rows. `after` requests older
            # candles. History-candles is used so the data is historical rather
            # than only the newest 300 bars.
            after = None
            safety = 0
            while len(all_candles) < fetch_target and safety < 50:
                safety += 1
                need = min(300, fetch_target - len(all_candles))
                params = {"instId": provider_symbol, "bar": interval, "limit": need}
                if after is not None:
                    params["after"] = str(after)
                r = requests.get(
                    f"{OKX_BASE}/api/v5/market/history-candles",
                    params=params,
                    timeout=20,
                )
                if r.status_code != 200:
                    return [], f"OKX BACKTEST ERROR {r.status_code}"
                raw = r.json()
                if str(raw.get("code", "0")) != "0":
                    return [], f"OKX BACKTEST API ERROR {raw.get('msg', raw.get('code', 'UNKNOWN'))}"
                rows = raw.get("data", [])
                if not rows:
                    break
                add_rows(rows, "OKX")
                row_times = []
                for row in rows:
                    try:
                        row_times.append(int(row[0]))
                    except (TypeError, ValueError, IndexError):
                        pass
                oldest = min(row_times) if row_times else 0
                if oldest <= 0 or (after is not None and oldest >= int(after)) or len(rows) < need:
                    break
                after = oldest - 1

        else:
            return [], "UNKNOWN BACKTEST PROVIDER"

        # Deduplicate by candle timestamp and sort oldest -> newest.
        unique = {}
        for candle in all_candles:
            dt = parse_candle_time(candle.get("datetime"))
            if dt is not None:
                unique[dt.isoformat()] = candle
        candles = list(unique.values())
        candles.sort(
            key=lambda x: parse_candle_time(x.get("datetime"))
            or datetime.min.replace(tzinfo=timezone.utc)
        )
        closed = completed_candles(candles, resolution)
        if len(closed) < target_count:
            return closed, f"{provider.upper()} BACKTEST DATA • {len(closed)} COMPLETED CANDLES"
        return closed[-target_count:], f"{provider.upper()} BACKTEST DATA • {len(closed)} COMPLETED CANDLES"

    except requests.exceptions.Timeout:
        return [], f"{provider.upper()} BACKTEST TIMEOUT"
    except requests.exceptions.RequestException:
        return [], f"{provider.upper()} BACKTEST NETWORK ERROR"
    except Exception as exc:
        return [], f"{provider.upper()} BACKTEST DATA ERROR: {exc}"

@st.cache_data(ttl=TICK_CACHE_SECONDS, show_spinner=False)
def get_latest_tick(provider, provider_symbol, fresh=False):
    try:
        if provider == "BiQuote":
            r=requests.get(f"{BIQUOTE_BASE}/{provider_symbol}",timeout=10)
            if r.status_code!=200: return None, f"BIQUOTE TICK ERROR {r.status_code}"
            data=r.json(); price=data.get("mid")
            if price is None: price=data.get("last") or data.get("bid") or data.get("ask")
            if price is None: return None,"NO LIVE PRICE"
            return {"price":float(price),"timestamp":data.get("timestamp"),"market_state":data.get("marketState"),"stale":bool(data.get("stale",False))},"BIQUOTE LIVE PRICE CONNECTED"
        if provider == "Binance":
            r=requests.get(f"{BINANCE_BASE}/api/v3/ticker/price",params={"symbol":provider_symbol},timeout=10)
            if r.status_code!=200: return None,f"BINANCE TICK ERROR {r.status_code}"
            return {"price":float(r.json()["price"])},"BINANCE LIVE PRICE CONNECTED"
        if provider == "Bitget":
            r=requests.get(f"{BITGET_BASE}/api/v3/market/tickers",params={"category":"SPOT","symbol":provider_symbol},timeout=10)
            if r.status_code!=200: return None,f"BITGET TICK ERROR {r.status_code}"
            data=r.json().get("data",[])
            if not data: return None,"BITGET NO LIVE PRICE"
            return {"price":float(data[0].get("lastPr") or data[0].get("last") or data[0].get("bidPr"))},"BITGET LIVE PRICE CONNECTED"
        if provider == "OKX":
            r=requests.get(f"{OKX_BASE}/api/v5/market/ticker",params={"instId":provider_symbol},timeout=10)
            if r.status_code!=200: return None,f"OKX TICK ERROR {r.status_code}"
            data=r.json().get("data",[])
            if not data: return None,"OKX NO LIVE PRICE"
            return {"price":float(data[0]["last"])},"OKX LIVE PRICE CONNECTED"
        return None,"UNKNOWN MARKET PROVIDER"
    except requests.exceptions.RequestException:
        return None,f"{provider.upper()} TICK NETWORK ERROR"
    except Exception as exc:
        return None,f"{provider.upper()} TICK ERROR: {exc}"

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


def atr(candles, period=14):
    if len(candles) < period + 1:
        return None
    trs = []
    for i in range(1, len(candles)):
        high = float(candles[i]["high"])
        low = float(candles[i]["low"])
        prev_close = float(candles[i - 1]["close"])
        trs.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    if len(trs) < period:
        return None
    return sum(trs[-period:]) / period


def historical_setup_stats(candles, resolution, lookahead=None, max_samples=90):
    """
    Lightweight walk-forward validation on the available candles.
    This is deliberately not used as a hard trade filter. It calibrates
    confidence from historical outcomes of the same indicator logic.
    """
    if lookahead is None:
        lookahead = 1 if resolution == "1" else 1

    closed = completed_candles(candles, resolution)
    if len(closed) < 90:
        return None

    # Use a compact sample to keep Streamlit responsive for many users.
    usable = closed[:-lookahead]
    start_i = max(55, len(usable) - max_samples)

    wins = losses = draws = 0
    samples = 0

    # Stop early enough to leave a valid future candle for lookahead.
    for i in range(start_i, len(usable) - lookahead):
        window = usable[:i + 1]
        closes = [float(c["close"]) for c in window]
        if len(closes) < 55:
            continue

        e9 = ema(closes, 9)
        e21 = ema(closes, 21)
        e50 = ema(closes, 50)
        rv = rsi(closes, 14)
        mv, _ = macd(closes)

        score = 0
        if e9 is not None and e21 is not None:
            score += 1 if e9 > e21 else -1 if e9 < e21 else 0
        if e21 is not None and e50 is not None:
            score += 1 if e21 > e50 else -1 if e21 < e50 else 0
        if e21 is not None:
            score += 1 if closes[-1] > e21 else -1 if closes[-1] < e21 else 0
        if rv is not None:
            score += 1 if rv >= 55 else -1 if rv <= 45 else 0
        if mv is not None:
            score += 1 if mv > 0 else -1 if mv < 0 else 0
        if len(closes) >= 6:
            score += 1 if closes[-1] > closes[-6] else -1 if closes[-1] < closes[-6] else 0

        if score >= 3:
            direction = "CALL"
        elif score <= -3:
            direction = "PUT"
        else:
            continue

        future = float(usable[i + lookahead]["close"])
        entry = float(window[-1]["close"])
        samples += 1

        if future > entry and direction == "CALL":
            wins += 1
        elif future < entry and direction == "PUT":
            wins += 1
        elif future == entry:
            draws += 1
        else:
            losses += 1

    decided = wins + losses
    if decided < 8:
        return None

    rate = wins / decided
    return {
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "samples": samples,
        "rate": rate,
    }


def analyze_market(provider, symbol, timeframe):
    resolution = TIMEFRAMES.get(timeframe)
    if resolution is None:
        return {
            "success": False, "signal": "NO TRADE", "strength": 0,
            "description": "Use 1 MIN or 5 MIN.",
            "status": "TIMEFRAME UNAVAILABLE",
        }

    candles, market_status = get_candles(provider, symbol, resolution, fresh=True)
    if len(candles) < 61:
        return {
            "success": False, "signal": "NO TRADE", "strength": 0,
            "description": market_status, "status": market_status,
        }

    closed = completed_candles(candles, resolution)
    if len(closed) < 60:
        return {
            "success": False, "signal": "NO TRADE", "strength": 0,
            "description": "WAITING FOR ENOUGH COMPLETED CANDLES",
            "status": market_status,
        }

    closes = [float(c["close"]) for c in closed]
    current = closes[-1]
    e9, e21, e50 = ema(closes, 9), ema(closes, 21), ema(closes, 50)
    rv = rsi(closes, 14)
    mv, pmv = macd(closes)
    atr_value = atr(closed, 14)

    score = 0
    reasons = []
    bullish = bearish = 0

    # Trend: weighted conceptually, but retain the existing -6..+6 style score.
    if e9 is not None and e21 is not None:
        if e9 > e21:
            score += 1; bullish += 1; reasons.append("EMA 9 is above EMA 21")
        elif e9 < e21:
            score -= 1; bearish += 1; reasons.append("EMA 9 is below EMA 21")

    if e21 is not None and e50 is not None:
        if e21 > e50:
            score += 1; bullish += 1; reasons.append("Medium-term trend is bullish")
        elif e21 < e50:
            score -= 1; bearish += 1; reasons.append("Medium-term trend is bearish")

    if e21 is not None:
        if current > e21:
            score += 1; bullish += 1; reasons.append("Price is above EMA 21")
        elif current < e21:
            score -= 1; bearish += 1; reasons.append("Price is below EMA 21")

    # Momentum.
    if rv is not None:
        if rv >= 55:
            score += 1; bullish += 1; reasons.append(f"RSI bullish ({rv:.1f})")
        elif rv <= 45:
            score -= 1; bearish += 1; reasons.append(f"RSI bearish ({rv:.1f})")
        else:
            reasons.append(f"RSI neutral ({rv:.1f})")

    if mv is not None:
        if mv > 0:
            score += 1; bullish += 1; reasons.append("MACD is positive")
        elif mv < 0:
            score -= 1; bearish += 1; reasons.append("MACD is negative")

        if pmv is not None:
            if mv > pmv:
                reasons.append("MACD momentum is rising")
            elif mv < pmv:
                reasons.append("MACD momentum is falling")

    if len(closes) >= 6:
        momentum = closes[-1] - closes[-6]
        if momentum > 0:
            score += 1; bullish += 1; reasons.append("Recent momentum is bullish")
        elif momentum < 0:
            score -= 1; bearish += 1; reasons.append("Recent momentum is bearish")

    # Candle-body / price-action confirmation.
    last = closed[-1]
    candle_range = max(float(last["high"]) - float(last["low"]), 1e-12)
    body = abs(float(last["close"]) - float(last["open"]))
    body_ratio = body / candle_range
    if body_ratio >= 0.55:
        if float(last["close"]) > float(last["open"]):
            score += 1; bullish += 1; reasons.append("Strong bullish candle body")
        elif float(last["close"]) < float(last["open"]):
            score -= 1; bearish += 1; reasons.append("Strong bearish candle body")

    # Volatility guard: avoid extremely flat candles relative to recent ATR.
    volatility_ok = True
    if atr_value is not None and current != 0:
        atr_pct = atr_value / current
        if atr_pct < 0.00002:
            volatility_ok = False
            reasons.append("Very low volatility")
        elif atr_pct > 0.03:
            volatility_ok = False
            reasons.append("Abnormally high volatility")

    news = get_market_news(symbol) if provider == "BiQuote" else {
        "sentiment": 0.0, "articles": 0,
        "status": "EXCHANGE MARKET DATA • NEWS NOT USED"
    }
    sentiment = float(news.get("sentiment", 0.0))
    news_count = int(news.get("articles", 0))

    # News is confirmation only; it cannot create a signal by itself.
    if news_count:
        if sentiment >= 0.15:
            score += 1; bullish += 1; reasons.append("Financial news sentiment is bullish")
        elif sentiment <= -0.15:
            score -= 1; bearish += 1; reasons.append("Financial news sentiment is bearish")
        else:
            reasons.append("Financial news sentiment is neutral")

    if score >= 3:
        signal = "CALL"
    elif score <= -3:
        signal = "PUT"
    else:
        signal = "NO TRADE"

    # Require directional agreement: a large score made from conflicting
    # components should not be treated like a clean setup.
    directional_agreement = max(bullish, bearish) / max(1, bullish + bearish)
    if signal == "CALL" and bearish > bullish:
        signal = "NO TRADE"
    elif signal == "PUT" and bullish > bearish:
        signal = "NO TRADE"

    # Historical walk-forward calibration, not a promise of future results.
    stats = historical_setup_stats(candles, resolution)
    if stats:
        historical_rate = stats["rate"]
        # Blend the historical rate with current setup quality.
        current_quality = min(1.0, max(0.0, 0.50 + abs(score) * 0.045 + (directional_agreement - 0.5) * 0.18))
        raw_probability = 0.70 * historical_rate + 0.30 * current_quality
        probability = int(round(100 * min(0.90, max(0.50, raw_probability))))
    else:
        # Honest fallback while insufficient history exists.
        probability = int(min(88, max(50, 50 + abs(score) * 5 + round(directional_agreement * 5))))

    # Do not force high confidence when volatility is unsuitable.
    if not volatility_ok:
        probability = min(probability, 62)
        if signal in ("CALL", "PUT"):
            signal = "NO TRADE"

    strength = min(5, max(1, round(abs(score) / 2))) if signal != "NO TRADE" else min(5, max(0, round(abs(score) / 2)))

    if signal == "CALL":
        description = f"Bullish setup. Score {score:+d}. Confidence is calibrated from current conditions and recent historical tests."
    elif signal == "PUT":
        description = f"Bearish setup. Score {score:+d}. Confidence is calibrated from current conditions and recent historical tests."
    else:
        description = f"Conditions are mixed or volatility is unsuitable. Score {score:+d}. Waiting for stronger confirmation."

    if stats:
        description += f" Similar historical setups: {stats['samples']}."

    recent_window = closed[-20:]
    support = min(float(c["low"]) for c in recent_window) if recent_window else None
    resistance = max(float(c["high"]) for c in recent_window) if recent_window else None

    tp_profile = None
    if signal in ("CALL", "PUT"):
        tp_profile = historical_favorable_excursion(candles, resolution, signal)
        if tp_profile and recent_window and current > 0:
            recent_high = max(float(c["high"]) for c in recent_window)
            recent_low = min(float(c["low"]) for c in recent_window)
            tp_profile["recent_range_pct"] = max(0.0, (recent_high - recent_low) / current)

    return {
        "success": True,
        "signal": signal,
        "strength": strength,
        "probability": probability,
        "score": score,
        "price": current,
        "support": support,
        "resistance": resistance,
        "entry_candle_time": closed[-1]["datetime"],
        "rsi": rv,
        "macd": mv,
        "atr": atr_value,
        "news_sentiment": sentiment,
        "news_count": news_count,
        "historical_samples": stats["samples"] if stats else 0,
        "historical_rate": stats["rate"] if stats else None,
        "description": description,
        "status": market_status,
        "news_status": news.get("status", "NO NEWS"),
        "reasons": reasons,
        "tp_profile": tp_profile,
    }

def historical_favorable_excursion(candles, resolution, signal, max_samples=120):
    """
    Estimate how far price historically moved in the signal direction during
    one complete trade window. This is used only to size TAKE PROFIT and does
    not change the CALL/PUT signal engine.
    """
    closed = completed_candles(candles, resolution)
    if len(closed) < 80:
        return None

    # Each candle represents the full configured trade window:
    # 1 candle for 1 MIN and 1 candle for 5 MIN.
    horizon = 1
    usable_end = len(closed) - horizon
    start_i = max(55, usable_end - max_samples)
    excursions = []

    for i in range(start_i, usable_end):
        entry = float(closed[i]["close"])
        if entry <= 0:
            continue
        future = closed[i + 1:i + 1 + horizon]
        if not future:
            continue

        if signal == "CALL":
            favorable = max(float(c["high"]) for c in future) - entry
        elif signal == "PUT":
            favorable = entry - min(float(c["low"]) for c in future)
        else:
            return None

        favorable_pct = favorable / entry
        if favorable_pct > 0:
            excursions.append(favorable_pct)

    if len(excursions) < 12:
        return None

    excursions.sort()

    def percentile(values, p):
        position = (len(values) - 1) * p
        low = int(position)
        high = min(low + 1, len(values) - 1)
        fraction = position - low
        return values[low] * (1 - fraction) + values[high] * fraction

    return {
        "samples": len(excursions),
        "p35": percentile(excursions, 0.35),
        "p40": percentile(excursions, 0.40),
        "p50": percentile(excursions, 0.50),
        "p60": percentile(excursions, 0.60),
        "max": max(excursions),
    }


@st.cache_data(ttl=BACKTEST_CACHE_SECONDS, show_spinner=False)
def run_xiga_backtest(provider, symbol, timeframe, target_count=BACKTEST_STANDARD_CANDLES):
    resolution = TIMEFRAMES.get(timeframe)
    if not resolution:
        return {"success": False, "error": "Unsupported timeframe."}

    candles, status = get_backtest_candles(provider, symbol, resolution, target_count)
    if len(candles) < target_count:
        return {
            "success": False,
            "error": f"Only {len(candles)} completed candles were available. XIGA requires {target_count:,} for this backtest. Try another provider/market or use the provider with deeper history.",
            "candles_available": len(candles),
            "status": status,
        }

    wins = losses = draws = calls = puts = call_wins = put_wins = tp_hits = tp_misses = 0
    favorable = []

    for i in range(55, len(candles) - 1):
        window = candles[:i + 1]
        closes = [float(x["close"]) for x in window]
        entry = closes[-1]
        e9, e21, e50 = ema(closes, 9), ema(closes, 21), ema(closes, 50)
        rv = rsi(closes, 14)
        mv, _ = macd(closes)
        atr_value = atr(window, 14)
        score = 0
        bullish = bearish = 0

        if e9 is not None and e21 is not None:
            if e9 > e21: score += 1; bullish += 1
            elif e9 < e21: score -= 1; bearish += 1
        if e21 is not None and e50 is not None:
            if e21 > e50: score += 1; bullish += 1
            elif e21 < e50: score -= 1; bearish += 1
        if e21 is not None:
            if entry > e21: score += 1; bullish += 1
            elif entry < e21: score -= 1; bearish += 1
        if rv is not None:
            if rv >= 55: score += 1; bullish += 1
            elif rv <= 45: score -= 1; bearish += 1
        if mv is not None:
            if mv > 0: score += 1; bullish += 1
            elif mv < 0: score -= 1; bearish += 1
        if len(closes) >= 6:
            if closes[-1] > closes[-6]: score += 1; bullish += 1
            elif closes[-1] < closes[-6]: score -= 1; bearish += 1

        # Same candle-body confirmation and volatility guard used by live analysis.
        last = window[-1]
        candle_range = max(float(last["high"]) - float(last["low"]), 1e-12)
        body_ratio = abs(float(last["close"]) - float(last["open"])) / candle_range
        if body_ratio >= 0.55:
            if float(last["close"]) > float(last["open"]): score += 1; bullish += 1
            elif float(last["close"]) < float(last["open"]): score -= 1; bearish += 1

        volatility_ok = True
        if atr_value is not None and entry:
            atr_pct = atr_value / entry
            if atr_pct < 0.00002 or atr_pct > 0.03:
                volatility_ok = False

        direction = "CALL" if score >= 3 else "PUT" if score <= -3 else None
        if not direction or not volatility_ok:
            continue
        if direction == "CALL" and bearish > bullish:
            continue
        if direction == "PUT" and bullish > bearish:
            continue

        future = candles[i + 1]
        fc = float(future["close"])
        calls += direction == "CALL"
        puts += direction == "PUT"

        if direction == "CALL":
            good = fc > entry
            fav = max(0.0, (float(future["high"]) - entry) / entry)
            if good: wins += 1; call_wins += 1
            elif fc < entry: losses += 1
            else: draws += 1
        else:
            good = fc < entry
            fav = max(0.0, (entry - float(future["low"])) / entry)
            if good: wins += 1; put_wins += 1
            elif fc > entry: losses += 1
            else: draws += 1

        favorable.append(fav)
        recent = window[-20:]
        profile = historical_favorable_excursion(window, resolution, direction, max_samples=120)
        if profile and recent and entry > 0:
            profile["recent_range_pct"] = max(0.0, (max(float(c["high"]) for c in recent) - min(float(c["low"]) for c in recent)) / entry)
        _, tp, _ = calculate_trade_levels(direction, entry, atr_value, timeframe=timeframe, tp_profile=profile)
        if tp is not None:
            hit = float(future["high"]) >= tp if direction == "CALL" else float(future["low"]) <= tp
            if hit: tp_hits += 1
            else: tp_misses += 1

    decided = wins + losses
    total_tp = tp_hits + tp_misses
    accuracy = wins / decided * 100 if decided else 0.0
    tp_rate = tp_hits / total_tp * 100 if total_tp else 0.0
    signals = calls + puts

    # Historical status is a transparent validation check, not a prediction.
    # These thresholds are intentionally simple and fixed so users know why a status appears.
    status_ok = signals >= 100 and accuracy >= 55.0 and tp_rate >= 50.0
    return {
        "success": True, "symbol": symbol, "timeframe": timeframe,
        "candles": len(candles), "signals": signals, "calls": calls, "puts": puts,
        "wins": wins, "losses": losses, "draws": draws,
        "accuracy": accuracy,
        "call_accuracy": call_wins / calls * 100 if calls else 0,
        "put_accuracy": put_wins / puts * 100 if puts else 0,
        "tp_hits": tp_hits, "tp_misses": tp_misses, "tp_rate": tp_rate,
        "avg_favorable": sum(favorable) / len(favorable) * 100 if favorable else 0,
        "status": status, "validation_ok": status_ok,
        "validation_reason": "Meets XIGA's historical validation thresholds." if status_ok else "Does not meet XIGA's historical validation thresholds.",
    }

def calculate_trade_levels(signal, entry_price, atr_value, support=None, resistance=None, timeframe="1 MIN", tp_profile=None):
    """
    Adaptive short-duration trade levels.

    TAKE PROFIT is derived from current ATR and the observed favorable move in
    the last 300 completed candles for the same trade direction/window.
    STOP LOSS remains display-only for the result logic.
    """
    entry = float(entry_price)
    atr_value = float(atr_value or 0)
    if entry <= 0:
        return None, None, None

    if timeframe == "5 MIN":
        atr_multiplier = 0.75
        min_tp_pct = 0.00010   # 0.010% minimum target
        min_risk_pct = 0.00012
        max_risk_pct = 0.00150
        resolution = "5"
    else:
        atr_multiplier = 0.55
        min_tp_pct = 0.00006   # 0.006% minimum target
        min_risk_pct = 0.00006
        max_risk_pct = 0.00060
        resolution = "1"

    atr_pct = (atr_value / entry) if entry else 0.0
    atr_target_pct = atr_pct * atr_multiplier

    # Recent 20-candle range acts as a market-specific ceiling rather than a
    # fixed universal percentage.
    recent_range_pct = 0.0
    if tp_profile and tp_profile.get("recent_range_pct") is not None:
        recent_range_pct = max(0.0, float(tp_profile["recent_range_pct"]))

    # Historical favorable excursion is the main adaptive component.
    if tp_profile and tp_profile.get("p40") is not None:
        historical_target_pct = float(tp_profile["p40"]) * 0.90
        target_pct = 0.55 * atr_target_pct + 0.45 * historical_target_pct
    else:
        target_pct = atr_target_pct

    # Keep TP reachable for the selected short window. The ceiling adapts to
    # both current ATR and the recent 20-candle trading range.
    dynamic_ceiling = max(
        min_tp_pct,
        min(
            max(atr_target_pct * 1.80, min_tp_pct),
            recent_range_pct * 0.35 if recent_range_pct > 0 else max(atr_target_pct * 1.80, min_tp_pct),
        ),
    )
    target_pct = min(max(target_pct, min_tp_pct), dynamic_ceiling)

    reward = entry * target_pct

    # SL is kept close to current volatility and is NOT used to determine WIN/LOSS.
    risk = max(atr_value * (0.60 if timeframe == "1 MIN" else 0.80), entry * min_risk_pct)
    risk = min(risk, entry * max_risk_pct)

    if signal == "CALL":
        stop = entry - risk
        target = entry + reward
    elif signal == "PUT":
        stop = entry + risk
        target = entry - reward
    else:
        return None, None, None

    decimals = max(2, min(8, len(f"{entry:.8f}".rstrip("0").split(".")[-1])))
    return round(entry, decimals), round(target, decimals), round(stop, decimals)

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

def _finish_live_trade(pending, outcome, result_price, reason, elapsed_seconds=0):
    """Finalize a live XIGA signal immediately when TP/SL/expiry resolves."""
    checked = datetime.now(ZoneInfo("Asia/Karachi")).strftime("%Y-%m-%d %H:%M:%S PKT")
    hit_minutes, hit_secs = divmod(max(0, int(elapsed_seconds)), 60)
    elapsed_text = f"{hit_minutes}m {hit_secs}s"

    for item in st.session_state.history:
        if item.get("id") == pending.get("id"):
            item["status"] = outcome
            item["result_price"] = result_price
            item["checked_at"] = checked
            item["tp_hit_second"] = int(elapsed_seconds) if outcome == "WIN" else None
            item["tp_hit_elapsed"] = elapsed_text if outcome == "WIN" else None
            item["result_reason"] = reason
            break

    result = dict(st.session_state.get("result") or {})
    result.update({
        "success": True,
        "signal": pending.get("signal"),
        "status": outcome,
        "result_price": result_price,
        "checked_at": checked,
        "entry_price": pending.get("entry_price"),
        "take_profit": pending.get("take_profit"),
        "stop_loss": pending.get("stop_loss"),
        "trade_time": pending.get("timeframe"),
        "result_time_seconds": int(elapsed_seconds),
        "result_time": elapsed_text,
        "result_reason": reason,
        "tp_hit_elapsed": elapsed_text if outcome == "WIN" else None,
        "tp_hit_price": result_price if outcome == "WIN" else None,
        "description": reason,
    })
    st.session_state.result = result
    st.session_state.trade_pending = None
    update_win_loss_totals()


def resolve_trade_if_ready():
    pending = st.session_state.get("trade_pending")
    if not pending:
        return

    tick, _status = get_latest_tick(
        pending["provider"],
        pending["symbol"],
        fresh=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
    now = datetime.now(timezone.utc)
    started = parse_candle_time(pending.get("started_at")) or now
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    elapsed_seconds = min(
        max(0, int((now - started).total_seconds())),
        60 if pending.get("timeframe") == "1 MIN" else 300,
    )

    if tick:
        live_price = float(tick["price"])
        pending["live_price"] = live_price
        signal = pending["signal"]
        target = float(pending["take_profit"])
        stop = float(pending["stop_loss"])

        if signal == "CALL":
            tp_hit = live_price >= target
            sl_hit = live_price <= stop
        else:
            tp_hit = live_price <= target
            sl_hit = live_price >= stop

        # If a single sampled tick crosses both levels, do not invent an order
        # between them. Treat it as a conservative stop-loss resolution.
        if tp_hit and sl_hit:
            _finish_live_trade(
                pending, "LOSS", live_price,
                "TP and SL were both crossed in the same live price update; XIGA could not determine the intratick order.",
                elapsed_seconds,
            )
            return
        if tp_hit:
            _finish_live_trade(
                pending, "WIN", live_price,
                f"TAKE PROFIT HIT at {elapsed_seconds // 60}m {elapsed_seconds % 60}s. TP {target:.8g} reached at {live_price:.8g}.",
                elapsed_seconds,
            )
            return
        if sl_hit:
            _finish_live_trade(
                pending, "LOSS", live_price,
                f"STOP LOSS HIT at {elapsed_seconds // 60}m {elapsed_seconds % 60}s. SL {stop:.8g} reached at {live_price:.8g}.",
                elapsed_seconds,
            )
            return

    if now >= (parse_candle_time(pending.get("complete_at")) or now):
        result_price = float(tick["price"]) if tick else float(pending["entry_price"])
        _finish_live_trade(
            pending, "EXPIRED", result_price,
            f"Trade window expired after {1 if pending.get('timeframe') == '1 MIN' else 5} minute(s) without TP or SL being reached.",
            elapsed_seconds,
        )

ASSETS, catalog_status = get_symbol_catalog()

# ==============================
# XIGA PRO MOBILE UI
# ==============================
st.markdown("""
<style>
html,body,[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 50% -10%,#173957 0%,#0a1c30 25%,#030914 62%,#020711 100%) !important}
[data-testid="stHeader"]{display:none !important;background:transparent !important}
[data-testid="stMainBlockContainer"]{max-width:520px !important;padding-top:0 !important;padding-left:12px !important;padding-right:12px !important}
.block-container{padding-top:0 !important;padding-bottom:25px !important}
footer,#MainMenu{display:none !important}
.xiga-topbar{display:grid;grid-template-columns:44px 1fr 76px;align-items:center;gap:8px;margin:0 0 12px;padding:4px 0}
.xiga-menu{font-size:28px;color:#e7f5ff;line-height:1;text-align:left}
.xiga-brand{text-align:center}.xiga-title{color:#fff;font-size:25px;font-weight:950;letter-spacing:1px}.xiga-title span{color:#2d8dff}.xiga-subtitle{margin-top:2px;color:#71859d;font-size:8px;letter-spacing:2px}.xiga-live{text-align:right;color:#28f3a5;font-size:9px;font-weight:800;line-height:1.4}.xiga-live small{display:block;color:#8aa0b5;font-weight:500}
.xiga-nav{margin:0 0 12px;background:rgba(4,18,31,.78);border:1px solid #143b5b;border-radius:16px;padding:4px}
div[role="radiogroup"]{display:flex !important;justify-content:space-between !important;gap:2px !important;flex-wrap:nowrap !important;margin:0 !important}div[role="radiogroup"] label{color:#7f95aa !important;font-size:9px !important;padding:8px 4px !important;white-space:nowrap !important;flex:1 !important;justify-content:center !important;text-align:center !important}div[role="radiogroup"] label:has(input:checked){color:#29f5a6 !important;background:rgba(19,91,130,.28);border-radius:11px}
.xiga-card{background:linear-gradient(145deg,rgba(13,34,57,.96),rgba(5,16,29,.97));border:1px solid rgba(32,91,132,.72);border-radius:20px;box-shadow:0 18px 45px rgba(0,0,0,.28),inset 0 1px rgba(255,255,255,.035);padding:13px;margin-bottom:12px}
.xiga-section-title{color:#fff;font-size:17px;font-weight:900;margin-bottom:8px}.xiga-muted{color:#8296ad;font-size:10px;line-height:1.5}
div[data-testid="stSelectbox"] label{color:#7d93aa !important;font-size:8px !important;letter-spacing:1.2px !important;text-transform:uppercase !important}div[data-baseweb="select"]>div{background:linear-gradient(145deg,rgba(9,39,64,.98),rgba(7,25,43,.98)) !important;border:1px solid #185276 !important;color:white !important;border-radius:12px !important}div[data-baseweb="select"] span{color:white !important}
.xiga-market-status{color:#29f4a5;font-size:8px;margin-top:2px}
.stButton>button{width:100%;height:54px;border-radius:15px;border:1px solid #5aaeff;background:linear-gradient(100deg,#087cff,#24b5ff);color:#fff;font-size:14px;font-weight:950;box-shadow:0 8px 28px rgba(0,126,255,.20)}.stButton>button:hover{border-color:#7cc7ff;color:#fff}
.xiga-analyze-note{text-align:center;color:#71879d;font-size:8px;margin:6px 0 10px}
.xiga-signal-card{border-radius:20px;padding:16px;background:linear-gradient(145deg,rgba(6,25,43,.98),rgba(3,13,24,.99));border:1px solid #17557d;box-shadow:0 15px 40px rgba(0,0,0,.28);margin-bottom:12px}
.xiga-signal-card.buy{border-color:rgba(41,245,166,.72);box-shadow:0 0 22px rgba(41,245,166,.10)}.xiga-signal-card.sell{border-color:rgba(255,61,112,.72);box-shadow:0 0 22px rgba(255,61,112,.10)}.xiga-signal-card.result-win{border-color:#29f5a6;box-shadow:0 0 28px rgba(41,245,166,.14)}.xiga-signal-card.result-loss{border-color:#ff416f;box-shadow:0 0 28px rgba(255,65,111,.12)}
.xiga-signal-head{display:flex;justify-content:space-between;align-items:center;color:#8ca1b7;font-size:9px;letter-spacing:1px;text-transform:uppercase}.xiga-badge{padding:5px 8px;border-radius:9px;color:#fff;background:#123d61;border:1px solid #216b9e;font-size:8px}.xiga-badge.live{color:#07160f;background:#2af5a5;border-color:#2af5a5}.xiga-badge.win{color:#03140d;background:#29f5a6;border-color:#29f5a6}.xiga-badge.loss{color:#fff;background:#ff416f;border-color:#ff416f}.xiga-badge.expired{color:#fff;background:#66788a;border-color:#66788a}
.xiga-signal-main{display:flex;justify-content:space-between;align-items:center;gap:10px;margin:15px 0 13px}.xiga-direction-word{font-size:44px;font-weight:950;letter-spacing:-1px}.buy-text{color:#29f5a6;text-shadow:0 0 22px rgba(41,245,166,.25)}.sell-text{color:#ff416f;text-shadow:0 0 22px rgba(255,65,111,.25)}.neutral-text{color:#91a9bd}.xiga-confidence{text-align:right}.xiga-confidence-label{color:#8195aa;font-size:9px}.xiga-confidence-value{color:#fff;font-size:30px;font-weight:950}.xiga-bar{height:7px;width:105px;background:#102d46;border-radius:10px;overflow:hidden;margin-top:5px}.xiga-bar span{display:block;height:100%;border-radius:10px;background:linear-gradient(90deg,#1d9cff,#29f5a6)}
.xiga-levels{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}.xiga-level{background:rgba(5,23,39,.96);border:1px solid #17557d;border-radius:13px;padding:10px 5px;text-align:center}.xiga-level-label{color:#8296ad;font-size:8px;text-transform:uppercase}.xiga-level-value{color:#fff;font-size:12px;font-weight:900;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.xiga-level-value.entry{color:#fff}.xiga-level-value.tp{color:#29f5a6}.xiga-level-value.sl{color:#ff718e}
.xiga-trade-status{text-align:center;padding:13px 8px;margin-top:9px;border-radius:15px;background:linear-gradient(145deg,rgba(7,29,49,.98),rgba(5,17,30,.98));border:1px solid #17557d}.xiga-timer{font-size:31px;font-weight:950;color:#fff}.xiga-timer.active{color:#29f5a6}.xiga-timer.loss{color:#ff416f}.xiga-timer.expired{color:#9eb0bf}.xiga-status-text{color:#8296ad;font-size:9px;margin-top:3px}.xiga-result-time{color:#29f5a6;font-size:10px;font-weight:900;margin-top:4px}
.xiga-why{display:flex;gap:10px;align-items:center;padding:13px;border-radius:16px;background:linear-gradient(145deg,rgba(7,37,47,.97),rgba(5,19,31,.97));border:1px solid rgba(31,181,150,.55);margin-bottom:12px}.xiga-why-icon{font-size:25px}.xiga-why-title{color:#fff;font-size:11px;font-weight:900}.xiga-why-text{color:#8396aa;font-size:9px;line-height:1.5;margin-top:3px}
.xiga-status-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}.xiga-status-item{background:rgba(5,23,39,.96);border:1px solid #17557d;border-radius:13px;padding:10px 5px;text-align:center}.xiga-status-label{color:#8296ad;font-size:8px}.xiga-status-value{color:#fff;font-size:10px;font-weight:900;margin-top:5px}.xiga-status-value.green{color:#29f5a6}.xiga-status-value.red{color:#ff416f}
.xiga-footer{text-align:center;margin-top:9px;color:#4f647a;font-size:7px;letter-spacing:.5px}
.xiga-account-card{background:linear-gradient(145deg,rgba(13,34,57,.98),rgba(5,16,29,.99));border:1px solid rgba(32,91,132,.72);border-radius:18px;padding:14px;margin-bottom:12px}.xiga-account-label{color:#7d93aa;font-size:8px;letter-spacing:1.2px;text-transform:uppercase}.xiga-account-value{color:#fff;font-size:12px;font-weight:800;margin-top:5px;word-break:break-word}.xiga-profile-levels{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:12px}.xiga-profile-level{background:rgba(5,23,39,.96);border:1px solid #17557d;border-radius:12px;padding:9px 4px;text-align:center}.xiga-profile-level b{display:block;color:#8296ad;font-size:7px;text-transform:uppercase}.xiga-profile-level span{display:block;color:#29f5a6;font-size:11px;font-weight:900;margin-top:4px}
.xiga-stat-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:7px}.xiga-stat-box{background:rgba(5,23,39,.96);border:1px solid #17557d;border-radius:13px;padding:11px;text-align:center}.xiga-stat-box b{display:block;color:#8296ad;font-size:8px}.xiga-stat-box span{display:block;color:#fff;font-size:19px;font-weight:950;margin-top:5px}.xiga-stat-box span.green{color:#29f5a6}.xiga-stat-box span.red{color:#ff416f}
.xiga-history-item{padding:12px;border:1px solid #17557d;border-radius:15px;background:rgba(5,23,39,.96);margin-bottom:8px}.xiga-history-top{display:flex;justify-content:space-between;color:#fff;font-size:11px;font-weight:900}.xiga-history-sub{color:#7f94a8;font-size:8px;margin-top:4px;line-height:1.5}.xiga-history-result{font-size:10px;font-weight:900;margin-top:7px}.win{color:#29f5a6}.loss{color:#ff416f}.expired{color:#a6b6c4}
.xiga-analysis-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:7px}.xiga-analysis-item{background:rgba(5,23,39,.96);border:1px solid #17557d;border-radius:13px;padding:11px}.xiga-analysis-item b{display:block;color:#8296ad;font-size:8px}.xiga-analysis-item span{display:block;color:#fff;font-size:13px;font-weight:900;margin-top:5px}.xiga-reason{padding:8px 0;color:#b6c8d8;font-size:10px;border-bottom:1px solid rgba(23,85,125,.45)}
@media(max-width:390px){.xiga-title{font-size:22px}.xiga-direction-word{font-size:38px}.xiga-confidence-value{font-size:26px}.xiga-status-grid{grid-template-columns:1fr}.xiga-levels{gap:4px}}
</style>
""", unsafe_allow_html=True)

nav_options = ["Dashboard", "Analysis", "Backtest", "History", "Profile"]
legacy_page = {"Trade": "Dashboard", "Learn": "Backtest"}
current_page = legacy_page.get(st.session_state.get("page", "Dashboard"), st.session_state.get("page", "Dashboard"))
if current_page not in nav_options:
    current_page = "Dashboard"
st.session_state.page = current_page

# Mobile-first navigation: the hamburger opens the five-page menu.
# A compact tab row remains below the header for one-tap navigation.
top_menu, top_brand, top_live = st.columns([0.65, 2.2, 1.0])
with top_menu:
    with st.popover("☰", use_container_width=True):
        st.markdown("**XIGA PRO**")
        for page_name in nav_options:
            if st.button(page_name, key=f"menu_{page_name}", use_container_width=True):
                st.session_state.page = page_name
                st.rerun()
with top_brand:
    st.markdown('<div class="xiga-brand"><div class="xiga-title"><span>▰</span> XIGA PRO</div><div class="xiga-subtitle">TRADE SMARTER</div></div>', unsafe_allow_html=True)
with top_live:
    st.markdown('<div class="xiga-live">● LIVE DATA<small>Market Connected</small></div>', unsafe_allow_html=True)

st.markdown('<div class="xiga-nav">', unsafe_allow_html=True)
selected_page = st.radio("Navigation", nav_options, index=nav_options.index(st.session_state.page), horizontal=True, label_visibility="collapsed", key="navigation")
st.session_state.page = selected_page
st.markdown('</div>', unsafe_allow_html=True)


def signal_label(signal):
    return {"CALL": "BUY", "PUT": "SELL"}.get(signal, signal)


def signal_class(signal):
    return "buy" if signal == "CALL" else "sell" if signal == "PUT" else "neutral"


def render_result_card(result, timeframe):
    signal = result.get("signal", "READY")
    display_signal = signal_label(signal)
    status = result.get("status", "READY")
    is_result = status in ("WIN", "LOSS", "EXPIRED")
    card_class = signal_class(signal)
    if status == "WIN": card_class += " result-win"
    if status == "LOSS": card_class += " result-loss"
    badge = "LIVE" if not is_result else status
    badge_class = "live" if not is_result else ("win" if status == "WIN" else "loss" if status == "LOSS" else "expired")
    probability = result.get("probability")
    probability_text = f"{int(probability)}%" if probability is not None else "—"
    entry = result.get("entry_price")
    tp = result.get("take_profit")
    sl = result.get("stop_loss")
    if entry is None: entry = result.get("price")
    levels = ""
    if signal in ("CALL", "PUT") and entry is not None and tp is not None and sl is not None:
        entry_label = "BUY AT" if signal == "CALL" else "SELL AT"
        levels = f"""<div class="xiga-levels"><div class="xiga-level"><div class="xiga-level-label">{entry_label}</div><div class="xiga-level-value entry">{float(entry):.8g}</div></div><div class="xiga-level"><div class="xiga-level-label">TAKE PROFIT</div><div class="xiga-level-value tp">{float(tp):.8g}</div></div><div class="xiga-level"><div class="xiga-level-label">STOP LOSS</div><div class="xiga-level-value sl">{float(sl):.8g}</div></div></div>"""

    if status == "WIN":
        timer = result.get("result_time", result.get("tp_hit_elapsed", "—"))
        timer_class = "active"
        timer_text = timer
        status_text = "TAKE PROFIT HIT"
    elif status == "LOSS":
        timer = result.get("result_time", "—")
        timer_class = "loss"
        timer_text = timer
        status_text = "STOP LOSS / LOSS"
    elif status == "EXPIRED":
        timer = result.get("result_time", "—")
        timer_class = "expired"
        timer_text = timer
        status_text = "TRADE WINDOW EXPIRED"
    elif st.session_state.get("trade_pending"):
        timer = format_countdown(seconds_until(st.session_state.trade_pending.get("complete_at")))
        timer_class = "active"
        timer_text = timer
        status_text = "TRADE ACTIVE • MONITORING LIVE PRICE"
    else:
        timer_text = "READY"
        timer_class = "expired"
        status_text = "READY FOR ANALYSIS"

    if status == "WIN":
        reason = result.get("result_reason", "Take profit target reached.")
    elif status == "LOSS":
        reason = result.get("result_reason", "Trade moved against the signal.")
    elif status == "EXPIRED":
        reason = result.get("result_reason", "Trade window ended without TP or SL.")
    else:
        reason = result.get("description", "Select your market and tap Analyze Market.")

    return f"""
<div class="xiga-signal-card {card_class}">
  <div class="xiga-signal-head"><span>XIGA SIGNAL • {result.get("entry_candle_time", "LIVE")}</span><span class="xiga-badge {badge_class}">{badge}</span></div>
  <div class="xiga-signal-main">
    <div class="xiga-direction-word {"buy-text" if signal == "CALL" else "sell-text" if signal == "PUT" else "neutral-text"}">{"↑" if signal == "CALL" else "↓" if signal == "PUT" else "—"} {display_signal}</div>
    <div class="xiga-confidence"><div class="xiga-confidence-label">CONFIDENCE</div><div class="xiga-confidence-value">{probability_text}</div><div class="xiga-bar"><span style="width:{int(probability or 0)}%"></span></div></div>
  </div>
  {levels}
  <div class="xiga-trade-status"><div class="xiga-timer {timer_class}">{timer_text}</div><div class="xiga-status-text">{status_text} • {timeframe}</div>{f'<div class="xiga-result-time">Result recorded at {result.get("result_time", "—")}</div>' if is_result else ''}</div>
  <div class="xiga-why"><div class="xiga-why-icon">💡</div><div><div class="xiga-why-title">{("Why this signal?" if not is_result else "Trade result")}</div><div class="xiga-why-text">{reason}</div></div></div>
</div>
"""


@st.fragment(run_every="1s")
def dashboard_page():
    resolve_trade_if_ready()
    provider_options = EXCHANGE_PROVIDERS
    current_provider = st.session_state.get("provider", "BiQuote")
    if current_provider not in provider_options:
        current_provider = "BiQuote"

    st.markdown('<div class="xiga-card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        provider = st.selectbox("Platform", provider_options, index=provider_options.index(current_provider), key="provider")
    if provider == "BiQuote":
        category_options = list(ASSETS.keys())
        default_category = st.session_state.get("category", category_options[0])
        if default_category not in category_options:
            default_category = category_options[0]
        with c2:
            category = st.selectbox("Market", category_options, index=category_options.index(default_category), key="category")
        asset_map = ASSETS.get(category) or {}
    else:
        asset_map = EXCHANGE_ASSETS[provider]
        with c2:
            st.selectbox("Market", ["Crypto / USDT"], disabled=True, key=f"asset_type_{provider}")

    asset_names = list(asset_map.keys())
    if not asset_names:
        st.error("No instruments are currently available for this platform.")
        st.markdown('</div>', unsafe_allow_html=True)
        return
    current_asset = st.session_state.get("asset")
    if current_asset not in asset_names:
        current_asset = asset_names[0]
    display_asset = st.selectbox("Asset", asset_names, index=asset_names.index(current_asset), key="asset")
    timeframe = st.selectbox("Timeframe", list(TIMEFRAMES.keys()), index=list(TIMEFRAMES.keys()).index(st.session_state.get("timeframe", "1 MIN")) if st.session_state.get("timeframe", "1 MIN") in TIMEFRAMES else 0, key="timeframe")
    provider_note = "BiQuote" if provider == "BiQuote" else provider
    st.markdown(f'<div class="xiga-market-status">● LIVE MARKET READY • {provider_note} • {catalog_status if provider == "BiQuote" else "PUBLIC API"}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    analysis_pending = st.session_state.get("analysis_pending")
    trade_pending = st.session_state.get("trade_pending")
    busy = bool(analysis_pending or trade_pending)

    if analysis_pending:
        remaining = seconds_until(analysis_pending.get("complete_at"))
        st.info(f"🔄 XIGA is analyzing {analysis_pending.get('asset')} • {format_countdown(remaining)} remaining")
    elif trade_pending:
        st.caption(f"Trade active — XIGA is monitoring live price every second. {format_countdown(seconds_until(trade_pending.get('complete_at')))} remaining.")

    if not busy:
        if st.button("⚡ ANALYZE MARKET", key="analyze_button", use_container_width=True):
            symbol = asset_map[display_asset]
            now_utc = datetime.now(timezone.utc)
            st.session_state.analysis_pending = {
                "id": now_utc.isoformat(), "asset": display_asset, "symbol": symbol, "provider": provider,
                "timeframe": timeframe, "started_at": now_utc.isoformat(),
                "complete_at": (now_utc + timedelta(seconds=4)).isoformat(),
            }
            st.session_state.trade_pending = None
            st.session_state.result = {
                "success": False, "signal": "READY", "strength": 0,
                "probability": None, "status": "ANALYSIS IN PROGRESS",
                "description": "Fetching fresh candles and checking the market setup..."
            }
            st.rerun()
    else:
        st.button("⏳ ANALYZING / TRADE ACTIVE", disabled=True, use_container_width=True)

    result = st.session_state.result
    if analysis_pending:
        st.markdown(render_result_card({"signal":"NO TRADE","status":"ANALYSIS IN PROGRESS","probability":None,"description":"XIGA is checking trend, momentum, volatility and market data quality."}, timeframe), unsafe_allow_html=True)
    elif result.get("success") or result.get("status") in ("WIN","LOSS","EXPIRED"):
        st.markdown(render_result_card(result, timeframe), unsafe_allow_html=True)
    else:
        st.markdown(render_result_card({"signal":"NO TRADE","status":"READY","probability":None,"description":"Select the market, asset and timeframe, then tap ANALYZE MARKET."}, timeframe), unsafe_allow_html=True)

    # Compact chart only after data is available; it is not required to make a decision.
    if result.get("success") and not analysis_pending:
        try:
            candles, _ = get_candles(provider, asset_map[display_asset], TIMEFRAMES[timeframe], fresh=False)
            closed = completed_candles(candles, TIMEFRAMES[timeframe])
            if closed:
                import pandas as pd
                chart_rows = [{"Time": parse_candle_time(c["datetime"]), "Price": float(c["close"])} for c in closed[-45:]]
                if chart_rows:
                    st.markdown('<div class="xiga-card"><div class="xiga-section-title">Live Price</div>', unsafe_allow_html=True)
                    st.line_chart(pd.DataFrame(chart_rows).set_index("Time"), height=190, use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)
        except Exception:
            pass

    # Market status is deliberately compact.
    if result.get("success"):
        signal = result.get("signal")
        st.markdown(f"""
<div class="xiga-card"><div class="xiga-section-title">Market Status</div>
<div class="xiga-status-grid">
<div class="xiga-status-item"><div class="xiga-status-label">TREND</div><div class="xiga-status-value {"green" if signal=="CALL" else "red" if signal=="PUT" else ""}">{"UPTREND" if signal=="CALL" else "DOWNTREND" if signal=="PUT" else "MIXED"}</div></div>
<div class="xiga-status-item"><div class="xiga-status-label">VOLATILITY</div><div class="xiga-status-value">{"NORMAL" if result.get("atr") is not None else "UNKNOWN"}</div></div>
<div class="xiga-status-item"><div class="xiga-status-label">MOMENTUM</div><div class="xiga-status-value {"green" if result.get("macd",0) and result.get("macd",0)>0 else "red" if result.get("macd",0) and result.get("macd",0)<0 else ""}">{"STRONG" if abs(result.get("score",0))>=4 else "MODERATE"}</div></div>
</div></div>""", unsafe_allow_html=True)

    st.markdown('<div class="xiga-footer">🔒 SECURE • XIGA PRO • LIVE MARKET ANALYSIS • NO AUTOMATIC TRADE EXECUTION</div>', unsafe_allow_html=True)


def analysis_page():
    result = st.session_state.get("result") or {}
    if not result.get("success"):
        st.markdown('<div class="xiga-card"><div class="xiga-section-title">📊 Analysis</div><div class="xiga-muted">Run an analysis from Dashboard first. This page shows the details behind the latest XIGA signal.</div></div>', unsafe_allow_html=True)
        return
    st.markdown('<div class="xiga-card">', unsafe_allow_html=True)
    st.markdown('<div class="xiga-section-title">📊 Signal Analysis</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="xiga-muted">{signal_label(result.get("signal"))} • {st.session_state.get("timeframe","1 MIN")} • {result.get("status","READY")}</div>', unsafe_allow_html=True)
    rsi_value = result.get("rsi")
    macd_value = result.get("macd")
    hist_rate = result.get("historical_rate")
    items = [
        ("EMA / TREND", "Bullish" if result.get("signal")=="CALL" else "Bearish" if result.get("signal")=="PUT" else "Mixed"),
        ("RSI", f"{rsi_value:.1f}" if rsi_value is not None else "—"),
        ("MACD", f"{macd_value:.6f}" if macd_value is not None else "—"),
        ("SCORE", f"{int(result.get('score',0)):+d}"),
        ("HISTORICAL SETUPS", str(result.get("historical_samples",0))),
        ("HISTORICAL RATE", f"{hist_rate*100:.1f}%" if hist_rate is not None else "—"),
    ]
    html = '<div class="xiga-analysis-grid">' + ''.join(f'<div class="xiga-analysis-item"><b>{a}</b><span>{b}</span></div>' for a,b in items) + '</div>'
    st.markdown(html, unsafe_allow_html=True)
    st.markdown('<div class="xiga-section-title" style="margin-top:14px">Why XIGA generated this</div>', unsafe_allow_html=True)
    reasons = result.get("reasons") or [result.get("description", "No detailed reason available.")]
    for reason in reasons[:10]:
        st.markdown(f'<div class="xiga-reason">• {reason}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="xiga-muted" style="margin-top:10px">Data: {result.get("status","—")}<br>News: {result.get("news_status","—")}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def backtest_page():
    st.markdown('<div class="xiga-card">', unsafe_allow_html=True)
    st.markdown('<div class="xiga-section-title">🧪 XIGA Backtest</div>', unsafe_allow_html=True)
    st.markdown('<div class="xiga-muted">Test the same core indicator logic against historical completed candles. Historical performance does not guarantee future results.</div>', unsafe_allow_html=True)
    bt_mode = st.radio("Backtest depth", ["STANDARD • 5,000 CANDLES", "DEEP • 10,000 CANDLES"], horizontal=True, key="backtest_mode")
    target_count = BACKTEST_DEEP_CANDLES if bt_mode.startswith("DEEP") else BACKTEST_STANDARD_CANDLES
    provider = st.selectbox("Platform", EXCHANGE_PROVIDERS, key="backtest_provider")
    if provider == "BiQuote":
        category = st.selectbox("Market", list(ASSETS.keys()), key="backtest_category")
        asset_map = ASSETS.get(category) or {}
    else:
        st.selectbox("Market", ["Crypto / USDT"], disabled=True, key=f"backtest_type_{provider}")
        asset_map = EXCHANGE_ASSETS[provider]
    asset_names = list(asset_map.keys())
    if asset_names:
        asset = st.selectbox("Asset", asset_names, key="backtest_asset")
        timeframe = st.selectbox("Timeframe", list(TIMEFRAMES.keys()), key="backtest_timeframe")
        if st.button("🧪 RUN BACKTEST", key="run_backtest", use_container_width=True):
            with st.spinner(f"Downloading and testing {target_count:,} completed candles..."):
                st.session_state.backtest_result = run_xiga_backtest(provider, asset_map[asset], timeframe, target_count)
        bt = st.session_state.get("backtest_result")
        if bt:
            if not bt.get("success"):
                st.error(bt.get("error", "Backtest failed."))
                st.caption(bt.get("status", ""))
            else:
                st.markdown(f'<div class="xiga-analysis-grid">'
                            f'<div class="xiga-analysis-item"><b>COMPLETED CANDLES</b><span>{bt["candles"]:,}</span></div>'
                            f'<div class="xiga-analysis-item"><b>BUY SIGNALS</b><span>{bt["calls"]:,}</span></div>'
                            f'<div class="xiga-analysis-item"><b>SELL SIGNALS</b><span>{bt["puts"]:,}</span></div>'
                            f'<div class="xiga-analysis-item"><b>WIN RATE</b><span>{bt["accuracy"]:.1f}%</span></div>'
                            f'<div class="xiga-analysis-item"><b>TP HITS</b><span>{bt["tp_hits"]:,}</span></div>'
                            f'<div class="xiga-analysis-item"><b>TP RATE</b><span>{bt["tp_rate"]:.1f}%</span></div>'
                            f'</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="xiga-muted" style="margin-top:10px">Total signals: {bt["signals"]:,} • Wins: {bt["wins"]:,} • Losses: {bt["losses"]:,} • Draws: {bt["draws"]:,}<br>BUY accuracy: {bt["call_accuracy"]:.1f}% • SELL accuracy: {bt["put_accuracy"]:.1f}%<br>Average favorable movement: {bt["avg_favorable"]:.3f}%</div>', unsafe_allow_html=True)
                if bt.get("validation_ok"):
                    st.success("Historical validation thresholds met.")
                else:
                    st.warning("Historical validation thresholds not met.")
                st.caption(bt.get("validation_reason", "Historical validation only."))
                st.caption("Validation thresholds: at least 100 historical signals, ≥55% directional accuracy, and ≥50% TP-hit rate. These are historical checks, not guarantees.")
    st.markdown('</div>', unsafe_allow_html=True)


def history_page():
    st.markdown('<div class="xiga-card">', unsafe_allow_html=True)
    st.markdown('<div class="xiga-section-title">📜 Signal History</div>', unsafe_allow_html=True)
    if not st.session_state.history:
        st.markdown('<div class="xiga-muted">No live signals have been generated yet.</div>', unsafe_allow_html=True)
    else:
        for item in st.session_state.history[:30]:
            status = item.get("status", "PENDING")
            status_cls = "win" if status == "WIN" else "loss" if status == "LOSS" else "expired"
            direction = signal_label(item.get("signal"))
            st.markdown(f"""
<div class="xiga-history-item"><div class="xiga-history-top"><span>{item.get("asset","—")}</span><span>{direction}</span></div>
<div class="xiga-history-sub">{item.get("provider","—")} • {item.get("timeframe","—")} • {item.get("time","—")}<br>Entry: {item.get("price","—")} • TP: {item.get("take_profit","—")} • SL: {item.get("stop_loss","—")}</div>
<div class="xiga-history-result {status_cls}">{status} {("• TP HIT IN " + str(item.get("tp_hit_elapsed"))) if status == "WIN" and item.get("tp_hit_elapsed") else ""}</div></div>
""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def profile_page():
    status = get_subscription_status() or st.session_state.get("xiga_status") or {}
    email = st.session_state.get("xiga_email") or status.get("email") or "Account"
    active = bool(status.get("active", True))
    expiry = status.get("subscription_expires_at") or "—"
    days = status.get("days_remaining", 0)
    expiry_short = str(expiry)[:10] if expiry != "—" else "—"
    total = len(st.session_state.history)
    wins = sum(1 for x in st.session_state.history if x.get("status") == "WIN")
    losses = sum(1 for x in st.session_state.history if x.get("status") == "LOSS")
    expired = sum(1 for x in st.session_state.history if x.get("status") == "EXPIRED")
    decided = wins + losses
    observed_rate = wins / decided * 100 if decided else 0
    tp_hit_rate = wins / total * 100 if total else 0

    st.markdown('<div class="xiga-card">', unsafe_allow_html=True)
    st.markdown('<div class="xiga-section-title">👤 Profile</div>', unsafe_allow_html=True)
    st.markdown(f"""
<div class="xiga-account-card"><div class="xiga-account-label">ACCOUNT EMAIL</div><div class="xiga-account-value">{email}</div>
<div class="xiga-profile-levels"><div class="xiga-profile-level"><b>STATUS</b><span>{"ACTIVE" if active else "INACTIVE"}</span></div><div class="xiga-profile-level"><b>DAYS LEFT</b><span>{days}</span></div><div class="xiga-profile-level"><b>EXPIRES</b><span>{expiry_short}</span></div></div></div>
""", unsafe_allow_html=True)

    st.markdown('<div class="xiga-section-title">Quick Stats</div>', unsafe_allow_html=True)
    st.markdown(f"""
<div class="xiga-stat-grid"><div class="xiga-stat-box"><b>TOTAL SIGNALS</b><span>{total}</span></div><div class="xiga-stat-box"><b>WINS</b><span class="green">{wins}</span></div><div class="xiga-stat-box"><b>LOSSES</b><span class="red">{losses}</span></div><div class="xiga-stat-box"><b>EXPIRED</b><span>{expired}</span></div><div class="xiga-stat-box"><b>OBSERVED WIN RATE</b><span>{observed_rate:.1f}%</span></div><div class="xiga-stat-box"><b>TP HIT RATE</b><span>{tp_hit_rate:.1f}%</span></div></div>
""", unsafe_allow_html=True)
    st.caption("Quick Stats are your recorded XIGA live-signal history. They are not a forecast of future performance.")
    if st.button("🚪 LOG OUT", key="profile_logout", use_container_width=True):
        clear_session()
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


if selected_page == "Dashboard":
    dashboard_page()
elif selected_page == "Analysis":
    analysis_page()
elif selected_page == "Backtest":
    backtest_page()
elif selected_page == "History":
    history_page()
elif selected_page == "Profile":
    profile_page()

st.caption("XIGA is a market-analysis assistant. It does not automatically place trades.")
