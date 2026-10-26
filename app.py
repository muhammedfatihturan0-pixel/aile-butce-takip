import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import requests

st.set_page_config(page_title="Aile Bütçe Takip", page_icon="💰", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 1.4rem; max-width: 1400px;}
[data-testid="stMetric"] {background: rgba(128,128,128,.08); padding: 14px 16px; border-radius: 12px;}
</style>
""", unsafe_allow_html=True)

st.title("💰 Aile Bütçe Takip")
st.caption("Gelir, gider, borç ve kredi kartı ekstrelerini tek yerde takip edin.")

def get_firestore():
    if "db" in st.session_state:
        return st.session_state.db
    if "firebase" not in st.secrets:
        st.error("Firebase bağlantısı yapılandırılmamış. Streamlit Secrets ayarlarını tamamlayın.")
        st.stop()
    cfg = st.secrets["firebase"]
    service_json = cfg.get("service_account_json", "")
    if not service_json:
        st.error("Secrets içindeki firebase.service_account_json alanı eksik.")
        st.stop()
    try:
        service_info = json.loads(service_json)
        project_id = cfg.get("project_id") or service_info.get("project_id")
        if not firebase_admin._apps:
            cred = credentials.Certificate(service_info)
            firebase_admin.initialize_app(cred, {"projectId": project_id})
        st.session_state.db = firestore.client()
        return st.session_state.db
    except Exception as e:
        st.error(f"Firebase bağlantısı kurulamadı: {e}")
        st.stop()

def money(v):
    try:
        return f"{float(v):,.0f} TL".replace(",", ".")
    except (ValueError, TypeError):
        return "0 TL"

def read_monthly_budget(db, month_key):
    doc = db.collection("monthly_budgets").document(month_key).get()
    if doc.exists:
        return doc.to_dict()
    return None

def save_monthly_budget(db, month_key, data):
    data["updated_at"] = datetime.utcnow().isoformat()
    db.collection("monthly_budgets").document(month_key).set(data, merge=True)

def load_transactions(db, month_key=None):
    query = db.collection("transactions")
    if month_key:
        query = query.where("month", "==", month_key)
    rows = []
    for d in query.stream():
        row = d.to_dict()
        row["id"] = d.id
        rows.append(row)
    return rows

def ensure_default_budget(db, month_key):
    current = read_monthly_budget(db, month_key)
    if current:
        return current
    year, month = map(int, month_key.split("-"))
    emin = 85300 if (year, month) >= (2027, 4) else 71500
    return {
        "income": {
            "Sizin Maaş": 73800, "Eş Maaş": 73200,
            "Sizin Ek Ders": 19800, "Eş Ek Ders": 20800
        },
        "expenses": {
            "Eminevim": emin, "Sizin Akbank": 47200, "Eş Akbank": 25300,
            "Colendi": 9103 if (year, month) <= (2027, 3) else 0,
            "İş Bankası": 5750, "Ziraat": 0
        },
        "notes": ""
    }

# Sidebar: month selection and login token
with st.sidebar:
    st.header("Menü")
    page = st.radio("Bölüm", [
        "Genel Bakış", "Aylık Bütçe", "Harcama Kayıtları",
        "Ekstre Yükleme", "Karşılaştırmalar", "Ayarlar"
    ])
    selected_month = st.selectbox(
        "Bütçe ayı",
        options=[f"{y}-{m:02d}" for y in range(2026, 2030) for m in range(1, 13)],
        index=(2026-2026)*12 + (10-1),
        format_func=lambda x: datetime.strptime(x, "%Y-%m").strftime("%B %Y")
    )
    st.caption("Veriler Firebase Firestore'da saklanır.")

db = get_firestore()
budget = read_monthly_budget(db, selected_month) or ensure_default_budget(db, selected_month)

income = budget.get("income", {})
expenses = budget.get("expenses", {})
total_income = sum(float(v or 0) for v in income.values())
total_expenses = sum(float(v or 0) for v in expenses.values())
cash_left = total_income - total_expenses

if page == "Genel Bakış":
    st.subheader(datetime.strptime(selected_month, "%Y-%m").strftime("%B %Y") + " özeti")
    c1, c2, c3 = st.columns(3)
    c1.metric("Toplam gelir", money(total_income))
    c2.metric("Toplam gider / ödeme planı", money(total_expenses))
    c3.metric("Planlanan kalan nakit", money(cash_left), delta=money(cash_left))
    st.info("Bu ekran planlanan bütçeyi gösterir. Kredi kartı ekstresi harcamaları ve kart ödemeleri ayrı izlenir; aynı tutarın iki kez gider yazılmaması için ekstre modülü henüz kayıt onayı aşamasındadır.")
    st.subheader("Gelir ve gider dağılımı")
    left, right = st.columns(2)
    with left:
        st.markdown("**Gelirler**")
        if income:
            st.dataframe(pd.DataFrame([{"Kalem": k, "Tutar (TL)": v} for k, v in income.items()]), hide_index=True, use_container_width=True)
    with right:
        st.markdown("**Giderler / ödeme planı**")
        if expenses:
            st.dataframe(pd.DataFrame([{"Kalem": k, "Tutar (TL)": v} for k, v in expenses.items()]), hide_index=True, use_container_width=True)

elif page == "Aylık Bütçe":
    st.subheader(f"Aylık bütçe düzenle — {selected_month}")
    st.caption("Her ay ayrı kayıt edilir. Bir ayı değiştirmeniz diğer ayların kayıtlarını değiştirmez.")
    with st.form("budget_form"):
        st.markdown("### Gelirler")
        new_income = {}
        c1, c2 = st.columns(2)
        for i, (name, val) in enumerate(income.items()):
            with (c1 if i % 2 == 0 else c2):
                new_income[name] = st.number_input(name, min_value=0.0, value=float(val), step=100.0, key=f"inc_{selected_month}_{name}")
        if st.button("Gelir kalemi ekle"):
            st.session_state["add_income"] = True
        st.markdown("### Giderler / ödeme planı")
        new_expenses = {}
        c1, c2 = st.columns(2)
        for i, (name, val) in enumerate(expenses.items()):
            with (c1 if i % 2 == 0 else c2):
                new_expenses[name] = st.number_input(name, min_value=0.0, value=float(val), step=100.0, key=f"exp_{selected_month}_{name}")
        notes = st.text_area("Ay notu", value=budget.get("notes", ""), key=f"notes_{selected_month}")
        submitted = st.form_submit_button("Bu ayın bütçesini kaydet", type="primary")
    if submitted:
        save_monthly_budget(db, selected_month, {"income": new_income, "expenses": new_expenses, "notes": notes, "month": selected_month})
        st.success("Bu ayın bütçesi kaydedildi.")
        st.rerun()
    if st.session_state.get("add_income"):
        st.markdown("#### Yeni gelir kalemi")
        with st.form("new_income_form"):
            ni_name = st.text_input("Kalem adı")
            ni_amount = st.number_input("Aylık tutar (TL)", min_value=0.0, step=100.0)
            if st.form_submit_button("Kalemi ekle"):
                if ni_name.strip():
                    new = read_monthly_budget(db, selected_month) or budget
                    new.setdefault("income", {})[ni_name.strip()] = ni_amount
                    save_monthly_budget(db, selected_month, new)
                    st.session_state["add_income"] = False
                    st.rerun()

elif page == "Harcama Kayıtları":
    st.subheader("Harcama kayıtları")
    with st.form("transaction_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            tx_date = st.date_input("İşlem tarihi", value=date.today())
            tx_amount = st.number_input("Tutar (TL)", min_value=0.01, step=10.0)
        with c2:
            tx_desc = st.text_input("Açıklama")
            tx_category = st.selectbox("Kategori", ["Market", "Fatura", "Ulaşım / Akaryakıt", "Giyim", "Çocuk", "Restoran / Yemek", "Sağlık", "Abonelik", "Taksit", "İade", "Kart ödemesi", "Diğer"])
        with c3:
            tx_owner = st.selectbox("Harcamayı yapan", ["Ben", "Eşim", "Diğer"])
            tx_card = st.text_input("Kart / hesap adı")
        tx_note = st.text_input("Not (isteğe bağlı)")
        add_tx = st.form_submit_button("Harcamayı kaydet", type="primary")
    if add_tx:
        if not tx_desc.strip():
            st.error("Lütfen işlem açıklaması girin.")
        else:
            tx_month = tx_date.strftime("%Y-%m")
            db.collection("transactions").add({
                "date": tx_date.isoformat(), "month": tx_month, "amount": float(tx_amount),
                "description": tx_desc.strip(), "category": tx_category, "owner": tx_owner,
                "card": tx_card.strip(), "note": tx_note.strip(), "source": "manual",
                "created_at": datetime.utcnow().isoformat()
            })
            st.success("Harcama kaydedildi.")
            st.rerun()
    st.markdown("### Seçili ayın işlemleri")
    rows = load_transactions(db, selected_month)
    if rows:
        df = pd.DataFrame(rows)
        cols = [c for c in ["date", "description", "category", "owner", "card", "amount", "note"] if c in df.columns]
        st.dataframe(df[cols].sort_values("date", ascending=False), hide_index=True, use_container_width=True)
        st.download_button("İşlemleri CSV indir", df[cols].to_csv(index=False).encode("utf-8-sig"), f"harcamalar_{selected_month}.csv", "text/csv")
    else:
        st.info("Bu ay için kayıtlı harcama bulunmuyor.")

elif page == "Ekstre Yükleme":
    st.subheader("Kredi kartı ekstresi yükle")
    st.warning("Bu ilk sürümde dosyalar yalnızca analiz için yüklenir; otomatik sınıflandırma ve Firebase'e kaydetme adımı henüz bağlanmadı. Kayıt önizlemesi onay mekanizmasıyla eklenecek.")
    uploaded = st.file_uploader("PDF, CSV veya Excel ekstre seç", type=["pdf", "csv", "xlsx", "xls"])
    if uploaded:
        st.write("Dosya:", uploaded.name, f"({uploaded.size:,} bayt)")
        if uploaded.name.lower().endswith(".csv"):
            try:
                preview = pd.read_csv(uploaded)
                st.dataframe(preview.head(30), use_container_width=True)
            except Exception as e:
                st.error(f"CSV okunamadı: {e}")
        elif uploaded.name.lower().endswith((".xlsx", ".xls")):
            try:
                preview = pd.read_excel(uploaded)
                st.dataframe(preview.head(30), use_container_width=True)
            except Exception as e:
                st.error(f"Excel okunamadı: {e}")
        else:
            st.info("PDF ayrıştırma, OCR ve yapay zekâ sınıflandırması bir sonraki geliştirme aşamasında eklenecek.")

elif page == "Karşılaştırmalar":
    st.subheader("Geçmiş ay karşılaştırmaları")
    all_budgets = []
    for doc in db.collection("monthly_budgets").stream():
        d = doc.to_dict()
        inc = d.get("income", {})
        exp = d.get("expenses", {})
        all_budgets.append({
            "Ay": doc.id,
            "Gelir (TL)": sum(float(v or 0) for v in inc.values()),
            "Ödeme planı (TL)": sum(float(v or 0) for v in exp.values()),
            "Kalan (TL)": sum(float(v or 0) for v in inc.values()) - sum(float(v or 0) for v in exp.values())
        })
    if all_budgets:
        df = pd.DataFrame(all_budgets).sort_values("Ay")
        st.dataframe(df, hide_index=True, use_container_width=True)
        st.line_chart(df.set_index("Ay")[["Gelir (TL)", "Ödeme planı (TL)", "Kalan (TL)"]])
    tx_rows = load_transactions(db)
    if tx_rows:
        txdf = pd.DataFrame(tx_rows)
        st.markdown("### Kategori bazlı harcama karşılaştırması")
        if {"month", "category", "amount"}.issubset(txdf.columns):
            pivot = txdf.pivot_table(index="category", columns="month", values="amount", aggfunc="sum", fill_value=0)
            st.dataframe(pivot, use_container_width=True)
            st.bar_chart(pivot)

elif page == "Ayarlar":
    st.subheader("Ayarlar ve yedekleme")
    st.write("Firebase projesi:", st.secrets.get("firebase", {}).get("project_id", "Yapılandırılmadı"))
    st.info("Verileri CSV/Excel olarak dışa aktarma araçları modüllere göre eklenecek. Firebase'in otomatik yedeklemesi ücretsiz Spark planında etkin değil.")
    st.markdown("### Veri yedekleme")
    if st.button("Tüm harcamaları CSV olarak hazırla"):
        rows = load_transactions(db)
        if rows:
            st.download_button("CSV dosyasını indir", pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig"), "tum_harcamalar.csv", "text/csv")
        else:
            st.info("Dışa aktarılacak harcama kaydı bulunmuyor.")

st.divider()
st.caption("Aile Bütçe Takip • İlk kurulum sürümü. Kişisel finans verilerini yalnızca güvenli, size ait hesaplarda tutun.")
