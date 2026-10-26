import hashlib
import calendar
import json
import re
import time
import unicodedata
from datetime import date, datetime
from zoneinfo import ZoneInfo
from io import BytesIO

import pandas as pd
import requests
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Aile Bütçe Takip", page_icon="💠", layout="wide", initial_sidebar_state="expanded")

# ---------- Modern dashboard styling ----------
st.markdown(r"""
<style>
:root { --aqua:#57e3c2; --blue:#6c8cff; --panel:#151b2b; --muted:#a7b2c8; }
.block-container {padding-top:1.1rem; padding-bottom:2.5rem; max-width:1500px;}
[data-testid="stSidebar"] { border-right:1px solid rgba(148,163,184,.14); }
[data-testid="stSidebar"] .block-container {padding-top:1.4rem;}
[data-testid="stMetric"] {background:linear-gradient(135deg,rgba(108,140,255,.13),rgba(87,227,194,.07)); border:1px solid rgba(148,163,184,.15); padding:15px 17px; border-radius:16px;}
[data-testid="stMetricLabel"] {color:#aeb8ca; font-size:.88rem;}
[data-testid="stMetricValue"] {font-weight:750; letter-spacing:-.035em;}
.stButton>button, .stDownloadButton>button {border-radius:11px; font-weight:650; min-height:2.55rem;}
[data-testid="stForm"] {border:1px solid rgba(148,163,184,.17); border-radius:16px; padding:1rem; background:rgba(128,128,128,.025);}
[data-testid="stDataFrame"] {border:1px solid rgba(148,163,184,.16); border-radius:12px; overflow:hidden;}
.app-hero {border-radius:22px; padding:26px 30px; margin:0 0 1.2rem 0; color:white; background:radial-gradient(circle at 88% 10%,rgba(87,227,194,.30),transparent 28%),linear-gradient(125deg,#12182b 0%,#202c4b 53%,#263b5a 100%); border:1px solid rgba(148,163,184,.23); box-shadow:0 18px 40px rgba(0,0,0,.16);}
.app-hero .eyebrow {font-size:.77rem; letter-spacing:.15em; text-transform:uppercase; color:#91f4dc; font-weight:800;}
.app-hero h1 {margin:.45rem 0 .4rem 0; font-size:2rem; line-height:1.12; letter-spacing:-.045em; color:white;}
.app-hero p {margin:0; color:#c7d1e4; font-size:.96rem;}
.app-hero .period {float:right; padding:8px 13px; border-radius:999px; font-size:.8rem; font-weight:700; color:#e7fff8; border:1px solid rgba(145,244,220,.36); background:rgba(87,227,194,.1);}
.section-head {display:flex; gap:12px; align-items:center; margin:1rem 0 .4rem 0;}
.section-icon {display:inline-flex; align-items:center; justify-content:center; width:40px;height:40px;border-radius:13px; background:linear-gradient(145deg,rgba(108,140,255,.22),rgba(87,227,194,.16)); border:1px solid rgba(148,163,184,.18); font-size:1.2rem;}
.section-title {font-weight:800;font-size:1.2rem;letter-spacing:-.02em;}
.section-sub {font-size:.84rem;color:var(--muted);margin-top:2px;}
.small-muted {font-size:.82rem;color:var(--muted);}
.kpi-note {font-size:.79rem;color:#aab5c8; margin-top:4px;}
.pill {display:inline-block; background:rgba(87,227,194,.1);border:1px solid rgba(87,227,194,.25); color:#8cf2d8; padding:5px 9px;border-radius:999px;font-size:.77rem;font-weight:700;}
hr {border-color:rgba(148,163,184,.16);}
</style>
""", unsafe_allow_html=True)

CATEGORIES = [
    "Market", "Faturalar", "Ulaşım", "Ulaşım / Seyahat", "Restoran / Yemek",
    "Giyim", "Çocuk", "Sağlık", "Ev / Yaşam", "Eğitim / Kırtasiye",
    "Online alışveriş", "Dijital abonelik", "Dijital abonelik / Oyun", "Kişisel bakım",
    "Bankacılık ücreti", "Resmi ödeme", "Kişisel alışveriş", "Taksit", "İade", "Kontrol edilecek", "Diğer"
]
OWNERS = ["Ben", "Eşim", "Ortak", "Diğer", "Belirsiz"]
COLLECTIONS = {"monthly_budgets", "transactions", "cards", "statements"}
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


