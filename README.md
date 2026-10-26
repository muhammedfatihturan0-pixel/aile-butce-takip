# Aile Bütçe Takip — v4

Streamlit + Firebase Authentication + Firestore ile aile bütçesi, kart ekstresi, borç ve kategori karşılaştırmaları.

## Bu sürümde
- Tüm ay adları Türkçe gösterilir; varsayılan dönem Türkiye tarihine göre seçilir.
- İşlem defterinde tek alanlı hızlı gider kaydı vardır: yalnızca tutarı girilir, tarih otomatik atanır.
- Ekstreler PDF/Excel/CSV yüklemesiyle analiz edilir; kategori, işletme (ör. A101, BİM, Migros), kişi ve kart gözden geçirilip aktarılır.
- Kartlar kişiye göre tanımlanır ve her kart için seçili aya özel **Ekstreyi kapat / yeniden aç** işlemi bulunur. Kapalı karta/aya geç işlem aktarımı engellenir.
- Borç ve ödeme ekranında mevcut kart/borç tutarı seçili ay için güncellenir; yeni özel borç kategorisi eklenebilir ve kişi/tür/bağlı hesap/ödeme durumu kaydedilir. Bu tutarlar Aylık Bütçe toplamlarıyla aynı kayıtlardan gelir ve iki kez sayılmaz.
- Firestore sorguları yalnızca `ownerUid` filtresiyle yapılır; ay, kart ve sıralama uygulamada filtrelenir. Böylece eksik composite index hatasının önüne geçilir.
- Tapu harcı satırları ekstre analizinden hariç bırakılır. Belirsiz OCR tutarları kontrol edilmeden otomatik dahil edilmez.

## Güncelleme
1. ZIP'i açın. `app.py`, `requirements.txt`, `packages.txt`, `firestore.rules` ve `README.md` dosyalarını GitHub deposundakilerle değiştirin veya ekleyin.
2. Commit edin ve Streamlit Cloud'un yeniden dağıtımını bekleyin.
3. Firebase Console → Firestore Database → Rules bölümünde `firestore.rules` içeriğini yayımlayın.
4. Ekstre işlemlerini yüklemeden önce Kartlar ve Ekstreler bölümünde her fiziksel kartı ayrı kaydedin; kart sahibi ve kesim/ödeme günlerini tanımlayın.

## Secrets
```toml
[firebase]
project_id = "aile-butce-takip-14da8"
api_key = "FIREBASE_WEB_APP_API_KEY"

[openai]
api_key = "OPENAI_API_KEY"
model = "gpt-4o-mini"
```
Yapay zekâ anahtarı kullanılmayacaksa `[openai]` bölümü eklenmeyebilir. Admin SDK özel anahtarı bu sürümde kullanılmaz ve GitHub'a yüklenmemelidir.
