# 🗺️ Türkiye MCP — Geliştirme Yol Haritası

> Bu dosya, projenin sıradaki geliştirmelerini ve durumlarını izler. Her oturum/otomatik
> çalıştırma buradan kaldığı yeri öğrenir. Bir madde tamamlandığında durumu `[x]` yapılır
> ve kısa not eklenir. Her artış ayrı commit + (gerekirse) sürüm etiketiyle yayınlanır.

## Çalışma kuralı (her oturum)
1. Bu dosyadaki **ilk `[ ]` (yapılmamış)** maddeyi seç.
2. Tek bir tutarlı artış olarak uygula; `python -c "import app"` + gömülü JS için `node --check` ile doğrula.
3. Mümkünse `minimax-m2.7:cloud` ile hızlı test et (yerel CPU yavaş).
4. Commit + push. Maddeyi `[x]` işaretle, kısa sonuç notu ekle.
5. Kullanıcı verisini/örnek belgeleri repoya ASLA ekleme. Atıf (OpenClaw/Anthropic vb.) yazma.

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

## Doğrulama (v1.6.12)
Tüm v1.6.5–v1.6.11 özellikleri test edildi. Bulunan kusurlar giderildi: sistem panelini tamamen kıran eksik `tab-computer` sekmesi eklendi + sekme geçişi sağlamlaştırıldı; computer_tools yol-güvenliği sıralaması sertleştirildi; memory/computer_tools spec'e eklendi. Bellek enjeksiyonu, skill kaydet/oku, gateway config, bilgisayar izinleri/engellemeleri, token ölçümü işlevsel doğrulandı.

## Tamamlananlar (özet)
- Çalışma alanı (klasör/oturum/dosya kalıcılığı), Ollama Cloud + dinamik modeller, belge zekâsı + çapraz hafıza, avukat personası + skills (9), durdurma butonu, LLM Gateway + failover, araç kataloğu, gerçek emsal karar metni çekme, ticari-olmayan lisans, README ekran galerisi.
