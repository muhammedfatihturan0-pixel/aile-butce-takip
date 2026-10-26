# Aile Bütçe Takip v8 — Kart toplamını güncelleme

## Hızlı tutar alanı
- Varsayılan seçenek `Kart toplamını güncelle` olur.
- Kart seçimi ilk olarak `Akbank Kredi Kartı F` seçeneğini gösterir.
- Tutar kutusu, seçilen ay ve kartın kayıtlı bütçe tutarıyla otomatik dolar. Örnek: Akbank Kredi Kartı F için 49.900 TL girip kaydetmek, seçili ayın `expenses["Akbank Kredi Kartı F"]` tutarını 49.900 TL ile değiştirir; yeni harcama/işlem satırı oluşturmaz.
- Kart seçimi kullanıcı değiştirene kadar hatırlanır.
- `Genel harcama toplamı ekle` ikinci seçenektir; bu tutarı ayrı ve kart ayrımı olmayan işlem kaydı olarak ekler.

## Dağıtım
GitHub deposundaki `app.py` dosyasını bu sürümle değiştirin. Gerekirse bağımlılık dosyalarını da birlikte yükleyin. Güvenlik kurallarını herkese açık yapmayın.

Bu paket geçmiş ekstre Excel'ini içermez; kişisel finansal hareketler public depoya eklenmemelidir.
