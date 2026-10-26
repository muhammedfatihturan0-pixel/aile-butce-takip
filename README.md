# Aile Bütçe Takip — kolay kullanım ve oturum hatırlama

## Yapılanlar
- CookieManager `set`, `delete` ve `get_all` çağrılarına benzersiz widget anahtarları eklendi; aynı `key='set'` hatası önlenir.
- Giriş ekranındaki “Bu cihazda oturumu açık tut (1 yıl)” seçeneği, parolayı saklamadan Firebase yenileme belirtecini çerezde saklar. Uygulamada oturum açma kaldırılmamıştır; halka açık finans uygulamasında bu, başkalarının aile bütçesine erişmesini önler.
- Hızlı kayıt varsayılan olarak “Toplam tutar (genel)” modunda açılır. “Kart / hesap toplamı” seçilirse kart seçilir. Nakit/banka kartı seçeneği kaldırılmıştır.
- Kart seçimi Firestore `app_meta` alanında saklanıp kullanıcı değiştirene kadar korunur.
- Daha okunaklı kontrast ve modern arayüz korunmuştur.

## Dağıtım
1. `app.py`, `requirements.txt` ve `packages.txt` dosyalarını GitHub deposunda değiştirin.
2. Firebase Console → Firestore Database → Rules alanında `firestore.rules` içeriğini yayımlayın.
3. Streamlit yeniden başladıktan sonra kişisel tarayıcınızda bir kez giriş yapın ve oturum hatırlama seçeneğini açık bırakın. Normal kullanımda aynı tarayıcıda bir yıl boyunca yeniden parola istememesi gerekir; çıkış yaparsanız, çerezleri temizlerseniz veya Firebase oturumu iptal edilirse tekrar giriş gerekir.

## Geçmiş ekstreler
Geçmiş işlem dosyası bu ZIP'e bilerek eklenmemiştir; depo herkese açık olduğundan tüm kart hareketlerini GitHub'a koymak istemeyebiliriz. `Axess_Gecmis_Ekstre_Aktarim.xlsx` dosyasını uygulamanın **Ekstre İçe Aktar** ekranından bir kez yükleyin. Dosyayı GitHub'a yüklemeyin.

**Güvenlik:** Firestore kurallarını herkese açık yapmayın. `firestore.rules` yalnızca oturum açmış kullanıcının `ownerUid` ile eşleşen belgelerine erişim verir.
