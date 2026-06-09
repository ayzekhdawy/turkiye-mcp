## 🇹🇷 Türkiye MCP v1.7.4

### 💾 Yedekleme / Dışa-İçe Aktarma
- **backup.py** modülü — tüm çalışma alanı verisini tek .zip dosyasında yedekleme
- 5 API endpoint: listele, oluştur, geri yükle, indir, sil
- 2 MCP aracı: `create_backup`, `list_backups`
- Sidebar'da yedekleme bölümü (oluştur, geri yükle, indir, sil)
- Path traversal koruması, 50 MB boyut sınırı, geri yükleme öncesi otomatik yedek

### 📋 Dava/Müvekkil Kartı
- **dava_kartlari.py** modülü — esas no, müvekkil, karşı taraf, mahkeme, durum takibi
- 14 dava türü, 5 durum kategorisi
- 7 MCP aracı, 7 API endpoint, Davalar paneli
- Süre bağlantısı (deadline ↔ dava kartı)
- **dava-yonetimi** skill'i

### ⏰ Süre/Takvim Takibi
- **deadlines.py** modülü — TBK m.149 süre hesaplama, hafta sonu kaydırma
- 8 süre kategorisi, 7 MCP aracı, 7 API endpoint
- Sidebar süre bölümü, Süreler paneli
- **hukuki-sureler** skill'i

### 🖥️ Frontend Ayırma
- 2540 satırlık `DASHBOARD_HTML` string'i gerçek dosyalara ayrıldı
- `templates/index.html`, `static/css/style.css`, `static/js/app.js`
- app.py 6171→~3700 satıra düştü
- PyInstaller uyumlu dosya sunumu (`_base_path()` + `StaticFiles`)

### ⚡ Gateway Geliştirmeleri
- Tool cache + `@cached_tool` decorator
- Keyring API anahtar yönetimi
- Önbellek/Anahtarlar UI paneli

### 📥 İndirme
- **TurkiyeMCP.exe** — Windows 10/11 (64-bit), kurulumsuz.