def login(email, password):
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
    }


def current_auth():
    return st.session_state.get("auth")


def logout():
    for key in ["auth", "import_preview", "import_source_name"]:
        st.session_state.pop(key, None)
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
    return True


def default_budget(month_key):
    # Only the current known budget is prefilled. Earlier months stay blank until the user enters history.
    if month_key < "2026-10":
        return {"income": {}, "expenses": {}, "notes": "Geçmiş ay; gerçekleşen tutarları girin."}
    year, month = map(int, month_key.split("-"))
    emin = 85300 if (year, month) >= (2027, 4) else 71500
    colendi = 9103 if (year, month) <= (2027, 3) else 0
    return {
        "income": {"Sizin Maaş": 73800, "Eş Maaş": 73200, "Sizin Ek Ders": 19800, "Eş Ek Ders": 20800},
        "expenses": {"Eminevim": emin, "Sizin Akbank": 47200, "Eş Akbank": 25300, "Colendi": colendi, "İş Bankası": 5750, "Ziraat": 0},
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
        submit = st.form_submit_button("Güvenli giriş", use_container_width=True, type="primary")
    if submit:
        if not API_KEY or not PROJECT_ID:
            st.error("Firebase yapılandırması eksik. Streamlit Settings → Secrets bölümünü kontrol edin.")
        elif not email.strip() or not password:
            st.warning("E-posta ve şifre girin.")
        else:
            try:
                login(email.strip(), password)
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
    login_view()
    st.stop()

auth = current_auth()
uid = auth["uid"]
now = today_tr()
month_options = [f"{year}-{month:02d}" for year in range(2026, 2031) for month in range(1, 13)]
current_month = now.strftime("%Y-%m")
with st.sidebar:
    st.markdown("## 💰 Aile Bütçe")
    st.markdown(f'<span class="pill">● Güvenli oturum</span><div class="small-muted" style="margin-top:8px">{auth.get("email", "Giriş yapıldı")}</div>', unsafe_allow_html=True)
    st.divider()
    page = st.radio("ÇALIŞMA ALANI", [
        "🏠 Genel Bakış", "🗓️ Aylık Bütçe", "🧾 İşlem Defteri", "📥 Ekstre İçe Aktar",
        "💳 Kartlar ve Ekstreler", "💸 Borçlar ve Ödemeler", "🔎 Harcama Analizi", "📊 Ay Karşılaştırma", "⚙️ Veri Yönetimi"
    ], label_visibility="collapsed")
    selected_month = st.selectbox("Aktif dönem", month_options, index=month_options.index(current_month) if current_month in month_options else 9,
                                  format_func=lambda x: month_label_tr(x))
    st.divider()
    if st.button("↪ Güvenli çıkış", use_container_width=True):
        logout()

try:
    budget = get_budget(uid, selected_month) or default_budget(selected_month)
    tx_rows = load_transactions(uid, selected_month)
except Exception as exc:
    st.error(f"Firebase'e erişim başarısız: {exc}")
    st.info("Bu sürüm Firestore sorgularında yalnızca ownerUid alanını sunucu tarafında filtreler; böylece composite index hatası oluşmamalıdır. Kurallar yayımlandı mı ve API anahtarı doğru mu kontrol edin.")
    st.stop()

income = budget.get("income", {}) or {}
expenses = budget.get("expenses", {}) or {}
total_income = sum(float(v or 0) for v in income.values())
total_expenses = sum(float(v or 0) for v in expenses.values())
net_cash = total_income - total_expenses
month_label = month_label_tr(selected_month)

if page == "🏠 Genel Bakış":
    title_hero(month_label, "Bütçenizi, kredi kartı harcamalarınızı ve aylık değişimleri hızlıca izleyin.")
    txdf = pd.DataFrame(tx_rows)
    statement_spend = 0.0
    if not txdf.empty and "amount" in txdf:
        statement_spend = pd.to_numeric(txdf["amount"], errors="coerce").fillna(0).sum()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💚 Toplam gelir", money(total_income))
    c2.metric("🧱 Planlanan ödemeler", money(total_expenses))
    c3.metric("✨ Planlanan kalan", money(net_cash))
    c4.metric("💳 Ekstre harcaması*", money(statement_spend))
    st.caption("*Ekstre harcaması; ekstre dönemine alınmış işlemleri gösterir. Kart borcu ödemeleri ve hariç bırakılan tapu harçları harcama toplamına katılmaz.")
    left, right = st.columns([1, 1.15], gap="large")
    with left:
        section("💸", "Gelir ve ödeme planı", "Seçili ayın bütçe kalemleri")
        if income or expenses:
            all_items = [{"Tür": "Gelir", "Kalem": k, "Tutar (TL)": float(v or 0)} for k,v in income.items()]
            all_items += [{"Tür": "Ödeme", "Kalem": k, "Tutar (TL)": float(v or 0)} for k,v in expenses.items()]
            bd = pd.DataFrame(all_items)
            fig = px.bar(bd, x="Tutar (TL)", y="Kalem", color="Tür", orientation="h", barmode="group", template="plotly_dark", height=330)
            fig.update_layout(margin=dict(l=0,r=10,t=5,b=5), legend_title_text="", xaxis_title="TL", yaxis_title="", font=dict(size=11))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Bu geçmiş ay için bütçe henüz girilmemiş. Aylık Bütçe bölümünden ekleyebilirsin.")
    with right:
        section("🛍️", "En çok harcanan kategoriler", "Ekstre kayıtlarına göre")
        if not txdf.empty and "category" in txdf:
            txdf["amount"] = pd.to_numeric(txdf["amount"], errors="coerce").fillna(0)
            by_cat = txdf.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False).head(8)
            fig = px.bar(by_cat, x="amount", y="category", orientation="h", template="plotly_dark", color="amount", color_continuous_scale=["#4263eb", "#57e3c2"], height=330)
            fig.update_layout(margin=dict(l=0,r=5,t=5,b=5), coloraxis_showscale=False, xaxis_title="TL", yaxis_title="", yaxis={"categoryorder":"total ascending"}, font=dict(size=11))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Bu dönem için henüz harcama kaydı yok.")
    section("🧭", "Hızlı özet", "Kayıtlar geldikçe bu alan güncellenir")
    if not txdf.empty:
        merchant_col = "merchant" if "merchant" in txdf else None
        if merchant_col:
            top = txdf.groupby(merchant_col)["amount"].sum().sort_values(ascending=False).head(5)
            st.write("**En çok harcama yapılan işletmeler:** " + " · ".join([f"{k}: {money(v)}" for k,v in top.items()]))
        st.dataframe(txdf[[c for c in ["date", "description", "category", "merchant", "amount", "owner", "card"] if c in txdf.columns]].head(10), hide_index=True, use_container_width=True)
    else:
        st.success("Başlangıç hazır. Önce ekstrelerini içe aktar; sonra kategori ve işletme bazlı analizler dolmaya başlayacak.")

