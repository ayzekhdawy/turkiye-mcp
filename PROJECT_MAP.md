---
name: turkiye-mcp-project-map
description: "Türkiye MCP projesinin tam dosya yapısı, mimarisi, fonksiyonları ve değişiklik geçmişi"
metadata: 
  node_type: memory
  type: project
  originSessionId: 4f4b5bd6-e2d6-4dab-b250-f27c49c0d823
---

# 🇹🇷 Türkiye MCP Server — Proje Haritası

> Son güncelleme: 2026-06-05  
> Bu dosya, projenin tam yapısını, yapılan değişiklikleri ve teknik kararları belgeler. Başka bir agent oturumunda projeyi hızlıca anlamak için referans olarak kullanılır.

---

## 📁 Proje Yapısı

```
turkiye-mcp/
├── app.py                    ← ANA DOSYA — ASGI uygulaması, dashboard HTML, tüm endpoint'ler
├── local_run.py              ← EXE giriş noktası — sunucu, pywebview, tray, persistence
├── server.py                 ← Alternatif sunucu (dashboard'sız, sadece MCP)
├── requirements.txt          ← Python bağımlılıkları
├── pyproject.toml            ← Proje meta verisi
├── turkiye_mcp.spec          ← PyInstaller EXE derleme spec'i
├── build.bat                 ← Windows EXE derleme betiği
├── Dockerfile                ← Docker container
├── Procfile                  ← Railway deployment
├── README.md                 ← Proje açıklaması
├── KULLANIM.md               ← Detaylı kullanım rehberi
├── release_notes.md          ← Sürüm notları (v1.3.0)
├── T_MCP.ico                 ← Uygulama ikonu
├── T_MCP.png                 ← Uygulama görseli
├── .github/workflows/        ← GitHub Actions (EXE build)
│
├── Modüller (her biri ayrı klasör):
│   ├── anayasa_mcp_module/   ← Anayasa Mahkemesi kararları
│   ├── bedesten_mcp_module/  ← Yargıtay/Danıştay birleşik arama
│   ├── bddk_mcp_module/      ← BDDK verileri
│   ├── borsa_module/          ← Borsa İstanbul finansal veriler
│   ├── borsa_models/          ← Borsa veri modelleri
│   ├── danistay_mcp_module/  ← Danıştay kararları
│   ├── emsal_mcp_module/     ← Emsal kararlar
│   ├── gib_module/            ← Gelir İdaresi Başkanlığı (sirküler)
│   ├── ihale_module/          ← Kamu ihaleleri (EKAP)
│   ├── iskur_module/          ← İŞKUR duyuruları
│   ├── ismmmo_module/        ← İstanbul SMMM odası
│   ├── ivd_module/            ← İntegral Vergi Dairesi
│   ├── kik_mcp_module/       ← Kamu İhale Kurumu
│   ├── kvkk_mcp_module/      ← KVKK kararları
│   ├── mevzuat_module/       ← Mevzuat Bilgi Sistemi
│   ├── mevzuat_search_module/ ← Mevzuat arama yardımcıları
│   ├── rekabet_mcp_module/   ← Rekabet Kurumu
│   ├── resmi_gazete_module/  ← Resmi Gazete
│   ├── sayistay_mcp_module/  ← Sayıştay kararları
│   ├── sgk_module/            ← SGK sorgulama
│   ├── sigorta_tahkim_mcp_module/ ← Sigorta Tahkim
│   ├── turmob_module/        ← TÜRMOB
│   ├── uyap_module/          ← UYAP EYP/UDF belge ayrıştırıcı
│   ├── uyusmazlik_mcp_module/ ← Uyuşmazlık Mahkemesi
│   ├── yargi_gib_module/     ← Yargı GİB
│   └── yargitay_mcp_module/  ← Yargıtay kararları
│
├── providers/                ← Finansal veri sağlayıcıları
│   ├── borsapy_bond_provider.py
│   ├── worldbank_provider.py
│   ├── buffett_analyzer_provider.py
│   └── isyatirim_provider.py
│
└── dist/
    └── TurkiyeMCP.exe        ← Derlenmiş EXE (~378 MB)
```

---

## 🏗️ app.py — Mimari

### Bölüm Sırası (satır numaraları yaklaşık):

