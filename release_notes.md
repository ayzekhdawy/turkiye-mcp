## 🇹🇷 Türkiye MCP v1.6.2 — Token & Bağlam Kullanımı

Artık her yanıtın **token tüketimini** ve modelin **bağlam penceresi doluluğunu** görebilirsiniz.

### 🔢 Token & Bağlam Takibi
- Her asistan yanıtının altında: **token sayısı** (giriş→çıkış) ve **bağlam doluluğu %** (modelin tahmini bağlam penceresine göre).
- Üst barda **oturum token toplamı** rozeti.
- **Sistem → Gateway** sekmesinde sağlayıcı başına toplam token.
- Sağlayıcı `usage` döndürmezse giriş token'ı metinden tahmin edilir; model bağlam penceresi model adından kestirilir (ör. minimax/claude 200K, gpt-oss/llama 128K, gemma 8K).

### 📥 İndirme
- **TurkiyeMCP.exe** — Windows 10/11 (64-bit), kurulumsuz.