elif page == "🗓️ Aylık Bütçe":
    title_hero(month_label, "Her ayın tutarı bağımsız kaydedilir; geçmiş aylar sonraki değişikliklerden etkilenmez.")
    if selected_month < "2026-10":
        st.info("Bu geçmiş ay için daha önce bütçe kaydı yoksa boş başlar. Gerçekleşen gelir ve giderlerini girerek tarihçeyi kurabilirsin.")
    with st.form("budget_form"):
        section("💰", "Gelirler", "Maaş, ek ders ve diğer gelirler")
        new_income = dict(income)
        col1, col2 = st.columns(2)
        existing_income = list(income.items())
        for i, (name, amount) in enumerate(existing_income):
            with (col1 if i % 2 == 0 else col2):
                new_income[name] = st.number_input(name, min_value=0.0, value=float(amount or 0), step=100.0, key=f"inc_{selected_month}_{name}")
        add_income_name = st.text_input("Yeni gelir kalemi adı", placeholder="Örn. Sınav görevi / ek gelir")
        add_income_value = st.number_input("Yeni gelir kalemi tutarı (TL)", min_value=0.0, step=100.0, key="add_income_amount")
        section("🧾", "Giderler ve borçlar", "Tutarları her ay yeniden güncelleyebilirsin")
        new_expenses = dict(expenses)
        col1, col2 = st.columns(2)
        existing_expenses = list(expenses.items())
        for i, (name, amount) in enumerate(existing_expenses):
            with (col1 if i % 2 == 0 else col2):
                new_expenses[name] = st.number_input(name, min_value=0.0, value=float(amount or 0), step=100.0, key=f"exp_{selected_month}_{name}")
        add_expense_name = st.text_input("Yeni gider / borç kalemi adı", placeholder="Örn. Kredi kartı X")
        add_expense_value = st.number_input("Yeni gider / borç kalemi tutarı (TL)", min_value=0.0, step=100.0, key="add_expense_amount")
        notes = st.text_area("Ayın notu", value=budget.get("notes", ""), placeholder="Örn. ekstre arttı, taksit bitti...")
        submitted = st.form_submit_button("💾 Seçili ayı kaydet", type="primary", use_container_width=True)
    if submitted:
        if add_income_name.strip(): new_income[add_income_name.strip()] = add_income_value
        if add_expense_name.strip(): new_expenses[add_expense_name.strip()] = add_expense_value
        try:
            save_budget(uid, selected_month, {"income": new_income, "expenses": new_expenses, "notes": notes})
            st.success(f"{month_label} bütçesi kaydedildi.")
            st.rerun()
        except Exception as exc:
            st.error(f"Kaydedilemedi: {exc}")
    st.markdown("---")
    ci1, ci2, ci3 = st.columns(3)
    ci1.metric("Toplam gelir", money(total_income))
    ci2.metric("Toplam gider / ödeme", money(total_expenses))
    ci3.metric("Kalan planlanan nakit", money(net_cash))

