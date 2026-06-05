# Türkiye MCP Server — Claude Code Rehberi

## Proje Hakkında
Türk hukuk, mali, ihale ve piyasa verileri için MCP server + web dashboard + Windows EXE.
ASGI uygulaması (Starlette + FastMCP), pywebview ile masaüstü penceresi.

## 🔴 Kritik Kurallar
- **API anahtarları asla repo'ya commit edilmez** — sadece env vars veya keyring
- **Starlette'e `lifespan` parametresi VERİLMEZ** — FastMCP lifespan protokolü uyumsuz, 500 hatası verir
- **EXE derleme**: `console=True` + `hide_console()` kullanılır, `console=False` pythonw crash yapar
- **`is_server_running()`**: 200 ve 500 yanıtı "çalışıyor" sayılır (modüller yüklenirken geçici 500 olabilir)

## 📁 Proje Haritası
Detaylı dosya yapısı, mimari, fonksiyonlar ve değişiklik geçmişi için **PROJECT_MAP.md** dosyasını oku.

## Hızlı Referans

| Dosya | İşlev |
|-------|-------|
| `app.py` | Ana ASGI uygulaması — DASHBOARD_HTML (satır 505-1214), tüm route'lar, MCP tool'ları |
| `local_run.py` | EXE giriş noktası — sunucu başlatma, pywebview, tray, persistence |
| `turkiye_mcp.spec` | PyInstaller derleme spec'i |
| `PROJECT_MAP.md` | Projenin tam haritası — mimari, fonksiyonlar, teknik kararlar |

## Sık Kullanılan Komutlar
```bash
# Geliştirme
python -m uvicorn app:app --host 127.0.0.1 --port 8080

# EXE derleme
python -m PyInstaller turkiye_mcp.spec --noconfirm

# EXE test
./dist/TurkiyeMCP.exe --debug
./dist/TurkiyeMCP.exe --no-gui --debug

# GitHub Release
gh release create v1.X.X dist/TurkiyeMCP.exe --title "Türkiye MCP v1.X.X" --notes-file release_notes.md
```

## EXE Sorun Giderme
- 500 Internal Server Error → Starlette lifespan parametresini kontrol et
- EXE crash → `dist/turkiye_mcp_crash.log` dosyasını oku
- Modül yüklenmiyor → magika model dosyaları spec'te var mı kontrol et
- Port çakışması → `taskkill /F /IM TurkiyeMCP.exe`