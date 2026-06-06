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

## 🆕 v1.6.0 — Gateway, Genişletilmiş Skills & Araç Kataloğu
- **gateway.py (LLMGateway)** — tüm LLM çağrıları buradan geçer. `complete(system, history, message, chain, api_keys, timeout_for)` model zincirini sırayla dener; hata/timeout/connect/**boş yanıt** → sonraki modele failover. Sağlayıcı başına metrik. `chat_endpoint` artık inline httpx yerine `GATEWAY.complete` çağırır; body'den `fallbacks` + `api_keys` alır; yanıtta `attempts` + `skills_used` döner.
- **reasoning max_tokens (kritik):** reasoning modelleri (`is_reasoning_model`) için `max_tokens=4096` (yoksa büyük sistem promptunda reasoning bütçeyi tüketip content BOŞ döner). reasoning_effort=low yine yalnızca reasoning modellerine; 400'de parametresiz retry.
- **Skills genişletildi (9):** + icra-iflas, kira-gayrimenkul, vergi-uyusmazligi, is-hukuku, sozlesme-inceleme. `set_enabled`/`_load_disabled` ile aç-kapa (skills_state.json, veri dizininde). `/api/skills/toggle`. Yanıtta `skills_used` → UI'de ⚡ etiket.
- **Araç kataloğu:** `TOOLS_CATALOG` + `/api/tools` (kategori/aktiflik). `/api/gateway/status` metrik.
- **UI Sistem paneli:** topbar ▦ → 3 sekme (Gateway+failover config, Skills toggle, Tools katalog). Inline handler'larda string yerine **index** kullanılır (tek tırnak tuzağı).
- **Test notu:** yerel CPU yavaş; testlerde `minimax-m2.7:cloud` (ollama cloud-proxy, ~5sn) kullan. Hukuk sorgularının yavaşlığı canlı araç çağrılarından (search_bedesten/emsal dış API) kaynaklı, model değil.

## 🆕 v1.5.0 — Avukat Modu (Belge Zekâsı, Skills, Çapraz Hafıza, Durdurma)
- **skills.py + skills/<ad>/SKILL.md** — YAML başlık + markdown gövdeli uzmanlık yönergeleri (playbook). `select_skills(message, doc_type)` bağlama göre seçer, `build_skills_prompt` sistem promptuna enjekte eder. EXE'de spec `datas`'a `skills/` eklenir.
- **Belge zekâsı** — `_classify_document(text)` belge türü/taraf/konu çıkarır (sezgisel, LLM gerektirmez). Upload yanıtında `understanding` döner.
- **Çapraz hafıza** — `workspace.find_related(refs, keywords, exclude_session_id)` tüm oturumlarda aynı esas/karar no veya konu eşleşmesi arar. Upload yanıtında `related` döner; chat'te "benzer kayıt var" olarak enjekte edilir.
- **chat_endpoint** artık `doc_type` + `related` alır; SYSTEM_PROMPT avukat personası + ilgililik denetimi.
- **Durdurma butonu** — frontend `AbortController`; gönder butonu `setSendMode(true)` ile durdurma butonuna döner.
- **reasoning_effort KAPISI (kritik):** `reasoning_effort: "low"` SADECE reasoning modellerine (`_is_reasoning_model()` → gpt-oss, deepseek, qwen3, minimax, glm-4.6…) gönderilir. gemma/llama gibi modeller bu parametreyle **400** döndürür. Ek güvenlik: 400 gelirse parametre çıkarılıp tekrar denenir.
- Yeni endpoint: `/api/skills`. `/health` artık `skills_count` döndürür.

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