elif page == "🧾 İşlem Defteri":
    title_hero(month_label, "Tek tutarla hızlı nakit gider kaydet; ayrıntılı kart harcamalarını ekstre yüklemesinden al.")
    section("⚡", "Hızlı gider", "Tarih otomatik olarak bugünün tarihiyle kaydedilir.")
    with st.form("quick_amount_form"):
        quick_amount = st.number_input("Tutar (TL)", min_value=0.01, value=100.0, step=10.0, format="%.2f")
        quick_save = st.form_submit_button("➕ Tutarı kaydet", type="primary", use_container_width=True)
    if quick_save:
        today = today_tr()
        row = {
            "date": today.isoformat(), "calendarMonth": today.strftime("%Y-%m"),
            "month": today.strftime("%Y-%m"), "statementMonth": today.strftime("%Y-%m"),
            "amount": float(quick_amount), "description": "Hızlı gider — sınıflandırılacak",
            "category": "Kontrol edilecek", "merchant": "Sınıflandırılacak",
            "subcategory": "Hızlı kayıt", "owner": "Belirsiz", "card": "Nakit / belirtilmedi",
            "transactionType": "quick_expense", "sourceRowId": "",
        }
        try:
            add_transaction(uid, row)
            st.success(f"{money(quick_amount)} hızlı gideri {today.strftime('%d.%m.%Y')} tarihiyle kaydedildi.")
            st.rerun()
        except Exception as exc:
            st.error(f"Hızlı gider kaydedilemedi: {exc}")
    st.info("Kart harcamalarını tek tek buradan girme. Ekstre İçe Aktar bölümünden ekstreyi yükle; kategori ve işletme ayrıntıları oradan oluşsun. Hızlı giderler daha sonra analiz ekranında 'Kontrol edilecek' filtresiyle bulunabilir.")
    try:
        rows = load_transactions(uid, selected_month)
        if not rows:
            st.info("Bu ay için kayıt bulunmuyor. Ekstre İçe Aktar bölümünden dosya yükleyebilirsin.")
        else:
            df = pd.DataFrame(rows)
            display_map = {"date":"İşlem tarihi", "description":"Açıklama", "category":"Ana kategori", "merchant":"İşletme", "subcategory":"Alt kategori", "amount":"Tutar (TL)", "owner":"Harcama sahibi", "card":"Kart", "transactionType":"İşlem türü"}
            view = df[[c for c in display_map if c in df]].rename(columns=display_map)
            st.markdown(f"#### {month_label} kayıtları · {len(view)} işlem")
            st.dataframe(view, hide_index=True, use_container_width=True, height=430)
            st.download_button("⬇️ Bu dönemi CSV indir", view.to_csv(index=False).encode("utf-8-sig"), f"islemler_{selected_month}.csv", "text/csv")
    except Exception as exc:
        st.error(f"İşlemler okunamadı: {exc}")

