## 🇹🇷 Türkiye MCP Server v1.3.0

### 🎨 Premium UI Entegrasyonu
- **Yeni Arayüz**: Tamamen yeniden tasarlanmış premium dark tema arayüzü
  - Bricolage Grotesque + Be Vietnam Pro fontları
  - Özel titlebar (bayrak ikonu ile)
  - Sidebar: marka, sohbet listesi, modül durumu
  - Hero/welcome ekranı ile animasyonlu kartlar
  - Modern composer: dosya ekleme butonu + gönder butonu
  - Ayarlar modal overlay (sağlayıcı/model/API anahtarı)
  - Model chip: üst barda aktif sağlayıcıyı gösterir
  - Sunucu durumu yeşil/kırmızı nokta ile gösterilir

### ✨ Önceki Sürümden Devralan Özellikler
- **Server Persistence**: EXE kapatıldığında server arka planda devam eder
- **Kopyala & Word'e Aktar**: Her mesajda kopyala ve Word'e aktar butonları
- **Markdown Render**: Tablolar, başlıklar, listeler düzgün gösterilir
- **SYSTEM_PROMPT**: Tool sonuçları artık açıklamalı, kaynaklı ve markdown formatında
- **Tray Menüsü**: Göster, Tarayıcıda Aç, Tamamen Kapat seçenekleri
- **Dosya Yükleme**: PDF ve EYP/UDF drag-and-drop desteği

### 🔧 Düzeltmeler
- EXE çalışma sorunu düzeltildi (console=True + hide_console)
- Timeout 30s → 120s (modüllerin yüklenmesi uzun sürebiliyor)
- FileAndConsoleHandler ile log yazımı düzeltildi
- Magika model dosyaları bundle'a eklendi
- pywebview API uyumluluk düzeltmesi

### 📥 İndirme
- **TurkiyeMCP.exe** — Windows 10/11 (64-bit)
- Çift tıkla ile çalıştır, ek kurulum gerekmez

### 🚀 Kullanım
1. `TurkiyeMCP.exe` dosyasını indirin
2. Çift tıklayarak çalıştırın
3. İlk açılışta modüller yüklenir (~20-30 saniye)
4. Dashboard otomatik olarak açılır
5. Kapatıp tekrar açarsanız mevcut server'a bağlanır

### ⌨️ Komut Satırı
- `TurkiyeMCP.exe` — GUI ile başlat
- `TurkiyeMCP.exe --no-gui` — Sadece sunucu
- `TurkiyeMCP.exe --browser` — Tarayıcıda aç
- `TurkiyeMCP.exe --port 9090` — Farklı port
- `TurkiyeMCP.exe --debug` — Konsol penceresini göster