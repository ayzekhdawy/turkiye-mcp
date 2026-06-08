## 🇹🇷 Türkiye MCP v1.6.12 — Düzeltmeler & Doğrulama

v1.6.5–v1.6.11 özellikleri (kopyala/yapıştır, bellek, sohbet içi skill, gateway özelleştirme, EXE hızlı açılış, macOS kurulum, bilgisayar araçları) test edildi; tespit edilen kusurlar giderildi.

### 🐞 Düzeltmeler
- **Kritik:** Sistem paneli açılışta çöküyordu — "Bilgisayar" sekmesi için sekme düğmesi eksikti (`tab-computer`), bu yüzden panel hiç açılamıyordu. Sekme eklendi ve sekme geçişi eksik elemana karşı sağlamlaştırıldı. Artık Gateway/Skills/Araçlar/Bilgisayar sekmelerinin tümü erişilebilir.
- **Güvenlik sertleştirme:** `read_file`/`list_directory` artık hassas yol kontrolünü dosya varlık kontrolünden ÖNCE yapıyor (hassas dosya varlığını sızdırmama).
- EXE derlemesi: `memory` ve `computer_tools` modülleri spec'e açıkça eklendi.

### ✅ Doğrulanan özellikler (test edildi)
- Bellek: ekleme + sohbete enjeksiyon çalışıyor (asistan kullanıcının adını/alanını hatırlıyor).
- Skill kaydet/oku, Gateway sunucu yapılandırması, bilgisayar izinleri (varsayılan kapalı), tehlikeli komut/hassas yol engelleme, token & bağlam ölçümü — hepsi işlevsel.

### 📥 İndirme
- **TurkiyeMCP.exe** — Windows 10/11 (64-bit), kurulumsuz.
