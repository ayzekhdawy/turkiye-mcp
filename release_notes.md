## 🇹🇷 Türkiye MCP Server v1.1.0

### 🔧 Düzeltmeler (v1.0.0'a göre)
- **EXE çalışma sorunu düzeltildi** — `console=False` (pythonw bootloader) yerine `console=True` + `hide_console()` kullanılıyor
- **Timeout artırıldı** — 30s → 120s (modüllerin yüklenmesi uzun sürebiliyor)
- **Crash log sistemi** — Hatalar `turkiye_mcp.log` ve `turkiye_mcp_crash.log` dosyalarına yazılır
- **pywebview API düzeltmesi** — `on_closed` parametre uyumsuzluğu giderildi
- **magika model dosyaları** — BDDK, Sigorta Tahkim modülleri için model dosyaları bundle'a eklendi
- **MessageBox fallback** — Hata durumunda Windows mesaj kutusu gösterilir
- **EXE ikonu** — Türkiye bayrağı ikonu eklendi

### 📦 Modüller (20/21 aktif)
| Modül | Durum |
|-------|-------|
| ✅ Resmi Gazete | Aktif |
| ✅ Mevzuat | Aktif |
| ✅ GİB | Aktif |
| ✅ İVD | Aktif |
| ✅ SGK | Aktif |
| ✅ İŞKUR | Aktif |
| ✅ TÜRMOB | Aktif |
| ✅ İSMMMO | Aktif |
| ✅ Bedesten | Aktif |
| ✅ Anayasa Mahkemesi | Aktif |
| ✅ KİK | Aktif |
| ✅ Rekabet Kurumu | Aktif |
| ✅ Sayıştay | Aktif |
| ✅ BDDK | Aktif |
| ✅ KVKK | Aktif |
| ✅ Sigorta Tahkim | Aktif |
| ✅ Uyuşmazlık Mahkemesi | Aktif |
| ✅ Emsal Kararlar | Aktif |
| ✅ İhale | Aktif |
| ❌ Borsa | yfscreen bağımlılık sorunu |
| ✅ UYAP | Aktif |

### 💬 Sohbet ve LLM Desteği
- OpenRouter, OpenAI, Anthropic, Gemini, Ollama desteği
- Otomatik sohbet başlığı oluşturma
- Sohbet geçmişi (localStorage)
- PDF yükleme + OCR desteği
- UYAP EYP/UDF dosya yükleme

### 📥 İndirme
- **TurkiyeMCP.exe** — Windows 10/11 (64-bit)
- Dosyayı indirip çift tıkla ile çalıştırın

### 🚀 Kullanım
1. `TurkiyeMCP.exe` dosyasını indirin
2. Çift tıklayarak çalıştırın
3. İlk açılışta modüller yüklenir (~20-30 saniye)
4. Dashboard otomatik olarak açılır
5. Sistem tepsisinde 🇹🇷 ikonu görünür

### ⌨️ Komut Satırı Seçenekleri
- `TurkiyeMCP.exe` — GUI ile başlat
- `TurkiyeMCP.exe --no-gui` — Sadece sunucu modu
- `TurkiyeMCP.exe --browser` — Tarayıcıda aç
- `TurkiyeMCP.exe --port 9090` — Farklı port
- `TurkiyeMCP.exe --no-tray` — Sistem tepsisi ikonu yok
- `TurkiyeMCP.exe --debug` — Konsol penceresini göster (hata ayıklama)

### 🔍 Sorun Giderme
- **İlk açılış yavaş**: Modüllerin yüklenmesi 20-30 saniye sürebilir
- **Windows Defender uyarısı**: "Devam et" seçin — EXE güvenlidir
- **Hata dosyaları**: `turkiye_mcp.log` ve `turkiye_mcp_crash.log` EXE'nin yanında oluşur
- **pywebview açılmazsa**: `--browser` flag ile tarayıcıda açabilirsiniz

### ⚠️ Not
- API anahtarları kaynak kodunda bulunmaz — yalnızca ortam değişkenleri veya Windows Credential Manager ile saklanır