| Satır | Bölüm | Açıklama |
|-------|-------|----------|
| 1-37 | İmportlar | Tüm modüller, Starlette, FastMCP, vb. |
| 39-65 | MODULES_AVAILABLE | Modül yükleme (try/except ile graceful fallback) |
| 67-500 | MCP Tool fonksiyonları | Her modül için `@app.tool()` dekoratörlü fonksiyonlar |
| 505-1214 | **DASHBOARD_HTML** | Premium dark tema UI (tek string olarak) |
| 1217-1230 | `homepage()` | `/` route → HTMLResponse(DASHBOARD_HTML) |
| 1217-1235 | `health_endpoint()` | `/health` route → JSON modül durumu |
| 1233-2100 | UYAP/PDF yardımcıları | Belge ayrıştırma, referans çıkarma |
| 2100-2120 | ASGI uygulaması | Starlette route tanımları + MCP mount |

### DASHBOARD_HTML İçeriği (satır 505-1214):

**CSS (satır ~515-920):**
- CSS variables: `--bg:#0b0d10`, `--accent:#e23b4e`, vb.
- Bricolage Grotesque + Be Vietnam Pro fontları
- Custom titlebar, sidebar, hero ekranı, composer, settings modal
- Mesaj balonları, markdown tabloları, typing indicator, msg-actions
- Responsive breakpoint (768px)

**HTML (satır ~920-1110):**
- Titlebar (bayrak ikonu + başlık + pencere butonları)
- Sidebar: brand mark (TR), yeni sohbet butonu, sohbet listesi, modül durumu
- Main: topbar (server status + model chip + ayarlar), canvas (hero/mesajlar), composer (textarea + attach + send)
- Settings modal overlay (sağlayıcı, model, API key)
- File drop overlay, hidden file input

**JavaScript (satır ~1110-1212):**
- `PROVIDERS` objesi — 5 sağlayıcı (OpenRouter, OpenAI, Anthropic, Gemini, Ollama)
- Chat yönetimi: `chats`, `activeChatId`, `newChat()`, `selectChat()`, `deleteChat()`
- Mesaj gönderme: `sendMessage()` — `/api/chat` endpoint'ine POST
- Dosya yükleme: `handleFileUpload()` — PDF → `/api/upload/pdf`, UYAP → `/api/upload/uyap`
- Drag & drop: `.main` area üzerinde dragover/dragleave/drop
- Markdown render: `renderMarkdown()` — tablo, başlık, liste, kalın/italik, link, kod
- Kopyala/Word: `copyMessage()`, `exportWord()` — HTML blob → .doc
- Ayarlar: `openSettings()`, `closeSettings()`, `saveConfig()`, `onProviderChange()`
- Modül durumu: `loadModules()` — `/health` endpoint'inden
- Sunucu durumu: `checkServerStatus()` — 30sn interval ile polling

### ASGI Route'ları:

| Route | Method | Fonksiyon | Açıklama |
|-------|--------|-----------|----------|
| `/` | GET | `homepage()` | Dashboard HTML |
| `/health` | GET | `health_endpoint()` | Modül durumu JSON |
| `/api/chat` | POST | `chat_endpoint()` | LLM sohbet + MCP araç çağrısı |
| `/api/chat/providers` | GET | `providers_endpoint()` | Sağlayıcı listesi |
| `/api/chat/configure` | POST | `configure_llm_endpoint()` | API key kaydetme |
| `/api/chat/status` | GET | `llm_status_endpoint()` | Mevcut yapılandırma |
| `/api/upload/pdf` | POST | `upload_pdf_endpoint()` | PDF yükleme |
| `/api/search/refs` | POST | `search_document_refs_endpoint()` | Belge referans arama |
| `/api/upload/uyap` | POST | `upload_uyap_endpoint()` | UYAP EYP/UDF yükleme |
| `/` | MOUNT | `mcp_asgi` | FastMCP SSE endpoint |

> **ÖNEMLİ:** `lifespan` parametresi Starlette'e VERİLMEMELİ. FastMCP 3.3.1 lifespan protokolü Starlette ile uyumsuz → 500 hatası veriyor.

### SYSTEM_PROMPT (satır ~2198):