elif page == "📥 Ekstre İçe Aktar":
    title_hero("Ekstre merkezi", "PDF, CSV veya Excel yükle; işlemleri kontrol et ve onayladıktan sonra kaydet.")
    st.warning("PDF ekstreleri OCR ile okunur. Tutarı otomatik doğrulanamayan satırlar varsayılan olarak işaretli değildir; kontrol etmeden içe aktarma. Tapu harçları, bilinen vergi dairesi taksitleri, kart borcu ödemeleri ve chip-para düzeltmeleri otomatik hariç bırakılır.")
    col1, col2 = st.columns([1.1, 1])
    registered_cards_for_import = load_collection(uid, "cards")
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
    if uploads and st.button("🔎 Dosyaları oku ve önizleme oluştur", type="primary", use_container_width=True):
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
            preview[edit_cols], use_container_width=True, num_rows="dynamic", height=450, key="import_editor",
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
            if st.button("✨ Yapay zekâyla kategorileri düzelt", disabled=not bool(AI.get("api_key")), use_container_width=True):
                try:
                    with st.spinner("İşletme ve kategoriler sınıflandırılıyor..."):
                        st.session_state["import_preview"] = ai_classify_dataframe(editable.copy())
                    st.success("Sınıflandırma bitti. Sonuçları tekrar kontrol et.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Sınıflandırma başarısız: {exc}")
        with b:
            if st.button("💾 Onaylanan işlemleri Firebase'e kaydet", type="primary", use_container_width=True):
                saveable = editable[editable["Dahil"].astype(bool)].copy()
                saved, duplicates, skipped = 0, 0, 0
                try:
                    existing = load_transactions(uid, limit=1000)
                    existing_keys = {x.get("dedupeKey") for x in existing}
                    closed_statements = load_collection(uid, "statements")
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
                st.dataframe(excluded_df, hide_index=True, use_container_width=True)
                st.download_button("Hariç tutulan satırları indir", excluded_df.to_csv(index=False).encode("utf-8-sig"), "ekstre_haric_satirlar.csv", "text/csv")

