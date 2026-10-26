# Aile Bütçe Takip — Firestore 403 düzeltmesi

Bu paket, olmayan `app_meta` belgelerine doğrudan GET atıldığında Firestore REST'in döndürebildiği 403 hatasını gidermek için `get_document` fonksiyonuna güvenli kullanıcı kapsamlı sorgu geri dönüşü ekler.

## Kurulum
1. GitHub deposunda `app.py` dosyasını bu pakettekiyle değiştirin.
2. Firebase Console → Firestore Database → Rules bölümünü açın.
3. Bu paketteki `firestore.rules` içeriğinin tamamını Rules editörüne yapıştırıp **Publish** edin.
4. Streamlit Cloud dağıtımı tamamlandıktan sonra uygulamayı yenileyin.

Kurallar veritabanını herkese açmaz: oturum açan kullanıcı yalnızca `ownerUid` değeri kendi UID'si olan kayıtları okuyup yazabilir. Eksik bir belgeye GET isteğinin 404 döndürebilmesi için yalnızca oturum açmış kullanıcılara mevcut olmayan belge yollarında get izni verilir; mevcut kayıtlar yine ownerUid ile korunur.

Python sözdizimi kontrol edildi; canlı Firebase hesabında test edilmedi.
