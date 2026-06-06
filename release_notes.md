## 🇹🇷 Türkiye MCP v1.6.0 — Gateway · Genişletilmiş Skills & Araçlar

[OpenClaw](https://github.com/openclaw/openclaw) mimarisinden esinlenerek merkezi bir **Gateway** katmanı, daha kapsamlı **skills** ve bir **araç kataloğu** eklendi.

### 🔀 LLM Gateway + Otomatik Failover
- Tüm model çağrıları artık tek bir **gateway** katmanından geçer
- **Model failover:** Birincil model hata/zaman aşımı/**boş yanıt** verirse, tanımladığınız **yedek modellere** sırayla otomatik geçilir (örn. yerel Ollama → Ollama Cloud → OpenRouter)
- **Metrikler:** Sağlayıcı başına başarı/başarısızlık/ortalama gecikme — Sistem panelinde
- Reasoning modelleri (gpt-oss, minimax, deepseek…) için token bütçesi otomatik artırılır → boş yanıt sorunu giderildi

### ⚡ Genişletilmiş Skills (9 uzmanlık)
Hukuki Emsal Araştırması · Belge Analizi · **İcra-İflas** · **Kira-Gayrimenkul** · **Vergi Uyuşmazlıkları** · **İş Hukuku** · **Sözleşme İnceleme** · Mali Müşavirlik · Kamu İhale
- Her skill **açılıp kapatılabilir** (Sistem → Skills)
- Yanıtta **hangi uzmanlığın uygulandığı** ⚡ etiketle gösterilir
- `skills/<ad>/SKILL.md` ekleyerek genişletilebilir ([Anthropic skill formatı](https://github.com/anthropics/skills))

### 🧰 Araç Kataloğu (31 araç)
- **Sistem paneli** → Araçlar sekmesi: tüm MCP araçları kategori bazında (Hukuk, Mali, İhale, Piyasa, UYAP…), aktif/pasif durumlarıyla
- Yanıtlarda çağrılan araçlar ve **kullanılan model** zengin biçimde gösterilir

### 🖥️ Yeni "Sistem" Paneli
Sağ üstteki ▦ düğmesi: **Gateway** (failover + metrikler), **Skills** (aç/kapa), **Araçlar** (katalog) tek yerde.

### 📥 İndirme
- **TurkiyeMCP.exe** — Windows 10/11 (64-bit), kurulumsuz. Veriler cihazınızda kalır.