elif page == "💳 Kartlar ve Ekstreler":
    title_hero(month_label, "Kartları kişiye göre ayır, ekstreyi tek dokunuşla kapat ve dönem toplamını sabitle.")
    cards = load_collection(uid, "cards")
    statements = load_collection(uid, "statements")
    existing_statement_map = {(str(s.get("month", "")), str(s.get("card", ""))): s for s in statements}
    left, right = st.columns([0.9, 1.1], gap="large")
    with left:
        section("💳", "Kartlar", "Senin, eşinin ve diğer hesapların ayrı ayrı")
        with st.form("new_card_form"):
            card_label = st.text_input("Kart / hesap adı", placeholder="Örn. Benim Axess, Eşimin Akbank")
            bank = st.text_input("Banka", placeholder="Örn. Akbank")
            card_owner = st.selectbox("Kart sahibi", ["Ben", "Eşim", "Ortak", "Diğer"])
            cutoff_day = st.number_input("Ekstre kesim günü", min_value=1, max_value=31, value=7)
            due_day = st.number_input("Son ödeme günü", min_value=1, max_value=31, value=17)
            save_card = st.form_submit_button("➕ Kartı ekle", type="primary", use_container_width=True)
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
            st.dataframe(cdf, hide_index=True, use_container_width=True)
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
                            if st.button("🔓 Ekstreyi yeniden aç", key=f"reopen_{selected_month}_{name}", use_container_width=True):
                                try:
                                    sid = current_statement.get("id") or f"{uid}_{selected_month}_{re.sub(r'[^a-zA-Z0-9]+','-',name).strip('-').lower()}"
                                    write_document("statements", sid, {"ownerUid":uid,"month":selected_month,"card":name,"cardOwner":owner_text,"status":"Açık","closed":False,"updatedAt":datetime.utcnow().isoformat(timespec="seconds")})
                                    st.success("Ekstre yeniden açıldı.")
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Ekstre açılamadı: {exc}")
                        else:
                            if st.button("🔒 Ekstreyi kapat", key=f"close_{selected_month}_{name}", type="primary", use_container_width=True):
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
    statements = load_collection(uid, "statements")
    if statements:
        sdf = pd.DataFrame([{"Ay":month_label_tr(s.get("month", "")),"Dönem kodu":s.get("month"),"Kart":s.get("card"),"Sahibi":s.get("cardOwner", "Belirsiz"),"Kesim tarihi":s.get("cutoffDate"),"Son ödeme":s.get("dueDate"),"Ekstre (TL)":s.get("total"),"İşlem sayısı":s.get("transactionCount", 0),"Durum":s.get("status")} for s in statements])
        sdf = sdf.sort_values(["Dönem kodu","Kart"], ascending=[False,True])
        st.dataframe(sdf.drop(columns=["Dönem kodu"]), hide_index=True, use_container_width=True)
    else:
        st.info("Henüz kapatılmış ekstre yok. Her kart için ilgili ayda 'Ekstreyi kapat' düğmesini kullanabilirsin.")

