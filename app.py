
import streamlit as st
import requests
import extra_streamlit_components as stx
import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

try:
    import plotly.graph_objects as go
except Exception:
    go = None

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
COOKIE_DAYS = 3650  # ~10 years; manual LOG OUT explicitly deletes the cookie.

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
        "portal": "XIGA APP",
        "admin_mode": False,
        "partner_mode": False,
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

EXCHANGE_ASSETS_FALLBACK = {
    "Binance": {"Bitcoin (BTC/USDT)":"BTCUSDT","Ethereum (ETH/USDT)":"ETHUSDT","Solana (SOL/USDT)":"SOLUSDT","BNB (BNB/USDT)":"BNBUSDT","XRP (XRP/USDT)":"XRPUSDT","Dogecoin (DOGE/USDT)":"DOGEUSDT","Cardano (ADA/USDT)":"ADAUSDT","Chainlink (LINK/USDT)":"LINKUSDT","Avalanche (AVAX/USDT)":"AVAXUSDT","Tron (TRX/USDT)":"TRXUSDT","Sui (SUI/USDT)":"SUIUSDT","Polkadot (DOT/USDT)":"DOTUSDT","Litecoin (LTC/USDT)":"LTCUSDT","Shiba Inu (SHIB/USDT)":"SHIBUSDT","Pepe (PEPE/USDT)":"PEPEUSDT"},
    "Bitget": {"Bitcoin (BTC/USDT)":"BTCUSDT","Ethereum (ETH/USDT)":"ETHUSDT","Solana (SOL/USDT)":"SOLUSDT","BNB (BNB/USDT)":"BNBUSDT","XRP (XRP/USDT)":"XRPUSDT","Dogecoin (DOGE/USDT)":"DOGEUSDT","Cardano (ADA/USDT)":"ADAUSDT","Chainlink (LINK/USDT)":"LINKUSDT","Avalanche (AVAX/USDT)":"AVAXUSDT","Sui (SUI/USDT)":"SUIUSDT","Polkadot (DOT/USDT)":"DOTUSDT","Litecoin (LTC/USDT)":"LTCUSDT","Shiba Inu (SHIB/USDT)":"SHIBUSDT","Pepe (PEPE/USDT)":"PEPEUSDT"},
    "OKX": {"Bitcoin (BTC/USDT)":"BTC-USDT","Ethereum (ETH/USDT)":"ETH-USDT","Solana (SOL/USDT)":"SOL-USDT","BNB (BNB/USDT)":"BNB-USDT","XRP (XRP/USDT)":"XRP-USDT","Dogecoin (DOGE/USDT)":"DOGE-USDT","Cardano (ADA/USDT)":"ADA-USDT","Chainlink (LINK/USDT)":"LINK-USDT","Avalanche (AVAX/USDT)":"AVAX-USDT","Sui (SUI/USDT)":"SUI-USDT","Polkadot (DOT/USDT)":"DOT-USDT","Litecoin (LTC/USDT)":"LTC-USDT","Shiba Inu (SHIB/USDT)":"SHIB-USDT","Pepe (PEPE/USDT)":"PEPE-USDT"},
}
EXCHANGE_ASSETS = {k: dict(v) for k,v in EXCHANGE_ASSETS_FALLBACK.items()}

EXCHANGE_PROVIDERS = ["BiQuote", "Binance", "Bitget", "OKX"]
BACKTEST_PROVIDERS = ["Binance", "Bitget", "OKX"]  # BiQuote remains live-only because its historical depth is not reliable enough for 5k/10k validation.

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

def call_xiga_function(action, key=None, extra=None):
    token = st.session_state.get("xiga_access_token")
    payload = {"action": action}
    if key is not None:
        payload["key"] = key
    if isinstance(extra, dict):
        payload.update(extra)
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

def _portal_tabs():
    portal = st.session_state.get("portal", "XIGA APP")
    selected = st.radio("Portal", ["XIGA APP", "REFERRAL"], index=0 if portal == "XIGA APP" else 1, horizontal=True, label_visibility="collapsed", key="portal_switch")
    if selected != portal:
        st.session_state.portal = selected
        st.session_state.admin_mode = False
        st.session_state.partner_mode = False
        st.rerun()
    return selected


def _contact_activation_box():
    st.markdown('''<div class="xiga-auth-card" style="text-align:center"><div style="font-size:13px;font-weight:900;color:#fff">Need your activation key?</div><div style="font-size:10px;color:#8ca1b7;margin-top:4px">Contact XIGA Admin to get your key.</div><div style="display:flex;justify-content:center;gap:10px;margin-top:10px"><a href="https://wa.me/923164451403" style="text-decoration:none;font-size:20px">🟢</a><a href="mailto:contactxigapro@gmail.com" style="text-decoration:none;font-size:20px">✉️</a><a href="https://www.facebook.com/xigapro" style="text-decoration:none;font-size:20px">🔵</a></div><div style="font-size:8px;color:#71899e;margin-top:7px">WhatsApp 03164451403 • contactxigapro@gmail.com • @xigapro</div></div>''', unsafe_allow_html=True)


def _partner_status():
    code, data = call_xiga_function("partner_status")
    return data if code == 200 else None


def _render_referral_partner_dashboard():
    data = _partner_status() or {}
    if not data.get("partner"):
        return False
    st.markdown('<div class="xiga-auth-topbar"><div></div><div class="xiga-auth-brand"><span>▰</span> XIGA</div><div class="xiga-auth-pro-wrap"><div class="xiga-auth-pro">REFERRAL</div></div></div>', unsafe_allow_html=True)
    st.markdown('<div class="xiga-auth-title">REFERRAL <span>PARTNER</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="xiga-auth-sub">Your referral account, earnings and referral history.</div>', unsafe_allow_html=True)
    code = data.get("referral_code", "—"); link = data.get("referral_link", "—")
    st.markdown(f'''<div class="xiga-auth-card"><div style="font-size:8px;color:#8ca1b7">YOUR REFERRAL CODE</div><div style="font-size:22px;font-weight:950;color:#20e7a0;margin-top:3px">{code}</div><div style="font-size:8px;color:#8ca1b7;margin-top:10px">YOUR REFERRAL LINK</div><div style="font-size:10px;color:#eaf6ff;word-break:break-all;margin-top:3px">{link}</div></div>''', unsafe_allow_html=True)
    st.markdown(f'''<div class="xiga-stat-grid"><div class="xiga-stat-box"><b>TOTAL REFERRALS</b><span>{int(data.get("total_referrals",0))}</span></div><div class="xiga-stat-box"><b>QUALIFIED</b><span class="green">{int(data.get("qualified",0))}</span></div><div class="xiga-stat-box"><b>PENDING</b><span>{int(data.get("pending",0))}</span></div><div class="xiga-stat-box"><b>EARNED</b><span>Rs. {int(data.get("earned",0)):,}</span></div><div class="xiga-stat-box"><b>PAID</b><span class="green">Rs. {int(data.get("paid",0)):,}</span></div><div class="xiga-stat-box"><b>UNPAID</b><span class="red">Rs. {int(data.get("unpaid",0)):,}</span></div></div>''', unsafe_allow_html=True)
    st.markdown('<div class="xiga-page-card"><div class="xiga-page-title" style="font-size:14px">Referral History</div></div>', unsafe_allow_html=True)
    history = data.get("history") or []
    if not history: st.caption("No referrals yet.")
    for item in history[:100]:
        status = str(item.get("status", "PENDING")).upper(); pay = str(item.get("payment_status", "UNPAID")).upper(); cls = "green" if status == "QUALIFIED" else ""
        st.markdown(f'''<div class="xiga-history-item"><div class="xiga-history-top"><span>{item.get("referred_email","—")}</span><span class="{cls}">{status}</span></div><div class="xiga-history-sub">Code: {item.get("referral_code",code)} • Reward: Rs. {int(item.get("reward",1000)):,}<br>Payment: {pay}</div></div>''', unsafe_allow_html=True)
    if st.button("LOG OUT", key="partner_logout", use_container_width=True): clear_session(); st.session_state.portal="REFERRAL"; st.rerun()
    return True


