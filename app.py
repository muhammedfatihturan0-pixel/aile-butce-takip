import hashlib
import calendar
import json
import re
import time
import unicodedata
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
import extra_streamlit_components as stx
import plotly.express as px

st.set_page_config(page_title="Aile Bütçe Takip", page_icon="💠", layout="wide", initial_sidebar_state="expanded")

# Bu cihazda oturumu açık tutmak için tarayıcı çerezi (şifre saklanmaz).
_cookie_manager = stx.CookieManager(key="aile_butce_auth_cookie")

# ---------- Modern dashboard styling ----------
st.markdown(r"""
<style>
:root {
  --bg: #0b1220;
  --surface: #111b2b;
  --surface-2: #162337;
  --line: rgba(159,181,210,.15);
  --text: #edf4ff;
  --muted: #91a2bc;
  --accent: #65e2c2;
  --accent-2: #8aa8ff;
}
.block-container {padding-top:1.15rem; padding-bottom:2.4rem; max-width:1420px;}
[data-testid="stAppViewContainer"] {background:radial-gradient(ellipse at 78% 0%, rgba(38,75,107,.18), transparent 34%), var(--bg);}
[data-testid="stHeader"] {background:transparent;}
[data-testid="stSidebar"] {background:#0e1726; border-right:1px solid var(--line);}
[data-testid="stSidebar"] .block-container {padding-top:1.3rem;}
[data-testid="stSidebar"] hr {margin:1.1rem 0; border-color:var(--line);}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {color:#c2cee0;}
[data-testid="stMetric"] {
  background:linear-gradient(145deg,rgba(22,35,55,.96),rgba(16,27,43,.96));
  border:1px solid var(--line); padding:16px 18px; border-radius:17px;
  box-shadow:0 8px 24px rgba(0,0,0,.12); min-height:112px;
}
[data-testid="stMetricLabel"] {color:#d0dced !important; font-size:.86rem; font-weight:600;}
[data-testid="stMetricValue"] {color:#ffffff !important; font-weight:760; letter-spacing:-.035em; font-size:clamp(1.25rem,2vw,1.8rem);}
[data-testid="stMetricDelta"] {font-size:.8rem; color:#c9d7e9 !important;}
[data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li, [data-testid="stCaptionContainer"] {
  color:#e3ebf7;
}
[data-testid="stCaptionContainer"] {color:#b8c6d9 !important;}
label, [data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label,
[data-testid="stRadio"] label, [data-testid="stCheckbox"] label {
  color:#eaf1fb !important;
}
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea, [data-testid="stDateInput"] input {
  color:#ffffff !important; -webkit-text-fill-color:#ffffff !important;
  background:#202c3e !important; caret-color:#65e2c2;
}
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
  color:#ffffff !important; background:#202c3e !important;
}
[data-testid="stSelectbox"] [data-baseweb="select"] span,
[data-testid="stMultiSelect"] [data-baseweb="select"] span {
  color:#ffffff !important;
}
[data-baseweb="popover"], [data-baseweb="menu"], [role="listbox"] {
  background:#172337 !important; color:#ffffff !important;
}
[role="option"], [role="option"] * {color:#f4f7fc !important;}
[data-testid="stDataFrame"] {color:#f2f6fc;}
[data-testid="stAlert"] {color:#f5f8ff !important;}
[data-testid="stAlert"] p, [data-testid="stAlert"] div {color:inherit;}
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary p {
  color:#edf4ff !important;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] label {color:#e1eaf7 !important;}
.small-muted, .section-sub, .kpi-note {color:#b8c7dc !important;}
.stButton>button, .stDownloadButton>button, [data-testid="stFormSubmitButton"] button {
  border-radius:11px; font-weight:650; min-height:2.55rem; transition:all .16s ease;
}
.stButton>button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"] {
  background:var(--accent)!important; border:1px solid var(--accent)!important;
  color:#08221d!important; box-shadow:0 5px 14px rgba(101,226,194,.12);
}
.stButton>button[kind="primary"]:hover, [data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
  background:#83efd5!important; border-color:#83efd5!important; transform:translateY(-1px);
}
.stButton>button:not([kind="primary"]), .stDownloadButton>button {
  background:#172337; border:1px solid var(--line); color:#e6eefb;
}
.stButton>button:not([kind="primary"]):hover, .stDownloadButton>button:hover {
  border-color:rgba(101,226,194,.55); color:var(--accent);
}
[data-testid="stForm"] {
  border:1px solid var(--line); border-radius:16px; padding:1rem;
  background:rgba(17,27,43,.72);
}
[data-testid="stDataFrame"] {border:1px solid var(--line); border-radius:12px; overflow:hidden;}
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stDateInput"] input, [data-testid="stTextArea"] textarea {
  border-radius:10px!important;
}
[data-testid="stExpander"] {border:1px solid var(--line); border-radius:13px; overflow:hidden;}
[data-testid="stAlert"] {border-radius:12px;}
.app-hero {
  position:relative; overflow:hidden; border-radius:22px; padding:25px 29px; margin:0 0 1.15rem 0;
  color:white; background:linear-gradient(115deg,#121d31 0%,#192b43 63%,#183c43 100%);
  border:1px solid rgba(146,178,210,.2); box-shadow:0 16px 34px rgba(0,0,0,.14);
}
.app-hero:after {content:"";position:absolute;right:-58px;top:-115px;width:260px;height:260px;border-radius:50%;border:1px solid rgba(101,226,194,.16);box-shadow:0 0 0 28px rgba(101,226,194,.025),0 0 0 58px rgba(101,226,194,.02);}
.app-hero .eyebrow {font-size:.7rem;letter-spacing:.18em;text-transform:uppercase;color:var(--accent);font-weight:850;}
.app-hero h1 {margin:.55rem 0 .42rem 0;font-size:clamp(1.55rem,2.4vw,2.1rem);line-height:1.12;letter-spacing:-.045em;color:white;}
.app-hero p {margin:0;color:#e0e9f6;font-size:.94rem;max-width:780px;}
.app-hero .period {float:right;position:relative;z-index:1;padding:7px 11px;border-radius:10px;font-size:.78rem;font-weight:750;color:#c8fff1;border:1px solid rgba(101,226,194,.25);background:rgba(101,226,194,.08);}
.section-head {display:flex;gap:11px;align-items:center;margin:1.2rem 0 .55rem 0;}
.section-icon {display:inline-flex;align-items:center;justify-content:center;width:38px;height:38px;border-radius:12px;background:#172b3a;border:1px solid rgba(101,226,194,.18);font-size:1.12rem;}
.section-title {font-weight:800;font-size:1.08rem;letter-spacing:-.025em;color:#ffffff;}
.section-sub {font-size:.81rem;color:var(--muted);margin-top:2px;}
.small-muted {font-size:.8rem;color:var(--muted);}
.kpi-note {font-size:.78rem;color:var(--muted);margin-top:4px;}
.pill {display:inline-block;background:rgba(101,226,194,.09);border:1px solid rgba(101,226,194,.23);color:#8df0d7;padding:5px 9px;border-radius:999px;font-size:.74rem;font-weight:750;}
hr {border-color:var(--line);}
[data-testid="stVerticalBlockBorderWrapper"] {border-color:var(--line)!important;border-radius:15px!important;}
@media (max-width: 800px) {
 .block-container {padding-top:.65rem;padding-left:1rem;padding-right:1rem;}
 .app-hero {padding:20px;border-radius:17px;}
 .app-hero .period {float:none;display:inline-block;margin-bottom:12px;}
 [data-testid="stMetric"] {padding:12px;border-radius:13px;min-height:94px;}
}
</style>
""", unsafe_allow_html=True)

CATEGORIES = [
    "Market", "Faturalar", "Ulaşım", "Ulaşım / Seyahat", "Restoran / Yemek",
    "Giyim", "Çocuk", "Sağlık", "Ev / Yaşam", "Eğitim / Kırtasiye",
    "Online alışveriş", "Dijital abonelik", "Dijital abonelik / Oyun", "Kişisel bakım",
    "Bankacılık ücreti", "Resmi ödeme", "Kişisel alışveriş", "Taksit", "İade", "Kontrol edilecek",
    "Toplam harcama", "Kart toplamı", "Diğer"
]
OWNERS = ["Ben", "Eşim", "Ortak", "Diğer", "Belirsiz"]
COLLECTIONS = {"monthly_budgets", "transactions", "cards", "statements", "app_meta"}
# Comma-decimal amounts must be matched before integers; OCR can also lose the decimal point (1,34144 -> 1,341.44).
AMOUNT_TOKEN_RE = r"(?<![A-Za-z0-9/])(?:\d{1,3},\d{3}\d{2}|\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\d+,\d{2}|\d+(?:\.\d{2})?)(?:\(-\))?"

# ---------- Secrets / Firebase Auth ----------
def get_secret_section(key):
    try:
        return st.secrets[key]
    except Exception:
        return {}

FB = get_secret_section("firebase")
AI = get_secret_section("openai")
PROJECT_ID = str(FB.get("project_id", "")).strip()
API_KEY = str(FB.get("api_key", "")).strip()
FS_ROOT = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents" if PROJECT_ID else ""


def money(value):
    try:
        return f"{float(value):,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "0,00 TL"


AYLAR_TR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

def today_tr():
    return datetime.now(ZoneInfo("Europe/Istanbul")).date()

def month_label_tr(month_key):
    try:
        year, month = map(int, str(month_key)[:7].split("-"))
        return f"{AYLAR_TR[month - 1]} {year}"
    except Exception:
        return str(month_key)

def add_months(year, month, delta=1):
    n = year * 12 + (month - 1) + delta
    return n // 12, n % 12 + 1

def scheduled_statement_dates(month_key, cutoff_day, due_day):
    year, month = map(int, month_key.split("-"))
    cutoff = date(year, month, min(int(cutoff_day), calendar.monthrange(year, month)[1]))
    due_year, due_month = add_months(year, month, 1)
    due = date(due_year, due_month, min(int(due_day), calendar.monthrange(due_year, due_month)[1]))
    return cutoff, due

def section(icon, title, subtitle=""):
    st.markdown(
        f'<div class="section-head"><span class="section-icon">{icon}</span><div><div class="section-title">{title}</div><div class="section-sub">{subtitle}</div></div></div>',
        unsafe_allow_html=True,
    )


