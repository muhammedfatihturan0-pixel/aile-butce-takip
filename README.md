# Aile Bütçe Takip — v5

- Firebase Authentication e-posta/şifre girişi
- Firestore REST API üzerinden kullanıcı sahipliği kontrolü
- Ana sayfada modül kartlarıyla sade gezinme
- İşlem defteri Genel Bakış ekranına taşındı
- Bütçe ve borç/ödeme durumu tek modülde birleştirildi
- Türkçe ay adları ve otomatik tarihli hızlı nakit gideri
- PDF/CSV/XLSX ekstre içe aktarımı ve onaylı kayıt
- Kategori, işletme, kişi ve ay karşılaştırmaları

## Yayınlama
1. `app.py`, `requirements.txt`, `packages.txt`, `README.md` ve `firestore.rules` dosyalarını GitHub deposunda güncelleyin.
2. Firebase Console → Firestore Database → Rules bölümünde `firestore.rules` içeriğini yayımlayın. `cards` ve `statements` koleksiyonları kurallara dahil olmalı.
3. Streamlit Cloud uygulamasının Secrets ayarlarını koruyun. Yeniden dağıtım başlayınca modülleri test edin.

## Güvenlik
Firebase Admin SDK özel anahtarını GitHub'a yüklemeyin. Web API anahtarı, e-posta/şifre girişi ve Firestore kuralları dışında gizli anahtarları kaynak koda gömmeyin.
