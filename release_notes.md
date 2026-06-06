## 🇹🇷 Türkiye MCP v1.6.1 — Gerçek Emsal Karar Metinleri

Belge yükleyip emsal karşılaştırması istendiğinde artık **gerçek karar metinleri** çekilir — model artık karar içeriğini uydurmaz.

### ⚖️ Emsal Analizi Yeniden Yazıldı
- **Konuya göre arama:** Emsal, belgenin KENDİ esas/karar numaralarıyla değil; belgeden çıkarılan **konu/suç tipiyle** (ör. *"banka veya kredi kartlarının kötüye kullanılması, TCK 245"*) aranır.
- **Gerçek metin çekimi:** Bulunan kararların ilk birkaçının **TAM METNİ** Bedesten'den indirilir ve modele verilir. Böylece karşılaştırma uydurmaya değil, gerçek içeriğe dayanır.
- **Künye + referans:** Her emsal **Mahkeme/Daire · Esas No · Karar No · Bedesten ID** ile sunulur; ID, kararın UYAP/Bedesten'de bulunması için referanstır.
- **Yapılandırılmış çıktı:** Olay → emsalin ilgili kısmı/ilkesi → **benzerlik/farklılık** → **olası sonuç (lehte/aleyhte)** → öneriler.
- **Uydurma yasağı:** Metni verilmeyen bir kararın içeriği aktarılmaz; içerik çekilemezse bu açıkça belirtilir.
- Ceza nitelikli belgelerde (iddianame, savcılık) ceza daireleri; hukuk uyuşmazlıklarında hukuk daireleri taranır.

### 📥 İndirme
- **TurkiyeMCP.exe** — Windows 10/11 (64-bit), kurulumsuz.

> ⚠️ Üretilen analiz bilgilendirme amaçlıdır; nihai karar için karar metinlerini ve mevzuatı resmi kaynaktan teyit ediniz.
