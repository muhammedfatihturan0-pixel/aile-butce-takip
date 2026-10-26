# Aile Bütçe Takip — v6

- Firebase Authentication e-posta/şifre girişi
- Firestore REST API üzerinden kullanıcı sahipliği kontrolü
- Ana sayfada modül kartlarıyla sade gezinme
- İşlem defteri Genel Bakış ekranına taşındı
- Bütçe ve borç/ödeme durumu tek modülde birleştirildi
- Türkçe ay adları ve otomatik tarihli hızlı nakit gideri
- Mayıs–Ekim 2026 geçmiş Axess ekstrelerinin ilk girişte otomatik ve mükerrer korumalı aktarımı
- PDF/CSV/XLSX ekstre içe aktarımı ve onaylı kayıt
- Kategori, işletme, kişi ve ay karşılaştırmaları

## Yayınlama
1. `app.py`, `requirements.txt`, boş `packages.txt`, `README.md`, `firestore.rules` ve `data/Axess_Gecmis_Ekstre_Aktarim.xlsx` dosyalarını GitHub deposunda güncelleyin.
2. Firebase Console → Firestore Database → Rules bölümünde `firestore.rules` içeriğini yayımlayın. `cards`, `statements` ve `app_meta` koleksiyonları kurallara dahil olmalı. Kurallar yayımlanınca geçmiş 550 onaylı işlem ilk girişte otomatik yüklenir; 96 kontrol bekleyen ve 28 hariç bırakılan satır otomatik içe aktarılmaz. Tapu harçları ve ilişkili vergi taksitleri hariçtir.
3. Streamlit Cloud uygulamasının Secrets ayarlarını koruyun. Yeniden dağıtım başlayınca modülleri test edin.

## Güvenlik
Firebase Admin SDK özel anahtarını GitHub'a yüklemeyin. Web API anahtarı, e-posta/şifre girişi ve Firestore kuralları dışında gizli anahtarları kaynak koda gömmeyin.