```
Sen Türkiye MCP asistanısın. Türk hukuk, mali, ihale ve piyasa verileri konusunda uzmansın.
YANIT FORMATI KURALLARI:
1. Her araç sonucunu açıklayıcı sun — raw tablo YERİNE kart formatında
2. Sonuçları markdown formatında sun
3. Hukuki terimleri açıkla
6. Her yanıtın sonunda 📋 Kaynak bölümü ekle
```

---

## 🖥️ local_run.py — EXE Giriş Noktası

### Akış Diyagramı:

```
main()
  ├── _EXE_DIR, _CRASH_LOG tanımla
  ├── hide_console() (debug değilse)
  ├── args parse (--debug, --no-gui, --browser, --port, --no-tray)
  ├── is_server_running()? ──EVET──→ GUI'ye bağlan
  │                              └──HAYIR→ start_server() thread
  │                                        └── wait_for_server(120s)
  │                                              ├── 200 → OK, GUI aç
  │                                              ├── 500 → 1s bekle, tekrar dene
  │                                              └── bağlantı hatası → 0.5s bekle
  ├── run_webview() veya run_browser()
  └── create_tray_icon() (pystray)
       ├── "🇹🇷 Göster" → webview.show()
       ├── "🌐 Tarayıcıda Aç" → run_browser()
       └── "❌ Tamamen Kapat" → server'ı da kapat
```

### Önemli Fonksiyonlar:

| Fonksiyon | Açıklama |
|-----------|----------|
| `is_server_running()` | 200 veya 500 yanıtı = sunucu çalışıyor |
| `wait_for_server()` | 200 = hazır, 500 = modüller yükleniyor (1s bekle), hata = 0.5s bekle |
| `start_server()` | `from app import starlette_app` → `uvicorn.run(starlette_app, ...)` |
| `hide_console()` | `ctypes.windll.user32.ShowWindow(hwnd, 0)` ile konsolu gizle |
| `FileAndConsoleHandler` | `FileHandler` tabanlı — `sys.stderr=None` durumunda crash önler |
| `_log_crash()` | Crash log dosyasına yaz |
| `_global_excepthook()` | Yakalanmayan istisnaları logla |

### EXE Derleme Spec (turkiye_mcp.spec):

- `console=True` + Python kodunda `hide_console()` (pythonw bootloader sessiz crash yapıyor)
- `icon='T_MCP.ico'`
- Magika model dosyaları otomatik toplanıyor
- Hidden imports: tüm modüller, keyring, pywebview, pystray

---

## 🔑 Teknik Kararlar ve Geçmiş

### v1.4.0 Değişiklikleri (Çalışma Alanı + Ollama Cloud + Belge/Emsal):
1. **workspace.py** — yeni modül. Sunucu taraflı klasör (proje), oturum (sohbet) ve dosya kalıcılığı (JSON + ham dosya). Veri dizini `%LOCALAPPDATA%/TurkiyeMCP/workspace` veya `TURKIYE_MCP_DATA_DIR`. Stdlib-only.
2. **Workspace endpoint'leri** (app.py): `/api/workspace` (GET ağaç), `/api/workspace/folder` (create/rename/delete), `/api/workspace/session` (GET+POST upsert), `/api/workspace/session/delete` (delete/move), `/api/workspace/file` (yükle+çözümle), `/api/workspace/files`, `/api/workspace/file/delete`.
3. **Ollama Cloud** sağlayıcısı (`ollama_cloud` → ollama.com, API key, OpenAI-uyumlu). Ayrıca yerel `ollama` için **dinamik model listesi** `/api/ollama/models` (localhost:11434/api/tags) → kullanıcının cloud-proxy modelleri (`gpt-oss:120b-cloud` vb.) Ayarlar'da otomatik listelenir.
4. **gpt-oss boş yanıt düzeltmesi**: reasoning modelleri varsayılanda tüm token bütçesini gizli düşünceye harcayıp `content`'i boş döndürüyordu. Ollama sağlayıcılarına `reasoning_effort: "low"` eklendi + content boşsa `reasoning` alanına fallback. (Kullanıcının "ollama cloud beceremedi" sorununun kök nedeni buydu.)
5. **Belge bağlamı + emsal**: `chat_endpoint` artık `document_context` (ekli dosya metni) ve `history` (çok turlu süreklilik) alıyor. Ekli belge varsa veya "emsal/içtihat" istenirse `search_emsal` otomatik çağrılır. max_tokens 1024→2048, timeout sağlayıcıya göre (yerel ollama 300s).
6. **Kararlı API yönetimi**: sağlayıcı başına anahtar (`llm-keys` localStorage map), `/api/chat/test` ile "Bağlantıyı Test Et", model chip düzeltmesi.
7. **Arayüz**: sidebar klasör ağacı (`data-*` + delegated `setupTree()`), sürükle-bırak ile oturum taşıma, ekli belge chip'leri (⚖ Emsal butonu), toast bildirimleri, "kaldığı yerden devam" (sunucudan en son oturum açılır).
8. **renderMarkdown düzeltildi** — tek ters bölülü regex'ler (`\n`, `\d`, `\[`, `<\/li>`) servis edilen JS'i bozuyordu; tümü çift ters bölü yapıldı. Markdown artık düzgün render oluyor.

