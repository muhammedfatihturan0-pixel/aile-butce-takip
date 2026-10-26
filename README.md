# Aile Bütçe Takip

Streamlit + Firebase Authentication + Cloud Firestore REST API ile kişisel aile bütçesi uygulaması.

## İlk kurulum

1. Bu depodaki dosyaları GitHub'a yükleyin.
2. Firebase Authentication içinde Email/Password etkin olsun ve kullanıcı hesabı Firebase Console → Authentication → Users bölümünden oluşturulsun. Uygulama içi kayıt kapalıdır.
3. Cloud Firestore → Rules bölümüne `firestore.rules` dosyasındaki kuralları uygulayın ve **Publish** edin.
4. Streamlit Community Cloud'da bu depoyu seçerek `app.py` dosyasını yayımlayın.
5. Streamlit App settings → Secrets içine aşağıdaki bilgileri koyun:

```toml
[firebase]
project_id = "aile-butce-takip-14da8"
api_key = "FIREBASE_WEB_API_KEY"

[openai]
api_key = "OPENAI_API_KEY"
model = "gpt-4o-mini"
```

`[openai]` bölümü isteğe bağlıdır ancak yapay zekâ sınıflandırması ve PDF ekstre ayrıştırması için gerekir. Boş anahtar koymak yerine bu bölümü eklememek de mümkündür.

## Güvenlik

- Bu sürüm Firebase kullanıcı adı/şifre doğrulaması yapar ve Firestore'a kullanıcının ID token'ı ile REST üzerinden bağlanır.
- Firestore kuralları her dokümanda `ownerUid == request.auth.uid` şartını uygular.
- Firebase Admin SDK özel anahtarı bu sürümde kullanılmaz. Bu nedenle özel anahtarı depoya koymayın.
- `firestore.rules` yayımlanmadan önce uygulama kullanılmamalıdır.
- OpenAI sınıflandırmasında işlem açıklaması, tarih ve tutar gibi alanlar API'ye gönderilir. PDF metni gönderilmeden önce yaygın hesap numarası biçimleri ayıklanmaya çalışılır; buna rağmen kişisel bilgilerin tamamen temizlendiği garanti edilemez. Yüklemeden önce dosyayı kontrol edin.
- Bu uygulama finansal kayıt defteridir; banka hesabınıza bağlanmaz ve bankanızın resmî kayıtlarının yerine geçmez.

## Modüller

- Aylık gelir / ödeme planı
- Manuel işlem kaydı
- CSV/Excel içe aktarma önizlemesi
- PDF metninden AI yardımıyla işlem çıkarımı (metin tabanlı PDF; taranmış PDF OCR gerektirebilir)
- Kategori ve kişi bazlı aylık karşılaştırma
