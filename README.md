# 🇹🇷 Türkiye MCP Server

**Türkiye Hukuk, Mali, İhale ve Piyasa Verileri - Birleştirilmiş MCP Sunucusu**

Bu proje, 5 farklı MCP sunucusunu tek bir birleştirilmiş projede harmanlar:

| Kaynak | Açıklama | Araç Sayısı |
|--------|----------|-------------|
| **Yargı MCP** | Yargıtay, Danıştay, Anayasa, KİK, Rekabet, Sayıştay, BDDK, KVKK, Sigorta Tahkim, Bedesten | ~15 |
| **Mevzuat MCP** | Mevzuat Bilgi Sistemi, kanun, KHK, yönetmelik | ~2 |
| **İhale MCP** | Kamu ihale arama (EKAP v2), resmi ilanlar | ~4 |
| **Borsa MCP** | BIST, kripto, döviz, yatırım fonları | ~3 |
| **Mali Müşavir MCP** | Resmi Gazete, GİB, İVD, SGK, İŞKUR, TÜRMOB, İSMMMO | ~10 |

**Toplam: ~34+ araç**

## Kurulum

```bash
pip install -r requirements.txt
```

## Çalıştırma

```bash
# Lokal
python server.py

# SSE transport (Railway için)
python server.py
```

## Claude Desktop Yapılandırması

```json
{
    "mcpServers": {
        "turkiye": {
            "url": "https://your-app.up.railway.app/sse"
        }
    }
}
```

## Araçlar

### 🔍 Hukuk (Yargı)
- `search_bedesten_unified` - Birden fazla mahkemede birleştirilmiş arama
- `get_bedesten_document` - Bedesten'den karar metni
- `search_anayasa_unified` - Anayasa Mahkemesi arama
- `search_kik_v2_decisions` - KİK karar arama
- `search_rekabet_kurumu` - Rekabet Kurumu arama
- `search_sayistay_unified` - Sayıştay arama
- `search_kvkk_decisions` - KVKK arama
- `search_bddk_decisions` - BDDK arama
- `search_sigorta_tahkim` - Sigorta Tahkim arama
- `search_uyusmazlik` - Uyuşmazlık Mahkemesi arama
- `search_emsal` - EMSAL (UYAP Örnek) arama

### 📋 Mali Müşavir
- `search_resmi_gazete` - Resmi Gazete belge arama
- `get_daily_bulletin` - Günlük Resmi Gazete bülteni
- `get_recent_mali_changes` - Son N günün mali belgeleri
- `search_gib_sirkuler` - GİB sirküler arama
- `get_tax_calendar` - Vergi takvimi
- `check_efatura_taxpayer` - e-Fatura mükellef sorgulama
- `get_asgari_ucret` - Asgari ücret bilgileri
- `get_prim_matrahi` - SGK prim oranları
- `get_turmob_pratik_bilgiler` - TÜRMOB pratik bilgileri
- `get_ismmmo_pratik_bilgiler` - İSMMMO pratik bilgileri

### 🏗️ İhale
- `search_tenders` - Kamu ihale arama
- `get_recent_tenders` - Son ihaleler
- `search_ilan_ads` - Resmi ilan arama

### 📈 Borsa
- `get_bist_stock` - BIST hisse verileri
- `get_fx_rates` - Döviz kurları
- `get_crypto` - Kripto para verileri

### 🏥 Sağlık
- `check_health` - Tüm modüllerin sağlık kontrolü

## Mimari

Her modül ayrı ayrı yüklenir ve hata durumunda graceful fallback sağlar. Bir modül yüklenemezse, sunucu diğer modüllerle çalışmaya devam eder.

## Lisans

MIT

## Kaynaklar

- [yargi-mcp](https://github.com/saidsurucu/yargi-mcp) - Türk hukuk veritabanları
- [mevzuat-mcp](https://github.com/saidsurucu/mevzuat-mcp) - Mevzuat Bilgi Sistemi
- [ihale-mcp](https://github.com/saidsurucu/ihale-mcp) - Kamu ihale arama
- [borsa-mcp](https://github.com/saidsurucu/borsa-mcp) - Borsa verileri
- [musavir-mcp](https://github.com/ayzekhdawy/musavir-mcp) - Mali müşavir araçları