def _render_referral_portal():
    render_auth_styles(); _portal_tabs()
    if not SUPABASE_URL or not SUPABASE_PUBLISHABLE_KEY: st.error("XIGA account settings are missing."); st.stop()
    if ensure_session_from_cookie():
        if _render_referral_partner_dashboard(): return
        clear_session()
    st.markdown('<div class="xiga-auth-topbar"><div></div><div class="xiga-auth-brand"><span>▰</span> XIGA</div><div class="xiga-auth-pro-wrap"><div class="xiga-auth-pro">REFERRAL</div></div></div>', unsafe_allow_html=True)
    st.markdown('<div class="xiga-auth-title">REFERRAL <span>PARTNER</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="xiga-auth-sub">Create a referral account and earn Rs. 1,000 for each qualified referral.</div>', unsafe_allow_html=True)
    mode = st.radio("Referral access", ["LOGIN", "SIGN UP"], horizontal=True, label_visibility="collapsed", key="partner_access_mode")
    if mode == "LOGIN":
        with st.form("partner_login"):
            email=st.text_input("Email"); password=st.text_input("Password",type="password"); submit=st.form_submit_button("LOGIN")
        if submit:
            try:
                response=requests.post(f"{SUPABASE_URL}/auth/v1/token?grant_type=password",headers=auth_headers(),json={"email":email.strip(),"password":password},timeout=15)
                if response.status_code==200:
                    save_session(response.json())
                    call_xiga_function("partner_register")
                    st.session_state.portal="REFERRAL"; st.rerun()
                else: st.error("Invalid email or password, or the referral account is not confirmed.")
            except requests.RequestException: st.error("Unable to connect to XIGA account service.")
    else:
        with st.form("partner_signup"):
            full_name=st.text_input("Full name"); email=st.text_input("Email"); password=st.text_input("Password",type="password"); confirm=st.text_input("Confirm password",type="password"); payment_method=st.selectbox("Payment method",["EasyPaisa","JazzCash"]); payment_account=st.text_input("Payment account / number"); submit=st.form_submit_button("CREATE REFERRAL ACCOUNT")
        if submit:
            if not full_name.strip() or not email.strip() or len(password)<6 or password!=confirm or not payment_account.strip(): st.error("Complete all fields and use a matching password of at least 6 characters.")
            else:
                try:
                    response=requests.post(f"{SUPABASE_URL}/auth/v1/signup",headers=auth_headers(),json={"email":email.strip(),"password":password,"data":{"full_name":full_name.strip(),"portal":"REFERRAL","payment_method":payment_method,"payment_account":payment_account.strip()}},timeout=15)
                    if response.status_code in (200,201):
                        data=response.json()
                        if data.get("access_token"):
                            save_session(data)
                            call_xiga_function("partner_register", extra={"full_name":full_name.strip(),"payment_method":payment_method,"payment_account":payment_account.strip()})
                            st.session_state.portal="REFERRAL"; st.rerun()
                        st.success("Referral account created. Confirm your email, then log in.")
                    else:
                        try: msg=response.json().get("msg") or response.json().get("message")
                        except Exception: msg=None
                        st.error(msg or "Unable to create the referral account.")
                except requests.RequestException: st.error("Unable to connect to XIGA account service.")
    st.stop()


def _admin_status():
    code,data=call_xiga_function("admin_status")
    return data if code==200 else {}


def _admin_action(action, **kwargs):
    return call_xiga_function(action, extra=kwargs)


def admin_panel():
    render_auth_styles(); status=_admin_status()
    if not status.get("admin"): return False
    st.markdown('<div class="xiga-auth-topbar"><div></div><div class="xiga-auth-brand"><span>▰</span> XIGA</div><div class="xiga-auth-pro-wrap"><div class="xiga-auth-pro">ADMIN</div></div></div>', unsafe_allow_html=True)
    st.markdown('<div class="xiga-auth-title">XIGA <span>ADMIN</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="xiga-auth-sub">Administrative controls. Passwords are never displayed.</div>', unsafe_allow_html=True)
    section=st.radio("Admin sections",["Overview","Users","Generate Keys","Referrals","Partners","Subscriptions","Payments"],horizontal=True,label_visibility="collapsed",key="admin_section")
    overview=status.get("overview") or {}
    st.markdown(f'''<div class="xiga-stat-grid"><div class="xiga-stat-box"><b>USERS</b><span>{int(overview.get("users",0))}</span></div><div class="xiga-stat-box"><b>TOTAL REFERRALS</b><span>{int(overview.get("referrals",0))}</span></div><div class="xiga-stat-box"><b>QUALIFIED</b><span class="green">{int(overview.get("qualified",0))}</span></div><div class="xiga-stat-box"><b>PENDING</b><span>{int(overview.get("pending",0))}</span></div><div class="xiga-stat-box"><b>UNPAID REWARDS</b><span class="red">Rs. {int(overview.get("unpaid_rewards",0)):,}</span></div></div>''', unsafe_allow_html=True)
    if section=="Overview": st.caption("Use the sections above to manage accounts, keys, referrals and payments.")
    elif section=="Users":
        for u in status.get("users") or []:
            uid=u.get("id"); email=u.get("email","—")
            st.markdown(f'''<div class="xiga-history-item"><div class="xiga-history-top"><span>{email}</span><span>{"ACTIVE" if u.get("active") else "INACTIVE"}</span></div><div class="xiga-history-sub">Subscription: {u.get("subscription_expires_at") or "—"}<br>Key: {u.get("key_status","—")} • Referrals: {u.get("referral_count",0)}</div></div>''',unsafe_allow_html=True)
            c1,c2,c3,c4=st.columns(4)
            with c1:
                if st.button("BLOCK/UNBLOCK",key=f"block_{uid}"): _admin_action("admin_toggle_block",user_id=uid); st.rerun()
            with c2:
                if st.button("RESET PASSWORD",key=f"reset_{uid}"):
                    code,data=_admin_action("admin_send_password_reset",email=email); st.success(data.get("message","Password reset email requested.")) if code==200 else st.error(data.get("error","Reset failed."))
            with c3:
                if st.button("REMOVE",key=f"remove_{uid}"): _admin_action("admin_remove_user",user_id=uid); st.rerun()
            with c4:
                gift=st.selectbox("GIFT",["1 month","2 months","3 months","4 months","5 months","6 months","1 year"],key=f"gift_{uid}")
                if st.button("GIFT TIME",key=f"gift_btn_{uid}"):
                    code,data=_admin_action("admin_gift_subscription",user_id=uid,duration=gift); st.success(data.get("message","Subscription extended.")) if code==200 else st.error(data.get("error","Gift failed."))
    elif section=="Generate Keys":
        users=status.get("waiting_for_key") or []
        if not users: st.info("No users are currently waiting for an activation key.")
        for u in users:
            uid=u.get("id"); email=u.get("email","—")
            st.markdown(f'''<div class="xiga-history-item"><div class="xiga-history-top"><span>{email}</span><span>{u.get("key_status","WAITING")}</span></div><div class="xiga-history-sub">Signed up: {u.get("created_at","—")} • Existing key: {u.get("has_key",False)}</div></div>''',unsafe_allow_html=True)
            duration=st.selectbox("Subscription duration",["1 day","1 month","6 months","1 year","1.5 years","2 years"],key=f"key_duration_{uid}")
            if st.button("GENERATE KEY",key=f"gen_key_{uid}"):
                code,data=_admin_action("admin_generate_key",user_id=uid,duration=duration)
                if code==200: st.success(data.get("message","Key generated and sent to admin email.")); st.rerun()
                else: st.error(data.get("error","Unable to generate key."))
    elif section=="Referrals":
        for r in status.get("referrals") or []:
            pay=str(r.get("payment_status","UNPAID")).upper()
            st.markdown(f'''<div class="xiga-history-item"><div class="xiga-history-top"><span>{r.get("referrer_email","—")}</span><span>{str(r.get("status","PENDING")).upper()}</span></div><div class="xiga-history-sub">Code: {r.get("referral_code","—")} • Referred: {r.get("referred_email","—")}<br>Reward: Rs. {int(r.get("reward",1000)):,} • Payment: {pay}</div></div>''',unsafe_allow_html=True)
            if pay!="PAID" and st.button("MARK AS PAID",key=f"paid_{r.get('id')}"):
                code,data=_admin_action("admin_mark_referral_paid",referral_id=r.get("id")); st.success(data.get("message","Marked as paid.")) if code==200 else st.error(data.get("error","Payment update failed."))
    elif section=="Partners":
        for p in status.get("partners") or []:
            st.markdown(f'''<div class="xiga-history-item"><div class="xiga-history-top"><span>{p.get("full_name","—")}</span><span>{p.get("referral_code","—")}</span></div><div class="xiga-history-sub">{p.get("email","—")} • {p.get("payment_method","—")} • {p.get("payment_account","—")}<br>Referrals: {p.get("total_referrals",0)} • Qualified: {p.get("qualified",0)} • Unpaid: Rs. {int(p.get("unpaid",0)):,}</div></div>''',unsafe_allow_html=True)
    elif section=="Subscriptions":
        for u in status.get("subscriptions") or []: st.write(f'{u.get("email","—")} • {u.get("subscription_expires_at","—")}')
    elif section=="Payments":
        for p in status.get("payments") or []: st.write(p)
    if st.button("ADMIN LOG OUT",key="admin_logout",use_container_width=True): clear_session(); st.rerun()
    st.stop()


