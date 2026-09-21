
import streamlit as st
import requests
from streamlit_js import st_js_blocking
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
@st.cache_resource
def get_cookie_manager():
    return stx.CookieManager(key="xiga-pro-auth")

COOKIE_MANAGER = get_cookie_manager()
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
        cookies = COOKIE_MANAGER.get_all(key="xiga_refresh_cookie_read")
        if not cookies:
            return ""
        value = cookies.get(COOKIE_NAME)
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
    st.session_state.pop("xiga_cookie_checked", None)

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

    # Cookie components load asynchronously. Give the browser one rerun to
    # return the persistent cookie before displaying the login screen.
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

def get_browser_recovery_hash():
    """Read the Supabase recovery hash from the actual app page."""
    try:
        value = st_js_blocking(
            code="return window.parent.location.hash || window.location.hash || '';"
        )
        return value or ""
    except Exception:
        return ""


def handle_password_recovery():
    # Supabase's recovery flow returns the session in the URL fragment.
    # Streamlit Python cannot read fragments directly, so the small JS component
    # reads the fragment and hands it back to Python.
    recovery_hash = get_browser_recovery_hash()
    if recovery_hash and "type=recovery" in recovery_hash and "access_token=" in recovery_hash:
        from urllib.parse import parse_qs
        values = parse_qs(recovery_hash.lstrip("#"), keep_blank_values=True)
        access_token = values.get("access_token", [""])[0]
        refresh_token = values.get("refresh_token", [""])[0]
        if access_token:
            st.session_state["xiga_recovery_token"] = access_token
            st.session_state["xiga_recovery_refresh"] = refresh_token
            # Remove the recovery fragment from the visible URL.
            try:
                st_js_blocking(code="window.parent.history.replaceState({}, document.title, window.parent.location.pathname + window.parent.location.search); return true;")
            except Exception:
                pass
            st.rerun()

    access_token = st.session_state.get("xiga_recovery_token", "")
    refresh_token = st.session_state.get("xiga_recovery_refresh", "")
    if not access_token:
        return False

    st.markdown("## RESET PASSWORD")
    st.caption("Create a new password for your XIGA account.")
    with st.form("xiga_password_reset"):
        new_password = st.text_input("New password", type="password")
        confirm_password = st.text_input("Confirm new password", type="password")
        reset = st.form_submit_button("SAVE NEW PASSWORD")

    if reset:
        if len(new_password) < 6:
            st.error("Password must be at least 6 characters.")
            st.stop()
        if new_password != confirm_password:
            st.error("Passwords do not match.")
            st.stop()
        try:
            session_response = requests.post(
                f"{SUPABASE_URL}/auth/v1/token?grant_type=refresh_token",
                headers=auth_headers(),
                json={"refresh_token": refresh_token},
                timeout=15,
            ) if refresh_token else None
            token = access_token
            if session_response is not None and session_response.status_code == 200:
                token = session_response.json().get("access_token", access_token)
            response = requests.put(
                f"{SUPABASE_URL}/auth/v1/user",
                headers=auth_headers(token),
                json={"password": new_password},
                timeout=15,
            )
            if response.status_code == 200:
                st.session_state.pop("xiga_recovery_token", None)
                st.session_state.pop("xiga_recovery_refresh", None)
                st.success("Password updated successfully. Please log in with your new password.")
                st.session_state["access_mode"] = "LOGIN"
                st.rerun()
            else:
                try:
                    message = response.json().get("msg") or response.json().get("message")
                except ValueError:
                    message = None
                st.error(message or "Unable to update the password. The reset link may have expired.")
        except requests.RequestException:
            st.error("Unable to connect to the XIGA account service.")
    return True