def title_hero(month_label, subtitle="Aile gelirleri, ödemeler ve kart harcamaları tek yerde."):
    st.markdown(
        f'<div class="app-hero"><span class="period">📅 {month_label}</span><div class="eyebrow">AİLE FİNANS PANELİ</div><h1>Paranızın nereye gittiğini görün.</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


def to_fs_value(value):
    if value is None:
        return {"nullValue": None}
    if isinstance(value, bool):
        return {"booleanValue": value}
    if isinstance(value, int):
        return {"integerValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, (list, tuple)):
        return {"arrayValue": {"values": [to_fs_value(x) for x in value]}}
    if isinstance(value, dict):
        return {"mapValue": {"fields": {str(k): to_fs_value(v) for k, v in value.items()}}}
    return {"stringValue": str(value)}


def from_fs_value(value):
    if "stringValue" in value:
        return value["stringValue"]
    if "integerValue" in value:
        return int(value["integerValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "booleanValue" in value:
        return bool(value["booleanValue"])
    if "nullValue" in value:
        return None
    if "timestampValue" in value:
        return value["timestampValue"]
    if "mapValue" in value:
        return from_fs_fields(value["mapValue"].get("fields", {}))
    if "arrayValue" in value:
        return [from_fs_value(x) for x in value["arrayValue"].get("values", [])]
    return None


def from_fs_fields(fields):
    return {key: from_fs_value(value) for key, value in fields.items()}


def to_fs_fields(data):
    return {key: to_fs_value(value) for key, value in data.items()}


def auth_url(path):
    return f"https://identitytoolkit.googleapis.com/v1/{path}?key={API_KEY}"


def login(email, password, remember_device=False):
    response = requests.post(
        auth_url("accounts:signInWithPassword"),
        json={"email": email, "password": password, "returnSecureToken": True},
        timeout=20,
    )
    if response.status_code != 200:
        try:
            message = response.json().get("error", {}).get("message", "Giriş başarısız.")
        except Exception:
            message = "Giriş başarısız."
        raise ValueError(message.replace("_", " "))
    data = response.json()
    st.session_state["auth"] = {
        "id_token": data["idToken"], "refresh_token": data["refreshToken"],
        "uid": data["localId"], "email": data.get("email", email),
        "expires_at": time.time() + int(data.get("expiresIn", 3600)) - 60,
        "remember_device": bool(remember_device),
    }
    if remember_device:
        _cookie_manager.set(
            "fb_session",
            json.dumps({"refresh_token": data["refreshToken"], "email": data.get("email", email)}),
            key="set_login_session",
            expires_at=datetime.now() + timedelta(days=365),
            same_site="lax",
            secure=True,
        )
    else:
        try:
            _cookie_manager.delete("fb_session", key="delete_login_session")
        except Exception:
            pass


def restore_auth_from_cookie():
    """Restore a trusted-device session without asking for the password again."""
    if st.session_state.get("auth"):
        return True
    try:
        cookies = _cookie_manager.get_all(key="read_saved_session_cookie") or {}
        raw_session = cookies.get("fb_session")
        if not raw_session:
            return False
        saved = json.loads(raw_session)
        refresh_token = saved.get("refresh_token", "")
        email = saved.get("email", "")
        if not refresh_token:
            return False
        response = requests.post(
            f"https://securetoken.googleapis.com/v1/token?key={API_KEY}",
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            timeout=20,
        )
        if response.status_code != 200:
            try:
                _cookie_manager.delete("fb_session", key="delete_expired_session")
            except Exception:
                pass
            return False
        data = response.json()
        new_refresh_token = data.get("refresh_token", refresh_token)
        st.session_state["auth"] = {
            "id_token": data["id_token"],
            "refresh_token": new_refresh_token,
            "uid": data.get("user_id", ""),
            "email": email,
            "expires_at": time.time() + int(data.get("expires_in", 3600)) - 60,
            "remember_device": True,
        }
        _cookie_manager.set(
            "fb_session",
            json.dumps({"refresh_token": new_refresh_token, "email": email}),
            key="set_restored_session",
            expires_at=datetime.now() + timedelta(days=365),
            same_site="lax",
            secure=True,
        )
        return bool(st.session_state["auth"]["uid"])
    except Exception:
        return False

def current_auth():
    return st.session_state.get("auth")


def logout():
    get_budget.clear()
    load_transactions.clear()
    for key in ["auth", "import_preview", "import_source_name", "quick_card_preference_loaded", "quick_card_preference"]:
        st.session_state.pop(key, None)
    try:
        _cookie_manager.delete("fb_session", key="delete_logout_session")
    except Exception:
        pass
    st.rerun()


def get_id_token():
    auth = current_auth()
    if not auth:
        raise RuntimeError("Oturum açılmamış.")
    if time.time() < auth["expires_at"]:
        return auth["id_token"]
    response = requests.post(
        f"https://securetoken.googleapis.com/v1/token?key={API_KEY}",
        data={"grant_type": "refresh_token", "refresh_token": auth["refresh_token"]}, timeout=20,
    )
    if response.status_code != 200:
        st.session_state.pop("auth", None)
        raise RuntimeError("Oturum süresi doldu. Yeniden giriş yapın.")
    data = response.json()
    auth.update({
        "id_token": data["id_token"], "refresh_token": data.get("refresh_token", auth["refresh_token"]),
        "uid": data.get("user_id", auth["uid"]), "expires_at": time.time() + int(data.get("expires_in", 3600)) - 60,
    })
    st.session_state["auth"] = auth
    if auth.get("remember_device"):
        try:
            _cookie_manager.set(
                "fb_session",
                json.dumps({"refresh_token": auth["refresh_token"], "email": auth.get("email", "")}),
                key="set_refreshed_session",
                expires_at=datetime.now() + timedelta(days=365),
                same_site="lax",
                secure=True,
            )
        except Exception:
            pass
    return auth["id_token"]


def fs_request(method, url, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {get_id_token()}"
    headers["Content-Type"] = "application/json"
    response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
    if response.status_code == 401:
        st.session_state.pop("auth", None)
        raise RuntimeError("Firebase oturumu geçersiz. Yeniden giriş yapın.")
    if response.status_code >= 400:
        try:
            detail = response.json().get("error", {}).get("message", response.text)
        except Exception:
            detail = response.text
        raise RuntimeError(f"Firestore isteği başarısız ({response.status_code}): {detail}")
    if response.status_code == 204 or not response.text:
        return None
    return response.json()


def get_document(collection, doc_id):
    if collection not in COLLECTIONS:
        raise ValueError("İzin verilmeyen koleksiyon.")
    url = f"{FS_ROOT}/{collection}/{doc_id}"
    headers = {"Authorization": f"Bearer {get_id_token()}"}
    response = requests.get(url, headers=headers, timeout=20)
    if response.status_code == 404:
        return None
    if response.status_code >= 400:
        try:
            detail = response.json().get("error", {}).get("message", response.text)
        except Exception:
            detail = response.text
        raise RuntimeError(f"Firestore belge okuma hatası ({response.status_code}): {detail}")
    doc = response.json()
    item = from_fs_fields(doc.get("fields", {}))
    item["id"] = doc["name"].rsplit("/", 1)[-1]
    return item


def write_document(collection, doc_id, data):
    if collection not in COLLECTIONS:
        raise ValueError("İzin verilmeyen koleksiyon.")
    data = dict(data)
    params = [("updateMask.fieldPaths", key) for key in data.keys()]
    url = f"{FS_ROOT}/{collection}/{doc_id}"
    return fs_request("PATCH", url, params=params, json={"fields": to_fs_fields(data)})


def create_document(collection, data, doc_id=None):
    if collection not in COLLECTIONS:
        raise ValueError("İzin verilmeyen koleksiyon.")
    url = f"{FS_ROOT}/{collection}"
    params = {"documentId": doc_id} if doc_id else None
    return fs_request("POST", url, params=params, json={"fields": to_fs_fields(data)})


def list_documents(collection, uid, limit=1000):
    """Query only by ownerUid. All other filtering/sorting is client-side to avoid composite-index crashes."""
    if collection not in COLLECTIONS:
        raise ValueError("İzin verilmeyen koleksiyon.")
    query = {
        "from": [{"collectionId": collection}],
        "where": {"fieldFilter": {
            "field": {"fieldPath": "ownerUid"}, "op": "EQUAL", "value": to_fs_value(uid)
        }},
        "limit": limit,
    }
    response = fs_request("POST", f"{FS_ROOT}:runQuery", json={"structuredQuery": query})
    rows = []
    for item in response or []:
        doc = item.get("document")
        if not doc:
            continue
        row = from_fs_fields(doc.get("fields", {}))
        row["id"] = doc["name"].rsplit("/", 1)[-1]
        rows.append(row)
    return rows


def budget_id(uid, month_key):
    return f"{uid}_{month_key}"


@st.cache_data(ttl=45, show_spinner=False)
def get_budget(uid, month_key):
    # Query by ownerUid only and filter month locally. This avoids index errors and
    # avoids a direct GET of a not-yet-created budget document.
    rows = list_documents("monthly_budgets", uid, limit=1000)
    return next((row for row in rows if row.get("month") == month_key), None)


def save_budget(uid, month_key, data):
    payload = {
        "ownerUid": uid, "month": month_key, "income": data.get("income", {}),
        "expenses": data.get("expenses", {}), "notes": data.get("notes", ""),
        "updatedAt": datetime.utcnow().isoformat(timespec="seconds"),
    }
    # Preserve optional debt metadata unless the debt module explicitly updates it.
    if "debtMeta" in data:
        payload["debtMeta"] = data["debtMeta"]
    write_document("monthly_budgets", budget_id(uid, month_key), payload)
    get_budget.clear()


@st.cache_data(ttl=45, show_spinner=False)
def load_transactions(uid, month_key=None, limit=1000):
    rows = list_documents("transactions", uid, limit=limit)
    if month_key:
        rows = [row for row in rows if row.get("month") == month_key or row.get("statementMonth") == month_key]
    rows.sort(key=lambda row: (str(row.get("date", "")), str(row.get("createdAt", ""))), reverse=True)
    return rows


def load_collection(uid, collection, limit=1000):
    rows = list_documents(collection, uid, limit=limit)
    rows.sort(key=lambda row: str(row.get("updatedAt", row.get("createdAt", ""))), reverse=True)
    return rows


def safe_load_collection(uid, collection, limit=1000):
    """A modül, bir koleksiyon izin/kurallar hatası yüzünden tüm uygulamayı çökertmesin."""
    try:
        return load_collection(uid, collection, limit=limit)
    except Exception as exc:
        already = st.session_state.setdefault("collection_errors_shown", set())
        if collection not in already:
            st.error(f"'{collection}' koleksiyonuna erişilemedi. Firebase → Firestore → Rules içinde bu koleksiyon için güvenlik kuralı yayımlanmış olmalı.")
            with st.expander("Teknik ayrıntı", expanded=False):
                st.code(str(exc))
            already.add(collection)
        return []


def stable_dedupe_key(row):
    source_id = str(row.get("sourceRowId", "")).strip()
    if source_id:
        raw = "|".join([source_id, str(row.get("statementMonth", row.get("month", ""))), str(row.get("card", ""))])
    else:
        raw = "|".join([
            str(row.get("date", "")), str(row.get("month", "")),
            f"{float(row.get('amount', 0)):.2f}", re.sub(r"\s+", " ", str(row.get("description", "")).strip().lower()),
            str(row.get("card", "")), str(row.get("owner", "")), str(row.get("createdAt", "")),
        ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def add_transaction(uid, row):
    row = dict(row)
    row["ownerUid"] = uid
    row["createdAt"] = datetime.utcnow().isoformat(timespec="seconds")
    row["dedupeKey"] = stable_dedupe_key(row)
    # Dedupe query uses only ownerUid; don't require a composite index.
    existing = list_documents("transactions", uid, limit=1000)
    if any(x.get("dedupeKey") == row["dedupeKey"] for x in existing):
        return False
    create_document("transactions", row)
    load_transactions.clear()
    return True


def seed_historical_statements(uid):
    """İlk girişte, depodaki onaylı tarihsel Axess verisini bir kez Firestore'a aktarır."""
    marker_key = "axess_history_2026_v1"
    markers = list_documents("app_meta", uid, limit=100)
    if any(x.get("key") == marker_key for x in markers):
        return {"status": "already", "saved": 0}

    data_path = Path(__file__).with_name("data") / "Axess_Gecmis_Ekstre_Aktarim.xlsx"
    if not data_path.exists():
        return {"status": "missing", "saved": 0}

    current_rows = list_documents("transactions", uid, limit=1000)
    existing_ids = {str(x.get("id", "")) for x in current_rows}
    existing_keys = {str(x.get("dedupeKey", "")) for x in current_rows}
    cards = list_documents("cards", uid, limit=100)
    existing_card_names = {str(x.get("name", "")).strip() for x in cards}

    df = pd.read_excel(data_path, sheet_name="İşlemler")
    included = df[ df["Dahil"].fillna(False).astype(bool) ].copy()
    now_iso = datetime.utcnow().isoformat(timespec="seconds")
    writes = []
    transaction_count = 0
    card_names = sorted({str(x).strip() for x in included.get("Kart", pd.Series(dtype=str)).dropna() if str(x).strip()})

    for name in card_names:
        if name in existing_card_names:
            continue
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower() or hashlib.sha256(name.encode()).hexdigest()[:12]
        doc_id = f"{uid}_{slug}"
        # Kesim/ödeme günleri başlangıç değeridir; Kartlar ve Ekstreler ekranından değiştirilebilir.
        card = {"ownerUid": uid, "name": name, "bank": "Axess", "owner": "Belirsiz",
                "cutoffDay": 7, "dueDay": 17, "updatedAt": now_iso}
        writes.append({"create": {"name": f"{FS_ROOT}/cards/{doc_id}", "fields": to_fs_fields(card)}})

    for _, r in included.iterrows():
        dt = parse_date(r.get("İşlem Tarihi"))
        amount = parse_amount_generic(r.get("Tutar (TL)"))
        desc = str(r.get("Açıklama", "")).strip()
        month = str(r.get("Ekstre Ayı", ""))[:7]
        source_id = str(r.get("sourceRowId", "")).strip()
        card = str(r.get("Kart", "Axess Fiziksel")).strip() or "Axess Fiziksel"
        if not dt or amount is None or not desc or not re.fullmatch(r"\d{4}-\d{2}", month):
            continue
        category = str(r.get("Ana Kategori", "Diğer"))
        if category not in CATEGORIES: category = "Diğer"
        owner = str(r.get("Harcama Sahibi", "Belirsiz"))
        if owner not in OWNERS: owner = "Belirsiz"
        row = {
            "ownerUid": uid, "date": dt, "calendarMonth": dt[:7], "month": month, "statementMonth": month,
            "amount": float(amount), "description": desc, "category": category,
            "merchant": str(r.get("İşletme", "")).strip()[:100] or clean_merchant(desc),
            "subcategory": str(r.get("Alt Kategori", "")).strip()[:100], "owner": owner,
            "card": card, "transactionType": str(r.get("İşlem Türü", "purchase")),
            "sourceRowId": source_id, "sourceFile": str(r.get("Dosya", "Axess geçmiş ekstreleri")),
            "reviewNotes": str(r.get("Kontrol", "") or ""), "amountConfidence": str(r.get("Tutar Güveni", "")),
            "createdAt": now_iso,
        }
        row["dedupeKey"] = stable_dedupe_key(row)
        doc_id = "hist_" + hashlib.sha256(f"{month}|{source_id}|{card}".encode("utf-8")).hexdigest()[:40]
        if doc_id in existing_ids or row["dedupeKey"] in existing_keys:
            continue
        writes.append({"create": {"name": f"{FS_ROOT}/transactions/{doc_id}", "fields": to_fs_fields(row)}})
        existing_ids.add(doc_id)
        existing_keys.add(row["dedupeKey"])
        transaction_count += 1

    # Firestore Commit accepts at most 500 writes per request. Create deterministic IDs
    # and a marker only after data batches finish, so an interrupted run can resume safely.
    for start in range(0, len(writes), 400):
        fs_request("POST", f"{FS_ROOT}:commit", json={"writes": writes[start:start+400]})
    marker_id = f"{uid}_{marker_key}"
    create_document("app_meta", {"ownerUid": uid, "key": marker_key, "savedTransactions": transaction_count,
                                  "completedAt": now_iso}, doc_id=marker_id)
    return {"status": "imported", "saved": transaction_count}


def default_budget(month_key):
    # Only the current known budget is prefilled. Earlier months stay blank until the user enters history.
    if month_key < "2026-10":
        return {"income": {}, "expenses": {}, "notes": "Geçmiş ay; gerçekleşen tutarları girin."}
    year, month = map(int, month_key.split("-"))
    emin = 85300 if (year, month) >= (2027, 4) else 71500
    colendi = 9103 if (year, month) <= (2027, 3) else 0
    return {
        "income": {"Sizin Maaş": 73800, "Eş Maaş": 73200, "Sizin Ek Ders": 19800, "Eş Ek Ders": 20800},
        "expenses": {"Akbank Kredi Kartı F": 47200, "Akbank A": 25300, "Ziraat A": 0, "İşbank F": 5750, "Eminevim": emin, "Colendi": colendi},
        "notes": "Başlangıç tutarlarıdır; her ayın gerçek tutarlarını ayrı kaydedin."
    }

# ---------- Transaction categories / merchant normalisation ----------
def norm(s):
    s = str(s or "").upper()
    replacements = str.maketrans({"İ":"I", "I":"I", "ı":"I", "Ş":"S", "ş":"S", "Ğ":"G", "ğ":"G", "Ü":"U", "ü":"U", "Ö":"O", "ö":"O", "Ç":"C", "ç":"C"})
    s = s.translate(replacements)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9]+", " ", s)).strip()


def merchant_info(description):
    n = norm(description)
    # Brand/chain mapping first, so Market can be broken down into A101, BİM, Migros, etc.
    rules = [
        (r"\bA101\b|A101KANUNI|A101 SOGUTLU", "Market", "A101", "Market zinciri"),
        (r"\bBIM\b|BIMAS|BIMH|BIMV|BIM P", "Market", "BİM", "Market zinciri"),
        (r"MIGROS|MJET|MONEY PAY|MIGROSONE", "Market", "Migros", "Migros / MJet"),
        (r"\bSOK\b|SOK IGL|SOK 11|SOK 35", "Market", "ŞOK", "Market zinciri"),
        (r"CARREFOUR", "Market", "CarrefourSA", "Market zinciri"),
        (r"DIA GROSS", "Market", "DİA Gross", "Gross market"),
        (r"HALKTAN", "Market", "Halktan", "Market zinciri"),
        (r"HAS GIDA|HASGIDA|OZPAS GIDA|FİLENOVA PARK|FILENOVA PARK", "Market", "Gıda marketi", "Market"),
        (r"SEYIDOGLU MANAV|MORSALKIM MANAV|SEBZE VE MEYVE|MANAV", "Market", "Manav", "Manav / sebze-meyve"),
        (r"EBEBEK", "Çocuk", "ebebek", "Çocuk mağazası"),
        (r"ECZANE|ECZANESI|PHARMACY|DEVA ECZ", "Sağlık", "Eczane", "Eczane"),
        (r"ARAS ELEKTRIK", "Faturalar", "Aras Elektrik", "Elektrik"),
        (r"DOGUGAZ|DOGU GAZ", "Faturalar", "Doğugaz", "Doğalgaz"),
        (r"TURKNET", "Faturalar", "TurkNet", "İnternet"),
        (r"VODAFONE", "Faturalar", "Vodafone", "Telefon"),
        (r"TURK TELEKOM|AVEA", "Faturalar", "Türk Telekom", "Telefon"),
        (r"SHELL", "Ulaşım", "Shell", "Akaryakıt"),
        (r"PETROL|OPET|PETROLOFISI|PETROL OFISI|ARIPAK AKARYAKIT|AGAYAR PETROL|ZARA PETROL|ISLEYENLER PETROL", "Ulaşım", "Akaryakıt istasyonu", "Akaryakıt"),
        (r"OBILET|OBILET BILISIM", "Ulaşım / Seyahat", "Obilet", "Otobüs bileti"),
        (r"TREN|OTOBUS|THY|PEGASUS|AIRLINES", "Ulaşım / Seyahat", "Ulaşım işletmesi", "Seyahat"),
        (r"LCW|LC WAIKIKI|LCWAIKIKI|LOWAIKIKI|LOVAIKIKI|LO WAIKIKI", "Giyim", "LC Waikiki", "Giyim"),
        (r"BOYNER", "Giyim", "Boyner", "Giyim"),
        (r"ZARA|FLO MAGAZACILIK|FLO MAGAZA", "Giyim", "Giyim mağazası", "Giyim"),
        (r"SOFUOGLU IC GIYIM", "Giyim", "Sofuoğlu İç Giyim", "Giyim"),
        (r"GRATIS", "Kişisel bakım", "Gratis", "Kozmetik"),
        (r"TRENDYOL", "Online alışveriş", "Trendyol", "E-ticaret"),
        (r"HEPSIPAY|HEPSIBU|HEPSIBURADA", "Online alışveriş", "Hepsiburada", "E-ticaret"),
        (r"AMAZON|IYZICO", "Online alışveriş", "Amazon", "E-ticaret"),
        (r"CICEKSEPETI", "Online alışveriş", "Çiçeksepeti", "E-ticaret"),
        (r"GOOGLE.*YOUTUBE|GOOGLE.*YOUTUBE", "Dijital abonelik / Oyun", "YouTube", "Abonelik"),
        (r"GOOGLE|CLASH OF CLANS", "Dijital abonelik / Oyun", "Google Play", "Dijital içerik"),
        (r"APPLE.COM|APPLE", "Dijital abonelik / Oyun", "Apple", "Dijital içerik"),
        (r"YEMEKSEPETI", "Restoran / Yemek", "Yemeksepeti", "Yemek siparişi"),
        (r"CAFE|COFFEE|KAHVE|KOKOREC|LOKANT|RESTORAN|RESTAURANT|PASTANE|PASTANESI|SIMIT SARAY|CIGKOFTE|CIGERC|MADO|DONDURMA|BURGER|PIZZA|LEZZET|BABA CAY|LUI COFFEE|VIENNA COFFEE|UNLU MAMUL|UNLUMAMUL|BOREK|KOFTECI|KEBAP|DURUM|ZURNA|BUFE|KASAP|KURUYEMIS|SOMUNCU BABA|QUESTAY CAFFEE", "Restoran / Yemek", "Yeme-İçme işletmesi", "Restoran / kafe / yemek"),
        (r"KIRTASIYE|BASIN YAYIN|KITAP|EGITIM VE UYGULAMA|AKADEMI", "Eğitim / Kırtasiye", "Kırtasiye / eğitim", "Eğitim"),
        (r"KUYUM|ALTIN|TAKI", "Kişisel alışveriş", "Kuyumcu", "Takı"),
        (r"MADAME COCO|EV TEKSTILI|EV GERECLERI", "Ev / Yaşam", "Ev ve yaşam mağazası", "Ev / yaşam"),
        (r"BURULAS", "Ulaşım", "BURULAŞ", "Toplu taşıma"),
        (r"ZIPIRLAND|FUNKY PARK|PARTI PARTY", "Çocuk", "Çocuk / eğlence", "Eğlence"),
        (r"GENC ELEKTRIK|UCLER ELEKTRONIK|FATIH HIRDAVAT", "Ev / Yaşam", "Elektrik / hırdavat", "Ev / bakım"),
        (r"RUS PAZARI", "Market", "Rus Pazarı", "Yerel market"),
        (r"GOZDE KURUYEMIS|SENGUL ARMADA KURUYEMIS", "Market", "Kuruyemişçi", "Kuruyemiş"),
        (r"OTO|OTOMOTIV|LASTIK|ARAC|BAKIM ONAR", "Ulaşım", "Otomotiv / servis", "Araç bakım"),
        (r"VERGI DAIRE|TAPU VE KADASTRO|TAPU HARCI", "Resmi ödeme", "Vergi / tapu", "Resmi ödeme"),
        (r"FATURA ODEME UCRETI|FATURA ODEME UCETI|ODEME UCRETI", "Bankacılık ücreti", "Banka ücreti", "Ücret"),
        (r"GIDA|MARKET|SUPERMARKET|BAKKAL|GROSS|PAZARI", "Market", "Yerel market", "Market"),
    ]
    for pattern, category, merchant, subcategory in rules:
        if re.search(pattern, n):
            return category, merchant, subcategory, "Yüksek"
    cleaned = clean_merchant(description)
    return "Diğer", cleaned, "İşletme kontrolü", "Kontrol"


def clean_merchant(description):
    s = str(description or "")
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"\b(?:IGDIR|GDIR|BURSA|ISTANBUL|ERZURUM|SIVAS|VAN|AGRI|TOKAT|TUR|TR)\b", "", s, flags=re.I)
    s = re.sub(r"\b\d{5,}\b", "", s)
    s = re.sub(r"\s+", " ", s).strip(" -_/.,")
    return s[:75] or "Bilinmeyen işletme"


def parse_amount_token(token):
    raw = str(token or "").strip().replace("(-)", "").rstrip("-)")
    if not raw:
        return None, "Yok"
    if re.fullmatch(r"\d{1,3},\d{3}\d{2}", raw):
        digits = raw.replace(",", "")
        try:
            return float(f"{int(digits[:-2])}.{digits[-2:]}"), "Kontrol"
        except ValueError:
            return None, "Yok"
    if "," in raw and "." in raw:
        try: return float(raw.replace(",", "")), "Yüksek"
        except ValueError: pass
    if "," in raw and "." not in raw:
        if re.search(r",\d{2}$", raw):
            try: return float(raw.replace(".", "").replace(",", ".")), "Orta"
            except ValueError: pass
        try: return float(raw.replace(",", "")), "Orta"
        except ValueError: pass
    if "." in raw:
        try: return float(raw), "Yüksek"
        except ValueError: pass
    digits = re.sub(r"\D", "", raw)
    if len(digits) >= 3:
        try: return float(f"{int(digits[:-2])}.{digits[-2:]}"), "Kontrol"
        except ValueError: pass
    return None, "Yok"


def extract_current_amount(rest):
    # Current installment is the first amount after the installment marker, not the original principal.
    installment_pos = re.search(r"taksit(?:\s*-\s*iade|-iade)?\s+(.+)$", rest, flags=re.I)
    if installment_pos:
        tail = installment_pos.group(1)
        tokens = re.findall(AMOUNT_TOKEN_RE, tail)
        formatted = [tok for tok in tokens if "." in tok or re.search(r",\d{2}$", tok)]
        chosen = formatted[0] if formatted else (tokens[0] if tokens else None)
        if chosen:
            return parse_amount_token(chosen)[0], chosen, parse_amount_token(chosen)[1]
    tokens = re.findall(AMOUNT_TOKEN_RE, rest)
    if not tokens:
        return None, "", "Yok"
    # Tesseract sometimes reads the separate chip-points column after the amount; ignore a tiny trailing value.
    if len(tokens) >= 2:
        last_value, _ = parse_amount_token(tokens[-1])
        prev_value, _ = parse_amount_token(tokens[-2])
        if last_value is not None and prev_value is not None and last_value <= 2.0 and prev_value >= 10.0:
            tokens = tokens[:-1]
    token = tokens[-1]
    amount, confidence = parse_amount_token(token)
    return amount, token, confidence


def should_exclude_statement_line(description):
    n = norm(description)
    # Card payments and loyalty-points adjustments are not new merchant spending.
    if ("TESEKKUR" in n and ("INTERNET" in n or "ODEME" in n or "ODEMEN" in n)):
        return "Kredi kartı borcu ödemesi (harcama değil)"
    if "CHIP PARA ILE ODEME" in n or "EKSIK KALAN CHIP PARA" in n:
        return "Chip-para düzeltmesi (harcama değil)"
    if "TAPU VE KADASTRO" in n or "TAPU HARCI" in n or "TAPU HARCLARI" in n:
        return "Tapu harcı (kullanıcı talebiyle hariç)"
    if "VERGI DAIRE" in n and "TAKSIT" in n and ("83 600" in n or "25 000" in n):
        return "Yüksek tutarlı vergi dairesi taksiti (tapu harcı olarak hariç)"
    return ""


def parse_statement_pdf(pdf_bytes, filename, statement_month_override=None, card_name="Axess Platinum"):
    try:
        import fitz
        import pytesseract
        from PIL import Image
    except Exception as exc:
        raise RuntimeError("PDF OCR bileşenleri eksik. packages.txt ve requirements.txt dağıtıma eklenmeli.") from exc
    statement_month = statement_month_override
    stem_match = re.search(r"(\d{2})[._-](\d{2})[._-](20\d{2})", filename)
    if not statement_month and stem_match:
        statement_month = f"{stem_match.group(3)}-{stem_match.group(2)}"
    if not statement_month:
        statement_month = datetime.today().strftime("%Y-%m")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    rows, excluded = [], []
    virtual_card = False
    row_num = 0
    for page_index in range(min(3, len(doc))):
        page = doc[page_index]
        pix = page.get_pixmap(matrix=fitz.Matrix(2.4, 2.4), alpha=False)
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        text = pytesseract.image_to_string(image, lang="tur+eng", config="--psm 6")
        for line in text.splitlines():
            if "SANAL KART HARCAMALARI" in norm(line):
                virtual_card = True
                continue
            match = re.match(r"^\s*(\d{1,2}/\d{1,2}/20\d{2})\s+(.+)$", line)
            if not match:
                continue
            row_num += 1
            raw_date, rest = match.group(1), match.group(2).strip()
            exclusion = should_exclude_statement_line(rest)
            # OCR is not reliable for all merchant-name fields; retain the source line and allow review before save.
            try:
                day, month, year = [int(x) for x in raw_date.split("/")]
                transaction_date = date(year, month, day).isoformat()
            except Exception:
                continue
            source_row_id = f"{filename}|p{page_index+1}|r{row_num}"
            if exclusion:
                excluded.append({"Dosya": filename, "Ekstre Ayı": statement_month, "Tarih": transaction_date, "Açıklama": rest, "Hariç Tutma Nedeni": exclusion})
                continue
            amount, amount_raw, amount_confidence = extract_current_amount(rest)
            if amount is None:
                excluded.append({"Dosya": filename, "Ekstre Ayı": statement_month, "Tarih": transaction_date, "Açıklama": rest, "Hariç Tutma Nedeni": "Tutar okunamadı; inceleme gerekli"})
                continue
            is_refund = "IADE" in norm(rest) or "(-)" in rest or "(-}" in rest
            if is_refund:
                amount = -abs(amount)
            category, merchant, subcategory, category_conf = merchant_info(rest)
            transaction_type = "refund" if is_refund else ("installment" if "TAKSIT" in norm(rest) else ("fee" if "FATURA ODEME UCRETI" in norm(rest) else "purchase"))
            review_notes = []
            if amount_confidence == "Kontrol": review_notes.append("OCR tutarında noktalama eksik; kontrol et")
            if category_conf == "Kontrol": review_notes.append("Kategori/işletme sınıflandırması kontrolü")
            rows.append({
                "Ekstre Ayı": statement_month,
                "İşlem Tarihi": transaction_date,
                "Açıklama": rest,
                "Tutar (TL)": round(float(amount), 2),
                "Ana Kategori": category,
                "İşletme": merchant,
                "Alt Kategori": subcategory,
                "Harcama Sahibi": "Belirsiz",
                "Kart": card_name + (" - Sanal" if virtual_card else " - Fiziksel"),
                "İşlem Türü": transaction_type,
                "Tutar Güveni": amount_confidence,
                "Kontrol": "; ".join(review_notes),
                "Dahil": amount_confidence != "Kontrol",
                "sourceRowId": source_row_id,
                "Dosya": filename,
            })
    return pd.DataFrame(rows), pd.DataFrame(excluded)


def parse_spreadsheet(uploaded, default_month):
    if uploaded.name.lower().endswith(".csv"):
        raw = pd.read_csv(uploaded)
    else:
        raw = pd.read_excel(uploaded)
    # Prepared import workbook / canonical headers.
    date_col = next((c for c in ["İşlem Tarihi", "Tarih", "date"] if c in raw.columns), None)
    desc_col = next((c for c in ["Açıklama", "description", "Dönem İçi İşlemler"] if c in raw.columns), None)
    amount_col = next((c for c in ["Tutar (TL)", "Tutar", "amount"] if c in raw.columns), None)
    if not date_col or not desc_col or not amount_col:
        raise ValueError("Dosyada tarih, açıklama ve tutar sütunları bulunamadı. Hazırlanmış aktarım şablonunu kullanın.")
    out = pd.DataFrame()
    out["İşlem Tarihi"] = raw[date_col].map(parse_date)
    out["Açıklama"] = raw[desc_col].astype(str)
    out["Tutar (TL)"] = raw[amount_col].map(parse_amount_generic)
    out["Ekstre Ayı"] = raw["Ekstre Ayı"].astype(str) if "Ekstre Ayı" in raw.columns else default_month
    out["Ana Kategori"] = raw["Ana Kategori"] if "Ana Kategori" in raw.columns else "Diğer"
    out["İşletme"] = raw["İşletme"] if "İşletme" in raw.columns else out["Açıklama"].map(lambda x: merchant_info(x)[1])
    out["Alt Kategori"] = raw["Alt Kategori"] if "Alt Kategori" in raw.columns else "İşletme kontrolü"
    out["Harcama Sahibi"] = raw["Harcama Sahibi"] if "Harcama Sahibi" in raw.columns else "Belirsiz"
    out["Kart"] = raw["Kart"] if "Kart" in raw.columns else "Axess Platinum"
    out["İşlem Türü"] = raw["İşlem Türü"] if "İşlem Türü" in raw.columns else "purchase"
    out["Tutar Güveni"] = raw["Tutar Güveni"] if "Tutar Güveni" in raw.columns else "Kontrol et"
    out["Kontrol"] = raw["Kontrol"] if "Kontrol" in raw.columns else ""
    out["Dahil"] = raw["Dahil"] if "Dahil" in raw.columns else True
    out["sourceRowId"] = raw["sourceRowId"] if "sourceRowId" in raw.columns else [f"{uploaded.name}|row{i}" for i in range(len(raw))]
    out["Dosya"] = uploaded.name
    out = out.dropna(subset=["İşlem Tarihi", "Tutar (TL)"]).reset_index(drop=True)
    return out


def parse_date(value):
    if pd.isna(value): return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return pd.Timestamp(value).date().isoformat()
    text = str(value).strip()
    for dayfirst in (True, False):
        try: return pd.to_datetime(text, dayfirst=dayfirst, errors="raise").date().isoformat()
        except Exception: pass
    return None


def parse_amount_generic(value):
    if pd.isna(value): return None
    if isinstance(value, (int, float)): return float(value)
    s = str(value).strip().replace("TL", "").replace("₺", "").replace(" ", "")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else: s = s.replace(",", "")
    elif "," in s:
        s = s.replace(".", "").replace(",", ".")
    try: return float(s)
    except Exception: return None


def call_openai_json(prompt, model=None):
    api_key = str(AI.get("api_key", "")).strip()
    if not api_key:
        raise ValueError("Yapay zekâ API anahtarı eklenmemiş. Secrets'e [openai] api_key ekleyin ya da kurallı sınıflandırmayla devam edin.")
    model = model or str(AI.get("model", "gpt-4o-mini"))
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "temperature": 0, "response_format": {"type": "json_object"}, "messages": [
            {"role": "system", "content": "Finans ekstresi satırlarını dikkatle sınıflandır. Tutar veya tarih uydurma. Market altlarında A101, BİM, Migros, ŞOK gibi işletmeleri ayrı tut. Belirsizse Diğer ve düşük güven seç."},
            {"role": "user", "content": prompt},
        ]}, timeout=90,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Yapay zekâ API hatası ({response.status_code}): {response.text[:350]}")
    return json.loads(response.json()["choices"][0]["message"]["content"])


def ai_classify_dataframe(df):
    result = df.copy()
    # Keep requests modest; descriptions contain only merchant transaction rows, not account/profile details.
    for start in range(0, len(result), 50):
        part = result.iloc[start:start+50]
        rows = []
        for local_i, (_, r) in enumerate(part.iterrows()):
            rows.append({"index": local_i, "date": str(r.get("İşlem Tarihi", "")), "description": str(r.get("Açıklama", ""))[:130], "amount": float(r.get("Tutar (TL)", 0) or 0)})
        prompt = (
            "İşlemleri kategorize et. Yalnızca şu ana kategorilerden birini kullan: " + ", ".join(CATEGORIES) + ". "
            "Her satır için işletme adını normalleştir (ör. A101, BİM, Migros, ŞOK, Shell, TurkNet), alt kategoriyi belirt. "
            "Harcama sahibini açıklamadan çıkaramıyorsan Belirsiz yaz. JSON biçimi: {\"transactions\":[{\"index\":0,\"category\":\"Market\",\"merchant\":\"A101\",\"subcategory\":\"Market zinciri\",\"owner\":\"Belirsiz\",\"confidence\":\"yüksek|orta|düşük\"}]}. Girdiler: "
            + json.dumps(rows, ensure_ascii=False)
        )
        api_result = call_openai_json(prompt)
        mapping = {int(x.get("index", -1)): x for x in api_result.get("transactions", []) if isinstance(x, dict)}
        for local_i, idx in enumerate(part.index):
            item = mapping.get(local_i, {})
            category = item.get("category", result.at[idx, "Ana Kategori"])
            if category not in CATEGORIES: category = "Diğer"
            result.at[idx, "Ana Kategori"] = category
            if item.get("merchant"): result.at[idx, "İşletme"] = str(item["merchant"])[:80]
            if item.get("subcategory"): result.at[idx, "Alt Kategori"] = str(item["subcategory"])[:80]
            owner = item.get("owner", result.at[idx, "Harcama Sahibi"])
            if owner in OWNERS: result.at[idx, "Harcama Sahibi"] = owner
            confidence = item.get("confidence", "orta")
            old = str(result.at[idx, "Kontrol"] or "")
            if confidence == "düşük": result.at[idx, "Kontrol"] = (old + "; AI güveni düşük — kontrol et").strip("; ")
    return result


def login_view():
    st.markdown("<div style='max-width:680px;margin:9vh auto 0 auto;'>", unsafe_allow_html=True)
    st.markdown("<div class='app-hero'><div class='eyebrow'>AİLE FİNANS PANELİ</div><h1>💰 Aile Bütçe Takip</h1><p>Gelir, borç ve ekstrelerinize güvenli giriş yapın.</p></div>", unsafe_allow_html=True)
    with st.form("login_form"):
        email = st.text_input("E-posta", autocomplete="email")
        password = st.text_input("Şifre", type="password", autocomplete="current-password")
        remember_device = st.checkbox("Bu cihazda oturumu açık tut (1 yıl)", value=True)
        submit = st.form_submit_button("Güvenli giriş", width="stretch", type="primary")
    if submit:
        if not API_KEY or not PROJECT_ID:
            st.error("Firebase yapılandırması eksik. Streamlit Settings → Secrets bölümünü kontrol edin.")
        elif not email.strip() or not password:
            st.warning("E-posta ve şifre girin.")
        else:
            try:
                login(email.strip(), password, remember_device=remember_device)
                st.rerun()
            except Exception as exc:
                st.error(f"Giriş başarısız: {exc}")
    st.caption("Hesap oluşturma uygulama içinden kapalıdır; kullanıcıları Firebase Authentication konsolundan yönetebilirsiniz.")
    st.markdown("</div>", unsafe_allow_html=True)

# ---------- App boot ----------
if not API_KEY or not PROJECT_ID:
    st.title("💠 Aile Bütçe Merkezi")
    st.error("Firebase ayarları eksik. Streamlit Cloud → App settings → Secrets alanına Firebase proje ID'sini ve Web API anahtarını ekleyin.")
    st.code('[firebase]\nproject_id = "aile-butce-takip-14da8"\napi_key = "FIREBASE_WEB_APP_API_KEY"', language="toml")
    st.stop()

if not current_auth():
    restore_auth_from_cookie()

if not current_auth():
    login_view()
    st.stop()

auth = current_auth()
uid = auth["uid"]
# Geçmişte sağlanan 6 Axess ekstresi ilk girişte otomatik yüklenir; kullanıcıdan yeniden dosya seçmesi istenmez.
if not st.session_state.get("historical_seed_checked"):
    try:
        seed_result = seed_historical_statements(uid)
        st.session_state["historical_seed_checked"] = True
        if seed_result.get("status") == "imported" and seed_result.get("saved", 0):
            st.toast(f"Geçmiş ekstreler yüklendi: {seed_result['saved']} işlem.", icon="✅")
    except Exception as seed_exc:
        # The app can still show the underlying Firebase error below; don't hide it.
        st.session_state["historical_seed_error"] = str(seed_exc)
now = today_tr()
month_options = [f"{year}-{month:02d}" for year in range(2026, 2031) for month in range(1, 13)]
current_month = now.strftime("%Y-%m")
PAGE_HOME = "🏠 Genel Bakış"
PAGE_BUDGET = "🗓️ Bütçe ve Borçlar"
PAGE_IMPORT = "📥 Ekstre İçe Aktar"
PAGE_CARDS = "💳 Kartlar ve Ekstreler"
PAGE_ANALYSIS = "🔎 Harcama Analizi"
PAGE_COMPARE = "📊 Ay Karşılaştırma"
PAGE_DATA = "⚙️ Veri Yönetimi"
VALID_PAGES = {PAGE_HOME, PAGE_BUDGET, PAGE_IMPORT, PAGE_CARDS, PAGE_ANALYSIS, PAGE_COMPARE, PAGE_DATA}
if st.session_state.get("app_page") not in VALID_PAGES:
    st.session_state["app_page"] = PAGE_HOME
with st.sidebar:
    st.markdown("## 💠 Aile Bütçe")
    st.markdown(f'<span class="pill">● Güvenli oturum</span><div class="small-muted" style="margin-top:8px">{auth.get("email", "Giriş yapıldı")}</div>', unsafe_allow_html=True)
    st.divider()
    if st.button("🏠 Ana sayfa", width="stretch", type="primary" if st.session_state["app_page"] == PAGE_HOME else "secondary"):
        st.session_state["app_page"] = PAGE_HOME
        st.rerun()
    selected_month = st.selectbox("Aktif dönem", month_options, index=month_options.index(current_month) if current_month in month_options else 9,
                                  format_func=lambda x: month_label_tr(x))
    st.caption("Modüller ana sayfadaki kartlardan açılır.")
    st.divider()
    if st.button("↪ Güvenli çıkış", width="stretch"):
        logout()
page = st.session_state["app_page"]

try:
    budget = get_budget(uid, selected_month) or default_budget(selected_month)
    tx_rows = load_transactions(uid, selected_month)
except Exception as exc:
    st.error(f"Firebase'e erişim başarısız: {exc}")
    st.info("Bu sürüm Firestore sorgularında yalnızca ownerUid alanını sunucu tarafında filtreler; böylece composite index hatası oluşmamalıdır. Kurallar yayımlandı mı ve API anahtarı doğru mu kontrol edin.")
    st.stop()

income = budget.get("income", {}) or {}
expenses = dict(budget.get("expenses", {}) or {})
# Eski isimleri yeni kart etiketlerine taşı; tutarlar kaybolmaz ve kullanıcı kaydettiğinde yeni adlarla saklanır.
LEGACY_EXPENSE_NAMES = {
    "Sizin Akbank": "Akbank Kredi Kartı F",
    "Eş Akbank": "Akbank A",
    "İş Bankası": "İşbank F",
    "Ziraat": "Ziraat A",
}
for old_name, new_name in LEGACY_EXPENSE_NAMES.items():
    if old_name in expenses:
        old_amount = expenses.pop(old_name)
        expenses.setdefault(new_name, old_amount)
# Kartlar önce, sabit borçlar sonra gösterilsin; tutarların kendisi değişmez.
CARD_EXPENSE_NAMES = ["Akbank Kredi Kartı F", "Akbank A", "Ziraat A", "İşbank F"]
FIXED_EXPENSE_NAMES = ["Eminevim", "Colendi"]
total_income = sum(float(v or 0) for v in income.values())
total_expenses = sum(float(v or 0) for v in expenses.values())
net_cash = total_income - total_expenses
month_label = month_label_tr(selected_month)

if page == PAGE_HOME:
    title_hero(month_label, "Ailenin bütçesini, kart ekstrelerini ve harcamalarını tek ekrandan yönet.")
    txdf = pd.DataFrame(tx_rows)
    statement_spend = 0.0
    if not txdf.empty and "amount" in txdf:
        txdf["amount"] = pd.to_numeric(txdf["amount"], errors="coerce").fillna(0)
        statement_spend = txdf[~txdf.get("transactionType", pd.Series(index=txdf.index, dtype=str)).astype(str).str.lower().isin(["payment", "card_payment", "kart ödemesi"])] ["amount"].sum()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💚 Toplam gelir", money(total_income))
    c2.metric("🧾 Planlanan ödemeler", money(total_expenses))
    c3.metric("✨ Planlanan kalan", money(net_cash))
    c4.metric("💳 Kart harcaması", money(statement_spend))

    st.markdown("### ⚡ Hızlı tutar kaydı")
    quick_cards = safe_load_collection(uid, "cards")
    quick_card_names = [str(c.get("name", "")).strip() for c in quick_cards if str(c.get("name", "")).strip()]
    # Cash is not a selectable pseudo-card. Most quick entries are aggregate totals.
    default_quick_cards = ["Akbank Kredi Kartı F", "Akbank A", "Ziraat A", "İşbank F"]
    quick_card_options = list(dict.fromkeys(default_quick_cards + quick_card_names))
    general_total_card = "Genel toplam (kart ayrımı yok)"

    # Card choice is remembered in Firestore and remains selected until the user changes it.
    preference_key = "quick_card_preference"
    if not st.session_state.get("quick_card_preference_loaded"):
        try:
            preference_doc = get_document("app_meta", f"{uid}_quick_card_preference")
            saved_card = str((preference_doc or {}).get("card", quick_card_options[0] if quick_card_options else "Akbank Kredi Kartı F"))
            if saved_card in {"Nakit / banka kartı", general_total_card}:
                saved_card = quick_card_options[0] if quick_card_options else "Akbank Kredi Kartı F"
            if saved_card and saved_card not in quick_card_options:
                quick_card_options.append(saved_card)
            st.session_state[preference_key] = saved_card
        except Exception:
            st.session_state[preference_key] = quick_card_options[0]
        st.session_state["quick_card_preference_loaded"] = True

    def persist_quick_card_preference():
        selected_card = st.session_state.get(preference_key, quick_card_options[0] if quick_card_options else "Akbank Kredi Kartı F")
        doc_id = f"{uid}_quick_card_preference"
        payload = {"ownerUid": uid, "key": "quick_card_preference", "card": selected_card,
                   "updatedAt": datetime.utcnow().isoformat(timespec="seconds")}
        try:
            existing_preference = get_document("app_meta", doc_id)
            if existing_preference:
                write_document("app_meta", doc_id, payload)
            else:
                create_document("app_meta", payload, doc_id=doc_id)
            st.session_state.pop("quick_card_preference_error", None)
        except Exception as exc:
            st.session_state["quick_card_preference_error"] = str(exc)

    quick_mode = st.radio(
        "Kayıt biçimi",
        ["Toplam tutar (genel)", "Kart / hesap toplamı"],
        horizontal=True,
        index=0,
        key="quick_record_mode",
        help="Genel toplamı tek kayıt olarak giriyorsan kart ayrımı yapılmaz. Belirli bir karta ait tutarsa ikinci seçeneği kullan.",
    )
    quick_a, quick_b = st.columns([1, 1.5])
    with quick_a:
        quick_amount = st.number_input("Tutar (TL)", min_value=0.01, value=100.0, step=10.0,
                                       format="%.2f", key="quick_amount_home")
    with quick_b:
        if quick_mode == "Kart / hesap toplamı":
            quick_card = st.selectbox("Kart", quick_card_options, key=preference_key,
                                      on_change=persist_quick_card_preference)
        else:
            quick_card = general_total_card
            st.text_input("Kart", value="Genel toplam — kart ayrımı yok", disabled=True, key="quick_general_total_label")
    st.caption("Genel toplam kayıtları toplam harcamaya eklenir; işletme bazlı ekstre ayrıntısı yerine geçmez. Aynı tutar ayrıntılı ekstrede de varsa iki kez sayılmaması için yalnızca bir yöntemi kullan.")

    with st.form("quick_amount_home_form", border=True):
        quick_save = st.form_submit_button("➕ Bugünün tutarını kaydet", type="primary", width="stretch")
    if quick_save:
        today = today_tr()
        is_general_total = quick_mode == "Toplam tutar (genel)"
        row = {
            "date": today.isoformat(), "calendarMonth": today.strftime("%Y-%m"), "month": today.strftime("%Y-%m"),
            "statementMonth": today.strftime("%Y-%m"), "amount": float(quick_amount),
            "description": "Genel toplam harcama" if is_general_total else "Kart toplamı — ayrıntısız kayıt",
            "category": "Toplam harcama" if is_general_total else "Kart toplamı",
            "merchant": "Genel toplam" if is_general_total else "Kart toplamı (ayrıntısız)",
            "subcategory": "Toplu tutar kaydı" if is_general_total else "Kart toplamı kaydı",
            "owner": "Belirsiz", "card": quick_card,
            "transactionType": "quick_total" if is_general_total else "quick_card_total", "sourceRowId": "",
        }
        try:
            added = add_transaction(uid, row)
            if added:
                st.success(f"{money(quick_amount)} tutar bugünün tarihiyle ({today.strftime('%d.%m.%Y')}) kaydedildi.")
            else:
                st.warning("Aynı kayıt zaten mevcut.")
            st.rerun()
        except Exception as exc:
            st.error(f"Tutar kaydedilemedi: {exc}")
    if st.session_state.get("quick_card_preference_error"):
        st.caption("Kart tercihi bu oturumda korundu ancak kalıcı kaydedilemedi. Firestore Rules içinde app_meta koleksiyonuna erişim iznini kontrol edin.")
    left, right = st.columns([1, 1.15], gap="large")
    with left:
        section("💰", "Gelir ve ödeme planı", "Aktif ayın özeti")
        all_items = [{"Tür": "Gelir", "Kalem": k, "Tutar (TL)": float(v or 0)} for k,v in income.items()]
        all_items += [{"Tür": "Ödeme", "Kalem": k, "Tutar (TL)": float(v or 0)} for k,v in expenses.items()]
        if all_items:
            bd = pd.DataFrame(all_items)
            fig = px.bar(bd, x="Tutar (TL)", y="Kalem", color="Tür", orientation="h", barmode="group", template="plotly_dark", height=300)
            fig.update_layout(margin=dict(l=0,r=10,t=5,b=5), legend_title_text="", xaxis_title="TL", yaxis_title="", font=dict(size=11))
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Bu ayın bütçesini Bütçe ve Borçlar bölümünden girebilirsin.")
    with right:
        section("🛍️", "Kategori özeti", "Ekstrelerden çıkarılan işlemler")
        if not txdf.empty and "category" in txdf:
            filtered = txdf[~txdf.get("transactionType", pd.Series(index=txdf.index, dtype=str)).astype(str).str.lower().isin(["payment", "card_payment", "kart ödemesi"])].copy()
            by_cat = filtered.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False).head(7)
            fig = px.bar(by_cat, x="amount", y="category", orientation="h", template="plotly_dark", color="amount", color_continuous_scale=["#4263eb", "#57e3c2"], height=300)
            fig.update_layout(margin=dict(l=0,r=5,t=5,b=5), coloraxis_showscale=False, xaxis_title="TL", yaxis_title="", yaxis={"categoryorder":"total ascending"}, font=dict(size=11))
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Ekstrelerini içe aktardığında kategori özeti burada oluşacak.")

    section("🧭", "İşlem defteri", f"{month_label} · {len(tx_rows)} kayıt")
    if not txdf.empty:
        f1, f2 = st.columns([1, 1])
        categories = ["Tümü"] + sorted(txdf.get("category", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
        with f1:
            filter_category = st.selectbox("Kategori filtresi", categories, key="home_tx_category")
        with f2:
            filter_owner = st.selectbox("Harcama sahibi", ["Tümü"] + OWNERS, key="home_tx_owner")
        viewdf = txdf.copy()
        if filter_category != "Tümü": viewdf = viewdf[viewdf["category"] == filter_category]
        if filter_owner != "Tümü" and "owner" in viewdf: viewdf = viewdf[viewdf["owner"] == filter_owner]
        display_map = {"date":"Tarih", "description":"Açıklama", "category":"Kategori", "merchant":"İşletme", "subcategory":"Alt kategori", "amount":"Tutar (TL)", "owner":"Harcama sahibi", "card":"Kart", "transactionType":"İşlem türü"}
        visible = [c for c in display_map if c in viewdf.columns]
        st.dataframe(viewdf[visible].rename(columns=display_map), hide_index=True, width="stretch", height=300)
        st.download_button("⬇️ Bu ayın işlem defterini indir", viewdf[visible].rename(columns=display_map).to_csv(index=False).encode("utf-8-sig"), f"islem_defteri_{selected_month}.csv", "text/csv")
    else:
        st.info("Bu dönemde kayıt yok. Ekstre yükleyebilir veya yukarıdan hızlı nakit gideri ekleyebilirsin.")

    st.markdown("---")
    section("🧩", "Modüller", "İstediğin bölüme dokunarak geç. Soldaki menü sade tutuldu.")
    module_cards = [
        ("🗓️ Bütçe ve Borçlar", PAGE_BUDGET, "Aylık gelir, ödeme tutarları, yeni borç kalemleri ve ödendi/bekliyor durumu."),
        ("📥 Ekstre İçe Aktar", PAGE_IMPORT, "PDF, CSV ve Excel ekstrelerini analiz et, doğrula ve kaydet."),
        ("💳 Kartlar ve Ekstreler", PAGE_CARDS, "Senin ve eşinin kartlarını ayrı tut; her kartın ekstresini kapat."),
        ("🔎 Harcama Analizi", PAGE_ANALYSIS, "Kategori, işletme, kişi ve kart bazında ayrıntılı inceleme."),
        ("📊 Ay Karşılaştırma", PAGE_COMPARE, "Geçmiş ayların bütçelerini ve kategori harcamalarını kıyasla."),
        ("⚙️ Veri Yönetimi", PAGE_DATA, "Kayıtlarını dışa aktar ve yedek al.")
    ]
    for row_start in range(0, len(module_cards), 3):
        cols = st.columns(3, gap="medium")
        for col, module in zip(cols, module_cards[row_start:row_start+3]):
            title, key, desc = module
            with col:
                with st.container(border=True):
                    st.markdown(f"#### {title}")
                    st.caption(desc)
                    if st.button("Aç →", key=f"home_open_{key}", width="stretch"):
                        st.session_state["app_page"] = key
                        st.rerun()

elif page == PAGE_BUDGET:
    title_hero(month_label, "Gelirini, aylık borç tutarlarını ve ödeme durumunu tek ekrandan yönet.")
    if selected_month < "2026-10":
        st.info("Bu geçmiş ay için bütçe kaydı yoksa sıfırdan girebilirsin. Başka ayların kayıtları değişmez.")
    with st.form("combined_budget_form", border=True):
        section("💰", "Gelirler", "Aylık gelirleri gir")
        new_income = dict(income)
        existing_income = list(income.items())
        for i, (name, amount) in enumerate(existing_income):
            cols = st.columns([2, 1])
            with cols[0]:
                new_income[name] = st.number_input(name, min_value=0.0, value=float(amount or 0), step=100.0, key=f"inc_{selected_month}_{name}")
            with cols[1]:
                st.caption("TL / ay")
        add_income_name = st.text_input("➕ Yeni gelir kalemi", placeholder="Örn. sınav görevi")
        add_income_value = st.number_input("Yeni gelir tutarı (TL)", min_value=0.0, step=100.0, key="add_income_amount_combined")
        st.markdown("---")
        section("🧾", "Borçlar ve aylık ödemeler", "Kart borçları solda, sabit ödemeler sağda. F = Fatih, A = Asiye.")
        new_expenses = dict(expenses)
        expense_left, expense_right = st.columns(2, gap="large")
        with expense_left:
            st.markdown("#### 💳 Kredi kartları")
            for name in CARD_EXPENSE_NAMES:
                amount = float(expenses.get(name, 0) or 0)
                new_expenses[name] = st.number_input(
                    f"{name} (TL)", min_value=0.0, value=amount, step=100.0,
                    key=f"exp_{selected_month}_{name}"
                )
        with expense_right:
            st.markdown("#### 🏠 Sabit borçlar")
            for name in FIXED_EXPENSE_NAMES:
                amount = float(expenses.get(name, 0) or 0)
                new_expenses[name] = st.number_input(
                    f"{name} (TL)", min_value=0.0, value=amount, step=100.0,
                    key=f"exp_{selected_month}_{name}"
                )
            other_expenses = [(name, amount) for name, amount in expenses.items()
                              if name not in CARD_EXPENSE_NAMES and name not in FIXED_EXPENSE_NAMES]
            if other_expenses:
                st.markdown("#### 📌 Diğer giderler")
                for name, amount in other_expenses:
                    new_expenses[name] = st.number_input(
                        f"{name} (TL)", min_value=0.0, value=float(amount or 0), step=100.0,
                        key=f"exp_{selected_month}_{name}"
                    )
        with st.expander("➕ Yeni borç / gider kalemi ekle", expanded=False):
            add_expense_name = st.text_input("Kalem adı", placeholder="Örn. yeni kredi kartı veya taksit")
            add_expense_value = st.number_input("Aylık tutar (TL)", min_value=0.0, step=100.0, key="add_expense_amount_combined")
        notes = st.text_area("Ay notu", value=budget.get("notes", ""), placeholder="İsteğe bağlı ay notu")
        submitted = st.form_submit_button("💾 Bu ayın bütçesini kaydet", type="primary", width="stretch")
    if submitted:
        if add_income_name.strip():
            new_income[add_income_name.strip()] = add_income_value
        if add_expense_name.strip():
            if add_expense_name.strip() in new_expenses:
                st.warning("Bu isimde bir kalem var; mevcut kalemi güncelle.")
            else:
                new_expenses[add_expense_name.strip()] = add_expense_value
        try:
            # Eski debtMeta verisi korunur, artık ödeme durumu/sorumlu sorulmaz.
            save_budget(uid, selected_month, {"income": new_income, "expenses": new_expenses, "notes": notes,
                                              "debtMeta": budget.get("debtMeta", {}) or {}})
            st.success(f"{month_label} bütçesi kaydedildi.")
            st.rerun()
        except Exception as exc:
            st.error(f"Kaydedilemedi: {exc}")
    ci1, ci2, ci3 = st.columns(3)
    ci1.metric("Toplam gelir", money(total_income))
    ci2.metric("Planlanan ödeme", money(total_expenses))
    ci3.metric("Kalan planlanan nakit", money(net_cash))
    st.caption("Bu ekran Genel Bakış'taki aylık tutarlarla aynı kaydı kullanır; ayrı bir Borçlar ve Ödemeler modülü yoktur. Geçmiş ayları seçerek geriye dönük bütçe girebilirsin.")

elif page == "📥 Ekstre İçe Aktar":
    title_hero("Ekstre merkezi", "Mayıs–Ekim 2026 geçmiş Axess işlemleri ilk girişte otomatik yüklenir; yeni ekstreleri buradan ekleyebilirsin.")
    st.warning("PDF ekstreleri OCR ile okunur. Tutarı otomatik doğrulanamayan satırlar varsayılan olarak işaretli değildir; kontrol etmeden içe aktarma. Tapu harçları, bilinen vergi dairesi taksitleri, kart borcu ödemeleri ve chip-para düzeltmeleri otomatik hariç bırakılır.")
    col1, col2 = st.columns([1.1, 1])
    registered_cards_for_import = safe_load_collection(uid, "cards")
    registered_names_for_import = [str(c.get("name", "")).strip() for c in registered_cards_for_import if c.get("name")]
    with col1:
        statement_month_fallback = st.selectbox("Dosya adından dönem bulunamazsa kullanılacak ekstre ayı", month_options, index=month_options.index(current_month))
        if registered_names_for_import:
            card_choice_import = st.selectbox("Ekstre hangi karta ait?", registered_names_for_import + ["➕ Listede olmayan kart"], key="import_card_choice")
            if card_choice_import == "➕ Listede olmayan kart":
                card_name = st.text_input("Yeni kartın adı (Kartlar ve Ekstreler bölümünden de ekleyebilirsin)", value="Axess Platinum")
            else:
                card_name = card_choice_import
        else:
            card_name = st.text_input("Kart adı", value="Axess Platinum")
            st.caption("Kartı önce Kartlar ve Ekstreler bölümünden kaydedersen kesim düğmesi ve kart sahibi takibiyle eşleşir.")
    with col2:
        if AI.get("api_key"):
            st.success("Yapay zekâ sınıflandırması hazır.")
        else:
            st.info("Yapay zekâ anahtarı henüz eklenmemiş; kurallı sınıflandırma kullanılacak.")
    uploads = st.file_uploader("Bir veya birden fazla ekstre seç", type=["pdf", "csv", "xlsx", "xls"], accept_multiple_files=True)
    if uploads and st.button("🔎 Dosyaları oku ve önizleme oluştur", type="primary", width="stretch"):
        frames, excluded_frames, parse_errors = [], [], []
        progress = st.progress(0, text="Dosyalar hazırlanıyor...")
        card_owner_default = next((str(c.get("owner", "Belirsiz")) for c in registered_cards_for_import if str(c.get("name", "")).strip() == card_name), "Belirsiz")
        for idx, uploaded in enumerate(uploads):
            try:
                if uploaded.name.lower().endswith(".pdf"):
                    frame, excluded = parse_statement_pdf(uploaded.getvalue(), uploaded.name, None, card_name)
                    if not frame.empty:
                        frame["Kart"] = card_name
                        if card_owner_default in OWNERS:
                            frame.loc[frame["Harcama Sahibi"] == "Belirsiz", "Harcama Sahibi"] = card_owner_default
                    frames.append(frame)
                    if not excluded.empty: excluded_frames.append(excluded)
                else:
                    frame = parse_spreadsheet(uploaded, statement_month_fallback)
                    if "Kart" in frame: frame["Kart"] = frame["Kart"].replace("", card_name)
                    else: frame["Kart"] = card_name
                    if card_owner_default in OWNERS and "Harcama Sahibi" in frame:
                        frame.loc[frame["Harcama Sahibi"] == "Belirsiz", "Harcama Sahibi"] = card_owner_default
                    frames.append(frame)
            except Exception as exc:
                parse_errors.append(f"{uploaded.name}: {exc}")
            progress.progress((idx+1)/len(uploads), text=f"Okunuyor: {uploaded.name}")
        combined = pd.concat([x for x in frames if x is not None and not x.empty], ignore_index=True) if any(x is not None and not x.empty for x in frames) else pd.DataFrame()
        excluded_combined = pd.concat(excluded_frames, ignore_index=True) if excluded_frames else pd.DataFrame()
        if not combined.empty:
            # Ensure month/cycle fields exist and use statement month for statement-based comparison.
            if "Ekstre Ayı" not in combined: combined["Ekstre Ayı"] = statement_month_fallback
            combined["Ekstre Ayı"] = combined["Ekstre Ayı"].fillna(statement_month_fallback).astype(str)
            combined["Dahil"] = combined["Dahil"].fillna(True).astype(bool)
            st.session_state["import_preview"] = combined
            st.session_state["import_excluded"] = excluded_combined
            st.session_state["import_source_name"] = ", ".join([x.name for x in uploads])
        for err in parse_errors: st.error(err)
        if combined.empty and not parse_errors: st.warning("İşlem satırı bulunamadı.")
    preview = st.session_state.get("import_preview")
    if preview is not None and not preview.empty:
        st.markdown("### 1. İşlemleri kontrol et")
        st.caption(f"{len(preview)} işlem hazır. 'Ekstre Ayı' karşılaştırma dönemidir; taksitli işlemlerde görünen asıl işlem tarihi daha eski olabilir.")
        columns = ["Ekstre Ayı", "İşlem Tarihi", "Açıklama", "Tutar (TL)", "Ana Kategori", "İşletme", "Alt Kategori", "Harcama Sahibi", "Kart", "İşlem Türü", "Tutar Güveni", "Kontrol", "Dahil", "sourceRowId", "Dosya"]
        edit_cols = [c for c in columns if c in preview.columns]
        editable = st.data_editor(
            preview[edit_cols], width="stretch", num_rows="dynamic", height=450, key="import_editor",
            column_config={
                "Ana Kategori": st.column_config.SelectboxColumn("Ana Kategori", options=CATEGORIES, required=True),
                "Harcama Sahibi": st.column_config.SelectboxColumn("Harcama Sahibi", options=OWNERS, required=True),
                "İşlem Türü": st.column_config.SelectboxColumn("İşlem Türü", options=["purchase","installment","refund","fee"], required=True),
                "Dahil": st.column_config.CheckboxColumn("Dahil", help="İşaretliyse Firebase'e kaydedilir."),
                "Tutar (TL)": st.column_config.NumberColumn("Tutar (TL)", format="%.2f", min_value=-10000000.0, max_value=10000000.0),
            },
        )
        a, b = st.columns([1,1])
        with a:
            if st.button("✨ Yapay zekâyla kategorileri düzelt", disabled=not bool(AI.get("api_key")), width="stretch"):
                try:
                    with st.spinner("İşletme ve kategoriler sınıflandırılıyor..."):
                        st.session_state["import_preview"] = ai_classify_dataframe(editable.copy())
                    st.success("Sınıflandırma bitti. Sonuçları tekrar kontrol et.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Sınıflandırma başarısız: {exc}")
        with b:
            if st.button("💾 Onaylanan işlemleri Firebase'e kaydet", type="primary", width="stretch"):
                saveable = editable[editable["Dahil"].astype(bool)].copy()
                saved, duplicates, skipped = 0, 0, 0
                try:
                    existing = load_transactions(uid, limit=1000)
                    existing_keys = {x.get("dedupeKey") for x in existing}
                    closed_statements = safe_load_collection(uid, "statements")
                    closed_keys = {(str(s.get("month", "")), str(s.get("card", ""))) for s in closed_statements if s.get("closed") or s.get("status") in ["Kesildi", "Ödendi"]}
                    progress = st.progress(0, text="Kayıtlar Firebase'e aktarılıyor...")
                    locked_rows = 0
                    for idx, (_, r) in enumerate(saveable.iterrows()):
                        dt = parse_date(r.get("İşlem Tarihi"))
                        amount = parse_amount_generic(r.get("Tutar (TL)"))
                        desc = str(r.get("Açıklama", "")).strip()
                        statement_month = str(r.get("Ekstre Ayı", statement_month_fallback))[:7]
                        if not dt or amount is None or not desc:
                            skipped += 1
                            continue
                        category = str(r.get("Ana Kategori", "Diğer"))
                        if category not in CATEGORIES: category = "Diğer"
                        owner = str(r.get("Harcama Sahibi", "Belirsiz"))
                        if owner not in OWNERS: owner = "Belirsiz"
                        row_card = str(r.get("Kart", card_name))[:100]
                        if (statement_month, row_card) in closed_keys:
                            locked_rows += 1
                            continue
                        row = {
                            "date": dt, "calendarMonth": dt[:7], "month": statement_month, "statementMonth": statement_month,
                            "amount": float(amount), "description": desc, "category": category,
                            "merchant": str(r.get("İşletme", ""))[:100] or clean_merchant(desc),
                            "subcategory": str(r.get("Alt Kategori", ""))[:100], "owner": owner,
                            "card": row_card, "transactionType": str(r.get("İşlem Türü", "purchase")),
                            "sourceRowId": str(r.get("sourceRowId", "")), "sourceFile": str(r.get("Dosya", st.session_state.get("import_source_name", "upload"))),
                            "reviewNotes": str(r.get("Kontrol", "")), "amountConfidence": str(r.get("Tutar Güveni", "")),
                        }
                        row["dedupeKey"] = stable_dedupe_key(row)
                        if row["dedupeKey"] in existing_keys:
                            duplicates += 1
                        else:
                            create_document("transactions", {**row, "ownerUid": uid, "createdAt": datetime.utcnow().isoformat(timespec="seconds")})
                            existing_keys.add(row["dedupeKey"])
                            saved += 1
                        progress.progress((idx+1)/max(1,len(saveable)), text=f"Kaydediliyor: {idx+1}/{len(saveable)}")
                    st.success(f"Aktarım tamamlandı: {saved} yeni işlem, {duplicates} mükerrer atlandı, {skipped} eksik satır atlandı.")
                    if locked_rows:
                        st.warning(f"{locked_rows} işlem kaydedilmedi: ilgili kartın bu aya ait ekstresi kapatılmış. Gerekliyse Kartlar ve Ekstreler bölümünden ekstreyi yeniden açıp aktarımı tekrarla.")
                    st.session_state.pop("import_preview", None)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Aktarım durdu: {exc}. Bir kısmı kaydedilmiş olabilir; aynı dosyayı tekrar yüklersen sourceRowId ile mükerrer kontrolü yapılır.")
        excluded_df = st.session_state.get("import_excluded")
        if excluded_df is not None and not excluded_df.empty:
            with st.expander(f"Otomatik hariç bırakılan satırlar ({len(excluded_df)})", expanded=False):
                st.dataframe(excluded_df, hide_index=True, width="stretch")
                st.download_button("Hariç tutulan satırları indir", excluded_df.to_csv(index=False).encode("utf-8-sig"), "ekstre_haric_satirlar.csv", "text/csv")

elif page == "💳 Kartlar ve Ekstreler":
    title_hero(month_label, "Kartları kişiye göre ayır, ekstreyi tek dokunuşla kapat ve dönem toplamını sabitle.")
    cards = safe_load_collection(uid, "cards")
    statements = safe_load_collection(uid, "statements")
    existing_statement_map = {(str(s.get("month", "")), str(s.get("card", ""))): s for s in statements}
    left, right = st.columns([0.9, 1.1], gap="large")
    with left:
        section("💳", "Kartlar", "Senin, eşinin ve diğer hesapların ayrı ayrı")
        with st.form("new_card_form"):
            card_label = st.text_input("Kart / hesap adı", placeholder="Örn. Benim Axess, Eşimin Akbank")
            bank = st.text_input("Banka", placeholder="Örn. Akbank")
            card_owner = st.selectbox("Kart sahibi", ["Belirsiz", "Ben", "Eşim", "Ortak", "Diğer"])
            cutoff_day = st.number_input("Ekstre kesim günü", min_value=1, max_value=31, value=7)
            due_day = st.number_input("Son ödeme günü", min_value=1, max_value=31, value=17)
            save_card = st.form_submit_button("➕ Kartı ekle", type="primary", width="stretch")
        if save_card:
            if not card_label.strip():
                st.error("Kart / hesap adı gerekli.")
            else:
                slug = re.sub(r"[^a-zA-Z0-9]+", "-", card_label.strip()).strip("-").lower()
                doc_id = f"{uid}_{slug}"
                try:
                    write_document("cards", doc_id, {"ownerUid":uid,"name":card_label.strip(),"bank":bank.strip(),"owner":card_owner,"cutoffDay":int(cutoff_day),"dueDay":int(due_day),"updatedAt":datetime.utcnow().isoformat(timespec="seconds")})
                    st.success("Kart kaydedildi.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Kart kaydedilemedi: {exc}")
        if cards:
            cdf = pd.DataFrame([{"Kart / hesap":c.get("name"),"Banka":c.get("bank"),"Sahibi":c.get("owner"),"Kesim günü":c.get("cutoffDay"),"Son ödeme günü":c.get("dueDay")} for c in cards])
            st.dataframe(cdf, hide_index=True, width="stretch")
            with st.expander("Kart sahibi ve tarihlerini düzenle", expanded=False):
                for card_item in cards:
                    card_id = card_item.get("id")
                    with st.form(f"edit_card_{card_id}"):
                        st.markdown(f"**{card_item.get('name', 'Kart')}**")
                        e1, e2, e3 = st.columns(3)
                        with e1:
                            edit_owner = st.selectbox("Kart sahibi", ["Belirsiz", "Ben", "Eşim", "Ortak", "Diğer"], index=( ["Belirsiz", "Ben", "Eşim", "Ortak", "Diğer"].index(card_item.get("owner", "Belirsiz")) if card_item.get("owner", "Belirsiz") in ["Belirsiz", "Ben", "Eşim", "Ortak", "Diğer"] else 0), key=f"edit_owner_{card_id}")
                        with e2:
                            edit_cutoff = st.number_input("Kesim günü", min_value=1, max_value=31, value=int(card_item.get("cutoffDay", 7)), key=f"edit_cutoff_{card_id}")
                        with e3:
                            edit_due = st.number_input("Son ödeme günü", min_value=1, max_value=31, value=int(card_item.get("dueDay", 17)), key=f"edit_due_{card_id}")
                        if st.form_submit_button("Kart bilgilerini kaydet", width="stretch"):
                            try:
                                write_document("cards", card_id, {"ownerUid":uid,"name":card_item.get("name", "Kart"),"bank":card_item.get("bank", ""),"owner":edit_owner,"cutoffDay":int(edit_cutoff),"dueDay":int(edit_due),"updatedAt":datetime.utcnow().isoformat(timespec="seconds")})
                                st.success("Kart bilgileri güncellendi.")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Kart bilgileri kaydedilemedi: {exc}")
        else:
            st.info("Önce kendi ve eşinin kartlarını ayrı isimlerle ekle. Ekstre içe aktarırken burada tanımlı kartı seçebilirsin.")

    with right:
        section("🔒", "Ekstreyi kapat", f"Seçili dönem: {month_label}")
        st.caption("Kapatma işlemi ilgili kartın seçili ayını sabitler. Sonradan içe aktarılan işlemler, ekstre yeniden açılmadıkça kaydedilmez.")
        if not cards:
            st.warning("Ekstre kapatma düğmesi için önce en az bir kart tanımla.")
        else:
            for card_item in cards:
                name = str(card_item.get("name", "Kart"))
                owner_text = str(card_item.get("owner", "Belirsiz"))
                current_statement = existing_statement_map.get((selected_month, name))
                txs_for_card = [x for x in load_transactions(uid, selected_month) if str(x.get("card", "")) == name]
                # Card payments are transfers against the card balance, not merchant spend.
                eligible = [x for x in txs_for_card if str(x.get("transactionType", "purchase")).lower() not in ["payment", "card_payment", "kart ödemesi"]]
                computed_total = sum(float(x.get("amount", 0) or 0) for x in eligible)
                with st.container(border=True):
                    c1, c2 = st.columns([1.7, 1])
                    with c1:
                        st.markdown(f"**💳 {name}**")
                        st.caption(f"Kart sahibi: {owner_text} · {len(eligible)} işlem · Toplam: {money(computed_total)}")
                        if current_statement and (current_statement.get("closed") or current_statement.get("status") in ["Kesildi", "Ödendi"]):
                            st.success(f"🔒 Ekstre kapalı · {money(current_statement.get('total', computed_total))}")
                        else:
                            st.info("🟢 Ekstre açık")
                    with c2:
                        if current_statement and (current_statement.get("closed") or current_statement.get("status") in ["Kesildi", "Ödendi"]):
                            if st.button("🔓 Ekstreyi yeniden aç", key=f"reopen_{selected_month}_{name}", width="stretch"):
                                try:
                                    sid = current_statement.get("id") or f"{uid}_{selected_month}_{re.sub(r'[^a-zA-Z0-9]+','-',name).strip('-').lower()}"
                                    write_document("statements", sid, {"ownerUid":uid,"month":selected_month,"card":name,"cardOwner":owner_text,"status":"Açık","closed":False,"updatedAt":datetime.utcnow().isoformat(timespec="seconds")})
                                    st.success("Ekstre yeniden açıldı.")
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Ekstre açılamadı: {exc}")
                        else:
                            if st.button("🔒 Ekstreyi kapat", key=f"close_{selected_month}_{name}", type="primary", width="stretch"):
                                slug = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
                                sid = f"{uid}_{selected_month}_{slug}"
                                cutoff, due = scheduled_statement_dates(selected_month, card_item.get("cutoffDay", 7), card_item.get("dueDay", 17))
                                try:
                                    write_document("statements", sid, {
                                        "ownerUid":uid,"month":selected_month,"card":name,"cardOwner":owner_text,
                                        "cutoffDate":cutoff.isoformat(),"dueDate":due.isoformat(),
                                        "total":round(computed_total, 2),"transactionCount":len(eligible),
                                        "status":"Kesildi","closed":True,
                                        "closedAt":datetime.utcnow().isoformat(timespec="seconds"),
                                        "updatedAt":datetime.utcnow().isoformat(timespec="seconds"),
                                    })
                                    st.success(f"{name} ekstresi {money(computed_total)} olarak kapatıldı.")
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Ekstre kapatılamadı: {exc}")
    st.markdown("---")
    section("🗂️", "Ekstre geçmişi", "Kart ve kişiye göre kapatılmış dönemler")
    statements = safe_load_collection(uid, "statements")
    if statements:
        sdf = pd.DataFrame([{"Ay":month_label_tr(s.get("month", "")),"Dönem kodu":s.get("month"),"Kart":s.get("card"),"Sahibi":s.get("cardOwner", "Belirsiz"),"Kesim tarihi":s.get("cutoffDate"),"Son ödeme":s.get("dueDate"),"Ekstre (TL)":s.get("total"),"İşlem sayısı":s.get("transactionCount", 0),"Durum":s.get("status")} for s in statements])
        sdf = sdf.sort_values(["Dönem kodu","Kart"], ascending=[False,True])
        st.dataframe(sdf.drop(columns=["Dönem kodu"]), hide_index=True, width="stretch")
    else:
        st.info("Henüz kapatılmış ekstre yok. Her kart için ilgili ayda 'Ekstreyi kapat' düğmesini kullanabilirsin.")

elif page == "🔎 Harcama Analizi":
    title_hero("Harcama keşfi", "Bir kategori seç; işletme, kişi ve işlem düzeyinde ayrıntıya in.")
    all_rows = load_transactions(uid, limit=1000)
    if not all_rows:
        st.info("Analiz için önce ekstre yükle veya harcama kaydı ekle.")
    else:
        df = pd.DataFrame(all_rows)
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
        months = sorted(df["month"].dropna().astype(str).unique()) if "month" in df else []
        default_start = months[max(0,len(months)-3)] if months else selected_month
        filters = st.columns(4)
        with filters[0]: start_month = st.selectbox("Başlangıç ayı", months or [selected_month], index=(months.index(default_start) if default_start in months else 0))
        with filters[1]: end_month = st.selectbox("Bitiş ayı", months or [selected_month], index=(months.index(months[-1]) if months else 0))
        with filters[2]: cat_options = ["Tümü"] + sorted(df["category"].dropna().astype(str).unique().tolist())
        category_filter = st.selectbox("Ana kategori", cat_options)
        with filters[3]: owner_filter = st.selectbox("Harcama sahibi", ["Tümü"] + OWNERS)
        dff = df[(df["month"].astype(str) >= start_month) & (df["month"].astype(str) <= end_month)].copy()
        if category_filter != "Tümü": dff = dff[dff["category"] == category_filter]
        if owner_filter != "Tümü" and "owner" in dff: dff = dff[dff["owner"] == owner_filter]
        merchants = sorted(dff.get("merchant", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
        selected_merchant = st.selectbox("İşletme / alt kırılım", ["Tümü"] + merchants)
        if selected_merchant != "Tümü": dff = dff[dff["merchant"] == selected_merchant]
        c1,c2,c3 = st.columns(3)
        c1.metric("Filtredeki net tutar", money(dff["amount"].sum() if not dff.empty else 0))
        c2.metric("İşlem sayısı", f"{len(dff):,}".replace(",","."))
        c3.metric("İşletme sayısı", str(dff["merchant"].nunique() if not dff.empty and "merchant" in dff else 0))
        left,right = st.columns([1,1], gap="large")
        with left:
            section("🏪", "İşletme bazında", "A101, BİM, Migros ve diğer işletmeler ayrı ayrı")
            if not dff.empty and "merchant" in dff:
                md = dff.groupby("merchant", as_index=False)["amount"].sum().sort_values("amount", ascending=False).head(15)
                fig = px.bar(md, x="amount", y="merchant", orientation="h", template="plotly_dark", color="amount", color_continuous_scale=["#6c8cff","#57e3c2"])
                fig.update_layout(height=380, margin=dict(l=0,r=0,t=5,b=5), coloraxis_showscale=False, xaxis_title="TL", yaxis_title="", yaxis={"categoryorder":"total ascending"})
                st.plotly_chart(fig, width="stretch")
        with right:
            section("📈", "Aylık hareket", "Seçili aralıkta kategori / işletme eğilimi")
            if not dff.empty:
                group_field = "merchant" if selected_merchant == "Tümü" and category_filter != "Tümü" else "category"
                tr = dff.groupby(["month", group_field], as_index=False)["amount"].sum()
                fig = px.line(tr, x="month", y="amount", color=group_field, markers=True, template="plotly_dark")
                fig.update_layout(height=380, margin=dict(l=0,r=0,t=5,b=5), xaxis_title="Ekstre ayı", yaxis_title="TL", legend_title_text="")
                st.plotly_chart(fig, width="stretch")
        section("🔍", "İşlem detayları", "Kategori filtresinin altındaki tüm işlemler")
        st.dataframe(dff[[c for c in ["month","date","description","category","merchant","subcategory","amount","owner","card","transactionType"] if c in dff.columns]].sort_values(["month","date"], ascending=[False,False]), hide_index=True, width="stretch", height=420)
        st.download_button("⬇️ Filtrelenmiş işlemleri indir", dff.to_csv(index=False).encode("utf-8-sig"), "harcama_analizi.csv", "text/csv")

elif page == "📊 Ay Karşılaştırma":
    title_hero("Ay karşılaştırma", "Önceki aya göre hangi kategori ve işletmenin ne kadar değiştiğini görün.")
    all_rows = load_transactions(uid, limit=1000)
    if not all_rows:
        st.info("Karşılaştırma için ekstre verileri gerekiyor.")
    else:
        df = pd.DataFrame(all_rows)
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
        months = sorted(df["month"].dropna().astype(str).unique())
        if len(months) < 2:
            st.info("Ay karşılaştırması için en az iki farklı ekstre ayı gerekli.")
        else:
            c1,c2 = st.columns(2)
            with c1: previous = st.selectbox("Karşılaştırma ayı", months, index=max(0,len(months)-2), format_func=month_label_tr)
            with c2: current = st.selectbox("Güncel ay", months, index=len(months)-1, format_func=month_label_tr)
            view_type = st.segmented_control("Karşılaştırma düzeyi", ["Ana kategori", "İşletme"], default="Ana kategori")
            group = "category" if view_type == "Ana kategori" else "merchant"
            p = df[df["month"] == previous].groupby(group)["amount"].sum()
            c = df[df["month"] == current].groupby(group)["amount"].sum()
            compare = pd.concat([p.rename("Önceki ay"), c.rename("Seçili ay")], axis=1).fillna(0)
            compare["Fark (TL)"] = compare["Seçili ay"] - compare["Önceki ay"]
            compare["Değişim (%)"] = compare.apply(lambda r: ((r["Fark (TL)"] / abs(r["Önceki ay"])) * 100) if r["Önceki ay"] else (100.0 if r["Seçili ay"] else 0.0), axis=1)
            compare = compare.sort_values("Fark (TL)", ascending=False)
            st.dataframe(compare.reset_index(names="Kategori / işletme").style.format({"Önceki ay": "{:,.2f}", "Seçili ay": "{:,.2f}", "Fark (TL)": "{:,.2f}", "Değişim (%)": "{:+.1f}%"}), hide_index=True, width="stretch")
            fig = px.bar(compare.reset_index(names="Kalem").head(15), x="Kalem", y="Fark (TL)", color="Fark (TL)", color_continuous_scale=["#57e3c2","#6c8cff"], template="plotly_dark")
            fig.update_layout(height=380, margin=dict(l=0,r=0,t=5,b=5), coloraxis_showscale=False, xaxis_title="", yaxis_title="Fark (TL)")
            st.plotly_chart(fig, width="stretch")
            st.caption("Karşılaştırmalar ekstre ayına göre yapılır. Taksitler, harcamanın özgün tarihi eski olsa bile içinde bulunduğu ekstre dönemine göre raporlanır.")

elif page == "⚙️ Veri Yönetimi":
    title_hero("Veri yönetimi", "Verilerini dışa aktar ve geçmiş ayların yedeğini al.")
    st.info("Finansal işlem verileri GitHub koduna yazılmaz; Firebase Firestore'da oturum açan kullanıcıya ait olarak tutulur.")
    if st.button("📦 Tüm kayıtları hazırla", type="primary"):
        try:
            txs = load_transactions(uid, limit=1000)
            budgets = safe_load_collection(uid, "monthly_budgets")
            cards = safe_load_collection(uid, "cards")
            statements = safe_load_collection(uid, "statements")
            st.session_state["backup_tx"] = txs
            st.session_state["backup_budgets"] = budgets
            st.session_state["backup_cards"] = cards
            st.session_state["backup_statements"] = statements
            st.success("Dışa aktarılacak kayıtlar hazır.")
        except Exception as exc:
            st.error(f"Kayıtlar alınamadı: {exc}")
    if "backup_tx" in st.session_state:
        txs = st.session_state["backup_tx"]
        budgets = st.session_state["backup_budgets"]
        cards = st.session_state["backup_cards"]
        statements = st.session_state["backup_statements"]
        txdf = pd.DataFrame(txs)
        if not txdf.empty:
            st.download_button("Harcamalar CSV", txdf.to_csv(index=False).encode("utf-8-sig"), "tum_harcamalar.csv", "text/csv")
        xls = BytesIO()
        with pd.ExcelWriter(xls, engine="openpyxl") as writer:
            pd.DataFrame(txs).to_excel(writer, sheet_name="Harcamalar", index=False)
            pd.DataFrame(budgets).to_excel(writer, sheet_name="AylikButce", index=False)
            pd.DataFrame(cards).to_excel(writer, sheet_name="Kartlar", index=False)
            pd.DataFrame(statements).to_excel(writer, sheet_name="Ekstreler", index=False)
        st.download_button("📥 Tüm kayıtları Excel indir", xls.getvalue(), "aile_butce_yedek.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.caption("Firebase Spark ücretsiz planında otomatik veritabanı yedeği açık olmayabilir. Bu dışa aktarımı düzenli almanı öneririz.")

st.divider()
st.caption("Aile Bütçe Merkezi · Güvenli oturum · Geçmişe dönük veriler ayrı ekstre aylarıyla saklanır.")