def xiga_subscription_login():
    render_auth_styles()
    if not SUPABASE_URL or not SUPABASE_PUBLISHABLE_KEY: st.error("XIGA PRO subscription settings are missing."); st.stop()
    if st.session_state.get("portal","XIGA APP")=="REFERRAL": _render_referral_portal(); st.stop()
    if ensure_session_from_cookie():
        admin=_admin_status()
        if admin.get("admin"): st.session_state.admin_mode=True; admin_panel()
        status=get_subscription_status()
        if status is None: st.error("Unable to verify your XIGA PRO subscription right now."); st.stop()
        st.session_state["xiga_email"]=st.session_state.get("xiga_email") or status.get("email","")
        if status.get("active"): st.session_state["xiga_subscription_active"]=True; return True
        st.session_state["xiga_subscription_active"]=False
        st.markdown("## XIGA PRO SUBSCRIPTION"); st.warning("Your XIGA PRO subscription is not active.")
        expires=status.get("subscription_expires_at")
        if expires: st.info(f"Previous subscription expiry: {expires}")
        _contact_activation_box()
        with st.form("xiga_activate_key"):
            activation_key=st.text_input("ACTIVATION KEY",placeholder="Enter the key provided to your account"); activate=st.form_submit_button("ACTIVATE KEY")
        if activate:
            if not activation_key.strip(): st.error("Please enter your activation key."); st.stop()
            code,data=call_xiga_function("activate",activation_key.strip())
            if code==200: st.success("Subscription activated. Opening XIGA PRO..."); st.rerun()
            else: st.error(data.get("error","Activation failed."))
        if st.button("LOG OUT",key="expired_logout",use_container_width=True): clear_session(); st.rerun()
        st.stop()
    st.markdown('<div class="xiga-auth-topbar"><div></div><div class="xiga-auth-brand"><span>▰</span> XIGA</div><div class="xiga-auth-pro-wrap"><div class="xiga-auth-pro">👑 PRO</div></div></div>',unsafe_allow_html=True)
    _portal_tabs()
    st.markdown('<div class="xiga-auth-title">XIGA <span>PRO</span><br>SECURE ACCESS</div>',unsafe_allow_html=True)
    st.markdown('<div class="xiga-auth-sub">Use your XIGA account to access the XIGA PRO trading app.</div>',unsafe_allow_html=True)
    mode=st.radio("Access",["LOGIN","SIGN UP"],horizontal=True,label_visibility="collapsed",key="access_mode")
    if mode=="LOGIN":
        with st.form("xiga_pro_login"):
            email=st.text_input("Email"); password=st.text_input("Password",type="password"); login=st.form_submit_button("LOGIN")
        if login:
            if not email or not password: st.error("Please enter your email and password."); st.stop()
            try:
                response=requests.post(f"{SUPABASE_URL}/auth/v1/token?grant_type=password",headers=auth_headers(),json={"email":email.strip(),"password":password},timeout=15)
                if response.status_code!=200: st.error("Invalid email or password. If you just signed up, confirm your email first."); st.stop()
                save_session(response.json()); st.session_state.portal="XIGA APP"; st.rerun()
            except requests.RequestException: st.error("Unable to connect to XIGA account service."); st.stop()
    else:
        with st.form("xiga_pro_signup"):
            full_name=st.text_input("Full name"); email=st.text_input("Email"); password=st.text_input("Password",type="password"); confirm=st.text_input("Confirm password",type="password")
            try:
                link_ref = str(st.query_params.get("ref", "")).strip()
            except Exception:
                link_ref = ""
            referral_code=st.text_input("Referral code (optional)", value=link_ref)
            signup=st.form_submit_button("CREATE ACCOUNT")
        if signup:
            if not email or not password: st.error("Email and password are required."); st.stop()
            if len(password)<6: st.error("Password must be at least 6 characters."); st.stop()
            if password!=confirm: st.error("Passwords do not match."); st.stop()
            try:
                response=requests.post(f"{SUPABASE_URL}/auth/v1/signup",headers=auth_headers(),json={"email":email.strip(),"password":password,"data":{"full_name":full_name.strip()}},timeout=15)
                if response.status_code in (200,201):
                    data=response.json()
                    if data.get("access_token"):
                        save_session(data)
                        if referral_code.strip(): call_xiga_function("attach_referral",extra={"referral_code":referral_code.strip()})
                        st.rerun()
                    st.success("Account created. Please check your email, confirm your account, then log in.")
                else:
                    try: message=response.json().get("msg") or response.json().get("error_description") or response.json().get("message")
                    except ValueError: message=None
                    st.error(message or "Unable to create the account.")
            except requests.RequestException: st.error("Unable to connect to XIGA account service.")
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

@st.cache_data(ttl=900, show_spinner=False)
def get_spot_exchange_assets(provider):
    fallback = EXCHANGE_ASSETS_FALLBACK.get(provider, {})
    try:
        pairs = {}
        if provider == "Binance":
            r = requests.get(f"{BINANCE_BASE}/api/v3/exchangeInfo", timeout=20)
            if r.status_code != 200: return fallback, f"BINANCE SPOT CATALOG ERROR {r.status_code}"
            for x in r.json().get("symbols", []):
                if x.get("status") == "TRADING" and x.get("quoteAsset") == "USDT" and x.get("isSpotTradingAllowed", True):
                    base, sym = str(x.get("baseAsset") or ""), str(x.get("symbol") or "")
                    if base and sym: pairs[f"{base} (USDT)"] = sym
        elif provider == "Bitget":
            r = requests.get(f"{BITGET_BASE}/api/v3/market/instruments", params={"category":"SPOT"}, timeout=20)
            if r.status_code != 200: return fallback, f"BITGET SPOT CATALOG ERROR {r.status_code}"
            for x in r.json().get("data", []):
                if str(x.get("status","")).lower() == "online" and str(x.get("quoteCoin","")).upper() == "USDT":
                    base, sym = str(x.get("baseCoin") or ""), str(x.get("symbol") or "")
                    if base and sym: pairs[f"{base} (USDT)"] = sym
        elif provider == "OKX":
            r = requests.get(f"{OKX_BASE}/api/v5/public/instruments", params={"instType":"SPOT"}, timeout=20)
            if r.status_code != 200: return fallback, f"OKX SPOT CATALOG ERROR {r.status_code}"
            raw = r.json()
            if str(raw.get("code","0")) != "0": return fallback, f"OKX SPOT CATALOG ERROR {raw.get('msg','UNKNOWN')}"
            for x in raw.get("data", []):
                if str(x.get("state","")).lower() == "live" and str(x.get("quoteCcy","")).upper() == "USDT":
                    base, sym = str(x.get("baseCcy") or ""), str(x.get("instId") or "")
                    if base and sym: pairs[f"{base} (USDT)"] = sym
        if not pairs: return fallback, f"{provider.upper()} SPOT CATALOG EMPTY • USING FALLBACK"
        pairs = dict(sorted(pairs.items(), key=lambda kv: kv[0].lower()))
        return pairs, f"{provider.upper()} SPOT • {len(pairs)} USDT PAIRS"
    except requests.exceptions.Timeout:
        return fallback, f"{provider.upper()} SPOT CATALOG TIMEOUT • USING FALLBACK"
    except requests.exceptions.RequestException:
        return fallback, f"{provider.upper()} SPOT CATALOG NETWORK ERROR • USING FALLBACK"
    except Exception as exc:
        return fallback, f"{provider.upper()} SPOT CATALOG ERROR • USING FALLBACK: {exc}"

def _parse_exchange_candles(provider, raw, resolution):
    candles=[]
    try:
        if provider == "Binance":
            rows = raw
            for row in reversed(rows):
                candles.append({"open":float(row[1]),"high":float(row[2]),"low":float(row[3]),"close":float(row[4]),"volume":float(row[5]),"datetime":datetime.fromtimestamp(row[0]/1000, tz=timezone.utc).isoformat(),"is_open":datetime.now(timezone.utc).timestamp()*1000 < row[6]})
        elif provider == "Bitget":
            rows = raw.get("data", [])
            for row in reversed(rows):
                candles.append({"open":float(row[1]),"high":float(row[2]),"low":float(row[3]),"close":float(row[4]),"volume":float(row[5]) if len(row)>5 else 0.0,"datetime":datetime.fromtimestamp(int(row[0])/1000, tz=timezone.utc).isoformat(),"is_open":False})
        elif provider == "OKX":
            rows = raw.get("data", [])
            for row in reversed(rows):
                candles.append({"open":float(row[1]),"high":float(row[2]),"low":float(row[3]),"close":float(row[4]),"volume":float(row[5]) if len(row)>5 else 0.0,"datetime":datetime.fromtimestamp(int(row[0])/1000, tz=timezone.utc).isoformat(),"is_open":str(row[8]) != "1" if len(row)>8 else False})
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
                    candles.append({"open":float(bar["open"]),"high":float(bar["high"]),"low":float(bar["low"]),"close":float(bar["close"]),"volume":float(bar.get("volume",0) or 0),"datetime":str(bar["openTime"]),"is_open":bool(bar.get("isOpen",False))})
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
            return {"price":float(data[0].get("lastPrice") or data[0].get("lastPr") or data[0].get("last") or data[0].get("bidPr"))},"BITGET LIVE PRICE CONNECTED"
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
        # STOP LOSS is display-only. It never determines WIN/LOSS.
        if tp_hit:
            _finish_live_trade(
                pending, "WIN", live_price,
                f"TAKE PROFIT HIT at {elapsed_seconds // 60}m {elapsed_seconds % 60}s. TP {target:.8g} reached at {live_price:.8g}.",
                elapsed_seconds,
            )
            return

    # TP is the only early WIN trigger. If TP was not reached by expiry,
    # resolve from the final price versus the original entry price.
    # STOP LOSS is display-only and never determines WIN/LOSS.
    if now >= (parse_candle_time(pending.get("complete_at")) or now):
        result_price = float(tick["price"]) if tick else float(pending["entry_price"])
        entry_price = float(pending["entry_price"])
        outcome = calculate_outcome(pending["signal"], entry_price, result_price)

        _finish_live_trade(
            pending,
            outcome,
            result_price,
            f"Trade expired. Entry: {entry_price:.8g}. Final price: {result_price:.8g}. TP was not reached.",
            elapsed_seconds,
        )


