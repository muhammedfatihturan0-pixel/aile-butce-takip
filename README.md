# Aile Bütçe Takip v12 — Ana sayfa sadeleştirme

## Değişiklikler
- Ekstre İçe Aktar, Kartlar ve Ekstreler, Ay Karşılaştırma sayfaları ana sayfadaki modül kartlarından ve geçerli sayfa listesinden çıkarıldı.
- Ayı kapat / yeniden aç kontrolü Genel Bakış ana sayfasına taşındı.
- Kategori özeti ayrı ekstre ekranından kaldırıldı; Harcama Analizi modülü korunuyor.
- Mevcut Firestore kayıtları silinmez; geçmiş işlemler Harcama Analizi ve Veri Yönetimi üzerinden kullanılabilir.

## Kurulum
1. GitHub deposundaki `app.py` dosyasını bu dosyayla değiştirin ve commit edin.
2. Firebase kurallarınız zaten v11 sürümündeki güvenli `ownerUid` kurallarıysa tekrar değiştirmek gerekmez. Değilse `firestore.rules` dosyasını Firebase Console → Firestore Database → Rules bölümünde yayımlayın.
3. Streamlit dağıtımı tamamlandıktan sonra sayfayı yenileyin.

Python sözdizimi kontrol edildi; canlı Firebase ortamında uçtan uca test edilmedi.
