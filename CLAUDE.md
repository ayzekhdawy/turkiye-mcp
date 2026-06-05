# Türkiye MCP Server — Claude Code Rehberi

## Proje Hakkında
Türk hukuk, mali, ihale ve piyasa verileri için MCP server + web dashboard + Windows EXE.
ASGI uygulaması (Starlette + FastMCP), pywebview ile masaüstü penceresi.

## 🔴 Kritik Kurallar
- **API anahtarları asla repo'ya commit edilmez** — sadece env vars veya keyring
- **Starlette'e `lifespan` parametresi VERİLMEZ** — FastMCP lifespan protokolü uyumsuz, 500 hatası verir
- **EXE derleme**: `console=True` + `hide_console()` kullanılır, `console=False` pythonw crash yapar
- **`is_server_running()`**: 200 ve 500 yanıtı "çalışıyor" sayılır (modüller yüklenirken geçici 500 olabilir)
- **DASHBOARD_HTML içindeki JS'te ters bölü ÇİFT yazılır** — `DASHBOARD_HTML` bir Python `"""..."""` string'i. Python `\n`, `\'`, `\d` gibi tek ters bölülü kaçışları işler (siler/dönüştürür) → tarayıcıya bozuk JS gider. Regex/escape için JS'e ulaşması gereken HER ters bölü `\\n`, `\\d`, `\\*` gibi ÇİFT yazılmalı. Doğrula: `python -c "import app,re;open('x.js','w').write(re.search(r'<script>(.*)</script>',app.DASHBOARD_HTML,re.S).group(1))"` sonra `node --check x.js`.
- **JS ile kurulan string'lere apostrof/tek tırnak literal koyma** — inline handler argümanları değişken birleştirme olmalı (`fn(\'' + id + '\')`), literal değil. Klasör/oturum ağacı `data-*` attribute + delegated listener kullanır (`setupTree()`).
- **gpt-oss / reasoning modelleri için `reasoning_effort: "low"`** — Ollama'da gpt-oss varsayılanda tüm token bütçesini gizli düşünceye harcayıp `content`'i BOŞ döndürür. Ollama sağlayıcılarında `reasoning_effort=low` gönderilir; ayrıca content boşsa `reasoning` alanına fallback yapılır.

## 🆕 v1.4.0 — Çalışma Alanı, Ollama Cloud, Belge/Emsal
- **workspace.py** — sunucu taraflı klasör/oturum/dosya kalıcılığı (JSON). Veri dizini: `%LOCALAPPDATA%/TurkiyeMCP/workspace` (veya `TURKIYE_MCP_DATA_DIR`). Endpoint'ler: `/api/workspace`, `/api/workspace/folder`, `/api/workspace/session` (GET+POST), `/api/workspace/session/delete`, `/api/workspace/file`, `/api/workspace/files`, `/api/workspace/file/delete`.
- **Ollama Cloud** sağlayıcısı (`ollama_cloud`, ollama.com, API key) + yerel `ollama` için **dinamik model listesi** (`/api/ollama/models` → localhost:11434/api/tags). Kullanıcının cloud-proxy modelleri (`gpt-oss:120b-cloud` vb.) otomatik görünür.
- **Belge bağlamı + emsal**: `chat_endpoint` artık `document_context` ve `history` alır; ekli belge varsa/emsal istenirse `search_emsal` otomatik çağrılır. Yüklenen dosyalar oturuma "ek" (attachment chip) olarak iliştirilir.
- **API kararlılığı**: sağlayıcı başına anahtar (`llm-keys`), `/api/chat/test` ile "Bağlantıyı Test Et", sağlayıcıya göre timeout (yerel ollama 300s).
- **renderMarkdown düzeltildi** — eski sürümde tek ters bölülü regex'ler servis edilen JS'i bozuyordu (markdown hiç render olmuyordu).

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