ASSETS, catalog_status = get_symbol_catalog()

# ==============================
# XIGA PRO MOBILE UI — FINAL
# ==============================

ANALYSIS_SECONDS = 4


def perform_pending_analysis():
    # Complete the short analysis countdown and immediately create the live trade.
    pending = st.session_state.get("analysis_pending")
    if not pending or seconds_until(pending.get("complete_at")) > 0:
        return
    provider = pending["provider"]
    symbol = pending["symbol"]
    timeframe = pending["timeframe"]
    try:
        analysis = analyze_market(provider, symbol, timeframe)
    except Exception as exc:
        analysis = {"success": False, "signal": "NO TRADE", "strength": 0, "probability": None, "status": "ANALYSIS ERROR", "description": "XIGA could not complete this analysis. Please try again.", "error": str(exc)}
    st.session_state.analysis_pending = None
    st.session_state.result = analysis
    if not analysis.get("success"):
        return
    signal = analysis.get("signal")
    if signal not in ("CALL", "PUT"):
        return
    tick, tick_status = get_latest_tick(provider, symbol, fresh=True)
    entry_price = float(tick["price"]) if tick else float(analysis.get("price") or 0)
    entry, take_profit, stop_loss = calculate_trade_levels(signal, entry_price, analysis.get("atr"), analysis.get("support"), analysis.get("resistance"), timeframe, analysis.get("tp_profile"))
    if not entry or take_profit is None or stop_loss is None:
        st.session_state.result.update({"success": False, "signal": "NO TRADE", "status": "NO TRADE", "description": "XIGA could not calculate safe trade levels from the current market data."})
        return
    duration_seconds = 60 if timeframe == "1 MIN" else 300
    now = datetime.now(timezone.utc)
    trade_id = pending["id"]
    st.session_state.result.update({"entry_price": entry, "take_profit": take_profit, "stop_loss": stop_loss, "status": "TRADE ACTIVE", "entry_status": tick_status, "description": analysis.get("description", "Signal generated from the current market conditions.")})
    st.session_state.trade_pending = {"id": trade_id, "asset": pending["asset"], "symbol": symbol, "provider": provider, "timeframe": timeframe, "signal": signal, "probability": int(analysis.get("probability") or 50), "entry_price": entry, "take_profit": take_profit, "stop_loss": stop_loss, "started_at": now.isoformat(), "complete_at": (now + timedelta(seconds=duration_seconds)).isoformat(), "state": "TRADE ACTIVE", "live_price": entry}
    st.session_state.history.insert(0, {"id": trade_id, "asset": pending["asset"], "symbol": symbol, "provider": provider, "signal": signal, "strength": analysis.get("strength", 0), "probability": analysis.get("probability", 50), "price": entry, "take_profit": take_profit, "stop_loss": stop_loss, "timeframe": timeframe, "time": now.astimezone(ZoneInfo("Asia/Karachi")).strftime("%Y-%m-%d %H:%M:%S PKT"), "status": "PENDING", "result_price": "—", "analysis_description": analysis.get("description", ""), "entry_status": tick_status})
    st.session_state.signals = len(st.session_state.history)


def render_candlestick_chart(provider, symbol, resolution, timeframe, active_trade=None):
    candles, status = get_candles(provider, symbol, resolution, fresh=False)
    if not candles:
        st.markdown(f'<div class="xiga-chart-empty">LIVE CANDLES UNAVAILABLE<br><span>{status}</span></div>', unsafe_allow_html=True)
        return
    rows = candles[-45:]
    if go is None:
        st.markdown('<div class="xiga-chart-empty">Candlestick chart requires Plotly.</div>', unsafe_allow_html=True)
        return
    times = [parse_candle_time(c.get("datetime")) for c in rows]
    opens = [float(c["open"]) for c in rows]
    highs = [float(c["high"]) for c in rows]
    lows = [float(c["low"]) for c in rows]
    closes = [float(c["close"]) for c in rows]
    volumes = [float(c.get("volume", 0) or 0) for c in rows]
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=times, open=opens, high=highs, low=lows, close=closes, increasing_line_color="#20e7a0", increasing_fillcolor="#20e7a0", decreasing_line_color="#ff4d5d", decreasing_fillcolor="#ff4d5d", name="Price"))
    if any(volumes):
        fig.add_trace(go.Bar(x=times, y=volumes, name="Volume", marker_color=["#20e7a0" if c >= o else "#ff4d5d" for c, o in zip(closes, opens)], opacity=0.25, yaxis="y2"))
    latest_price = closes[-1]
    if active_trade:
        for value, color, label in ((active_trade.get("entry_price"), "#8ca6bd", "ENTRY"), (active_trade.get("take_profit"), "#20e7a0", "TP"), (active_trade.get("stop_loss"), "#ff4d5d", "SL")):
            if value is not None:
                fig.add_hline(y=float(value), line_dash="dot", line_color=color, annotation_text=label, annotation_position="top left")
    fig.add_hline(y=latest_price, line_dash="dot", line_color="#2da8ff", opacity=0.75)
    fig.update_layout(height=300, margin=dict(l=8, r=8, t=32, b=8), paper_bgcolor="#041322", plot_bgcolor="#041322", font=dict(color="#a9bdd0", size=10), showlegend=False, xaxis=dict(showgrid=True, gridcolor="rgba(40,93,128,.20)", rangeslider_visible=False), yaxis=dict(showgrid=True, gridcolor="rgba(40,93,128,.20)", side="right", fixedrange=True), yaxis2=dict(overlaying="y", side="left", showgrid=False, showticklabels=False), hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})
    st.markdown(f'<div class="xiga-chart-meta">{symbol} • {timeframe} • {provider} • {status} • LIVE CANDLES</div>', unsafe_allow_html=True)


def signal_display(signal):
    return "BUY" if signal == "CALL" else "SELL" if signal == "PUT" else "NO TRADE"


def signal_color_class(signal):
    return "buy" if signal == "CALL" else "sell" if signal == "PUT" else "neutral"


