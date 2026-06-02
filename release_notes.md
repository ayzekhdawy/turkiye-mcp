## 🇹🇷 Türkiye MCP Server v1.0.0

Türkiye'nin resmi kurumlarına erişim sağlayan MCP (Model Context Protocol) sunucusu — tek EXE ile çalışır!

### 🖥️ Masaüstü Uygulaması
- **TurkiyeMCP.exe** — İkili tıkla ve çalıştır, ek kurulum gerekmez
- Premium karanlık tema arayüz
- Sistem tepsisi ikonu (system tray)
- pywebview ile yerel pencere
- BYOK (Kendi API Anahtarını Getir) LLM desteği

### 📦 Modüller
| Modül | Açıklama |
|-------|----------|
| ✅ Resmi Gazete | Resmi Gazete arama ve getirme |
| ✅ Mevzuat | Kanun, KHK, yönetmelik arama |
| ✅ GİB | Gelir İdaresi Başkanlığı verileri |
| ✅ İVD | İçişleri Bakanlığı verileri |
| ✅ SGK | Sosyal Güvenlik Kurumu sorgulama |
| ✅ İŞKUR | İŞKUR iş ilanları arama |
| ✅ TÜRMOB | Serbest muhasebeci verileri |
| ✅ İSMMMO | İstanbul SMMMO verileri |
| ✅ Bedesten | Bedesten MCP araçları |
| ✅ Anayasa Mahkemesi | AYM kararları arama |
| ✅ KİK | Kamu İhale Kurumu ihale arama |
| ✅ Rekabet Kurumu | Rekabet kararları |
| ✅ Sayıştay | Sayıştay kararları |
| ✅ BDDK | Bankacılık düzenleme verileri |
| ✅ KVKK | Kişisel veri koruma kararları |
| ✅ Sigorta Tahkim | Sigorta tahkim kararları |
| ✅ Uyuşmazlık Mahkemesi | Uyuşmazlık kararları |
| ✅ Emsal Kararlar | Emsal karar arama |
| ✅ İhale | İhale arama ve detay |
| ❌ Borsa | YFScreen bağımlılık sorunu |

### 💬 Sohbet ve LLM Desteği
- OpenRouter, OpenAI, Anthropic, Gemini, Ollama desteği
- Otomatik sohbet başlığı oluşturma
- Sohbet geçmişi (localStorage)
- PDF yükleme + OCR desteği
- UYAP EYP/UDF dosya yükleme

### 📥 İndirme
- **TurkiyeMCP.exe** — Windows 10/11 (64-bit)
- Dosyayı indirip ikili tıkla ile çalıştırın

### 🚀 Kullanım
1. `TurkiyeMCP.exe` dosyasını indirin
2. İkili tıkla ile çalıştırın
3. Sistem tepsisinde 🇹🇷 ikonu görünür
4. Dashboard otomatik olarak açılır

### ⌨️ Komut Satırı Seçenekleri
- `TurkiyeMCP.exe` — GUI ile başlat
- `TurkiyeMCP.exe --no-gui` — Sadece sunucu modu
- `TurkiyeMCP.exe --browser` — Tarayıcıda aç
- `TurkiyeMCP.exe --port 9090` — Farklı port
- `TurkiyeMCP.exe --no-tray` — Sistem tepsisi ikonu yok

### ⚠️ Not
- API anahtarları kaynak kodunda bulunmaz — yalnızca ortam değişkenleri veya Windows Credential Manager ile saklanır
- İlk çalıştırmada Windows Defender uyarısı çıkabilir — "Devam et" seçin