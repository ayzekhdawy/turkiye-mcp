# 🗺️ Türkiye MCP — Geliştirme Yol Haritası

> Bu dosya, projenin sıradaki geliştirmelerini ve durumlarını izler. Her oturum/otomatik
> çalıştırma buradan kaldığı yeri öğrenir. Bir madde tamamlandığında durumu `[x]` yapılır
> ve kısa not eklenir. Her artış ayrı commit + (gerekirse) sürüm etiketiyle yayınlanır.

## ⛔ Otomatik geliştirme KAPALI
> Zamanlanmış (6 saatlik) otomatik turlar **devre dışı**. Maddeler yalnızca kullanıcı
> açıkça "şunu yapalım / devam et" dediğinde, onayıyla işlenir. Kendi başına bir madde
> seçip uygulama YAPILMAZ.

## Çalışma kuralı (kullanıcı onayı verince)
1. Kullanıcının seçtiği maddeyi tek bir tutarlı artış olarak uygula.
2. Doğrula: `python -c "import app"` + gömülü JS için `node --check`.
3. Mümkünse `minimax-m2.7:cloud` ile hızlı test et (yerel CPU yavaş).
4. Commit + push. Maddeyi `[x]` işaretle, kısa sonuç notu ekle.
5. Kullanıcı verisini/örnek belgeleri repoya ASLA ekleme. Atıf (OpenClaw/Anthropic vb.) yazma. Lisans ticari-olmayan kalmalı.

## Sıradaki maddeler (öncelik sırasıyla)

- [x] **1. Token & bağlam kullanımı takibi** — Gateway `usage` (prompt/completion/total) yakalar; prompt eksikse girdiden tahmin eder. Mesaj alt bilgisinde token + bağlam %'si, topbar'da oturum token toplamı, Sistem→Gateway'de sağlayıcı başına token. (v1.6.2)
- [x] **2. Ayarlar paneli geliştirme** — Sekmeli ayarlar (Bağlantı / Tercihler): açık-koyu tema, token bütçesi uyarısı, gateway zaman aşımı override, salt-okunur veri dizini. (v1.6.3)
- [x] **3. Profesyonel ikon paketi** — Tek tip `ICONS` seti + `ic()` yardımcısı (lucide tarzı çizgi ikonlar). Klasör menüsü, mesaj aksiyonları, sistem/ayarlar sekmeleri, emsal/kaldır butonları emoji yerine SVG. (v1.6.4)
- [x] **4. Gelişmiş kopyala/yapıştır** — Markdown/düz metin/Word olarak kopyala, kod bloğu kopyala, künye/atıf kopyala; yapıştırma iyileştirmeleri. (v1.6.5)
- [x] **5. Bellek (memory) özelliği** — Kullanıcı başına kalıcı bellek; tercih/olguları saklar, bağlama enjekte eder; "kullanıcısını tanır, ne yapacağını hafızasından kontrol eder". `/api/memory` CRUD + UI. (v1.6.6)
- [x] **6. Sohbet içinden skill düzenleme** — Kullanıcı sohbette "yeni skill ekle / şu skill'i düzenle" deyince SKILL.md yazılır/güncellenir (kendini geliştiren skills). Onay akışıyla. `/api/skills/content` + `/api/skills/save`, detectSkillBlocks(), onay modalı, "Yeni Skill Oluştur" butonu. (v1.6.7)
- [x] **7. Gateway server özelleştirme** — Sağlayıcı base URL/zaman aşımı/model zinciri sunucu tarafında saklansın; `/api/gateway/config` GET+POST; UI'den düzenlenebilsin.
- [x] **8. EXE hızlı açılış + kalıcı server** — PID dosya kilidi, health her zaman 200, daha hızlı server tespiti, tray bildirimi, tooltip düzeltmesi. (v1.6.9)
- [x] **9. macOS kolay kurulum** — install-macos.sh + install-macos.command (cift tikla), turkiye_mcp_mac.spec, README macOS bolumu. (v1.6.10)
- [x] **10. Bilgisayar/yetki düzeyi araçlar (dikkatli)** — computer_tools.py (dosya okuma, dizin listeleme, sistem bilgisi, komut çalıştırma), izin sistemi (varsayılan kapalı), /api/computer/permissions, UI Bilgisayar sekmesi. (v1.6.11)

## Faz 2 — Tam ürün eksiklikleri (kullanıcı onayıyla, sırasız)

> Kod incelemesiyle doğrulanan gerçek boşluklar. Öncelik kullanıcı belirler.