st.markdown('''
<style>
html,body,[data-testid="stAppViewContainer"]{background:#020a12 !important;color:#eaf6ff !important}
[data-testid="stHeader"]{display:none !important;height:0 !important}[data-testid="stToolbar"]{display:none !important}
[data-testid="stMainBlockContainer"]{max-width:920px !important;padding-top:0 !important;padding-left:8px !important;padding-right:8px !important}.block-container{padding-top:0 !important;padding-bottom:86px !important}
footer,#MainMenu{display:none !important}section[data-testid="stSidebar"]{display:none !important}.xiga-app{max-width:900px;margin:0 auto}
.xiga-header{display:flex;align-items:center;justify-content:space-between;padding:2px 2px 8px;border-bottom:1px solid rgba(33,102,143,.25)}.xiga-logo{font-size:24px;font-weight:950;letter-spacing:1px;color:#fff;line-height:1}.xiga-logo b{color:#1d9dff}.xiga-tag{font-size:7px;letter-spacing:2px;color:#71899e;margin-top:3px}.xiga-live-box{text-align:right}.xiga-live-dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#20e7a0;box-shadow:0 0 12px #20e7a0;margin-right:5px}.xiga-live-text{color:#20e7a0;font-weight:900;font-size:11px}.xiga-live-sub{display:block;color:#91a6b9;font-size:8px;margin-top:2px}.xiga-pro{display:inline-block;margin-left:7px;padding:6px 8px;border:1px solid #a98026;border-radius:9px;color:#ffd66d;background:#171207;font-size:8px;font-weight:900}
.xiga-selector-card{margin-top:8px;background:linear-gradient(145deg,#061a2b,#04111d);border:1px solid #075d8e;border-radius:15px;padding:9px;box-shadow:0 10px 25px rgba(0,0,0,.22)}.xiga-selector-card [data-testid="stSelectbox"] label{color:#89a0b5 !important;font-size:8px !important;letter-spacing:1.2px !important;text-transform:uppercase !important}.xiga-selector-card [data-baseweb="select"]>div{background:#071827 !important;border:1px solid #125b86 !important;border-radius:11px !important;min-height:43px !important;color:#edf7ff !important}.xiga-selector-card [data-baseweb="select"] *{color:#edf7ff !important}.xiga-market-ready{font-size:8px;color:#20e7a0;margin-top:7px;letter-spacing:.4px}
.xiga-card,.xiga-page-card{background:linear-gradient(145deg,#061b2d,#03101b);border:1px solid #075887;border-radius:18px;padding:12px;margin-top:10px;box-shadow:0 14px 34px rgba(0,0,0,.25),inset 0 1px rgba(255,255,255,.025)}.xiga-page-title{font-size:19px;font-weight:950;color:#fff}.xiga-page-sub{font-size:9px;color:#8399ad;line-height:1.5;margin-top:4px}
.xiga-signal-card{padding:13px;border-radius:18px;border:1px solid #0871a7;background:radial-gradient(circle at 50% 0%,#073148 0%,#03131f 55%,#020d16 100%);margin-top:10px}.xiga-signal-card.buy{border-color:#0bd99a;box-shadow:0 0 22px rgba(20,231,160,.10)}.xiga-signal-card.sell{border-color:#ff4052;box-shadow:0 0 22px rgba(255,64,82,.08)}
.xiga-signal-head{display:flex;justify-content:space-between;align-items:center;color:#8ba3b7;font-size:8px;letter-spacing:1.3px}.xiga-badge{padding:6px 9px;border-radius:9px;font-size:8px;font-weight:900}.xiga-badge.live,.xiga-badge.win{color:#03140d;background:#20e7a0}.xiga-badge.loss{color:#fff;background:#ff4052}.xiga-badge.expired{color:#09131b;background:#a8b7c5}
.xiga-signal-main{display:grid;grid-template-columns:1.25fr .75fr;gap:10px;align-items:center;margin:9px 0}.xiga-direction{font-size:50px;font-weight:1000;line-height:.95;letter-spacing:-2px}.buy-text{color:#20e7a0;text-shadow:0 0 18px rgba(32,231,160,.25)}.sell-text{color:#ff4052;text-shadow:0 0 18px rgba(255,64,82,.20)}.neutral-text{color:#9bb0c1}.xiga-confidence-label{font-size:8px;color:#8da2b6;letter-spacing:1px;text-align:right}.xiga-confidence-value{font-size:31px;font-weight:950;color:#f3f9ff;text-align:right;margin:2px 0}.xiga-bar{height:6px;background:#0b3046;border-radius:8px;overflow:hidden}.xiga-bar span{display:block;height:100%;background:#20e7a0;border-radius:8px}
.xiga-levels{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:8px}.xiga-level{border:1px solid #0a5d88;border-radius:12px;background:#041726;padding:9px 6px;text-align:center}.xiga-level-label{font-size:7px;color:#8ca0b2;letter-spacing:.7px}.xiga-level-value{font-size:14px;font-weight:900;margin-top:4px}.xiga-level-value.entry{color:#eef8ff}.xiga-level-value.tp{color:#20e7a0}.xiga-level-value.sl{color:#ff4052}
.xiga-live-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}.xiga-mini{border:1px solid #0a547d;border-radius:13px;background:#041523;padding:10px}.xiga-mini-label{font-size:7px;color:#8399ad;letter-spacing:1px}.xiga-mini-value{font-size:20px;font-weight:950;color:#eef8ff;margin-top:3px}.xiga-mini-sub{font-size:8px;color:#20e7a0;margin-top:3px}
.xiga-chart-card{margin-top:10px;border:1px solid #0a5b87;border-radius:17px;background:#041421;overflow:hidden;padding:6px 6px 4px}.xiga-chart-title{font-size:10px;font-weight:900;color:#dbeaf5;padding:5px 6px 1px}.xiga-chart-meta{font-size:7px;color:#6f8ca2;text-align:center;letter-spacing:.4px;margin-top:-3px}.xiga-chart-empty{border:1px solid #16435e;border-radius:14px;padding:35px 10px;text-align:center;color:#8098ac;font-size:10px}.xiga-chart-empty span{font-size:8px}
.xiga-why{display:flex;gap:10px;align-items:center}.xiga-why-icon{width:35px;height:35px;border-radius:11px;background:#13280d;border:1px solid #657d20;display:flex;align-items:center;justify-content:center;font-size:18px}.xiga-why-title{color:#f0f8ff;font-weight:900;font-size:12px}.xiga-why-text{color:#8da2b5;font-size:9px;line-height:1.45;margin-top:3px}.xiga-tech-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:10px}.xiga-tech{border:1px solid #104e70;border-radius:10px;background:#051827;padding:7px 4px;text-align:center}.xiga-tech b{display:block;color:#7790a5;font-size:7px}.xiga-tech span{display:block;color:#e9f6ff;font-size:11px;font-weight:900;margin-top:3px}
.xiga-status-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}.xiga-status-item{border:1px solid #0d5377;border-radius:12px;background:#041624;padding:9px;text-align:center}.xiga-status-label{font-size:7px;color:#8299ad;letter-spacing:.8px}.xiga-status-value{font-size:11px;font-weight:900;color:#edf8ff;margin-top:4px}.green{color:#20e7a0 !important}.red{color:#ff4052 !important}
.stButton>button{min-height:50px !important;border-radius:15px !important;border:1px solid #5af7c1 !important;background:linear-gradient(100deg,#11cf8b,#2ff1ad) !important;color:#02130c !important;font-weight:950 !important;font-size:14px !important;box-shadow:0 0 22px rgba(32,231,160,.17) !important}.stButton>button:disabled{background:#0b3550 !important;color:#7391a5 !important;border-color:#1d5d80 !important;box-shadow:none !important}
.xiga-analyze-wrap{margin-top:10px}.xiga-analyze-sub{text-align:center;color:#688298;font-size:8px;margin-top:5px}.xiga-topnav{margin:7px 0 8px}.xiga-topnav .stRadio{margin:0 !important}.xiga-topnav div[role="radiogroup"]{display:grid !important;grid-template-columns:repeat(4,1fr) !important;gap:0 !important;width:100% !important;margin:0 !important}.xiga-topnav div[role="radiogroup"] label{position:relative !important;display:flex !important;align-items:center !important;justify-content:center !important;min-height:32px !important;padding:0 3px !important;margin:0 !important;color:#71889b !important;font-size:8px !important;font-weight:950 !important;letter-spacing:.5px !important;white-space:nowrap !important;cursor:pointer !important;background:transparent !important;border:0 !important;box-shadow:none !important}.xiga-topnav div[role="radiogroup"] label:hover{color:#20e7a0 !important}.xiga-topnav div[role="radiogroup"] label:has(input:checked){color:#20e7a0 !important}.xiga-topnav div[role="radiogroup"] label:has(input:checked)::after{content:"" !important;position:absolute !important;left:24% !important;right:24% !important;bottom:0 !important;height:2px !important;border-radius:4px !important;background:#20e7a0 !important;box-shadow:0 0 8px rgba(32,231,160,.55) !important}.xiga-topnav div[role="radiogroup"] label > div:first-child{display:none !important}.xiga-topnav div[role="radiogroup"] label p{font-size:8px !important;font-weight:950 !important;letter-spacing:.5px !important;margin:0 !important}.xiga-topnav [data-testid="stRadio"]{padding:0 !important}.xiga-signal-circle{width:112px;height:112px;border-radius:50%;margin:12px auto 10px;display:flex;align-items:center;justify-content:center;border:3px solid currentColor;background:rgba(3,18,28,.94);box-shadow:0 0 28px currentColor}.xiga-signal-circle.buy{color:#20e7a0}.xiga-signal-circle.sell{color:#ff4052}.xiga-signal-circle.neutral{color:#9bb0c1}.xiga-signal-circle-inner{text-align:center}.xiga-signal-circle-icon{font-size:34px;font-weight:950;line-height:1}.xiga-signal-circle-text{font-size:12px;font-weight:950;letter-spacing:1px;margin-top:4px}
.xiga-backtest-grid,.xiga-stat-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:7px;margin-top:10px}.xiga-stat-box{border:1px solid #0d5275;border-radius:12px;background:#041624;padding:10px;text-align:center}.xiga-stat-box b{display:block;font-size:7px;color:#8198aa}.xiga-stat-box span{display:block;font-size:17px;font-weight:950;color:#edf8ff;margin-top:4px}.xiga-history-item{border:1px solid #0d4e70;border-radius:13px;background:#041521;padding:10px;margin-top:7px}.xiga-history-top{display:flex;justify-content:space-between;font-size:11px;font-weight:900}.xiga-history-sub{font-size:8px;color:#8197aa;line-height:1.6;margin-top:4px}.xiga-history-result{margin-top:5px;font-size:8px;font-weight:900}.xiga-account-card{border:1px solid #0d5a80;border-radius:15px;background:#041624;padding:12px}.xiga-account-label{font-size:7px;color:#7e96aa;letter-spacing:1px}.xiga-account-value{font-size:13px;color:#f0f8ff;font-weight:900;margin-top:4px;word-break:break-all}.xiga-profile-levels{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:10px}.xiga-profile-level{border:1px solid #0b4e70;border-radius:10px;padding:8px 4px;text-align:center}.xiga-profile-level b{display:block;color:#7891a4;font-size:7px}.xiga-profile-level span{display:block;color:#20e7a0;font-size:11px;font-weight:900;margin-top:4px}.xiga-footer{text-align:center;color:#4d687c;font-size:7px;letter-spacing:1px;margin:12px 0 4px}.xiga-muted{color:#8198aa;font-size:9px;line-height:1.5}.xiga-note{color:#7891a5;font-size:8px;line-height:1.5;margin-top:8px}
@media(max-width:600px){[data-testid="stMainBlockContainer"]{padding-left:6px !important;padding-right:6px !important}.xiga-logo{font-size:21px}.xiga-direction{font-size:44px}.xiga-tech-grid{grid-template-columns:repeat(2,1fr)}.xiga-levels{gap:5px}.xiga-level-value{font-size:12px}.xiga-status-grid{grid-template-columns:repeat(3,1fr)}}
@media(max-width:390px){.xiga-direction{font-size:38px}.xiga-confidence-value{font-size:27px}.xiga-level-label{font-size:6px}.xiga-level-value{font-size:10px}.xiga-logo{font-size:19px}}
</style>
''', unsafe_allow_html=True)