elif page == "💸 Borçlar ve Ödemeler":
    title_hero(month_label, "Kart, kredi ve diğer borçlarının aylık tutarını ve ödeme durumunu buradan yönet.")
    current_expenses = dict(expenses or {})
    debt_meta = dict(budget.get("debtMeta", {}) or {})
    cards_for_debts = load_collection(uid, "cards")
    card_names = [str(c.get("name", "")) for c in cards_for_debts if c.get("name")]
    account_options = ["Borç kaleminin adı", "Nakit / banka hesabı"] + card_names
    section("🧾", "Bu ayın borç ve ödeme planı", "Kart veya borç kalemini seç; yalnızca seçili ayın tutarı değişir.")
    if current_expenses:
        for debt_name, debt_amount in current_expenses.items():
            meta = debt_meta.get(debt_name, {}) if isinstance(debt_meta.get(debt_name, {}), dict) else {}
            status = meta.get("status", "Bekliyor")
            owner_name = meta.get("owner", "Eşim" if "eş" in norm(debt_name) else ("Ben" if any(x in norm(debt_name) for x in ["SIZIN", "COLENDI"]) else "Belirsiz"))
            st.markdown(f"**{debt_name}** · {money(debt_amount)} · {owner_name} · {'✅ Ödendi' if status == 'Ödendi' else ('🟡 Kısmi ödeme' if status == 'Kısmi' else '⏳ Bekliyor')}")
    with st.expander("✏️ Mevcut borç / kart tutarını güncelle", expanded=True):
        if current_expenses:
            with st.form("edit_debt_form"):
                selected_debt = st.selectbox("Borç / kart", list(current_expenses.keys()))
                selected_meta = debt_meta.get(selected_debt, {}) if isinstance(debt_meta.get(selected_debt, {}), dict) else {}
                updated_amount = st.number_input("Bu ay ödenecek tutar (TL)", min_value=0.0, value=float(current_expenses.get(selected_debt, 0) or 0), step=100.0)
                c1,c2 = st.columns(2)
                with c1:
                    updated_owner = st.selectbox("Sorumlu kişi", ["Ben","Eşim","Ortak","Diğer","Belirsiz"], index=(["Ben","Eşim","Ortak","Diğer","Belirsiz"].index(selected_meta.get("owner", "Belirsiz")) if selected_meta.get("owner", "Belirsiz") in ["Ben","Eşim","Ortak","Diğer","Belirsiz"] else 4))
                    updated_kind = st.selectbox("Borç türü", ["Kredi kartı", "Banka kredisi", "Finansman / Eminevim", "Taksit", "Diğer"], index=(["Kredi kartı", "Banka kredisi", "Finansman / Eminevim", "Taksit", "Diğer"].index(selected_meta.get("kind", "Diğer")) if selected_meta.get("kind", "Diğer") in ["Kredi kartı", "Banka kredisi", "Finansman / Eminevim", "Taksit", "Diğer"] else 4))
                with c2:
                    saved_account = selected_meta.get("account", "Borç kaleminin adı")
                    updated_account = st.selectbox("Bağlı kart / hesap", account_options, index=(account_options.index(saved_account) if saved_account in account_options else 0))
                    updated_status = st.selectbox("Bu ayın ödeme durumu", ["Bekliyor", "Kısmi", "Ödendi"], index=(["Bekliyor", "Kısmi", "Ödendi"].index(selected_meta.get("status", "Bekliyor")) if selected_meta.get("status", "Bekliyor") in ["Bekliyor", "Kısmi", "Ödendi"] else 0))
                saved = st.form_submit_button("💾 Borç kaydını güncelle", type="primary", use_container_width=True)
            if saved:
                current_expenses[selected_debt] = updated_amount
                debt_meta[selected_debt] = {"owner":updated_owner,"kind":updated_kind,"account":updated_account,"status":updated_status,"updatedAt":datetime.utcnow().isoformat(timespec="seconds")}
                try:
                    save_budget(uid, selected_month, {"income":income,"expenses":current_expenses,"notes":budget.get("notes", ""),"debtMeta":debt_meta})
                    st.success(f"{selected_debt} güncellendi.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Borç kaydedilemedi: {exc}")
        else:
            st.info("Bu ay için henüz ödeme kalemi yok.")
    with st.expander("➕ Yeni borç / kart / ödeme kategorisi ekle", expanded=False):
        with st.form("new_debt_form"):
            new_debt_name = st.text_input("Kategori / borç adı", placeholder="Örn. Yeni kredi kartı, taşıt kredisi, aile borcu")
            c1,c2 = st.columns(2)
            with c1:
                new_debt_amount = st.number_input("Bu ayki tutar (TL)", min_value=0.0, step=100.0)
                new_debt_owner = st.selectbox("Sorumlu kişi", ["Ben","Eşim","Ortak","Diğer","Belirsiz"])
            with c2:
                new_debt_kind = st.selectbox("Borç türü", ["Kredi kartı", "Banka kredisi", "Finansman / Eminevim", "Taksit", "Diğer"])
                new_debt_account = st.selectbox("Bağlı kart / hesap", account_options)
            new_debt_status = st.selectbox("Bu ayın ödeme durumu", ["Bekliyor", "Kısmi", "Ödendi"])
            add_debt = st.form_submit_button("➕ Borç kategorisini ekle", type="primary", use_container_width=True)
        if add_debt:
            if not new_debt_name.strip():
                st.error("Borç / kategori adı gerekli.")
            elif new_debt_name.strip() in current_expenses:
                st.warning("Bu adla bir kalem zaten var; mevcut kalemi güncelle bölümünü kullan.")
            else:
                current_expenses[new_debt_name.strip()] = new_debt_amount
                debt_meta[new_debt_name.strip()] = {"owner":new_debt_owner,"kind":new_debt_kind,"account":new_debt_account,"status":new_debt_status,"updatedAt":datetime.utcnow().isoformat(timespec="seconds")}
                try:
                    save_budget(uid, selected_month, {"income":income,"expenses":current_expenses,"notes":budget.get("notes", ""),"debtMeta":debt_meta})
                    st.success(f"{new_debt_name.strip()} eklendi.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Borç kategorisi eklenemedi: {exc}")
    st.markdown("---")
    st.columns(3)[0].metric("Bu ay planlanan ödeme", money(sum(float(v or 0) for v in current_expenses.values())))
    st.caption("Bu modül Aylık Bütçe ekranındaki aynı ödeme kalemlerini kullanır; tutarlar iki kez toplanmaz. Yeni kalemler seçili aya eklenir. Sonraki ay tutarları ayrı düzenlenebilir.")

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
                st.plotly_chart(fig, use_container_width=True)
        with right:
            section("📈", "Aylık hareket", "Seçili aralıkta kategori / işletme eğilimi")
            if not dff.empty:
                group_field = "merchant" if selected_merchant == "Tümü" and category_filter != "Tümü" else "category"
                tr = dff.groupby(["month", group_field], as_index=False)["amount"].sum()
                fig = px.line(tr, x="month", y="amount", color=group_field, markers=True, template="plotly_dark")
                fig.update_layout(height=380, margin=dict(l=0,r=0,t=5,b=5), xaxis_title="Ekstre ayı", yaxis_title="TL", legend_title_text="")
                st.plotly_chart(fig, use_container_width=True)
        section("🔍", "İşlem detayları", "Kategori filtresinin altındaki tüm işlemler")
        st.dataframe(dff[[c for c in ["month","date","description","category","merchant","subcategory","amount","owner","card","transactionType"] if c in dff.columns]].sort_values(["month","date"], ascending=[False,False]), hide_index=True, use_container_width=True, height=420)
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
            with c1: previous = st.selectbox("Karşılaştırma ayı", months, index=max(0,len(months)-2))
            with c2: current = st.selectbox("Güncel ay", months, index=len(months)-1)
            view_type = st.segmented_control("Karşılaştırma düzeyi", ["Ana kategori", "İşletme"], default="Ana kategori")
            group = "category" if view_type == "Ana kategori" else "merchant"
            p = df[df["month"] == previous].groupby(group)["amount"].sum()
            c = df[df["month"] == current].groupby(group)["amount"].sum()
            compare = pd.concat([p.rename("Önceki ay"), c.rename("Seçili ay")], axis=1).fillna(0)
            compare["Fark (TL)"] = compare["Seçili ay"] - compare["Önceki ay"]
            compare["Değişim (%)"] = compare.apply(lambda r: ((r["Fark (TL)"] / abs(r["Önceki ay"])) * 100) if r["Önceki ay"] else (100.0 if r["Seçili ay"] else 0.0), axis=1)
            compare = compare.sort_values("Fark (TL)", ascending=False)
            st.dataframe(compare.reset_index(names="Kategori / işletme").style.format({"Önceki ay": "{:,.2f}", "Seçili ay": "{:,.2f}", "Fark (TL)": "{:,.2f}", "Değişim (%)": "{:+.1f}%"}), hide_index=True, use_container_width=True)
            fig = px.bar(compare.reset_index(names="Kalem").head(15), x="Kalem", y="Fark (TL)", color="Fark (TL)", color_continuous_scale=["#57e3c2","#6c8cff"], template="plotly_dark")
            fig.update_layout(height=380, margin=dict(l=0,r=0,t=5,b=5), coloraxis_showscale=False, xaxis_title="", yaxis_title="Fark (TL)")
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Karşılaştırmalar ekstre ayına göre yapılır. Taksitler, harcamanın özgün tarihi eski olsa bile içinde bulunduğu ekstre dönemine göre raporlanır.")

elif page == "⚙️ Veri Yönetimi":
    title_hero("Veri yönetimi", "Verilerini dışa aktar ve geçmiş ayların yedeğini al.")
    st.info("Finansal işlem verileri GitHub koduna yazılmaz; Firebase Firestore'da oturum açan kullanıcıya ait olarak tutulur.")
    if st.button("📦 Tüm kayıtları hazırla", type="primary"):
        try:
            txs = load_transactions(uid, limit=1000)
            budgets = load_collection(uid, "monthly_budgets")
            cards = load_collection(uid, "cards")
            statements = load_collection(uid, "statements")
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
