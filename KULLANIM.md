# 🇹🇷 Türkiye MCP Server — Kullanım Kılavuzu

> **Avukatlar ve hukuk profesyonelleri için hazırlanmıştır.**

## İçindekiler

1. [Hızlı Başlangıç](#hızlı-başlangıç)
2. [EXE Kurulumu](#exe-kurulumu)
3. [AI Sohbet Asistanı](#ai-sohbet-asistanı)
4. [API Anahtarı Yapılandırması (BYOK)](#api-anahtarı-yapılandırması-byok)
5. [PDF Belge Yükleme](#pdf-belge-yükleme)
6. [Hukuki Belge Referansları](#hukuki-belge-referansları)
7. [MCP Araçları](#mcp-araçları)
8. [Klavye Kısayolları](#klavye-kısayolları)
9. [Sorun Giderme](#sorun-giderme)

---

## Hızlı Başlangıç

### Yöntem 1: EXE ile Başlatma (Önerilen)

1. `TurkiyeMCP.exe` dosyasını çift tıklayın
2. Sistem tepsisinde 🇹🇷 ikonu görünür
3. Dashboard otomatik olarak açılır
4. Kapatmak için sistem tepsisi ikonundan "Kapat" seçin

### Yöntem 2: Python ile Başlatma

```bash
# Gerekli paketleri yükleyin
pip install -r requirements.txt
pip install pywebview pystray Pillow keyring

# GUI modunda başlatın
python local_run.py

# Sadece sunucu modunda başlatın (başka terminal'den erişim)
python local_run.py --no-gui

# Tarayıcıda açın
python local_run.py --browser

# Farklı portta başlatın
python local_run.py --port 9090
```

### Yöntem 3: Railway (Bulut) Dağıtımı

Railway üzerinde dağıtım yapılmışsa, web tarayıcısından erişebilirsiniz:
- Dashboard: `https://sizin-url.up.railway.app/`
- SSE Endpoint: `https://sizin-url.up.railway.app/sse`

---

## EXE Kurulumu

### Gereksinimler

- Windows 10/11 (64-bit)
- İnternet bağlantısı

### Build Adımları

```bash
# Paketleri yükleyin
pip install -r requirements.txt
pip install pyinstaller pywebview pystray Pillow keyring

# EXE oluşturun
build.bat

# veya manuel:
pyinstaller turkiye_mcp.spec
```

Oluşturulan EXE: `dist/TurkiyeMCP.exe`

### EXE Komut Satırı Seçenekleri

| Parametre | Açıklama |
|-----------|----------|
| `--no-gui` | GUI penceresini açma, sadece sunucu |
| `--browser` | pywebview yerine tarayıcıda aç |
| `--port PORT` | Farklı port numarası (varsayılan: 8080) |
| `--no-tray` | Sistem tepsisi ikonunu devre dışı bırak |

---

## AI Sohbet Asistanı

Dashboard'daki "Soru Sor" bölümünden hukuk, mali, ihale ve piyasa verileri hakkında soru sorabilirsiniz.

### Örnek Sorular

```
"2025 asgari ücret ne kadar?"
"Yargıtay mülkiyet hakkı kararları"
"Son 7 günde yayımlanan mali belgeler"
"Ankara'daki aktif ihaleler"
"BIST THYAO hisse verisi"
"GİB vergi sirküleri KDV ara"
"e-Fatura 1234567890 mükellef mi?"
"KİK uyuşmazlık kararlarını listele"
"Bugünkü döviz kurları"
```

### Sohbet Akışı

1. Kullanıcı soru sorar
2. Sistem anahtar kelimelere göre ilgili MCP araçlarını çağırır
3. Araç sonuçları + soru LLM'e gönderilir
4. LLM Türkçe yanıt üretir

---

## API Anahtarı Yapılandırması (BYOK)

Chat özelliği için bir LLM (büyük dil modeli) sağlayıcısı gerekir. **Bring Your Own Key (BYOK)** — kendi API anahtarınızı getirin.

### Desteklenen Sağlayıcılar

| Sağlayıcı | API Anahtarı | Modeller | Açıklama |
|------------|-------------|----------|----------|
| **OpenRouter** | Gerekli | gpt-4o-mini, claude-3.5-sonnet, gemini-2.0-flash | Çoklu model, düşük maliyet |
| **OpenAI** | Gerekli | gpt-4o-mini, gpt-4o, gpt-4-turbo | OpenAI modelleri |
| **Anthropic** | Gerekli | claude-sonnet-4, claude-haiku-4 | Claude modelleri |
| **Google Gemini** | Gerekli | gemini-2.0-flash, gemini-1.5-pro | Google modelleri |
| **Ollama (Yerel)** | Gerekli değil | llama3.2, mistral, qwen2.5 | Tamamen yerel, internet gerekmez |

### API Anahtarı Nasıl Alınır?

**OpenRouter (Önerilen):**
1. https://openrouter.ai adresine gidin
2. Hesap oluşturun
3. "Keys" bölümünden yeni anahtar oluşturun
4. Anahtarı dashboard'a yapıştırın

**Ollama (Yerel, Ücretsiz):**
1. https://ollama.ai adresinden Ollama'yı indirin
2. Terminal'de `ollama serve` çalıştırın
3. `ollama pull llama3.2` ile modeli indirin
4. Dashboard'da "Ollama (Yerel)" seçin — API anahtarı gerekmez!

### API Anahtarı Güvenliği

- API anahtarınız **Windows Credential Manager**'da saklanır (keyring ile)
- Kodda veya yapılandırma dosyasında saklanmaz
- Sadece yerel EXE modunda keyring desteği vardır
- Railway (bulut) dağıtımında `OPENROUTER_API_KEY` environment variable kullanılır

---

## PDF Belge Yükleme

Dashboard'daki "Belge Yükle" bölümünden PDF dosyası yükleyebilirsiniz.

### Desteklenen Özellikler

- **PDF metin çıkarma**: PyMuPDF ile doğrudan metin çıkarma
- **OCR fallback**: Metin çıkarılamazsa Tesseract OCR ile taranmış belgeleri okuma
- **Referans tespiti**: Esas numarası, karar numarası, RG sayısı vb. otomatik tespit
- **Bir tıkla arama**: Tespit edilen referansları MCP araçlarıyla arama

### Kullanım

1. PDF dosyasını sürükleyip bırakın veya tıklayarak seçin
2. Sistem belgeyi analiz eder
3. Çıkarılan metin ve referans numaraları görüntülenir
4. "Tüm Referansları Ara" butonuna tıklayın

### OCR Kurulumu (Opsiyonel)

Taranmış belgeler için OCR desteği:

```bash
# Tesseract OCR kurulumu
# Windows: https://github.com/UB-Mannheim/tesseract/wiki
# Türkçe dil paketi: tesseract-ocr-tur

pip install pytesseract pdf2image

# Poppler kurulumu (pdf2image için gerekli)
# Windows: https://github.com/oschwartz10612/poppler-windows/releases
```

---

## Hukuki Belge Referansları

PDF yüklendiğinde sistem aşağıdaki referans türlerini otomatik tespit eder:

| Referans Türü | Örnek | MCP Aracı |
|--------------|-------|-----------|
| **Esas No** | 2023/1234 | Bedesten arama |
| **Karar No** | K.2024/567 | Bedesten arama |
| **Resmi Gazete** | RG 32222 | Resmi Gazete arama |
| **VKN/TCKN** | 1234567890 | e-Fatura sorgulama |
| **Kanun No** | 4721 sayılı kanun | Resmi Gazete arama |
| **İhale Kayıt No** | 2024/123456 | İhale arama |
| **Dosya No** | D:2023/456 | Bedesten arama |

---

## MCP Araçları

### Yargı (Hukuk)

| Araç | Açıklama |
|------|----------|
| `search_bedesten_unified` | Yargıtay, Danıştay, İstinaf karar arama |
| `get_bedesten_document` | Karar metni getirme |
| `search_anayasa_unified` | Anayasa Mahkemesi karar arama |
| `search_kik_v2_decisions` | KİK kararları |
| `search_rekabet_kurumu` | Rekabet Kurumu kararları |
| `search_sayistay_unified` | Sayıştay kararları |
| `search_kvkk_decisions` | KVKK kararları |
| `search_bddk_decisions` | BDDK kararları |
| `search_sigorta_tahkim` | Sigorta Tahkim kararları |
| `search_uyusmazlik` | Uyuşmazlık Mahkemesi kararları |
| `search_emsal` | EMSAL (UYAP Örnek) kararları |

### Mali Müşavir

| Araç | Açıklama |
|------|----------|
| `search_resmi_gazete` | Resmi Gazete arama |
| `get_daily_bulletin` | Günlük bülten |
| `get_recent_mali_changes` | Son mali değişiklikler |
| `search_gib_sirkuler` | GİB sirküler arama |
| `get_tax_calendar` | Vergi takvimi |
| `check_efatura_taxpayer` | e-Fatura mükellef sorgulama |
| `get_asgari_ucret` | Asgari ücret bilgileri |
| `get_prim_matrahi` | SGK prim oranları |

### İhale

| Araç | Açıklama |
|------|----------|
| `search_tenders` | Kamu ihale arama |
| `get_recent_tenders` | Son ihaleler |
| `search_ilan_ads` | Resmi ilan arama |

### Borsa

| Araç | Açıklama |
|------|----------|
| `get_bist_stock` | BIST hisse verileri |
| `get_fx_rates` | Döviz kurları |
| `get_crypto` | Kripto para verileri |

---

## Klavye Kısayolları

| Kısayol | Açıklama |
|---------|----------|
| `Enter` | Mesaj gönder |
| `Ctrl+V` | Metin yapıştır |
| Pencereyi kapat | Arka planda çalışmaya devam eder |
| Sistem tepsisi → Göster | Pencereyi tekrar aç |
| Sistem tepsisi → Kapat | Uygulamayı kapat |

---

## Sorun Giderme

### Sunucu Başlatılamıyor

```bash
# Port kullanımda mı kontrol edin
netstat -an | findstr 8080

# Farklı portta başlatın
python local_run.py --port 9090
```

### API Anahtarı Çalışmıyor

1. API anahtarının doğru kopyalandığından emin olun
2. OpenRouter'da kredi/bakiye kontrolü yapın
3. Başka bir sağlayıcı deneyin (Ollama tamamen yerel)

### Ollama Bağlantı Hatası

```bash
# Ollama'nın çalıştığından emin olun
ollama serve

# Modelin indirildiğinden emin olun
ollama pull llama3.2

# Test edin
ollama run llama3.2 "Merhaba"
```

### PDF Yükleme Çalışmıyor

- PDF dosyasının 20MB'den küçük olduğundan emin olun
- Sadece PDF formatı desteklenir
- Taranmış belgeler için OCR kurulumu gerekir

### Modül Yüklenemiyor

```bash
# Health endpoint'i kontrol edin
curl http://127.0.0.1:8080/health

# Eksik paketleri yükleyin
pip install -r requirements.txt
```

---

## Sistem Gereksinimleri

| Bileşen | Minimum | Önerilen |
|---------|---------|----------|
| İşletim Sistemi | Windows 10 64-bit | Windows 11 |
| Python | 3.11+ | 3.12+ |
| RAM | 512 MB | 1 GB |
| Disk | 200 MB | 500 MB |
| İnternet | Gerekli (bulut LLM) | Yerel LLM için gerekli değil |

## Lisans

MIT License — Açık kaynak ve ücretsiz.

## İletişim

- GitHub: https://github.com/ayzekhdawy/turkiye-mcp
- Sorular ve öneriler için GitHub Issues kullanabilirsiniz