st.markdown("""<style>
/* Compact same-tab navigation: text tabs, not large button boxes. */
.xiga-topnav{display:grid;grid-template-columns:repeat(4,1fr);gap:0;margin:2px 0 10px;border-bottom:1px solid #10334a}
.xiga-topnav .stButton{margin:0!important}
.xiga-topnav .stButton>button{background:transparent!important;border:0!important;box-shadow:none!important;border-radius:0!important;height:34px!important;min-height:34px!important;padding:0 2px!important;color:#7891a5!important;font-size:9px!important;font-weight:900!important;letter-spacing:.6px!important}
.xiga-topnav .stButton>button:hover{background:transparent!important;color:#dfffee!important;border:0!important;box-shadow:none!important}
.xiga-topnav .stButton>button:focus{outline:none!important;box-shadow:none!important}
.xiga-topnav .stButton>button[kind="primary"]{color:#29f5a6!important}
@media(max-width:390px){.xiga-topnav .stButton>button{font-size:8px!important;letter-spacing:.3px!important}}

</style>
""", unsafe_allow_html=True)

def render_app_header(active_page):
    provider = st.session_state.get("provider", "Binance")
    if provider not in EXCHANGE_PROVIDERS:
        provider = "Binance"

    st.markdown(f'''<div class="xiga-header"><div><div class="xiga-logo"><b>XI</b>GA PRO</div><div class="xiga-tag">TRADE SMARTER</div></div><div class="xiga-live-box"><span class="xiga-live-dot"></span><span class="xiga-live-text">LIVE MARKET</span><span class="xiga-live-sub">{provider} • PUBLIC DATA <span class="xiga-pro">♛ PRO</span></span></div></div>''', unsafe_allow_html=True)

    # Compact tab navigation using a Streamlit radio widget, not buttons or links.
    # This stays in the same browser tab and the same Streamlit session.
    pages = ("Dashboard", "Backtest", "History", "Profile")
    current_index = pages.index(active_page) if active_page in pages else 0
    selected = st.radio(
        "XIGA navigation",
        pages,
        index=current_index,
        horizontal=True,
        label_visibility="collapsed",
        key="xiga_tab_navigation",
    )
    if selected != st.session_state.get("page"):
        st.session_state.page = selected
        st.rerun()


