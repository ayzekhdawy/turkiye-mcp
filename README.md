# 🇹🇷 Türkiye MCP Server

**Türkiye Hukuk, Mali, İhale ve Piyasa Verileri — Birleştirilmiş MCP Sunucusu**

5 farklı MCP sunucusunu tek bir projede birleştiren, [Railway](https://railway.app) üzerinde yayınlanabilir, SSE transport ile çalışan bir MCP (Model Context Protocol) sunucusu.

---

## 📊 İçerik

| Kaynak | Açıklama | Araç Sayısı |
|--------|----------|-------------|
| ⚖️ **Yargi MCP** | Yargıtay, Danıştay, Anayasa, KİK, Rekabet, Sayıştay, BDDK, KVKK, Sigorta Tahkim, Bedesten, Uyuşmazlık, EMSAL | ~13 |
| 📋 **Mevzuat MCP** | Mevzuat Bilgi Sistemi, kanun, KHK, yönetmelik arama | ~2 |
| 🏗️ **İhale MCP** | Kamu ihale arama (EKAP v2), resmi ilanlar (ilan.gov.tr) | ~3 |
| 📈 **Borsa MCP** | BIST hisseler, kripto para, döviz kurları | ~3 |
| 💰 **Mali Müşavir MCP** | Resmi Gazete, GİB, İVD, SGK, İŞKUR, TÜRMOB, İSMMMO | ~10 |

**Toplam: ~31+ araç** | **1 sağlık kontrolü**

---

## 🚀 Hızlı Başlangıç

### Railway'de Yayınlama

1. Repo'yu fork'la veya klonla
2. [Railway](https://railway.app)'de yeni proje oluştur
3. GitHub repo'yu bağla
4. Otomatik deploy başlar
5. Domain atanır (ör: `https://web-production-xxxx.up.railway.app`)

### Lokal Çalıştırma

```bash
# Gereksinimleri yükle
pip install -r requirements.txt

# Sunucuyu başlat
python app.py

# Tarayıcıda aç
# http://localhost:8080 → Web dashboard
# http://localhost:8080/sse → MCP SSE endpoint
# http://localhost:8080/health → JSON sağlık kontrolü
```

---

## 🔗 MCP Client Yapılandırması

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) veya
`%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "turkiye": {
      "url": "https://web-production-4fd5e.up.railway.app/sse"
    }
  }
}
```

### Claude Code (CLI)

```bash
# SSE transport ile ekle
claude mcp add turkiye --transport sse https://web-production-4fd5e.up.railway.app/sse

# Doğrula
claude mcp list
```

### Cursor

`.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "turkiye": {
      "url": "https://web-production-4fd5e.up.railway.app/sse"
    }
  }
}
```

### VS Code (Copilot)

`.vscode/mcp.json`:

```json
{
  "servers": {
    "turkiye": {
      "type": "sse",
      "url": "https://web-production-4fd5e.up.railway.app/sse"
    }
  }
}
```

### Lokal Kullanım

```json
{
  "mcpServers": {
    "turkiye-local": {
      "url": "http://localhost:8080/sse"
    }
  }
}
```

---

## 🛠️ Araçlar (Tools)

### ⚖️ Yargı (Hukuk)

| Araç | Açıklama | Parametreler |
|------|----------|-------------|
| `search_bedesten_unified` | Birden fazla Türk mahkemesinde birleştirilmiş arama | `keyword` (zorunlu), `court_types` (isteğe bağlı: `YARGITAYKARARI`, `DANISTAYKARAR`, `YERELHUKUK`, `ISTINAFHUKUK`, `KYB`), `page_number` |
| `get_bedesten_document` | Bedesten'den belirli bir kararın tam metnini getirir | `document_id` (zorunlu) |
| `search_anayasa_unified` | Anayasa Mahkemesi kararlarında arama | `keywords` (zorunlu), `decision_type` (`bireysel_basvuru`, `itiraz`, `genel_kurul`), `page` |
| `search_kik_v2_decisions` | Kamu İhale Kurumu karar arama | `decision_type` (`uyusmazlik`, `idari`, `onarim`), `keyword`, `karar_no` |
| `search_rekabet_kurumu` | Rekabet Kurumu karar arama | `keyword`, `page` |
| `search_sayistay_unified` | Sayıştay karar arama | `decision_type` (`genel_kurul`, `dava_daireleri`, `tetkik_kurulu`), `keyword`, `page` |
| `search_kvkk_decisions` | KVKK (Kişisel Verilerin Korunması) karar arama | `keyword`, `page` |
| `search_bddk_decisions` | BDDK (Bankacılık Düzenleme) karar arama | `keyword`, `page` |
| `search_sigorta_tahkim` | Sigorta Tahkim Komisyonu karar arama | `keyword`, `page` |
| `search_uyusmazlik` | Uyuşmazlık Mahkemesi karar arama | `keyword`, `page` |
| `search_emsal` | EMSAL (UYAP Örnek Kararlar) arama | `keyword`, `page` |

#### Bedesten Mahkeme Türleri

| Kod | Mahkeme |
|-----|---------|
| `YARGITAYKARARI` | Yargıtay (Temyiz) |
| `DANISTAYKARAR` | Danıştay (İdari Yargı) |
| `YERELHUKUK` | Yerel Hukuk Mahkemeleri |
| `ISTINAFHUKUK` | İstinaf Mahkemeleri (Bölge Adliye) |
| `KYB` | Kanun Yararına Bozma |

### 💰 Mali Müşavir

| Araç | Açıklama | Parametreler |
|------|----------|-------------|
| `search_resmi_gazete` | Resmi Gazete'de belge arama | `anahtar_kelime` (zorunlu), `belge_turu` (`kanun`, `khk`, `cbk`, `yonetmelik`, `teblig`, `sirkuler`, `genelge`), `baslangic_tarihi`, `bitis_tarihi` (YYYY-MM-DD), `sayfa` |
| `get_daily_bulletin` | Belirli bir tarihin Resmi Gazete bültenini getirir | `tarih` (YYYY-MM-DD, boş ise bugün) |
| `get_recent_mali_changes` | Son N günün mali belgelerini getirir | `gun` (varsayılan: 7) |
| `search_gib_sirkuler` | GİB sirkülerlerinde arama | `anahtar_kelime` (zorunlu), `sirkuler_turu` (`vergi_sirkuleri`, `ic_genelge`, `duyuru`, `teblig`), `yil`, `sayfa` |
| `get_tax_calendar` | Vergi takvimi bilgileri | `yil` (isteğe bağlı) |
| `check_efatura_taxpayer` | VKN/TCKN ile e-Fatura mükellef sorgulama | `vergi_kimlik_no` (zorunlu, 10 veya 11 hane) |
| `get_asgari_ucret` | Asgari ücret bilgileri | `yil` (isteğe bağlı) |
| `get_prim_matrahi` | SGK prim matrahı ve oranları | `yil` (isteğe bağlı) |
| `get_turmob_pratik_bilgiler` | TÜRMOB pratik bilgileri | `kategori` (isteğe bağlı) |
| `get_ismmmo_pratik_bilgiler` | İSMMMO pratik bilgileri | `kategori` (isteğe bağlı) |

### 🏗️ İhale

| Araç | Açıklama | Parametreler |
|------|----------|-------------|
| `search_tenders` | Kamu ihalelerinde arama (EKAP v2) | `search_text`, `limit` (varsayılan: 10) |
| `get_recent_tenders` | Son N günün ihalelerini getirir | `days` (varsayılan: 7), `limit` (varsayılan: 10) |
| `search_ilan_ads` | Resmi ilan arama (ilan.gov.tr) | `search_text`, `max_result_count` (varsayılan: 12) |

### 📈 Borsa

| Araç | Açıklama | Parametreler |
|------|----------|-------------|
| `get_bist_stock` | BIST hisse senedi verileri | `symbol` (zorunlu, örn: `THYAO`, `GARAN`) |
| `get_fx_rates` | Güncel döviz kurları | (parametre yok) |
| `get_crypto` | Kripto para verileri | `symbol` (zorunlu, örn: `BTC`, `ETH`) |

### 🏥 Sağlık

| Araç | Açıklama |
|------|----------|
| `check_health` | Tüm modüllerin aktif/pasif durumunu listeler |

---

## 💬 Örnek Kullanımlar (Claude ile)

### Hukuk
```
"Yargıtay 'mülkiyet hakkı' ile ilgili kararları ara"
"Danıştay 'kamu ihalesi' kararlarını listele"
"Anayasa Mahkemesi 'ifade özgürlüğü' bireysel başvuru kararları"
"KİK uyuşmazlık kararlarında 'ihale süresi' ara"
"EMSAL kararlarda 'tazminat' ara"
```

### Mali
```
"2025 asgari ücret ne kadar?"
"GİB sirkülerlerinde 'KDV' ara"
"1234567890 VKN e-Fatura mükellef mi?"
"Bugünkü Resmi Gazete bültenini göster"
"Son 7 günde yayımlanan mali belgeler"
"Vergi takvimini getir"
"SGK prim oranları 2025"
```

### İhale
```
"Ankara'daki aktif ihaleler"
"Son 30 gündeki yapım ihaleleri"
"'yol yapım' ihalelerini ara"
"Resmi ilanlarda 'taşınmaz satış' ara"
```

### Borsa
```
"BIST THYAO hisse verisi"
"Güncel döviz kurları"
"Bitcoin fiyatı"
"ETH kripto verisi"
```

---

## 🌐 Web Dashboard

Sunucu yayınlandığında kök URL'de bir web dashboard bulunur:

- **`/`** → HTML dashboard (modül durumu, araç listesi, bağlantı bilgisi)
- **`/health`** → JSON sağlık kontrolü endpoint'i
- **`/sse`** → MCP SSE endpoint (client bağlantısı için)
- **`/messages/`** → MCP JSON-RPC mesaj endpoint'i

Dashboard, modüllerin aktif/pasif durumunu gerçek zamanlı gösterir ve her MCP client için yapılandırma şablonu sunar.

---

## 🏗️ Mimari

```
turkiye-mcp/
├── app.py                    # Ana ASGI uygulaması (dashboard + MCP)
├── server.py                 # Alternatif doğrudan MCP sunucusu
├── requirements.txt          # Python bağımlılıkları
├── Dockerfile                 # Docker yapılandırması
├── Procfile                   # Railway Procfile
├── pyproject.toml             # Paket yapılandırması
│
├── yargitay_mcp_module/      # Yargıtay modülü
├── danistay_mcp_module/       # Danıştay modülü
├── emsal_mcp_module/         # EMSAL modülü
├── anayasa_mcp_module/       # Anayasa Mahkemesi modülü
├── kik_mcp_module/           # KİK modülü
├── rekabet_mcp_module/       # Rekabet Kurumu modülü
├── sayistay_mcp_module/      # Sayıştay modülü
├── bddk_mcp_module/          # BDDK modülü
├── kvkk_mcp_module/          # KVKK modülü
├── sigorta_tahkim_mcp_module/# Sigorta Tahkim modülü
├── bedesten_mcp_module/      # Bedesten modülü
├── uyusmazlik_mcp_module/    # Uyuşmazlık Mahkemesi modülü
├── yargi_gib_module/         # Yargı GİB modülü
│
├── mevzuat_search_module/    # Mevzuat arama modülü
├── resmi_gazete_module/      # Resmi Gazete modülü
├── mevzuat_module/           # Mevzuat modülü
├── gib_module/               # GİB modülü
├── ivd_module/               # İVD (e-Fatura) modülü
├── sgk_module/               # SGK modülü
├── iskur_module/             # İŞKUR modülü
├── turmob_module/            # TÜRMOB modülü
├── ismmmo_module/            # İSMMMO modülü
│
├── ihale_module/             # İhale modülü (EKAP + İlan)
├── borsa_module/             # Borsa modülü
├── providers/                # Borsa veri sağlayıcıları
├── borsa_models/             # Borsa modelleri
```

### Graceful Loading

Her modül ayrı ayrı yüklenir. Bir modül yüklenemezse (örneğin bir bağımlılık eksikse), sunucu diğer modüllerle çalışmaya devam eder. `MODULES_AVAILABLE` dict'i her modülün durumunu takip eder ve ilgili araçlar sadece modül aktifse kaydedilir.

### Transport

- **SSE (Server-Sent Events)**: Remote (Railway) deployment için
- Client → `GET /sse` → Session endpoint alır → `POST /messages/?session_id=...` ile JSON-RPC gönderir

---

## 🔧 Ortam Değişkenleri

| Değişken | Varsayılan | Açıklama |
|----------|-----------|----------|
| `PORT` | `8080` | Sunucu portu (Railway otomatik atar) |
| `MCP_HOST` | `0.0.0.0` | Bağlanma adresi |

---

## 📜 Lisans

MIT

## 🙏 Kaynaklar

- [yargi-mcp](https://github.com/saidsurucu/yargi-mcp) — Türk hukuk veritabanları
- [mevzuat-mcp](https://github.com/saidsurucu/mevzuat-mcp) — Mevzuat Bilgi Sistemi
- [ihale-mcp](https://github.com/saidsurucu/ihale-mcp) — Kamu ihale arama
- [borsa-mcp](https://github.com/saidsurucu/borsa-mcp) — Borsa verileri
- [musavir-mcp](https://github.com/ayzekhdawy/musavir-mcp) — Mali müşavir araçları