> **ÖNEMLİ (DASHBOARD JS):** `DASHBOARD_HTML` bir `"""..."""` string'i. JS'e ulaşması gereken her ters bölü ÇİFT yazılır (`\\n`). Ayrıca JS ile kurulan string'lere literal apostrof/tek tırnak konmaz (dış string'i bozar). Değişiklik sonrası `node --check` ile doğrula.

### v1.3.0 Değişiklikleri:
1. **Premium UI Entegrasyonu** — Eski basit UI → Yeni dark tema premium UI
   - Bricolage Grotesque + Be Vietnam Pro fontları
   - Custom titlebar, sidebar, hero ekranı, settings modal
   - Tüm mevcut JS fonksiyonları korundu (chat, upload, markdown, copy, word export)
2. **500 Internal Server Error düzeltmesi** — Starlette'e `lifespan=mcp_asgi.lifespan` parametresi kaldırıldı
   - FastMCP 3.3.1 lifespan protokolü Starlette ile uyumsuz
   - Kaldırılmazsa her request 500 dönüyor
3. **is_server_running() iyileştirmesi** — 500 yanıtı da "çalışıyor" sayılıyor
   - Modüller yüklenirken /health geçici olarak 500 dönebilir
4. **wait_for_server() iyileştirmesi** — 500 = 1s bekle, bağlantı hatası = 0.5s bekle
5. **Health/homepage endpoint'lerine try/except** eklendi
6. **JS regex SyntaxWarning'ler** düzeltildi (`\*\*` → `\\*\\*`, `\|` → `\\|`, `<\/li>` → `<\\/li>`)

### v1.2.0 Değişiklikleri:
1. Server persistence — EXE kapatıldığında server devam eder
2. Kopyala & Word export — her mesajda butonlar
3. Markdown render — tablolar, başlıklar, listeler
4. Tray menüsü — Göster, Tarayıcıda Aç, Tamamen Kapat
5. SYSTEM_PROMPT iyileştirmesi — tool sonuçları açıklamalı

### Bilinen Sorunlar:
- **Borsa modülü** `yfscreen` modülü eksik → `MODULES_AVAILABLE["borsa"] = False`
- **EXE boyutu** ~378 MB (magika model dosyaları dahil)

---

## 🚀 Hızlı Komutlar

```bash
# Geliştirme (Python ile doğrudan)
python -m uvicorn app:app --host 127.0.0.1 --port 8080

# EXE derleme
python -m PyInstaller turkiye_mcp.spec --noconfirm

# EXE test
./dist/TurkiyeMCP.exe --debug          # GUI + konsol
./dist/TurkiyeMCP.exe --no-gui --debug  # Sadece sunucu + konsol
./dist/TurkiyeMCP.exe --browser         # Tarayıcıda aç

# GitHub Release
gh release create v1.X.X dist/TurkiyeMCP.exe --title "Türkiye MCP v1.X.X" --notes-file release_notes.md

# Sağlık kontrolü
curl http://127.0.0.1:8080/health
```

---

## 🔗 Bağlantılı Bellek Dosyaları

- [[morecano-deployment-info]] — cPanel API ile dosya yükleme rehberi
- [[morecano-ftp-warning]] — FTP ile yükleme YASAK
- [[morecano-site-map]] — Morecano site yapısı
- [[thukiwin-port-progress]] — ThukiWin portlama ilerlemesi