def dashboard_page():
    st.markdown('<div class="xiga-app">', unsafe_allow_html=True)
    resolve_trade_if_ready()
    perform_pending_analysis()
    provider_options = EXCHANGE_PROVIDERS
    provider = st.session_state.get("provider", "Binance")
    if provider not in provider_options:
        provider = "Binance"
    trade_pending = st.session_state.get("trade_pending")
    analysis_pending = st.session_state.get("analysis_pending")
    controls_disabled = bool(trade_pending or analysis_pending)

    st.markdown('<div class="xiga-selector-card">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        provider = st.selectbox("Platform", provider_options, index=provider_options.index(provider), key="provider", disabled=controls_disabled)
    if provider == "BiQuote":
        categories = list(ASSETS.keys())
        category = st.session_state.get("category", categories[0])
        if category not in categories: category = categories[0]
        with c2:
            category = st.selectbox("Market", categories, index=categories.index(category), key="category", disabled=controls_disabled)
        asset_map = ASSETS.get(category) or {}
    else:
        with c2:
            st.selectbox("Market", ["Crypto / USDT • SPOT"], key="exchange_market_display", disabled=True)
        asset_map, exchange_catalog_status = get_spot_exchange_assets(provider)
    with c3:
        tf_default = st.session_state.get("timeframe", "1 MIN")
        timeframe = st.selectbox("Timeframe", list(TIMEFRAMES.keys()), index=list(TIMEFRAMES.keys()).index(tf_default) if tf_default in TIMEFRAMES else 0, key="timeframe", disabled=controls_disabled)
    asset_names = list(asset_map.keys())
    if not asset_names:
        st.error("No instruments are currently available.")
        st.markdown('</div></div>', unsafe_allow_html=True)
        return
    current_asset = st.session_state.get("asset", asset_names[0])
    if current_asset not in asset_names: current_asset = asset_names[0]
    display_asset = st.selectbox("Asset", asset_names, index=asset_names.index(current_asset), key="asset", disabled=controls_disabled)
    st.markdown(f'<div class="xiga-market-ready">● LIVE MARKET READY • {provider} • {catalog_status if provider == "BiQuote" else exchange_catalog_status}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    symbol = asset_map[display_asset]
    result = st.session_state.get("result") or {}
    signal = result.get("signal", "NO TRADE")
    status = result.get("status", "READY")
    probability = result.get("probability")

    # Analyze comes immediately after the selectors and before the result.
    st.markdown('<div class="xiga-analyze-wrap">', unsafe_allow_html=True)
    if not analysis_pending and not trade_pending:
        if st.button("⚡ ANALYZE MARKET", key="analyze_market_top", use_container_width=True):
            now = datetime.now(timezone.utc)
            st.session_state.analysis_pending = {"id": now.isoformat(), "asset": display_asset, "symbol": symbol, "provider": provider, "timeframe": timeframe, "started_at": now.isoformat(), "complete_at": (now + timedelta(seconds=ANALYSIS_SECONDS)).isoformat()}
            st.session_state.result = {"success": False, "signal": "NO TRADE", "strength": 0, "probability": None, "status": "ANALYSIS IN PROGRESS", "description": "Fetching and checking fresh market data..."}
            st.rerun()
    elif analysis_pending:
        st.button("⏳ ANALYZING MARKET...", key="analyzing_disabled", disabled=True, use_container_width=True)
    else:
        st.button("● TRADE ACTIVE — MONITORING", key="trade_active_disabled", disabled=True, use_container_width=True)
    st.markdown('<div class="xiga-analyze-sub">Fresh market analysis uses the configured live provider before every signal.</div></div>', unsafe_allow_html=True)

    if analysis_pending:
        remaining = seconds_until(analysis_pending.get("complete_at"))
        progress = max(5, min(100, int((ANALYSIS_SECONDS - remaining) / ANALYSIS_SECONDS * 100)))
        st.markdown(f'''<div class="xiga-signal-card neutral"><div class="xiga-signal-head"><span>XIGA SIGNAL • ANALYZING</span><span class="xiga-badge live">LIVE</span></div><div class="xiga-signal-circle neutral"><div class="xiga-signal-circle-inner"><div class="xiga-signal-circle-icon">⚡</div><div class="xiga-signal-circle-text">ANALYZING</div></div></div><div class="xiga-signal-main"><div class="neutral-text" style="font-size:13px;font-weight:900">MARKET CHECK</div><div><div class="xiga-confidence-label">ANALYSIS TIME</div><div class="xiga-confidence-value">{format_countdown(remaining)}</div><div class="xiga-bar"><span style="width:{progress}%"></span></div></div></div><div class="xiga-why"><div class="xiga-why-icon">⚡</div><div><div class="xiga-why-title">XIGA is checking the market</div><div class="xiga-why-text">Trend • momentum • volatility • structure • data quality</div></div></div></div>''', unsafe_allow_html=True)
    else:
        if signal not in ("CALL", "PUT", "NO TRADE"): signal = "NO TRADE"
        display_signal = signal_display(signal)
        card_class = signal_color_class(signal)
        badge, badge_class = (
            ("WIN", "win") if status == "WIN"
            else ("LOSS", "loss") if status == "LOSS"
            else ("DRAW", "expired") if status == "DRAW"
            else ("LIVE", "live")
        )
        if signal == "CALL": circle_class, icon, circle_text, direction_class = "buy", "↑", "BUY", "buy-text"
        elif signal == "PUT": circle_class, icon, circle_text, direction_class = "sell", "↓", "SELL", "sell-text"
        else: circle_class, icon, circle_text, direction_class = "neutral", "—", "NO TRADE", "neutral-text"
        probability_text = f"{int(probability)}%" if probability is not None else "—"
        entry = result.get("entry_price") or result.get("price")
        tp = result.get("take_profit"); sl = result.get("stop_loss")
        levels = ""
        if entry is not None and tp is not None and sl is not None and signal in ("CALL", "PUT"):
            levels = f'''<div class="xiga-levels"><div class="xiga-level"><div class="xiga-level-label">{"BUY AT" if signal == "CALL" else "SELL AT"}</div><div class="xiga-level-value entry">{float(entry):.8g}</div></div><div class="xiga-level"><div class="xiga-level-label">TAKE PROFIT</div><div class="xiga-level-value tp">{float(tp):.8g}</div></div><div class="xiga-level"><div class="xiga-level-label">STOP LOSS</div><div class="xiga-level-value sl">{float(sl):.8g}</div></div></div>'''
        if trade_pending:
            timer = format_countdown(seconds_until(trade_pending.get("complete_at"))); live_status = "MONITORING LIVE PRICE"
        elif status == "WIN":
            timer = result.get("tp_hit_elapsed") or result.get("result_time") or "—"; live_status = "TAKE PROFIT HIT • TIMER STOPPED"
        elif status == "LOSS":
            timer = result.get("result_time") or "—"; live_status = "TP NOT REACHED • TIMER STOPPED"
        elif status == "DRAW":
            timer = result.get("result_time") or "—"; live_status = "ENTRY PRICE • TIMER STOPPED"
        else:
            timer = "READY"; live_status = "WAITING FOR ANALYSIS"
        reason = result.get("result_reason") or result.get("description") or "Select your market, asset and timeframe, then analyze the market."
        st.markdown(f'''<div class="xiga-signal-card {card_class}"><div class="xiga-signal-head"><span>XIGA SIGNAL • {timeframe}</span><span class="xiga-badge {badge_class}">{badge}</span></div><div class="xiga-signal-circle {circle_class}"><div class="xiga-signal-circle-inner"><div class="xiga-signal-circle-icon">{icon}</div><div class="xiga-signal-circle-text">{circle_text}</div></div></div><div class="xiga-signal-main"><div class="{direction_class}" style="font-size:15px;font-weight:900">{display_signal if signal != "NO TRADE" else "WAIT FOR STRONGER CONFIRMATION"}</div><div><div class="xiga-confidence-label">CONFIDENCE</div><div class="xiga-confidence-value">{probability_text}</div><div class="xiga-bar"><span style="width:{int(probability or 0)}%"></span></div></div></div>{levels}</div>''', unsafe_allow_html=True)
        tick, _ = get_latest_tick(provider, symbol, fresh=True)
        live_price = float(tick["price"]) if tick else (float(trade_pending.get("live_price")) if trade_pending and trade_pending.get("live_price") else None)
        if trade_pending and live_price is not None: trade_pending["live_price"] = live_price
        entry_for_delta = float(entry) if entry is not None else live_price
        delta = (live_price - entry_for_delta) if live_price is not None and entry_for_delta is not None else 0
        delta_pct = (delta / entry_for_delta * 100) if entry_for_delta else 0
        st.markdown(f'''<div class="xiga-live-grid"><div class="xiga-mini"><div class="xiga-mini-label">TRADE TIMER</div><div class="xiga-mini-value">{timer}</div><div class="xiga-mini-sub">{timeframe} • {live_status}</div></div><div class="xiga-mini"><div class="xiga-mini-label">LIVE PRICE</div><div class="xiga-mini-value">{f'{live_price:.8g}' if live_price is not None else '—'}</div><div class="xiga-mini-sub">{delta:+.8g} ({delta_pct:+.2f}%)</div></div></div>''', unsafe_allow_html=True)

    if result.get("success"):
        reasons = result.get("reasons") or [result.get("description", "Current market conditions were analyzed.")]
        short_reason = " • ".join(reasons[:3])
        rsi_value = result.get("rsi"); macd_value = result.get("macd")
        trend = "UPTREND" if signal == "CALL" else "DOWNTREND" if signal == "PUT" else "MIXED"
        momentum = "STRONG" if abs(float(result.get("score", 0))) >= 4 else "MODERATE"
        volatility = "NORMAL" if result.get("atr") is not None else "UNKNOWN"
        st.markdown(f'''<div class="xiga-card"><div class="xiga-why"><div class="xiga-why-icon">💡</div><div><div class="xiga-why-title">Signal explanation</div><div class="xiga-why-text">{short_reason}</div></div></div><div class="xiga-tech-grid"><div class="xiga-tech"><b>RSI</b><span>{f'{rsi_value:.1f}' if rsi_value is not None else '—'}</span></div><div class="xiga-tech"><b>MACD</b><span>{f'{macd_value:.5f}' if macd_value is not None else '—'}</span></div><div class="xiga-tech"><b>EMA TREND</b><span>{trend}</span></div><div class="xiga-tech"><b>MOMENTUM</b><span>{momentum}</span></div></div></div>''', unsafe_allow_html=True)
        st.markdown(f'''<div class="xiga-card"><div class="xiga-section-title" style="font-size:12px">Market Status</div><div class="xiga-status-grid"><div class="xiga-status-item"><div class="xiga-status-label">TREND</div><div class="xiga-status-value {"green" if trend == "UPTREND" else "red" if trend == "DOWNTREND" else ""}">{trend}</div></div><div class="xiga-status-item"><div class="xiga-status-label">VOLATILITY</div><div class="xiga-status-value">{volatility}</div></div><div class="xiga-status-item"><div class="xiga-status-label">DATA</div><div class="xiga-status-value green">CONNECTED</div></div></div><div class="xiga-note">News: {result.get("news_status", "Not used")} • Historical setup sample: {result.get("historical_samples", 0)}</div></div>''', unsafe_allow_html=True)
    st.markdown('<div class="xiga-footer">🔒 SECURE • XIGA PRO • LIVE MARKET ANALYSIS • NO AUTOMATIC TRADE EXECUTION</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def backtest_page():
    st.markdown('<div class="xiga-app">',unsafe_allow_html=True)
    st.markdown('<div class="xiga-page-card"><div class="xiga-page-title">🧪 Backtest</div><div class="xiga-page-sub">Test XIGA against historical completed candles. Historical performance does not guarantee future results.</div></div>',unsafe_allow_html=True)
    bt_mode=st.radio("Backtest depth",["STANDARD • 5,000 CANDLES","DEEP • 10,000 CANDLES"],horizontal=True,key="backtest_mode")
    target_count=BACKTEST_DEEP_CANDLES if bt_mode.startswith("DEEP") else BACKTEST_STANDARD_CANDLES
    bt_default=st.session_state.get("backtest_provider","Binance")
    if bt_default not in BACKTEST_PROVIDERS: bt_default="Binance"
    provider=st.selectbox("Platform",BACKTEST_PROVIDERS,index=BACKTEST_PROVIDERS.index(bt_default),key="backtest_provider")
    if provider=="BiQuote":
        category=st.selectbox("Market",list(ASSETS.keys()),key="backtest_category"); asset_map=ASSETS.get(category) or {}
    else:
        st.selectbox("Market",["Crypto / USDT • SPOT"],disabled=True,key=f"backtest_market_{provider}"); asset_map, _ = get_spot_exchange_assets(provider)
    asset_names=list(asset_map.keys())
    if asset_names:
        asset=st.selectbox("Asset",asset_names,key="backtest_asset"); timeframe=st.selectbox("Timeframe",list(TIMEFRAMES.keys()),key="backtest_timeframe")
        if st.button("🧪 RUN BACKTEST",key="run_backtest",use_container_width=True):
            with st.spinner(f"Downloading and testing {target_count:,} completed candles..."): st.session_state.backtest_result=run_xiga_backtest(provider,asset_map[asset],timeframe,target_count)
        bt=st.session_state.get("backtest_result")
        if bt:
            if not bt.get("success"):
                st.error(bt.get("error","Backtest failed.")); st.caption(bt.get("status",""))
            else:
                st.markdown(f'''<div class="xiga-backtest-grid"><div class="xiga-stat-box"><b>COMPLETED CANDLES</b><span>{bt["candles"]:,}</span></div><div class="xiga-stat-box"><b>TOTAL SIGNALS</b><span>{bt["signals"]:,}</span></div><div class="xiga-stat-box"><b>WINS</b><span class="green">{bt["wins"]:,}</span></div><div class="xiga-stat-box"><b>LOSSES</b><span class="red">{bt["losses"]:,}</span></div><div class="xiga-stat-box"><b>WIN RATE</b><span>{bt["accuracy"]:.1f}%</span></div><div class="xiga-stat-box"><b>TP RATE</b><span>{bt["tp_rate"]:.1f}%</span></div></div>''',unsafe_allow_html=True)
                st.markdown(f'<div class="xiga-note">BUY signals: {bt["calls"]:,} • SELL signals: {bt["puts"]:,}<br>BUY accuracy: {bt["call_accuracy"]:.1f}% • SELL accuracy: {bt["put_accuracy"]:.1f}%<br>TP hits: {bt["tp_hits"]:,} • TP not reached: {bt["tp_misses"]:,}<br>Average favorable movement: {bt["avg_favorable"]:.3f}%</div>',unsafe_allow_html=True)
                if bt.get("validation_ok"): st.success("Historical validation thresholds met.")
                else: st.warning("Historical validation thresholds not met.")
                st.caption(bt.get("validation_reason","Historical validation only."))
                st.caption("Validation checks are historical only: at least 100 signals, ≥55% directional accuracy and ≥50% TP-hit rate. They are not future guarantees.")
    st.markdown('</div>',unsafe_allow_html=True)


def history_page():
    st.markdown('<div class="xiga-app">',unsafe_allow_html=True)
    st.markdown('<div class="xiga-page-card"><div class="xiga-page-title">📜 History</div><div class="xiga-page-sub">Recorded XIGA live signals from this session.</div></div>',unsafe_allow_html=True)
    if not st.session_state.history:
        st.markdown('<div class="xiga-page-card"><div class="xiga-muted">No live signals have been generated yet.</div></div>',unsafe_allow_html=True)
    else:
        for item in st.session_state.history[:30]:
            status=item.get("status","PENDING"); cls="green" if status=="WIN" else "red" if status=="LOSS" else ""
            st.markdown(f'''<div class="xiga-history-item"><div class="xiga-history-top"><span>{item.get("asset","—")}</span><span class="{cls}">{signal_display(item.get("signal"))}</span></div><div class="xiga-history-sub">{item.get("provider","—")} • {item.get("timeframe","—")} • {item.get("time","—")}<br>Entry: {item.get("price","—")} • TP: {item.get("take_profit","—")} • SL: {item.get("stop_loss","—")}</div><div class="xiga-history-result {cls}">{status}{(" • TP HIT IN " + str(item.get("tp_hit_elapsed"))) if status=="WIN" and item.get("tp_hit_elapsed") else ""}{(" • " + str(item.get("result_reason"))) if status in ("LOSS","EXPIRED") else ""}</div></div>''',unsafe_allow_html=True)
    st.markdown('</div>',unsafe_allow_html=True)


def profile_page():
    status=get_subscription_status() or st.session_state.get("xiga_status") or {}
    email=st.session_state.get("xiga_email") or status.get("email") or "Account"
    active=bool(status.get("active",True)); expiry=status.get("subscription_expires_at") or "—"; days=status.get("days_remaining",0); expiry_short=str(expiry)[:10] if expiry!="—" else "—"
    total=len(st.session_state.history); wins=sum(1 for x in st.session_state.history if x.get("status")=="WIN"); losses=sum(1 for x in st.session_state.history if x.get("status")=="LOSS"); expired=sum(1 for x in st.session_state.history if x.get("status")=="EXPIRED"); decided=wins+losses; observed_rate=wins/decided*100 if decided else 0; tp_hit_rate=wins/total*100 if total else 0
    st.markdown('<div class="xiga-app">',unsafe_allow_html=True)
    st.markdown(f'''<div class="xiga-page-card"><div class="xiga-page-title">👤 Profile</div><div class="xiga-account-card" style="margin-top:10px"><div class="xiga-account-label">ACCOUNT EMAIL</div><div class="xiga-account-value">{email}</div><div class="xiga-profile-levels"><div class="xiga-profile-level"><b>STATUS</b><span>{"ACTIVE" if active else "INACTIVE"}</span></div><div class="xiga-profile-level"><b>DAYS LEFT</b><span>{days}</span></div><div class="xiga-profile-level"><b>EXPIRES</b><span>{expiry_short}</span></div></div></div></div>''',unsafe_allow_html=True)
    st.markdown(f'''<div class="xiga-page-card"><div class="xiga-page-title" style="font-size:14px">Quick Stats</div><div class="xiga-stat-grid"><div class="xiga-stat-box"><b>TOTAL SIGNALS</b><span>{total}</span></div><div class="xiga-stat-box"><b>WINS</b><span class="green">{wins}</span></div><div class="xiga-stat-box"><b>LOSSES</b><span class="red">{losses}</span></div><div class="xiga-stat-box"><b>EXPIRED</b><span>{expired}</span></div><div class="xiga-stat-box"><b>WIN RATE</b><span>{observed_rate:.1f}%</span></div><div class="xiga-stat-box"><b>TP HIT RATE</b><span>{tp_hit_rate:.1f}%</span></div></div><div class="xiga-note">These are recorded XIGA signals from your current session, not a prediction.</div></div>''',unsafe_allow_html=True)
    ref_code, ref_data = call_xiga_function("referral_details")
    ref_data = ref_data if ref_code == 200 else {}
    st.markdown(f'''<div class="xiga-page-card"><div class="xiga-page-title" style="font-size:14px">Referral Details</div><div class="xiga-note">Refer unlimited customers. A referral becomes QUALIFIED only after the referred customer activates their XIGA subscription key. Reward: Rs. 1,000 per qualified referral.</div><div class="xiga-account-card" style="margin-top:9px"><div class="xiga-account-label">REFERRAL CODE</div><div class="xiga-account-value" style="color:#20e7a0">{ref_data.get("referral_code","—")}</div><div class="xiga-account-label" style="margin-top:8px">REFERRAL LINK</div><div style="font-size:9px;color:#dceeff;word-break:break-all;margin-top:3px">{ref_data.get("referral_link","—")}</div></div><div class="xiga-stat-grid"><div class="xiga-stat-box"><b>TOTAL</b><span>{int(ref_data.get("total_referrals",0))}</span></div><div class="xiga-stat-box"><b>QUALIFIED</b><span class="green">{int(ref_data.get("qualified",0))}</span></div><div class="xiga-stat-box"><b>PENDING</b><span>{int(ref_data.get("pending",0))}</span></div><div class="xiga-stat-box"><b>EARNED</b><span>Rs. {int(ref_data.get("earned",0)):,}</span></div><div class="xiga-stat-box"><b>PAID</b><span class="green">Rs. {int(ref_data.get("paid",0)):,}</span></div><div class="xiga-stat-box"><b>UNPAID</b><span class="red">Rs. {int(ref_data.get("unpaid",0)):,}</span></div></div></div>''',unsafe_allow_html=True)
    for item in (ref_data.get("history") or [])[:100]:
        status_label=str(item.get("status","PENDING")).upper(); cls="green" if status_label=="QUALIFIED" else ""
        st.markdown(f'''<div class="xiga-history-item"><div class="xiga-history-top"><span>{item.get("referred_email","—")}</span><span class="{cls}">{status_label}</span></div><div class="xiga-history-sub">Reward: Rs. {int(item.get("reward",1000)):,} • Payment: {str(item.get("payment_status","UNPAID")).upper()}</div></div>''',unsafe_allow_html=True)
    if st.button("🚪 LOG OUT",key="profile_logout",use_container_width=True): clear_session(); st.rerun()
    st.markdown('<div class="xiga-footer">XIGA PRO • ACCOUNT & SUBSCRIPTION</div></div>',unsafe_allow_html=True)



selected_page=st.session_state.get("page","Dashboard")
if selected_page not in ("Dashboard","Backtest","History","Profile"): selected_page="Dashboard"
render_app_header(selected_page)
if selected_page=="Dashboard":
    @st.fragment(run_every="1s")
    def dashboard_fragment(): dashboard_page()
    dashboard_fragment()
elif selected_page=="Backtest": backtest_page()
elif selected_page=="History": history_page()
elif selected_page=="Profile": profile_page()