**Hukuki güvenilirlik (yüksek öncelik)**
- [ ] **A. Streaming yanıt** — Model yanıtı token-token akmalı (SSE/stream); uzun hukuki cevaplarda algılanan hızı kökten artırır. Şu an tam yanıt beklenip tek seferde gösteriliyor.
- [ ] **B. OCR'ı EXE'ye gömme** — Taranmış (görüntü) PDF'ler okunamıyor; OCR fallback var ama pytesseract/poppler opsiyonel ve EXE'de yok. Tesseract'ı paketle veya gömülü bir OCR çözümü ekle.
- [ ] **C. Tam metin çekme (emsal/anayasa/kik/rekabet)** — Şu an yalnızca Bedesten gerçek karar metni getiriyor; diğerleri numara/kısaltma döndürüp uydurma riskine açık. İçerik çekimi eklensin.
- [ ] **D. Mevzuat tam metni** — "TCK 245'in tam metni" gibi kanun/madde metnini getiren araç bağlı değil; mevzuat tam-metin arama+okuma eklensin.
- [ ] **E. Tool sonuç önbelleği + kullanıcı API anahtarları** — Sunucu taraflı TTL önbellek (Bedesten rate-limit/yavaşlık); paylaşımlı dev token'ları (Tavily/Brave) yerine kullanıcı anahtarı.

**Profesyonel iş akışı**
- [ ] **F. Belge taslağı üretimi** — Dilekçe/sözleşme/ihtarname taslağı üret + Word/PDF dışa aktar (sadece analiz değil, drafting).
- [ ] **G. Süre/takvim takibi** — Dava açma/temyiz/itiraz süreleri (7/15/30 gün) için hatırlatma/takvim.
- [ ] **H. Dava/müvekkil kartı** — Klasöre esas no, müvekkil, karşı taraf gibi yapılandırılmış meta.

**Güvenlik & gizlilik**
- [ ] **I. Veri şifreleme + anahtar güvenliği** — Çalışma alanı/bellek şifreli saklama; anahtarların düz-metin localStorage yerine güvenli saklanması; belirgin KVKK/yerel-mod gizlilik duruşu.
- [ ] **J. execute_command sertleştirme** — Engel listesini genişlet (powershell -enc, curl|sh vb.) veya yalnızca beyaz-liste.

**Dağıtım & dayanıklılık**
- [ ] **K. Yedekleme/dışa-içe aktarma** — Çalışma alanı + bellek yedek al/geri yükle (.zip), makine değişiminde veri taşıma.
- [ ] **L. macOS doğrulama + otomatik güncelleme** — macOS'te gerçek test; EXE/uygulama için sürüm kontrolü + güncelleme bildirimi.

**Mühendislik olgunluğu**
- [ ] **M. Otomatik test paketi** — pytest (endpoint/güvenlik) + gömülü JS node --check CI adımı; regresyon koruması.
- [ ] **N. Frontend'i dosyalara ayırma** — Devasa gömülü HTML string'i gerçek statik dosyalara böl (bakım + ters-bölü/tırnak kırılganlığını azalt).

## Bellek komutları + daraltılabilir sidebar (v1.7.1)
Sohbet-içi "unut" komutu: learn endpoint mevcut belleği prompt'a verir, `{add, forget}` döndürür; istenen kayıtlar silinir. Daha seçici çıkarım promptu. `/api/memory/clear` + sidebar 🗑 temizle. Daraltılabilir kenar çubuğu: `.shell.sidebar-collapsed` (264↔66px), `toggleSidebar()`, localStorage'da kalıcı.

## Öğrenen bellek (v1.7.0)
Bellek artık sohbetlerden otomatik öğreniyor: her yanıt sonrası son görüşmeden kalıcı kullanıcı bilgisi/tercihi/talimatı arka planda çıkarılıp (LLM ile) `source=auto` olarak eklenir, tekrar engellenir, `oto` rozetiyle gösterilir, Tercihler'den açılıp kapatılır. Sonraki yanıtlara enjekte edilir → adaptif asistan. `/api/memory/learn` + `memory.has_similar` + `add_memory(source=...)`.

## Doğrulama (v1.6.12)
Tüm v1.6.5–v1.6.11 özellikleri test edildi. Bulunan kusurlar giderildi: sistem panelini tamamen kıran eksik `tab-computer` sekmesi eklendi + sekme geçişi sağlamlaştırıldı; computer_tools yol-güvenliği sıralaması sertleştirildi; memory/computer_tools spec'e eklendi. Bellek enjeksiyonu, skill kaydet/oku, gateway config, bilgisayar izinleri/engellemeleri, token ölçümü işlevsel doğrulandı.

## Tamamlananlar (özet)
- Çalışma alanı (klasör/oturum/dosya kalıcılığı), Ollama Cloud + dinamik modeller, belge zekâsı + çapraz hafıza, avukat personası + skills (9), durdurma butonu, LLM Gateway + failover, araç kataloğu, gerçek emsal karar metni çekme, ticari-olmayan lisans, README ekran galerisi.
