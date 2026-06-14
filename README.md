# Türkiye Deprem Karar Destek Sistemi

Türkiye'deki güncel deprem verilerini otomatik olarak çeken, şehir bazlı sismik aktiviteyi analiz eden ve illere yönelik bir risk skoru üreten bir karar destek sistemidir. Bitirme projesi kapsamında geliştirilmiştir.

Sistem; veriyi sürekli güncel tutan bir veri hattı (pipeline), şehir bazlı öznitelik üretimi, kümeleme analizi, çok bileşenli bir risk skoru ve harita destekli bir web panosundan (dashboard) oluşur.

## Ne Yapar?

- **Güncel veri toplama:** AFAD'dan deprem verilerini düzenli aralıklarla otomatik çeker ve PostgreSQL veritabanında saklar.
- **Şehir bazlı analiz:** Her il için deprem sayısı, ortalama/maksimum büyüklük, derinlik ve son dönem aktivitesi gibi öznitelikleri hesaplar.
- **Kümeleme:** İlleri sismik aktivite davranışlarına göre K-Means ile gruplar (Düşük / Orta / Yüksek aktivite).
- **Risk skoru:** Her il için, dört bileşenden oluşan şeffaf bir risk skoru üretir.
- **Görselleştirme:** Şehir seçimi, risk bileşeni dökümü, deprem yoğunluğu ısı haritası ve fay hattı katmanı sunan etkileşimli bir web panosu.

## Risk Skoru Nasıl Hesaplanır?

Risk skoru, "tehlike × maruziyet" mantığını izleyen dört bağımsız bileşenin ağırlıklı toplamıdır (başlangıçta her biri eşit ağırlıklı, 1/4):

1. **Aktivite** — İlin gözlenen sismik aktivitesi (deprem sayısı, büyük deprem sayıları, maksimum büyüklük).
2. **b-değeri** — Gutenberg-Richter ilişkisinden hesaplanan, büyük/küçük deprem oranını yansıtan parametre. Düşük b-değeri görece daha yüksek büyük-deprem potansiyeline işaret eder. Aki-Utsu maksimum olabilirlik yöntemiyle, tamamlık magnitüdü (Mc ≈ 1.4) üzerinde en az 50 olaya sahip iller için hesaplanır; yeterli verisi olmayan iller ülke geneli ortalama b-değerini kullanır.
3. **Nüfus (maruziyet)** — İl nüfusu. "Nerede deprem oluyor"dan "nerede insanlar tehlikede"ye geçişi sağlar.
4. **Fay yakınlığı** — İlin ana fay sistemlerine yakınlığı (3 kademeli: merkezden geçen / yakın / uzak).

Skor bir "kara kutu" değildir: her bileşenin alt-skoru ayrı ayrı saklanır ve web panosunda şehir seçildiğinde çubuk grafik olarak gösterilir.

## Model Doğrulama

Risk skoru, modelin kendi girdisi olmayan iki bağımsız referansla karşılaştırılarak doğrulanmıştır:

- **AFAD tehlike haritası ile:** Risk sıralaması, AFAD'ın resmi deprem tehlike değerlendirmesiyle güçlü ve istatistiksel olarak anlamlı bir uyum gösterir (Spearman ρ ≈ 0.66, p < 0.001).
- **Tarihsel depremlerle:** Geçmişte büyük (M≥6) deprem yaşamış iller, yaşamamışlara göre anlamlı şekilde daha yüksek risk skoruna sahiptir (Mann-Whitney U, p < 0.001).

## Kullanılan Teknolojiler

- **Python** — veri çekme, işleme ve modelleme
- **PostgreSQL** — ilişkisel veri saklama
- **pandas, scikit-learn, scipy** — veri işleme, K-Means kümeleme, istatistiksel doğrulama
- **Flask** — web panosu
- **Leaflet** — harita, ısı haritası ve fay hattı katmanları

## Veri Kaynakları

- **Deprem verisi:** AFAD (Afet ve Acil Durum Yönetimi Başkanlığı) — güncel deprem kayıtları.
- **İl nüfusu:** TÜİK (Türkiye İstatistik Kurumu) Adrese Dayalı Nüfus Kayıt Sistemi (ADNKS) verilerine dayalı.
- **Fay zonu / tehlike sınıfları:** MTA ve AFAD tehlike haritalarına dayalı, il düzeyinde basitleştirilmiş referans tablolar.

## Sınırlılıklar

Bu sistemin sınırlarını açıkça belirtmek, sonuçlarının doğru yorumlanması için önemlidir:

- **Gözlenen aktiviteye dayalıdır.** Risk skoru, kataloğun kapsadığı dönemde gözlenen sismik aktiviteyi temel alır. Bu nedenle uzun süredir sessiz olan ancak yüksek deprem potansiyeli taşıyan iller (örneğin Kuzey Anadolu Fayı üzerindeki **İstanbul** gibi sismik boşluk bölgeleri) modelde olduğundan **düşük** skor alabilir. Bu, aletsel-katalog temelli yaklaşımların bilinen bir kısıtıdır.
- **Uzun vadeli tehlike analizinin yerini tutmaz.** Sistem, AFAD'ın olasılıksal deprem tehlike analizi (PSHA) gibi resmi çalışmaların yerine geçmez; onları tamamlayıcı, görece bir aktivite/risk göstergesidir.
- **Fay hattı görselleştirmesi şematiktir.** Haritadaki fay hattı katmanı, ana fay sistemlerinin literatür kaynaklı **basitleştirilmiş/temsili** güzergâhını gösterir; MTA'nın detaylı diri fay geometrisi değildir.
- **Fay ve tehlike sınıfları il düzeyindedir.** Fay yakınlığı ve tehlike dereceleri il bazına indirgenmiş yorumlardır; il içi değişkenliği yansıtmaz.
- **Risk skoru görelidir.** Üretilen skor, iller arası göreli bir karşılaştırma sunar; mutlak bir deprem olasılığı veya tahmini değildir.

## Not

Bu proje akademik/demo amaçlıdır ve gerçek afet yönetimi kullanımı için tasarlanmamıştır.
