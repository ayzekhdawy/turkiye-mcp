## 🇹🇷 Türkiye MCP Server v1.4.0

### 🆕 Çalışma Alanı (Klasör · Oturum · Dosya Kalıcılığı)
- **Klasör oluşturma** ve sohbetleri klasörlere **sürükle-bırak** ile yerleştirme
- Oturumlar artık **sunucuda** saklanıyor → uygulama kapanıp açılsa bile **kaldığınız yerden devam**
- Yüklediğiniz belgeler ilgili klasöre kaydedilir
- Veri dizini: `%LOCALAPPDATA%\TurkiyeMCP\workspace` (veya `TURKIYE_MCP_DATA_DIR`)

### ☁️ Ollama Cloud + Dinamik Modeller
- Yeni **Ollama Cloud** sağlayıcısı (ollama.com API anahtarı ile)
- Yerel Ollama seçildiğinde makinenizdeki **gerçek modeller otomatik listelenir** (cloud-proxy modelleri dahil: `gpt-oss:120b-cloud`, `qwen3-coder:480b-cloud` vb.)
- **gpt-oss boş yanıt sorunu düzeltildi**: reasoning modelleri tüm token bütçesini gizli düşünceye harcayıp boş yanıt döndürüyordu → `reasoning_effort: "low"` + `reasoning` alanına fallback ile çözüldü

### 📄 Belge → Soru → Emsal
- Yüklenen PDF/UYAP/TXT belge sohbete **ek (chip)** olarak iliştirilir; esas/karar numaraları otomatik çıkarılır
- Belge hakkında soru sorduğunuzda metni bağlam olarak modele iletilir
- **⚖ Emsal** butonu ile belgeye dair emsal kararları ve içtihatlar otomatik aranır (`search_emsal`)
- Çok turlu süreklilik: önceki mesajlar bağlamda taşınır

### 🔑 Kararlı API Yönetimi
- **Sağlayıcı başına ayrı API anahtarı** hatırlanır (geçiş yapınca kaybolmaz)
- **⚡ Bağlantıyı Test Et** butonu — anahtar/model doğrulaması
- Sağlayıcıya göre timeout (yerel Ollama için 300s)

### 🔧 Düzeltmeler
- **Markdown render düzeltildi** — eski sürümde bozuk regex'ler yüzünden tablolar/başlıklar görünmüyordu
- Hata mesajları anlamlı hale getirildi (boş "Beklenmeyen hata" kaldırıldı)
- Toast bildirimleri eklendi

### 📥 İndirme
- **TurkiyeMCP.exe** — Windows 10/11 (64-bit), çift tıkla çalıştır, ek kurulum gerekmez

### 🚀 Kullanım
1. `TurkiyeMCP.exe` dosyasını indirip çift tıklayın (ilk açılışta modüller ~20-30 sn yüklenir)
2. Sağ üstten **Ayarlar** → sağlayıcı ve model seçin (Ollama için yerel modelleriniz otomatik gelir)
3. **Bağlantıyı Test Et** ile doğrulayın, soru sorun veya belge yükleyin
4. Sol panelden **klasör** oluşturup sohbetlerinizi düzenleyin

### ⌨️ Komut Satırı
- `TurkiyeMCP.exe` — GUI ile başlat
- `TurkiyeMCP.exe --no-gui` — Sadece sunucu
- `TurkiyeMCP.exe --browser` — Tarayıcıda aç
- `TurkiyeMCP.exe --port 9090` — Farklı port
- `TurkiyeMCP.exe --debug` — Konsol penceresini göster