def xiga_subscription_login():
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

    st.markdown("## XIGA PRO SECURE ACCESS")
    st.caption("Use your XIGA account to access the XIGA PRO trading app.")
    mode = st.radio("Access", ["LOGIN", "SIGN UP", "FORGOT PASSWORD"], horizontal=True, label_visibility="collapsed", key="access_mode")

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

    else:
        st.info("Enter your registered email and we will send a password reset link.")
        with st.form("xiga_pro_forgot_password"):
            email = st.text_input("Registered email")
            send_reset = st.form_submit_button("SEND RESET LINK")
        if send_reset:
            if not email.strip():
                st.error("Please enter your email address.")
                st.stop()
            try:
                response = requests.post(
                    f"{SUPABASE_URL}/auth/v1/recover",
                    headers=auth_headers(),
                    json={"email": email.strip(), "redirect_to": XIGA_PRO_URL},
                    timeout=15,
                )
                if response.status_code in (200, 201):
                    st.success("Password reset email sent. Open the email and follow the link to set a new password.")
                else:
                    st.error("Unable to send the password reset email. Check your Supabase redirect URL settings.")
            except requests.RequestException:
                st.error("Unable to connect to XIGA account service.")

    st.stop()

if not handle_password_recovery():
    xiga_subscription_login()
else:
    st.stop()

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
            response = requests.get(f"{BIQUOTE_BASE}/{provider_symbol}/ohlc", params={"interval":interval,"limit":150}, timeout=15)
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
            r=requests.get(f"{BINANCE_BASE}/api/v3/klines",params={"symbol":provider_symbol,"interval":interval,"limit":150},timeout=15)
        elif provider == "Bitget":
            r=requests.get(f"{BITGET_BASE}/api/v3/market/candles",params={"category":"SPOT","symbol":provider_symbol,"interval":interval,"limit":150},timeout=15)
        elif provider == "OKX":
            r=requests.get(f"{OKX_BASE}/api/v5/market/candles",params={"instId":provider_symbol,"bar":interval,"limit":150},timeout=15)
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
    }

def calculate_trade_levels(signal, entry_price, atr_value, support=None, resistance=None):
    entry = float(entry_price)
    atr_value = float(atr_value or 0)
    if entry <= 0:
        return None, None, None
    base_risk = max(atr_value * 1.10, entry * 0.001)
    if signal == "CALL":
        support_gap = entry - float(support) if support is not None else 0
        risk = max(base_risk, support_gap + atr_value * 0.15 if support_gap > 0 else base_risk)
        stop = entry - risk
        resistance_gap = float(resistance) - entry if resistance is not None else 0
        target = entry + max(risk * 1.5, resistance_gap if resistance_gap > risk * 1.05 else 0)
    elif signal == "PUT":
        resistance_gap = float(resistance) - entry if resistance is not None else 0
        risk = max(base_risk, resistance_gap + atr_value * 0.15 if resistance_gap > 0 else base_risk)
        stop = entry + risk
        support_gap = entry - float(support) if support is not None else 0
        target = entry - max(risk * 1.5, support_gap if support_gap > risk * 1.05 else 0)
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

