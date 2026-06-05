## 🇹🇷 Türkiye MCP v1.5.0 — "Avukat Modu"

Bu sürüm, asistanı yalnızca arama yapan bir araçtan, **bağlama göre uzmanlaşan bir hukuk/mali danışmana** dönüştürür.

### 🧠 Belge Zekâsı
- Yüklenen belgenin **türü** otomatik tespit edilir (dava dilekçesi, mahkeme kararı, sözleşme, ihtarname, icra takibi, fatura, ihale dokümanı, resmi yazı…)
- **Taraflar** (davacı/davalı, alacaklı/borçlu) ve **konu** çıkarılır; ek "chip" ve mesajda gösterilir
- **İlgililik denetimi:** Sorunuz belgeyle ilgisizse model kibarca uyarır, sonra yine de yardımcı olur

### 🔎 Çapraz Hafıza (geçmiş takibi)
- Aynı esas/karar numarası veya benzer konu **başka bir klasör/sohbette** geçiyorsa, model *"Çalışma alanınızdaki '…' kaydında benzer bir durum var"* diyerek sizi yönlendirir — tıpkı dosyalarını hatırlayan bir avukat gibi

### 📚 Skills (Uzmanlık Yönergeleri)
- [Anthropic skill formatında](https://github.com/anthropics/skills) oyun kitapları: **Hukuki Emsal Araştırması**, **Belge Analizi**, **Mali Müşavirlik**, **Kamu İhale Rehberi**
- Bağlama göre seçilip modele enjekte edilir → model hangi LLM olursa olsun alan uzmanı gibi, adım adım ve gerekçeli davranır
- `skills/<ad>/SKILL.md` ekleyerek kolayca genişletilebilir

### ⏹ Durdurma & Kararlılık
- Yanıt üretilirken **gönder butonu durdurma butonuna** dönüşür; tek tıkla iptal
- **Reasoning modeli düzeltmesi:** `reasoning_effort` yalnızca destekleyen modellere (gpt-oss, deepseek, qwen3, minimax, glm-4.6…) gönderilir; desteklemeyen modellerde otomatik geri çekilir (gemma/llama 400 hatası giderildi)

### 🧩 Avukat personası
- Sistem yönergesi yeniden yazıldı: uydurma yok, kaynaklı, gerekçeli, mevzuat atıflı yanıtlar; bilgilendirme niteliğinde

### 📥 İndirme
- **TurkiyeMCP.exe** — Windows 10/11 (64-bit), kurulumsuz. Veriler cihazınızda kalır.

### 🔌 MCP / SSE
- Aynı araçlar Claude Desktop/Code, Cursor, VS Code'a `http://localhost:8080/sse` ile bağlanır (ayrıntı: README → SSE Bağlantısı)
