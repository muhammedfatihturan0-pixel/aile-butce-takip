# Aile Bütçe Takip

Streamlit + Firebase Firestore tabanlı aile bütçesi, borç ve kredi kartı takip uygulaması.

## Özellikler (ilk sürüm)

- Aylık gelir ve ödeme planı kayıtları
- Ay bazında bağımsız bütçeler
- Manuel harcama kayıtları
- CSV/Excel önizlemesi
- Aylık bütçe ve kategori karşılaştırmaları
- Firestore'da kalıcı veri saklama

## Kurulum

1. GitHub deposuna dosyaları yükleyin.
2. Streamlit Community Cloud'da bu depoyu seçerek uygulamayı `app.py` dosyasından yayımlayın.
3. App settings → Secrets bölümüne `.streamlit/secrets.toml.example` dosyasındaki yapıyı kendi değerlerinizle girin.
4. Firebase Console'da Firestore ve Authentication ayarlarını tamamlayın.

## Güvenlik

- Firebase Admin SDK JSON dosyasını repoya yüklemeyin.
- Gerçek anahtarları README, kod veya issue'lara yazmayın.
- Admin SDK, Firestore güvenlik kurallarını atlayabildiğinden uygulamayı yalnızca güvenilir kullanıcılara açın.
- Bu başlangıç sürümü kullanıcı arayüzü kimlik doğrulamasını henüz tamamlamaz; yayına almadan önce erişim kontrolü eklenmelidir.

## Firebase Secrets örneği

`.streamlit/secrets.toml.example` dosyasını referans alın. Bu örneği gerçek sırlarla repoya yüklemeyin; değerleri Streamlit Cloud Secrets paneline girin.