def resolve_trade_if_ready():
    pending = st.session_state.get("trade_pending")
    if not pending or seconds_until(pending.get("complete_at")) > 0: return
    # At expiry, bypass the normal short cache so the result uses the latest
    # available market price/candle rather than an older cached value.
    tick, status = get_latest_tick(pending["provider"], pending["symbol"], fresh=datetime.now(timezone.utc).replace(microsecond=0).isoformat())
    if tick:
        result_price = float(tick["price"])
    else:
        candles, candle_status = get_candles(pending["provider"], pending["symbol"], TIMEFRAMES[pending["timeframe"]])
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
[data-testid="stMainBlockContainer"]{max-width:500px !important;padding-top:0 !important;padding-left:12px !important;padding-right:12px !important}.stElementContainer:has(iframe){display:none !important}
.block-container{padding-top:0 !important;padding-bottom:25px !important}
.xiga-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}.xiga-menu{width:42px;height:42px;border-radius:13px;display:flex;align-items:center;justify-content:center;background:rgba(11,30,49,.88);border:1px solid #214967;color:#dceeff;font-size:21px}.xiga-brand{text-align:center;flex:1}.xiga-title{color:#fff;font-size:25px;font-weight:900;letter-spacing:1px}.xiga-title span{color:#28f3a5}.xiga-subtitle{margin-top:4px;color:#71859d;font-size:8px;letter-spacing:2px}.xiga-pro{min-width:66px;padding:9px 8px;text-align:center;border-radius:12px;background:linear-gradient(135deg,#3d2d0d,#1f1809);border:1px solid #9b741d;color:#ffd76a;font-size:10px;font-weight:800}
.xiga-card{background:linear-gradient(145deg,rgba(13,34,57,.96),rgba(5,16,29,.97));border:1px solid rgba(32,91,132,.72);border-radius:20px;box-shadow:0 18px 45px rgba(0,0,0,.32),inset 0 1px rgba(255,255,255,.035);padding:12px;margin-bottom:12px}
div[data-testid="stSelectbox"] label{color:#7d93aa !important;font-size:8px !important;letter-spacing:1.4px !important;text-transform:uppercase !important}div[data-baseweb="select"]>div{background:linear-gradient(145deg,rgba(9,39,64,.98),rgba(7,25,43,.98)) !important;border:1px solid #185276 !important;color:white !important;border-radius:12px !important}div[data-baseweb="select"] span{color:white !important}.xiga-market-status{color:#29f4a5;font-size:7px;margin-top:3px}
.xiga-signal{text-align:center;position:relative;overflow:hidden;min-height:560px}.xiga-signal:before{content:"";position:absolute;left:-10%;right:-10%;top:105px;height:190px;opacity:.22;background:repeating-linear-gradient(0deg,transparent 0px,transparent 45px,#226082 46px)}.xiga-signal-label{color:#8ca1b7;font-size:9px;letter-spacing:1.5px;text-transform:uppercase;position:relative}.xiga-asset{color:white;font-size:22px;font-weight:900;position:relative;margin-top:4px}.xiga-time{color:#28f3a5;font-size:9px;letter-spacing:1px;margin-top:4px;position:relative}
.xiga-circle{width:205px;height:205px;border-radius:50%;margin:25px auto 18px;display:flex;align-items:center;justify-content:center;position:relative}.xiga-circle.call{background:radial-gradient(circle,rgba(38,246,165,.43) 0%,rgba(14,74,61,.70) 35%,rgba(3,15,27,.98) 72%);border:3px solid #29f5a6;box-shadow:0 0 11px #29f5a6,0 0 35px rgba(41,245,166,.65),0 0 80px rgba(41,245,166,.22),inset 0 0 32px rgba(41,245,166,.27)}.xiga-circle.put{background:radial-gradient(circle,rgba(255,53,103,.42) 0%,rgba(82,17,41,.72) 35%,rgba(3,15,27,.98) 72%);border:3px solid #ff3d70;box-shadow:0 0 11px #ff3d70,0 0 35px rgba(255,61,112,.65),0 0 80px rgba(255,61,112,.22)}.xiga-circle.neutral{background:radial-gradient(circle,rgba(80,140,180,.28) 0%,rgba(17,46,68,.72) 35%,rgba(3,15,27,.98) 72%);border:3px solid #5e91b5;box-shadow:0 0 11px #5e91b5,0 0 35px rgba(94,145,181,.35)}.xiga-arrow{font-size:76px;font-weight:900;line-height:1}.call-text{color:#35f4a9;text-shadow:0 0 20px rgba(53,244,169,.3)}.put-text{color:#ff416f;text-shadow:0 0 20px rgba(255,65,111,.3)}.neutral-text{color:#8fb4cf}.xiga-signal-title{font-size:29px;font-weight:950;position:relative}.xiga-direction{color:#8597ac;font-size:9px;letter-spacing:2px;margin-top:4px}.xiga-stat{background:linear-gradient(145deg,rgba(7,29,49,.98),rgba(5,17,30,.98));border:1px solid #17557d;border-radius:15px;padding:13px 8px;text-align:center;min-height:100px}.xiga-stat-label{color:#8296ad;font-size:9px;text-transform:uppercase}.xiga-strength{color:#29f5a6;font-size:18px;margin-top:8px;letter-spacing:2px}.xiga-number{color:white;font-size:12px;font-weight:800;margin-top:3px}.xiga-win{color:#29f5a6;font-size:24px;font-weight:900;margin-top:6px;letter-spacing:1px}.xiga-ai{display:flex;gap:11px;align-items:center;margin-top:11px;padding:12px;text-align:left;border-radius:15px;background:linear-gradient(145deg,rgba(7,37,47,.97),rgba(5,19,31,.97));border:1px solid rgba(31,181,150,.55)}.xiga-ai-icon{width:35px;height:35px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#2af5a5;border:1px solid rgba(42,245,165,.48);flex-shrink:0}.xiga-ai-title{color:#2af5a5;font-size:11px;font-weight:900}.xiga-ai-desc{color:#7f92a7;font-size:8px;margin-top:3px}
.stButton>button{width:100%;height:55px;border-radius:16px;border:1px solid #5affaf;background:linear-gradient(100deg,#13ca87,#38f5ad);color:#03130d;font-size:14px;font-weight:900;box-shadow:0 8px 28px rgba(37,245,166,.20)}.stButton>button:hover{border-color:#5affaf;color:#03130d}.xiga-footer{text-align:center;margin-top:9px;color:#4f647a;font-size:7px;letter-spacing:.5px}
div[role="radiogroup"]{display:flex !important;justify-content:center !important;gap:4px !important;flex-wrap:nowrap !important;margin:0 0 12px !important}div[role="radiogroup"] label{color:#8ca1b7 !important;font-size:10px !important;padding:5px 7px !important;white-space:nowrap !important}div[role="radiogroup"] label:has(input:checked){color:#29f5a6 !important}
.xiga-menu-button button{width:42px !important;height:42px !important;min-height:42px !important;padding:0 !important;border-radius:13px !important;background:rgba(11,30,49,.88) !important;border:1px solid #214967 !important;color:#dceeff !important;font-size:21px !important;box-shadow:none !important}.xiga-account-card{background:linear-gradient(145deg,rgba(13,34,57,.98),rgba(5,16,29,.99));border:1px solid rgba(32,91,132,.72);border-radius:18px;padding:14px;margin-bottom:12px}.xiga-account-label{color:#7d93aa;font-size:8px;letter-spacing:1.4px;text-transform:uppercase}.xiga-account-value{color:#fff;font-size:12px;font-weight:800;margin-top:4px}.xiga-levels{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:12px}.xiga-level{background:linear-gradient(145deg,rgba(7,29,49,.98),rgba(5,17,30,.98));border:1px solid #17557d;border-radius:12px;padding:9px 5px;text-align:center}.xiga-level-label{color:#8296ad;font-size:7px;text-transform:uppercase}.xiga-level-value{color:#29f5a6;font-size:11px;font-weight:900;margin-top:4px}.xiga-trade-levels{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin:14px 0 2px;padding:10px 6px;border-radius:15px;background:linear-gradient(145deg,rgba(7,29,49,.98),rgba(5,17,30,.98));border:1px solid #17557d}.xiga-trade-level{text-align:center;min-width:0}.xiga-trade-label{color:#8296ad;font-size:7px;text-transform:uppercase;letter-spacing:.4px}.xiga-trade-value{color:#fff;font-size:10px;font-weight:900;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.xiga-trade-value.entry{color:#29f5a6}.xiga-trade-value.tp{color:#7ed8ff}.xiga-trade-value.sl{color:#ff718e}
.xiga-top-spacer{display:none !important}.xiga-brand{text-align:center;width:100%;padding-top:0}.xiga-menu-button{display:flex;justify-content:flex-start;align-items:center}.xiga-menu-button button{width:42px !important;height:42px !important;min-height:42px !important;padding:0 !important;margin:0 !important;border-radius:13px !important;background:rgba(11,30,49,.88) !important;border:1px solid #214967 !important;color:#dceeff !important;font-size:21px !important;line-height:42px !important;box-shadow:none !important}.xiga-menu-button button:hover{background:rgba(16,43,67,.96) !important;border-color:#2d668c !important;color:#fff !important}.xiga-pro-wrap{display:flex;justify-content:flex-end;align-items:center}.xiga-pro{width:66px;min-width:66px;box-sizing:border-box;padding:9px 8px;text-align:center;border-radius:12px;background:linear-gradient(135deg,#3d2d0d,#1f1809);border:1px solid #9b741d;color:#ffd76a;font-size:10px;font-weight:800}.xiga-top-row{margin-top:0 !important;margin-bottom:8px !important}
header[data-testid="stHeader"] {
    display: none !important;
}
footer {
    display: none !important;
}
#MainMenu {
    display: none !important;
}
</style>
""", unsafe_allow_html=True)

top_left, top_center, top_right = st.columns([0.18, 0.64, 0.18], vertical_alignment="center")
with top_left:
    st.markdown('<div class="xiga-menu-button">', unsafe_allow_html=True)
    menu_clicked = st.button("☰", key="account_menu_button")
    st.markdown('</div>', unsafe_allow_html=True)
with top_center:
    st.markdown('<div class="xiga-brand"><div class="xiga-title"><span>▰</span> XIGA</div><div class="xiga-subtitle">TRADING SIGNAL BOT</div></div>', unsafe_allow_html=True)
with top_right:
    st.markdown('<div class="xiga-pro-wrap"><div class="xiga-pro">👑 PRO</div></div>', unsafe_allow_html=True)

if menu_clicked:
    st.session_state["show_account_menu"] = not st.session_state.get("show_account_menu", False)

if st.session_state.get("show_account_menu"):
    status = st.session_state.get("xiga_status") or {}
    email = st.session_state.get("xiga_email", "Account")
    expiry = status.get("subscription_expires_at") or "—"
    days = status.get("days_remaining", 0)
    expiry_short = str(expiry)[:10] if expiry != "—" else "—"
    st.markdown(f'<div class="xiga-account-card"><div class="xiga-account-label">ACCOUNT</div><div class="xiga-account-value">{email}</div><div class="xiga-levels"><div class="xiga-level"><div class="xiga-level-label">STATUS</div><div class="xiga-level-value">ACTIVE</div></div><div class="xiga-level"><div class="xiga-level-label">DAYS LEFT</div><div class="xiga-level-value">{days}</div></div><div class="xiga-level"><div class="xiga-level-label">EXPIRES</div><div class="xiga-level-value">{expiry_short}</div></div></div></div>', unsafe_allow_html=True)
    if st.button("LOG OUT", key="account_logout", use_container_width=True):
        clear_session()
        st.session_state["show_account_menu"] = False
        st.rerun()

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
        provider_options = EXCHANGE_PROVIDERS
        current_provider = st.session_state.get("provider", "BiQuote")
        if current_provider not in provider_options:
            current_provider = "BiQuote"

        st.markdown('<div class="xiga-card">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            provider = st.selectbox("Platform", provider_options, index=provider_options.index(current_provider), key="provider")
        if provider == "BiQuote":
            category_options = list(ASSETS.keys())
            default_category = st.session_state.get("category", category_options[0])
            if default_category not in category_options: default_category = category_options[0]
            with col2:
                category = st.selectbox("Asset", category_options, index=category_options.index(default_category), key="category")
            asset_map = ASSETS.get(category) or {}
        else:
            asset_map = EXCHANGE_ASSETS[provider]
            with col2:
                st.selectbox("Asset Type", ["Crypto / USDT"], disabled=True, key=f"asset_type_{provider}")

        asset_names = list(asset_map.keys())
        if not asset_names:
            st.error("No instruments are currently available for this platform.")
            st.markdown("</div>", unsafe_allow_html=True)
            return
        current_asset = st.session_state.get("asset")
        if current_asset not in asset_names: current_asset = asset_names[0]
        display_asset = st.selectbox("Market", asset_names, index=asset_names.index(current_asset), key="asset")
        timeframe = st.selectbox("Timeframe", list(TIMEFRAMES.keys()), index=0, key="timeframe")
        provider_note = "BiQuote live market data" if provider == "BiQuote" else f"{provider} live exchange market data"
        st.markdown(f'<div class="xiga-market-status">● LIVE MARKET READY • {provider_note} • {catalog_status if provider == "BiQuote" else "PUBLIC API"}</div>', unsafe_allow_html=True)
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
        active_levels = st.session_state.get("trade_pending") or {}
        level_signal = result.get("signal")
        level_entry = active_levels.get("entry_price") if active_levels else None
        level_tp = active_levels.get("take_profit") if active_levels else None
        level_sl = active_levels.get("stop_loss") if active_levels else None
        levels_html = ""
        if level_signal in ("CALL", "PUT") and level_entry is not None and level_tp is not None and level_sl is not None:
            entry_label = "BUY AT" if level_signal == "CALL" else "SELL AT"
            levels_html = f'<div class="xiga-trade-levels"><div class="xiga-trade-level"><div class="xiga-trade-label">{entry_label}</div><div class="xiga-trade-value entry">{level_entry:.8g}</div></div><div class="xiga-trade-level"><div class="xiga-trade-label">TAKE PROFIT</div><div class="xiga-trade-value tp">{level_tp:.8g}</div></div><div class="xiga-trade-level"><div class="xiga-trade-label">STOP LOSS</div><div class="xiga-trade-value sl">{level_sl:.8g}</div></div></div>'

        st.markdown(f'''
<div class="xiga-card xiga-signal">
<div class="xiga-signal-label">SIGNAL FOR</div>
<div class="xiga-asset">{clean_asset}</div>
<div class="xiga-time">● TIMEFRAME: {timeframe}</div>
<div class="xiga-circle {circle_class}"><div class="xiga-arrow">{arrow}</div></div>
<div class="xiga-signal-title {title_class}">{title}</div>
<div class="xiga-direction">{direction}</div>
{levels_html}
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
            selected_provider = provider
            duration_minutes = 1 if timeframe == "1 MIN" else 5
            now_utc = datetime.now(timezone.utc)
            st.session_state.analysis_pending = {
                "id": now_utc.isoformat(), "asset": clean_asset, "symbol": symbol, "provider": selected_provider,
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
            selected_provider = analysis_pending.get("provider", "BiQuote")
            tf = analysis_pending["timeframe"]
            with st.spinner("Finalizing market analysis..."):
                analysis = analyze_market(selected_provider, symbol, tf)
            st.session_state.result = analysis
            st.session_state.analysis_pending = None
            if analysis.get("success"):
                st.session_state.signals += 1

            if analysis.get("success") and analysis.get("signal") in ("CALL", "PUT"):
                entry_tick, entry_status = get_latest_tick(selected_provider, symbol)
                entry_price = float(entry_tick["price"]) if entry_tick else float(analysis.get("price", 0))
                entry_level, take_profit, stop_loss = calculate_trade_levels(analysis["signal"], entry_price, analysis.get("atr"), analysis.get("support"), analysis.get("resistance"))
                duration_minutes = 1 if tf == "1 MIN" else 5
                start = datetime.now(ZoneInfo("Asia/Karachi"))
                trade_id = analysis_pending["id"]
                st.session_state.trade_pending = {
                    "id": trade_id, "asset": analysis_pending["asset"], "symbol": symbol, "provider": selected_provider,
                    "timeframe": tf, "signal": analysis["signal"],
                    "probability": int(analysis.get("probability", 50)), "entry_price": entry_price,
                    "take_profit": take_profit, "stop_loss": stop_loss,
                    "started_at": start.isoformat(), "complete_at": (start + timedelta(minutes=duration_minutes)).isoformat(),
                    "state": "TRADE COUNTDOWN", "error": "",
                }
                st.session_state.history.insert(0, {
                    "id": trade_id, "asset": analysis_pending["asset"], "symbol": symbol, "provider": selected_provider,
                    "signal": analysis["signal"], "strength": analysis.get("strength", 0),
                    "probability": analysis.get("probability", 50), "price": entry_price,
                    "take_profit": take_profit, "stop_loss": stop_loss,
                    "timeframe": tf, "time": start.strftime("%Y-%m-%d %H:%M:%S PKT"), "provider": selected_provider,
                    "status": "PENDING", "result_price": "—",
                    "analysis_description": analysis.get("description", ""), "entry_status": entry_status,
                })
            st.rerun()

        st.markdown('<div class="xiga-footer">🔒 SECURE • XIGA AI • V5.4 • MULTI-PLATFORM ANALYSIS</div>', unsafe_allow_html=True)

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

Platform: **{item.get("provider", "BiQuote")}**

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
