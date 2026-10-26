import hashlib
import json
import re
import time
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Aile Bütçe Takip", page_icon="💰", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 1.4rem; max-width: 1400px;}
[data-testid="stMetric"] {background: rgba(128,128,128,.08); padding: 14px 16px; border-radius: 12px;}
</style>
""", unsafe_allow_html=True)

CATEGORIES = [
    "Market", "Fatura", "Ulaşım / Akaryakıt", "Giyim", "Çocuk",
    "Restoran / Yemek", "Sağlık", "Abonelik", "Ev / Eşya",
    "Eğitim", "Taksit", "İade", "Kart ödemesi", "Nakit çekim", "Diğer"
]
ROOT_COLLECTIONS = {"monthly_budgets", "transactions"}

def secret_section(name):
    try:
        return st.secrets[name]
    except Exception:
        return {}

FB = secret_section("firebase")
AI = secret_section("openai")
PROJECT_ID = str(FB.get("project_id", "")).strip()
API_KEY = str(FB.get("api_key", "")).strip()
FS_ROOT = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents" if PROJECT_ID else ""

def money(v):
    try:
        return f"{float(v):,.0f} TL".replace(",", ".")
    except (ValueError, TypeError):
        return "0 TL"

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
    return {k: from_fs_value(v) for k, v in fields.items()}

def to_fs_fields(data):
    return {k: to_fs_value(v) for k, v in data.items()}

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
            msg = response.json().get("error", {}).get("message", "Giriş başarısız.")
        except Exception:
            msg = "Giriş başarısız."
        raise ValueError(msg.replace("_", " "))
    data = response.json()
    st.session_state["auth"] = {
        "id_token": data["idToken"],
        "refresh_token": data["refreshToken"],
        "uid": data["localId"],
        "email": data.get("email", email),
        "expires_at": time.time() + int(data.get("expiresIn", 3600)) - 60,
    }

def current_auth():
    return st.session_state.get("auth")

def logout():
    st.session_state.pop("auth", None)
    st.session_state.pop("import_preview", None)
    st.rerun()

def get_id_token():
    auth = current_auth()
    if not auth:
        raise RuntimeError("Oturum açılmamış.")
    if time.time() < auth["expires_at"]:
        return auth["id_token"]
    response = requests.post(
        f"https://securetoken.googleapis.com/v1/token?key={API_KEY}",
        data={"grant_type": "refresh_token", "refresh_token": auth["refresh_token"]},
        timeout=20,
    )
    if response.status_code != 200:
        st.session_state.pop("auth", None)
        raise RuntimeError("Oturum süresi doldu. Yeniden giriş yapın.")
    data = response.json()
    auth.update({
        "id_token": data["id_token"],
        "refresh_token": data.get("refresh_token", auth["refresh_token"]),
        "uid": data.get("user_id", auth["uid"]),
        "expires_at": time.time() + int(data.get("expires_in", 3600)) - 60,
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

def list_documents(collection, filters, order_by=None, limit=1000):
    if collection not in ROOT_COLLECTIONS:
        raise ValueError("İzin verilmeyen koleksiyon.")
    clauses = []
    for field, op, value in filters:
        clauses.append({
            "fieldFilter": {
                "field": {"fieldPath": field},
                "op": op,
                "value": to_fs_value(value),
            }
        })
    where = None
    if len(clauses) == 1:
        where = clauses[0]
    elif clauses:
        where = {"compositeFilter": {"op": "AND", "filters": clauses}}
    query = {"from": [{"collectionId": collection}], "limit": limit}
    if where:
        query["where"] = where
    if order_by:
        query["orderBy"] = [{"field": {"fieldPath": order_by}, "direction": "DESCENDING"}]
    response = fs_request("POST", f"{FS_ROOT}:runQuery", json={"structuredQuery": query})
    rows = []
    for item in response or []:
        doc = item.get("document")
        if not doc:
            continue
        data = from_fs_fields(doc.get("fields", {}))
        data["id"] = doc["name"].rsplit("/", 1)[-1]
        rows.append(data)
    return rows

def create_document(collection, doc_id, data):
    if collection not in ROOT_COLLECTIONS:
        raise ValueError("İzin verilmeyen koleksiyon.")
    params = {"documentId": doc_id} if doc_id else None
    return fs_request("POST", f"{FS_ROOT}/{collection}", params=params, json={"fields": to_fs_fields(data)})

def update_document(collection, doc_id, data):
    if collection not in ROOT_COLLECTIONS:
        raise ValueError("İzin verilmeyen koleksiyon.")
    params = [("updateMask.fieldPaths", k) for k in data.keys()]
    return fs_request("PATCH", f"{FS_ROOT}/{collection}/{doc_id}", params=params, json={"fields": to_fs_fields(data)})

def save_budget(uid, month_key, data):
    data = {**data, "ownerUid": uid, "month": month_key, "updatedAt": datetime.utcnow().isoformat()}
    found = list_documents("monthly_budgets", [("ownerUid", "EQUAL", uid), ("month", "EQUAL", month_key)], limit=2)
    if found:
        update_document("monthly_budgets", found[0]["id"], data)
    else:
        create_document("monthly_budgets", f"{uid}_{month_key}", data)

def get_budget(uid, month_key):
    rows = list_documents("monthly_budgets", [("ownerUid", "EQUAL", uid), ("month", "EQUAL", month_key)], limit=2)
    return rows[0] if rows else None

def save_transaction(uid, data, doc_id=None):
    data = {**data, "ownerUid": uid, "createdAt": datetime.utcnow().isoformat()}
    if doc_id:
        update_document("transactions", doc_id, data)
    else:
        create_document("transactions", None, data)

def load_transactions(uid, month_key=None, limit=1000):
    filters = [("ownerUid", "EQUAL", uid)]
    if month_key:
        filters.append(("month", "EQUAL", month_key))
    return list_documents("transactions", filters, order_by="date", limit=limit)

def default_budget(month_key):
    year, month = map(int, month_key.split("-"))
    emin = 85300 if (year, month) >= (2027, 4) else 71500
    colendi = 9103 if ("2026-10" <= month_key <= "2027-03") else 0
    return {
        "income": {
            "Sizin Maaş": 73800,
            "Eş Maaş": 73200,
            "Sizin Ek Ders": 19800,
            "Eş Ek Ders": 20800,
        },
        "expenses": {
            "Eminevim": emin,
            "Sizin Akbank": 47200,
            "Eş Akbank": 25300,
            "Colendi": colendi,
            "İş Bankası": 5750,
            "Ziraat": 0,
        },
        "notes": "",
    }

def parse_amount(value):
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace("₺", "").replace("TL", "").replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(Decimal(s))
    except (InvalidOperation, ValueError):
        return None

def parse_date(value):
    if pd.isna(value):
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return pd.Timestamp(value).date().isoformat()
    text = str(value).strip()
    for dayfirst in (True, False):
        try:
            return pd.to_datetime(text, dayfirst=dayfirst, errors="raise").date().isoformat()
        except Exception:
            pass
    return None

def dedupe_key(row):
    raw = "|".join([
        str(row.get("date", "")),
        f"{float(row.get('amount', 0)):.2f}",
        re.sub(r"\s+", " ", str(row.get("description", "")).strip().lower()),
        str(row.get("card", "")).strip().lower(),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def call_openai_json(prompt, model=None):
    api_key = str(AI.get("api_key", "")).strip()
    if not api_key:
        raise ValueError("OpenAI API anahtarı Streamlit Secrets içinde tanımlanmamış.")
    model = model or str(AI.get("model", "gpt-4o-mini"))
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "Finans ekstresi işlemlerini sınıflandıran dikkatli bir asistansın. Uydurma işlem oluşturma; belirsizliği belirt."},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=90,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"OpenAI API hata verdi ({response.status_code}): {response.text[:400]}")
    text = response.json()["choices"][0]["message"]["content"]
    return json.loads(text)

def classify_transactions(df):
    cleaned = []
    for idx, row in df.iterrows():
        cleaned.append({
            "index": int(idx),
            "date": str(row.get("Tarih", "")),
            "description": str(row.get("Açıklama", ""))[:180],
            "amount": float(row.get("Tutar (TL)", 0) or 0),
        })
    prompt = (
        "Aşağıdaki liste kredi kartı ekstre işlemleridir. Her işlem için yalnızca şu kategorilerden birini seç: "
        + ", ".join(CATEGORIES)
        + ". Kart ödemesi ile alışverişi ayır; açıklama net değilse Diğer seç. Harcama sahibi için bilgi yoksa 'Belirsiz' yaz. "
        "Yalnızca JSON döndür: {\"transactions\":[{\"index\":0,\"category\":\"Market\",\"owner\":\"Belirsiz\",\"confidence\":\"yüksek|orta|düşük\"}]}. "
        "Girdiler: " + json.dumps(cleaned, ensure_ascii=False)
    )
    result = call_openai_json(prompt)
    out = result.get("transactions", [])
    mapped = {int(x.get("index", -1)): x for x in out if isinstance(x, dict)}
    cats, owners, confidence = [], [], []
    for idx in df.index:
        item = mapped.get(int(idx), {})
        cat = item.get("category", "Diğer")
        cats.append(cat if cat in CATEGORIES else "Diğer")
        owner = item.get("owner", "Belirsiz")
        owners.append(owner if owner in ["Ben", "Eşim", "Diğer", "Belirsiz"] else "Belirsiz")
        confidence.append(item.get("confidence", "düşük"))
    df["Kategori"] = cats
    df["Harcama Sahibi"] = owners
    df["Güven"] = confidence
    return df

def parse_pdf_with_ai(pdf_bytes):
    try:
        from pypdf import PdfReader
        import io
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:
        raise ValueError(f"PDF okunamadı: {exc}")
    if not text.strip():
        raise ValueError("PDF'den metin çıkarılamadı. Taranmış görüntü PDF için OCR gerekir.")
    # Remove likely sensitive account identifiers before sending extracted text to the model.
    text = re.sub(r"\bTR\d{24}\b", "[IBAN GİZLENDİ]", text, flags=re.I)
    text = re.sub(r"\b(?:\d[ -]*?){13,19}\b", "[KART NUMARASI GİZLENDİ]", text)
    text = re.sub(r"\b\d{11}\b", "[KİMLİK NUMARASI GİZLENDİ]", text)
    prompt = (
        "Bir kredi kartı ekstresinin metninden yalnızca gerçek işlem satırlarını çıkar. "
        "Hesap özeti, toplamlar, limitler, müşteri bilgileri, adresler ve ödeme talimatlarını işlem olarak ekleme. "
        "Tutarlar pozitif sayısal TL olsun; iade varsa işlem açıklamasında belirt ve amount pozitif, transactionType='refund' olsun. "
        "Yalnızca JSON döndür: {\"transactions\":[{\"date\":\"YYYY-MM-DD\",\"description\":\"...\",\"amount\":123.45,\"transactionType\":\"purchase|refund|payment\",\"category\":\"...\"}]}. "
        "Tarih veya tutar emin değilse o satırı dahil etme. Kategori şu listeden olsun: " + ", ".join(CATEGORIES) + ".\n"
        "Ekstre metni (tanımlayıcı numaralar ayıklandı):\n" + text[:30000]
    )
    result = call_openai_json(prompt)
    items = result.get("transactions", [])
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        tx_date = parse_date(item.get("date"))
        amount = parse_amount(item.get("amount"))
        desc = str(item.get("description", "")).strip()
        if not tx_date or amount is None or not desc:
            continue
        category = item.get("category", "Diğer")
        rows.append({
            "Tarih": tx_date,
            "Açıklama": desc,
            "Tutar (TL)": amount,
            "Kategori": category if category in CATEGORIES else "Diğer",
            "Harcama Sahibi": "Belirsiz",
            "Güven": "orta",
            "İşlem Türü": item.get("transactionType", "purchase"),
        })
    return pd.DataFrame(rows)

def show_login():
    st.title("💰 Aile Bütçe Takip")
    st.write("Devam etmek için Firebase hesabınla giriş yap.")
    with st.form("login"):
        email = st.text_input("E-posta", autocomplete="email")
        password = st.text_input("Şifre", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Giriş yap", type="primary", use_container_width=True)
    if submitted:
        if not API_KEY or not PROJECT_ID:
            st.error("Uygulama ayarları eksik. Streamlit Cloud → Settings → Secrets bölümünü tamamlayın.")
        elif not email.strip() or not password:
            st.error("E-posta ve şifre girin.")
        else:
            try:
                login(email.strip(), password)
                st.rerun()
            except Exception as exc:
                st.error(f"Giriş başarısız: {exc}")
    st.caption("Hesap oluşturma uygulama içinden kapalıdır. Kullanıcı Firebase Authentication konsolundan yönetilir.")

if not API_KEY or not PROJECT_ID:
    st.title("💰 Aile Bütçe Takip")
    st.error("Firebase yapılandırması eksik. Streamlit Cloud → Settings → Secrets bölümüne [firebase] project_id ve api_key değerlerini ekleyin.")
    st.code('[firebase]\nproject_id = "aile-butce-takip-14da8"\napi_key = "WEB_API_KEY_BURAYA"\n\n[openai]\napi_key = "OPENAI_API_KEY_BURAYA"\nmodel = "gpt-4o-mini"', language="toml")
    st.stop()

if not current_auth():
    show_login()
    st.stop()

auth = current_auth()
uid = auth["uid"]
with st.sidebar:
    st.markdown("### Aile Bütçe Takip")
    st.caption(auth.get("email", "Giriş yapıldı"))
    if st.button("Güvenli çıkış", use_container_width=True):
        logout()
    page = st.radio("Menü", [
        "Genel Bakış", "Aylık Bütçe", "Harcama Kayıtları",
        "Ekstre Yükleme", "Karşılaştırmalar", "Ayarlar"
    ])
    today = date.today()
    month_options = [f"{y}-{m:02d}" for y in range(2026, 2031) for m in range(1, 13)]
    current_key = today.strftime("%Y-%m")
    selected_month = st.selectbox(
        "Bütçe / ekstre ayı",
        options=month_options,
        index=month_options.index(current_key) if current_key in month_options else 9,
        format_func=lambda key: datetime.strptime(key, "%Y-%m").strftime("%B %Y")
    )

try:
    budget = get_budget(uid, selected_month) or default_budget(selected_month)
except Exception as exc:
    st.error(f"Firebase'e erişilemedi: {exc}")
    st.info("Firestore güvenlik kurallarını ve Firebase yapılandırmasını kontrol edin.")
    st.stop()

income = budget.get("income", {})
expenses = budget.get("expenses", {})
total_income = sum(float(v or 0) for v in income.values())
total_expenses = sum(float(v or 0) for v in expenses.values())

st.title("Aile Bütçe Takip")
if page == "Genel Bakış":
    st.subheader(datetime.strptime(selected_month, "%Y-%m").strftime("%B %Y") + " özeti")
    a, b, c = st.columns(3)
    a.metric("Toplam gelir", money(total_income))
    b.metric("Planlanan gider / ödeme", money(total_expenses))
    c.metric("Planlanan kalan nakit", money(total_income-total_expenses))
    st.caption("Planlanan bütçe ile gerçekleşen kart harcamaları ayrı tutulur. Ekstre harcamaları, kart ödemeleriyle çift sayılmamalıdır.")
    left, right = st.columns(2)
    with left:
        st.markdown("#### Gelirler")
        st.dataframe(pd.DataFrame([{"Kalem": k, "Tutar (TL)": v} for k,v in income.items()]), hide_index=True, use_container_width=True)
    with right:
        st.markdown("#### Giderler / ödeme planı")
        st.dataframe(pd.DataFrame([{"Kalem": k, "Tutar (TL)": v} for k,v in expenses.items()]), hide_index=True, use_container_width=True)
    txs = load_transactions(uid, selected_month)
    if txs:
        df = pd.DataFrame(txs)
        st.markdown("#### Kaydedilmiş kart / harcama işlemleri")
        st.metric("İşlem toplamı", money(df["amount"].astype(float).sum()))
        st.dataframe(df[[c for c in ["date","description","category","owner","card","amount","transactionType"] if c in df.columns]], hide_index=True, use_container_width=True)

elif page == "Aylık Bütçe":
    st.subheader(f"Aylık bütçeyi düzenle — {selected_month}")
    st.caption("Her ay bağımsız kaydedilir. Geçmiş ayları seçip değerlerini ayrıca girebilirsin.")
    with st.form("budget_form"):
        st.markdown("### Gelirler")
        new_income = {}
        a, b = st.columns(2)
        for i, (name, val) in enumerate(income.items()):
            with (a if i % 2 == 0 else b):
                new_income[name] = st.number_input(name, min_value=0.0, value=float(val or 0), step=100.0, key=f"inc_{selected_month}_{name}")
        st.markdown("### Giderler / ödeme planı")
        new_expenses = {}
        a, b = st.columns(2)
        for i, (name, val) in enumerate(expenses.items()):
            with (a if i % 2 == 0 else b):
                new_expenses[name] = st.number_input(name, min_value=0.0, value=float(val or 0), step=100.0, key=f"exp_{selected_month}_{name}")
        notes = st.text_area("Ay notu", value=budget.get("notes", ""), key=f"notes_{selected_month}")
        submitted = st.form_submit_button("Bütçeyi kaydet", type="primary")
    if submitted:
        try:
            save_budget(uid, selected_month, {"income": new_income, "expenses": new_expenses, "notes": notes})
            st.success("Seçili ayın bütçesi kaydedildi.")
            st.rerun()
        except Exception as exc:
            st.error(f"Kaydedilemedi: {exc}")
    st.markdown("### Ek gelir veya gider kalemi ekle")
    with st.form("add_budget_item"):
        col1, col2, col3 = st.columns([1,2,1])
        with col1:
            item_type = st.selectbox("Tür", ["income", "expenses"], format_func=lambda x: "Gelir" if x=="income" else "Gider")
        with col2:
            item_name = st.text_input("Kalem adı")
        with col3:
            item_value = st.number_input("Tutar (TL)", min_value=0.0, step=100.0)
        add_item = st.form_submit_button("Kalemi ekle")
    if add_item:
        if not item_name.strip():
            st.error("Kalem adı girin.")
        else:
            changed = {"income": dict(income), "expenses": dict(expenses), "notes": budget.get("notes", "")}
            changed[item_type][item_name.strip()] = item_value
            try:
                save_budget(uid, selected_month, changed)
                st.success("Kalem eklendi.")
                st.rerun()
            except Exception as exc:
                st.error(f"Kalem eklenemedi: {exc}")

elif page == "Harcama Kayıtları":
    st.subheader("Manuel harcama / işlem kaydı")
    with st.form("transaction_form"):
        c1,c2,c3 = st.columns(3)
        with c1:
            tx_date = st.date_input("İşlem tarihi", value=date.today())
            amount = st.number_input("Tutar (TL)", min_value=0.01, step=10.0)
        with c2:
            desc = st.text_input("Açıklama")
            category = st.selectbox("Kategori", CATEGORIES)
        with c3:
            owner = st.selectbox("Harcamayı yapan", ["Ben","Eşim","Diğer","Belirsiz"])
            card = st.text_input("Kart / hesap")
        tx_type = st.selectbox("İşlem türü", ["purchase","installment","refund","payment"], format_func=lambda x: {"purchase":"Harcama","installment":"Taksit","refund":"İade","payment":"Kart ödemesi"}[x])
        note = st.text_input("Not (isteğe bağlı)")
        save_tx = st.form_submit_button("İşlemi kaydet", type="primary")
    if save_tx:
        if not desc.strip():
            st.error("İşlem açıklaması gerekli.")
        else:
            row = {"date":tx_date.isoformat(),"month":tx_date.strftime("%Y-%m"),"amount":float(amount),
                   "description":desc.strip(),"category":category,"owner":owner,"card":card.strip(),
                   "note":note.strip(),"transactionType":tx_type}
            row["dedupeKey"] = dedupe_key(row)
            try:
                existing = load_transactions(uid, row["month"])
                if any(x.get("dedupeKey") == row["dedupeKey"] for x in existing):
                    st.warning("Aynı işlem zaten kayıtlı görünüyor; mükerrer kayıt oluşturulmadı.")
                else:
                    save_transaction(uid,row)
                    st.success("İşlem kaydedildi.")
                    st.rerun()
            except Exception as exc:
                st.error(f"Kaydedilemedi: {exc}")
    st.markdown("### Seçili ayın kayıtları")
    try:
        rows = load_transactions(uid, selected_month)
        if rows:
            df = pd.DataFrame(rows)
            view_cols = [c for c in ["date","description","category","owner","card","amount","transactionType","note"] if c in df.columns]
            st.dataframe(df[view_cols].sort_values("date", ascending=False), hide_index=True, use_container_width=True)
            st.download_button("CSV olarak indir", df[view_cols].to_csv(index=False).encode("utf-8-sig"), f"harcamalar_{selected_month}.csv", "text/csv")
        else:
            st.info("Bu ay için işlem kaydı yok.")
    except Exception as exc:
        st.error(f"Kayıtlar alınamadı: {exc}")

elif page == "Ekstre Yükleme":
    st.subheader("Ekstre yükleme ve kategorilendirme")
    st.warning("Ekstre metni üçüncü taraf yapay zekâ API'sine gönderilebilir. Yüklemeden önce dosyanı kontrol et. Kod, kart numarası/IBAN gibi belirli numaraları PDF metninden ayıklamaya çalışır; dosyadaki tüm kişisel bilgilerin temizlendiğini garanti etmez.")
    uploaded = st.file_uploader("PDF, CSV veya Excel ekstresi", type=["pdf","csv","xlsx","xls"])
    card_name = st.text_input("Kart / hesap adı", placeholder="Örn. Benim Akbank kartım")
    if uploaded:
        if uploaded.name.lower().endswith(".pdf"):
            st.caption("PDF ayrıştırması ve kategorilendirme API kullanır; taranmış görüntü PDF için OCR gerekebilir.")
            if st.button("PDF'yi analiz et ve işlemleri çıkar", type="primary"):
                try:
                    with st.spinner("PDF metni ayrıştırılıyor ve işlemler çıkarılıyor..."):
                        df = parse_pdf_with_ai(uploaded.getvalue())
                    if df.empty:
                        st.warning("PDF'den güvenilir işlem satırı çıkarılamadı.")
                    else:
                        df["Kart"] = card_name
                        st.session_state["import_preview"] = df
                        st.success(f"{len(df)} işlem bulundu. Kaydetmeden önce tabloyu kontrol et.")
                except Exception as exc:
                    st.error(f"PDF analiz edilemedi: {exc}")
        else:
            try:
                if uploaded.name.lower().endswith(".csv"):
                    raw_df = pd.read_csv(uploaded)
                else:
                    raw_df = pd.read_excel(uploaded)
                st.write("Dosyadan okunan örnek satırlar")
                st.dataframe(raw_df.head(10), use_container_width=True)
                cols = list(raw_df.columns)
                st.markdown("#### Sütun eşleştirme")
                c1,c2,c3 = st.columns(3)
                with c1:
                    date_col = st.selectbox("Tarih sütunu", cols, key="import_date_col")
                with c2:
                    desc_col = st.selectbox("Açıklama sütunu", cols, index=min(1,len(cols)-1), key="import_desc_col")
                with c3:
                    amount_col = st.selectbox("Tutar sütunu", cols, index=min(2,len(cols)-1), key="import_amount_col")
                if st.button("İşlemleri hazırla", type="primary"):
                    tmp = pd.DataFrame()
                    tmp["Tarih"] = raw_df[date_col].map(parse_date)
                    tmp["Açıklama"] = raw_df[desc_col].astype(str).str.strip()
                    tmp["Tutar (TL)"] = raw_df[amount_col].map(parse_amount)
                    tmp = tmp.dropna(subset=["Tarih","Tutar (TL)"])
                    tmp = tmp[tmp["Açıklama"].str.len() > 0].reset_index(drop=True)
                    tmp["Kategori"] = "Diğer"
                    tmp["Harcama Sahibi"] = "Belirsiz"
                    tmp["Güven"] = "düşük"
                    tmp["İşlem Türü"] = "purchase"
                    tmp["Kart"] = card_name
                    st.session_state["import_preview"] = tmp
                if st.session_state.get("import_preview") is not None and st.button("Yapay zekâyla kategorilendir", key="categorize_csv"):
                    with st.spinner("İşlemler kategorilendiriliyor..."):
                        current = st.session_state["import_preview"].copy()
                        current = classify_transactions(current)
                        st.session_state["import_preview"] = current
            except Exception as exc:
                st.error(f"Dosya okunamadı: {exc}")
    preview = st.session_state.get("import_preview")
    if preview is not None and not preview.empty:
        st.markdown("### Kaydetmeden önce kontrol et")
        editable = st.data_editor(preview, num_rows="dynamic", use_container_width=True, key="editable_import")
        if st.button("Onaylanan işlemleri Firebase'e kaydet", type="primary"):
            try:
                existing_by_month = {}
                saved, duplicates = 0, 0
                with st.spinner("İşlemler kaydediliyor..."):
                    for _, r in editable.iterrows():
                        tx_date = parse_date(r.get("Tarih"))
                        amount = parse_amount(r.get("Tutar (TL)"))
                        desc = str(r.get("Açıklama", "")).strip()
                        if not tx_date or amount is None or not desc:
                            continue
                        month = tx_date[:7]
                        if month not in existing_by_month:
                            existing_by_month[month] = load_transactions(uid, month)
                        owner = str(r.get("Harcama Sahibi", "Belirsiz"))
                        if owner not in ["Ben","Eşim","Diğer","Belirsiz"]:
                            owner = "Belirsiz"
                        cat = str(r.get("Kategori", "Diğer"))
                        if cat not in CATEGORIES:
                            cat = "Diğer"
                        row = {
                            "date":tx_date, "month":month, "amount":float(amount),
                            "description":desc, "category":cat, "owner":owner,
                            "card":str(r.get("Kart", card_name) or card_name),
                            "note":"Ekstre içe aktarımı",
                            "transactionType":str(r.get("İşlem Türü","purchase")),
                        }
                        row["dedupeKey"] = dedupe_key(row)
                        if any(x.get("dedupeKey") == row["dedupeKey"] for x in existing_by_month[month]):
                            duplicates += 1
                            continue
                        save_transaction(uid,row)
                        existing_by_month[month].append(row)
                        saved += 1
                st.session_state.pop("import_preview", None)
                st.success(f"{saved} işlem kaydedildi. {duplicates} mükerrer işlem atlandı.")
                st.rerun()
            except Exception as exc:
                st.error(f"İçe aktarım başarısız: {exc}")

elif page == "Karşılaştırmalar":
    st.subheader("Aylık ve kategori bazlı karşılaştırma")
    try:
        budgets = list_documents("monthly_budgets", [("ownerUid","EQUAL",uid)], order_by="month", limit=1000)
        if budgets:
            rows = []
            for b in budgets:
                inc, exp = b.get("income",{}), b.get("expenses",{})
                income_total = sum(float(v or 0) for v in inc.values())
                expense_total = sum(float(v or 0) for v in exp.values())
                rows.append({"Ay":b.get("month", ""), "Gelir (TL)":income_total, "Planlanan gider (TL)":expense_total, "Planlanan kalan (TL)":income_total-expense_total})
            bdf = pd.DataFrame(rows).sort_values("Ay")
            st.markdown("#### Bütçe geçmişi")
            st.dataframe(bdf, hide_index=True, use_container_width=True)
            st.line_chart(bdf.set_index("Ay"))
        transactions = load_transactions(uid, limit=1000)
        if transactions:
            df = pd.DataFrame(transactions)
            if {"month","category","amount"}.issubset(df.columns):
                st.markdown("#### Kategori bazında aylar")
                pivot = df.pivot_table(index="category", columns="month", values="amount", aggfunc="sum", fill_value=0)
                st.dataframe(pivot, use_container_width=True)
                st.bar_chart(pivot)
                st.markdown("#### Kişi bazında aylar")
                if "owner" in df.columns:
                    owner_pivot = df.pivot_table(index="owner", columns="month", values="amount", aggfunc="sum", fill_value=0)
                    st.dataframe(owner_pivot, use_container_width=True)
    except Exception as exc:
        st.error(f"Karşılaştırma yüklenemedi: {exc}")

elif page == "Ayarlar":
    st.subheader("Ayarlar ve veri dışa aktarma")
    st.write("Firebase projesi:", PROJECT_ID)
    st.info("Hesap oluşturma uygulama içinden kapalıdır. Yeni kullanıcılar Firebase Authentication konsolundan eklenir.")
    st.markdown("### Tüm harcamaları dışa aktar")
    if st.button("Tüm harcamaları getir"):
        try:
            rows = load_transactions(uid, limit=1000)
            if rows:
                df = pd.DataFrame(rows)
                st.download_button("CSV indir", df.to_csv(index=False).encode("utf-8-sig"), "tum_harcamalar.csv", "text/csv")
                st.download_button("Excel indir", df.to_excel(index=False, engine="openpyxl") if False else df.to_csv(index=False).encode("utf-8-sig"), "tum_harcamalar.csv", "text/csv")
            else:
                st.info("Dışa aktarılacak işlem bulunamadı.")
        except Exception as exc:
            st.error(f"Dışa aktarma başarısız: {exc}")

st.divider()
st.caption("Aile Bütçe Takip • Her kayıt oturum açan Firebase kullanıcısına ait olarak saklanır.")
