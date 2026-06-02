#!/usr/bin/env python3
"""Türkiye MCP Server - Unified Turkish Legal, Financial, Procurement & Market Data.

Bu MCP sunucusu 5 farklı veri kaynağını birleştirir:

1. YARGI (Hukuk) - Yargıtay, Danıştay, Anayasa, KİK, Rekabet, Sayıştay, BDDK, KVKK, Sigorta Tahkim, Bedesten, Uyuşmazlık
2. MEVZUAT - Mevzuat Bilgi Sistemi, kanun, KHK, yönetmelik arama
3. İHALE - Kamu ihale arama ve detay (EKAP v2)
4. BORSA - Borsa İstanbul, ABD hisseleri, kripto, yatırım fonları, döviz
5. MALİ MÜŞAVİR - Resmi Gazete, GİB, İVD, SGK, İŞKUR, TÜRMOB, İSMMMO

Kullanım:
    # Lokal
    python server.py

    # Railway'de otomatik başlatılır

Claude Desktop yapılandırması:
    {
        "mcpServers": {
            "turkiye": {
                "url": "https://your-app.up.railway.app/sse"
            }
        }
    }
"""

import os
import logging
from typing import Optional, List
from datetime import date, timedelta

from fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastMCP(
    name="Türkiye MCP Server",
    version="1.0.0",
)

# ============================================================
# MODÜL İÇERİKLERİNİ YÜKLE - Graceful fallback ile
# ============================================================

MODULES_AVAILABLE = {}

# --- MALİ MÜŞAVİR MODÜLLERİ ---
try:
    from resmi_gazete_module import ResmiGazeteClient
    from resmi_gazete_module.models import BelgeTuru, ResmiGazeteSearchRequest
    resmi_gazete_client = ResmiGazeteClient()
    MODULES_AVAILABLE["resmi_gazete"] = True
    logger.info("✅ Resmi Gazete modülü yüklendi")
except Exception as e:
    logger.warning(f"❌ Resmi Gazete modülü yüklenemedi: {e}")
    MODULES_AVAILABLE["resmi_gazete"] = False

try:
    from mevzuat_module import MevzuatClient
    from mevzuat_module.models import MevzuatSearchRequest, MevzuatTuru
    mevzuat_client = MevzuatClient()
    MODULES_AVAILABLE["mevzuat"] = True
    logger.info("✅ Mevzuat modülü yüklendi")
except Exception as e:
    logger.warning(f"❌ Mevzuat modülü yüklenemedi: {e}")
    MODULES_AVAILABLE["mevzuat"] = False

try:
    from gib_module import GibClient
    from gib_module.models import GibSirkulerSearchRequest, SirkulerTuru
    gib_client = GibClient()
    MODULES_AVAILABLE["gib"] = True
    logger.info("✅ GİB modülü yüklendi")
except Exception as e:
    logger.warning(f"❌ GİB modülü yüklenemedi: {e}")
    MODULES_AVAILABLE["gib"] = False

try:
    from ivd_module import IvdClient
    from ivd_module.models import FaturaDogrulama
    ivd_client = IvdClient()
    MODULES_AVAILABLE["ivd"] = True
    logger.info("✅ İVD modülü yüklendi")
except Exception as e:
    logger.warning(f"❌ İVD modülü yüklenemedi: {e}")
    MODULES_AVAILABLE["ivd"] = False

try:
    from sgk_module import SgkClient
    from sgk_module.models import SgkGenelgeSearchRequest
    sgk_client = SgkClient()
    MODULES_AVAILABLE["sgk"] = True
    logger.info("✅ SGK modülü yüklendi")
except Exception as e:
    logger.warning(f"❌ SGK modülü yüklenemedi: {e}")
    MODULES_AVAILABLE["sgk"] = False

try:
    from iskur_module import IskurClient
    from iskur_module.models import IskurDuyuruSearchRequest
    iskur_client = IskurClient()
    MODULES_AVAILABLE["iskur"] = True
    logger.info("✅ İŞKUR modülü yüklendi")
except Exception as e:
    logger.warning(f"❌ İŞKUR modülü yüklenemedi: {e}")
    MODULES_AVAILABLE["iskur"] = False

try:
    from turmob_module import TurmobClient
    from turmob_module.models import TurmobSirkulerSearchRequest
    turmob_client = TurmobClient()
    MODULES_AVAILABLE["turmob"] = True
    logger.info("✅ TÜRMOB modülü yüklendi")
except Exception as e:
    logger.warning(f"❌ TÜRMOB modülü yüklenemedi: {e}")
    MODULES_AVAILABLE["turmob"] = False

try:
    from ismmmo_module import IsmmmoClient
    from ismmmo_module.models import IsmmmoRehberSearchRequest
    ismmmo_client = IsmmmoClient()
    MODULES_AVAILABLE["ismmmo"] = True
    logger.info("✅ İSMMMO modülü yüklendi")
except Exception as e:
    logger.warning(f"❌ İSMMMO modülü yüklenemedi: {e}")
    MODULES_AVAILABLE["ismmmo"] = False

# --- YARGI MODÜLLERİ (yargi-mcp'den) ---
try:
    from bedesten_mcp_module.client import BedestenApiClient
    from bedesten_mcp_module.models import BedestenSearchRequest, BedestenSearchData, BedestenCourtTypeEnum
    bedesten_client = BedestenApiClient()
    MODULES_AVAILABLE["bedesten"] = True
    logger.info("✅ Bedesten modülü yüklendi")
except Exception as e:
    logger.warning(f"❌ Bedesten modülü yüklenemedi: {e}")
    MODULES_AVAILABLE["bedesten"] = False

try:
    from anayasa_mcp_module.unified_client import AnayasaUnifiedClient
    from anayasa_mcp_module.models import AnayasaUnifiedSearchRequest
    anayasa_client = AnayasaUnifiedClient()
    MODULES_AVAILABLE["anayasa"] = True
    logger.info("✅ Anayasa modülü yüklendi")
except Exception as e:
    logger.warning(f"❌ Anayasa modülü yüklenemedi: {e}")
    MODULES_AVAILABLE["anayasa"] = False

try:
    from kik_mcp_module.client_v2 import KikV2ApiClient
    from kik_mcp_module.models_v2 import KikV2DecisionType
    kik_client = KikV2ApiClient()
    MODULES_AVAILABLE["kik"] = True
    logger.info("✅ KİK modülü yüklendi")
except Exception as e:
    logger.warning(f"❌ KİK modülü yüklenemedi: {e}")
    MODULES_AVAILABLE["kik"] = False

try:
    from rekabet_mcp_module.client import RekabetKurumuApiClient
    from rekabet_mcp_module.models import RekabetKurumuSearchRequest
    rekabet_client = RekabetKurumuApiClient()
    MODULES_AVAILABLE["rekabet"] = True
    logger.info("✅ Rekabet modülü yüklendi")
except Exception as e:
    logger.warning(f"❌ Rekabet modülü yüklenemedi: {e}")
    MODULES_AVAILABLE["rekabet"] = False

try:
    from sayistay_mcp_module.unified_client import SayistayUnifiedClient
    from sayistay_mcp_module.models import SayistayUnifiedSearchRequest
    sayistay_client = SayistayUnifiedClient()
    MODULES_AVAILABLE["sayistay"] = True
    logger.info("✅ Sayıştay modülü yüklendi")
except Exception as e:
    logger.warning(f"❌ Sayıştay modülü yüklenemedi: {e}")
    MODULES_AVAILABLE["sayistay"] = False

try:
    from bddk_mcp_module.client import BddkApiClient
    from bddk_mcp_module.models import BddkSearchRequest
    bddk_client = BddkApiClient()
    MODULES_AVAILABLE["bddk"] = True
    logger.info("✅ BDDK modülü yüklendi")
except Exception as e:
    logger.warning(f"❌ BDDK modülü yüklenemedi: {e}")
    MODULES_AVAILABLE["bddk"] = False

try:
    from kvkk_mcp_module.client import KvkkApiClient
    from kvkk_mcp_module.models import KvkkSearchRequest
    kvkk_client = KvkkApiClient()
    MODULES_AVAILABLE["kvkk"] = True
    logger.info("✅ KVKK modülü yüklendi")
except Exception as e:
    logger.warning(f"❌ KVKK modülü yüklenemedi: {e}")
    MODULES_AVAILABLE["kvkk"] = False

try:
    from sigorta_tahkim_mcp_module.client import SigortaTahkimApiClient
    from sigorta_tahkim_mcp_module.models import SigortaTahkimSearchRequest
    sigorta_tahkim_client = SigortaTahkimApiClient()
    MODULES_AVAILABLE["sigorta_tahkim"] = True
    logger.info("✅ Sigorta Tahkim modülü yüklendi")
except Exception as e:
    logger.warning(f"❌ Sigorta Tahkim modülü yüklenemedi: {e}")
    MODULES_AVAILABLE["sigorta_tahkim"] = False

try:
    from uyusmazlik_mcp_module.client import UyusmazlikApiClient
    from uyusmazlik_mcp_module.models import UyusmazlikSearchRequest
    uyusmazlik_client = UyusmazlikApiClient()
    MODULES_AVAILABLE["uyusmazlik"] = True
    logger.info("✅ Uyuşmazlık modülü yüklendi")
except Exception as e:
    logger.warning(f"❌ Uyuşmazlık modülü yüklenemedi: {e}")
    MODULES_AVAILABLE["uyusmazlik"] = False

try:
    from emsal_mcp_module.client import EmsalApiClient
    from emsal_mcp_module.models import EmsalSearchRequest
    emsal_client = EmsalApiClient()
    MODULES_AVAILABLE["emsal"] = True
    logger.info("✅ Emsal modülü yüklendi")
except Exception as e:
    logger.warning(f"❌ Emsal modülü yüklenemedi: {e}")
    MODULES_AVAILABLE["emsal"] = False

# --- İHALE MODÜLÜ (ihale-mcp'den) ---
try:
    from ihale_module.ihale_client import EKAPClient
    from ihale_module.ilan_client import IlanClient
    ekap_client = EKAPClient()
    ilan_client_inst = IlanClient()
    MODULES_AVAILABLE["ihale"] = True
    logger.info("✅ İhale modülü yüklendi")
except Exception as e:
    logger.warning(f"❌ İhale modülü yüklenemedi: {e}")
    MODULES_AVAILABLE["ihale"] = False

# --- BORSA MODÜLÜ (borsa-mcp'den) ---
try:
    from borsa_module.borsa_client import BorsaClient
    borsa_client = BorsaClient()
    MODULES_AVAILABLE["borsa"] = True
    logger.info("✅ Borsa modülü yüklendi")
except Exception as e:
    logger.warning(f"❌ Borsa modülü yüklenemedi: {e}")
    MODULES_AVAILABLE["borsa"] = False


# ============================================================
# MALİ MÜŞAVİR ARAÇLARI
# ============================================================

if MODULES_AVAILABLE.get("resmi_gazete"):
    @app.tool(description="Resmi Gazete'de belge arama. Kanun, tebliğ, yönetmelik, sirküler arar.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def search_resmi_gazete(anahtar_kelime: str, belge_turu: str = "", baslangic_tarihi: str = "", bitis_tarihi: str = "", sayfa: int = 1) -> str:
        try:
            tur_map = {"kanun": BelgeTuru.KANUN, "khk": BelgeTuru.KANUN_HUKMUNDE_KARARNAME, "cbk": BelgeTuru.CUMHURBASKANLIKI_KARAR, "yonetmelik": BelgeTuru.YONETMELIK, "teblig": BelgeTuru.TEBLIG, "sirkuler": BelgeTuru.SIRKULER, "genelge": BelgeTuru.GENELGE}
            request = ResmiGazeteSearchRequest(
                anahtar_kelime=anahtar_kelime,
                belge_turu=tur_map.get(belge_turu.lower()) if belge_turu else None,
                baslangic_tarihi=date.fromisoformat(baslangic_tarihi) if baslangic_tarihi else None,
                bitis_tarihi=date.fromisoformat(bitis_tarihi) if bitis_tarihi else None,
                sayfa=sayfa
            )
            response = await resmi_gazete_client.search(request)
            result = f"# Resmi Gazete Arama Sonuçları\n\n**Toplam:** {response.toplam_sonuc} sonuç | **Sayfa:** {response.sayfa}/{response.toplam_sayfa}\n\n"
            for item in response.sonuclar:
                result += f"- **{item.baslik}** ({item.belge_turu}) - {item.tarihi}\n"
                if item.detay_url: result += f"  🔗 {item.detay_url}\n"
            return result
        except Exception as e:
            return f"❌ Resmi Gazete arama hatası: {str(e)}"

    @app.tool(description="Günlük Resmi Gazete bültenlerini getirir.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def get_daily_bulletin(tarih: str = "") -> str:
        try:
            target_date = date.fromisoformat(tarih) if tarih else date.today()
            bultens = await resmi_gazete_client.get_daily_bulletin(target_date)
            result = f"# Resmi Gazete - {target_date.strftime('%d.%m.%Y')}\n\n**Toplam:** {len(bultens)} belge\n\n"
            for item in bultens:
                result += f"- **{item.baslik}** ({item.belge_turu})\n"
            return result if bultens else "Bu tarihte bülten bulunamadı."
        except Exception as e:
            return f"❌ Bülten hatası: {str(e)}"

    @app.tool(description="Son N günün mali belgelerini getirir.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def get_recent_mali_changes(gun: int = 7) -> str:
        try:
            bultens = await resmi_gazete_client.get_recent_changes(days=gun)
            if not bultens: return f"Son {gun} günde mali belge bulunamadı."
            result = f"# Son {gun} Günün Mali Belgeleri\n\n**Toplam:** {len(bultens)} belge\n\n"
            for item in bultens: result += f"- **{item.baslik}** ({item.tarihi})\n"
            return result
        except Exception as e:
            return f"❌ Mali değişiklik hatası: {str(e)}"

if MODULES_AVAILABLE.get("gib"):
    @app.tool(description="GİB sirkülerlerinde arama yapar.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def search_gib_sirkuler(anahtar_kelime: str, sirkuler_turu: str = "", yil: int = None, sayfa: int = 1) -> str:
        try:
            tur_map = {"vergi_sirkuleri": SirkulerTuru.VERGI_SIRKULERI, "ic_genelge": SirkulerTuru.ICGENELGE, "duyuru": SirkulerTuru.DUYURU, "teblig": SirkulerTuru.TEBLIG}
            request = GibSirkulerSearchRequest(
                anahtar_kelime=anahtar_kelime,
                sirkuler_turu=tur_map.get(sirkuler_turu.lower()) if sirkuler_turu else None,
                yil=yil, sayfa=sayfa
            )
            response = await gib_client.search_sirkuler(request)
            result = f"# GİB Sirküler Arama\n\n**Toplam:** {response.toplam_sonuc} sonuç\n\n"
            for item in response.sonuclar:
                result += f"- **{item.baslik}** | No: {item.sirkuler_no or '-'} | Tarih: {item.tarih or '-'}\n"
            return result
        except Exception as e:
            return f"❌ GİB sirküler hatası: {str(e)}"

    @app.tool(description="Vergi takvimi bilgileri.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def get_tax_calendar(yil: int = None) -> str:
        try:
            donemler = await gib_client.get_tax_calendar(yil)
            target_yil = yil or date.today().year
            result = f"# {target_yil} Vergi Takvimi\n\n"
            for donem in donemler:
                result += f"## {donem.ay}\n"
                for oge in donem.ogeler: result += f"- **{oge.vergi_turu}**: {oge.beyanname_tarihi.strftime('%d.%m')} / {oge.odeme_tarihi.strftime('%d.%m')}\n"
            return result
        except Exception as e:
            return f"❌ Vergi takvimi hatası: {str(e)}"

if MODULES_AVAILABLE.get("ivd"):
    @app.tool(description="VKN/TCKN ile e-Fatura mükellef sorgulama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def check_efatura_taxpayer(vergi_kimlik_no: str) -> str:
        try:
            result = await ivd_client.check_efatura_taxpayer(vergi_kimlik_no)
            return f"# e-Fatura Mükellef Sorgulama\n\n**VKN/TCKN:** {result.vergi_kimlik_no}\n**Unvan:** {result.unvan or '-'}\n**e-Fatura:** {'✅' if result.efatura_mukellef else '❌'}\n**e-İrsaliye:** {'✅' if result.eirsaliye_mukellef else '❌'}"
        except Exception as e:
            return f"❌ e-Fatura sorgulama hatası: {str(e)}"

if MODULES_AVAILABLE.get("sgk"):
    @app.tool(description="Asgari ücret bilgileri.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def get_asgari_ucret(yil: int = None) -> str:
        try:
            data = await sgk_client.get_asgari_ucret(yil)
            return f"# Asgari Ücret - {data.yil}\n\n| Özellik | Tutar |\n|---------|-------|\n| Aylık Brüt | {data.aylik_brut:,.2f} TL |\n| Aylık Net | {data.aylik_net:,.2f} TL |\n| Saatlik Brüt | {data.saatlik_brut:,.2f} TL |"
        except Exception as e:
            return f"❌ Asgari ücret hatası: {str(e)}"

    @app.tool(description="SGK prim matrahı ve oranları.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def get_prim_matrahi(yil: int = None) -> str:
        try:
            data = await sgk_client.get_prim_matrahi(yil)
            return f"# SGK Prim Oranları - {data.yil}\n\n| Prim Türü | Oran |\n|-----------|------|\n| SGK İşçi | %{data.sgk_isci_premi} |\n| SGK İşveren | %{data.sgk_isveren_premi} |\n| İşsizlik İşçi | %{data.issizlik_isci_premi} |\n| İşsizlik İşveren | %{data.issizlik_isveren_premi} |"
        except Exception as e:
            return f"❌ Prim matrahı hatası: {str(e)}"

if MODULES_AVAILABLE.get("turmob"):
    @app.tool(description="TÜRMOB pratik bilgileri (KDV, stopaj, damga vergisi).", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def get_turmob_pratik_bilgiler(kategori: str = "") -> str:
        try:
            bilgiler = await turmob_client.get_pratik_bilgiler(kategori if kategori else None)
            result = "# TÜRMOB Pratik Bilgiler\n\n"
            for b in bilgiler: result += f"{b.icerik}\n\n---\n\n"
            return result
        except Exception as e:
            return f"❌ TÜRMOB hatası: {str(e)}"

if MODULES_AVAILABLE.get("ismmmo"):
    @app.tool(description="İSMMMO pratik bilgileri (vergi, SGK rehberleri).", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def get_ismmmo_pratik_bilgiler(kategori: str = "") -> str:
        try:
            bilgiler = await ismmmo_client.get_pratik_bilgiler(kategori if kategori else None)
            result = "# İSMMMO Pratik Bilgiler\n\n"
            for b in bilgiler: result += f"## {b.baslik}\n\n{b.icerik}\n\n---\n\n"
            return result
        except Exception as e:
            return f"❌ İSMMMO hatası: {str(e)}"

# ============================================================
# YARGI ARAÇLARI
# ============================================================

if MODULES_AVAILABLE.get("bedesten"):
    @app.tool(description="Birden fazla Türk mahkemesinde birleştirilmiş arama. Yargıtay, Danıştay, Yerel, İstinaf kararları.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def search_bedesten_unified(keyword: str, court_types: List[str] = None, page_number: int = 1) -> str:
        try:
            if court_types is None: court_types = ["YARGITAYKARARI", "DANISTAYKARAR"]
            search_data = BedestenSearchData(pageSize=10, pageNumber=page_number, itemTypeList=court_types, phrase=keyword)
            search_request = BedestenSearchRequest(data=search_data)
            response = await bedesten_client.search_documents(search_request)
            if response.data and response.data.emsalKararList:
                result = f"# Bedesten Arama\n\n**Arama:** {keyword}\n**Toplam:** {response.data.total} sonuç\n\n"
                for d in response.data.emsalKararList[:10]:
                    result += f"- **{d.birimAdi or '-'}** | Esas: {d.esasNo or '-'} | Karar: {d.kararNo or '-'} | Tarih: {d.kararTarihiStr or '-'}\n"
                return result
            return "Sonuç bulunamadı."
        except Exception as e:
            return f"❌ Bedesten arama hatası: {str(e)}"

    @app.tool(description="Bedesten'den karar metnini Markdown olarak getirir.", annotations={"readOnlyHint": True, "openWorldHint": False, "idempotentHint": True})
    async def get_bedesten_document(document_id: str) -> str:
        try:
            doc = await bedesten_client.get_document_as_markdown(document_id)
            if doc and doc.markdown_content: return doc.markdown_content[:8000]
            return "Belge bulunamadı."
        except Exception as e:
            return f"❌ Bedesten belge hatası: {str(e)}"

if MODULES_AVAILABLE.get("anayasa"):
    @app.tool(description="Anayasa Mahkemesi kararlarında arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def search_anayasa_unified(keywords: str, decision_type: str = "bireysel_basvuru", page: int = 1) -> str:
        try:
            request = AnayasaUnifiedSearchRequest(decision_type=decision_type, keywords=[keywords], page_to_fetch=page, results_per_page=10)
            result = await anayasa_client.search_unified(request)
            return str(result.model_dump())[:4000]
        except Exception as e:
            return f"❌ AYM arama hatası: {str(e)}"

if MODULES_AVAILABLE.get("kik"):
    @app.tool(description="KİK kararlarında arama (uyuşmazlık, düzenleyici, mahkeme).", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def search_kik_v2_decisions(decision_type: str = "uyusmazlik", keyword: str = "", karar_no: str = "") -> str:
        try:
            kik_type = KikV2DecisionType(decision_type)
            response = await kik_client.search_decisions(decision_type=kik_type, karar_metni=keyword, karar_no=karar_no)
            result = f"# KİK Arama ({decision_type})\n\n**Toplam:** {response.total_records} sonuç\n\n"
            for d in response.decisions[:10]:
                result += f"- **{d.kararNo or '-'}** | Başvuran: {d.basvuran or '-'} | Tarih: {d.kararTarihi or '-'}\n"
            return result
        except Exception as e:
            return f"❌ KİK arama hatası: {str(e)}"

if MODULES_AVAILABLE.get("rekabet"):
    @app.tool(description="Rekabet Kurumu kararlarında arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def search_rekabet_kurumu(keyword: str = "", page: int = 1) -> str:
        try:
            request = RekabetKurumuSearchRequest(sayfaAdi=keyword, page=page)
            result = await rekabet_client.search_decisions(request)
            return str(result.model_dump())[:4000]
        except Exception as e:
            return f"❌ Rekabet arama hatası: {str(e)}"

if MODULES_AVAILABLE.get("sayistay"):
    @app.tool(description="Sayıştay kararlarında arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def search_sayistay_unified(decision_type: str = "genel_kurul", keyword: str = "", page: int = 1) -> str:
        try:
            request = SayistayUnifiedSearchRequest(decision_type=decision_type, start=(page-1)*10, length=10, karar_tamami=keyword)
            result = await sayistay_client.search_unified(request)
            return str(result.model_dump())[:4000]
        except Exception as e:
            return f"❌ Sayıştay arama hatası: {str(e)}"

if MODULES_AVAILABLE.get("kvkk"):
    @app.tool(description="KVKK kararlarında arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def search_kvkk_decisions(keyword: str = "", page: int = 1) -> str:
        try:
            request = KvkkSearchRequest(keywords=[keyword], page=page)
            result = await kvkk_client.search_decisions(request)
            return str(result.model_dump())[:4000]
        except Exception as e:
            return f"❌ KVKK arama hatası: {str(e)}"

if MODULES_AVAILABLE.get("bddk"):
    @app.tool(description="BDDK kararlarında arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def search_bddk_decisions(keyword: str = "", page: int = 1) -> str:
        try:
            request = BddkSearchRequest(keywords=[keyword], page=page)
            result = await bddk_client.search_decisions(request)
            return str(result.model_dump())[:4000]
        except Exception as e:
            return f"❌ BDDK arama hatası: {str(e)}"

if MODULES_AVAILABLE.get("sigorta_tahkim"):
    @app.tool(description="Sigorta Tahkim kararlarında arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def search_sigorta_tahkim(keyword: str = "", page: int = 1) -> str:
        try:
            request = SigortaTahkimSearchRequest(keywords=[keyword], page=page)
            result = await sigorta_tahkim_client.search_decisions(request)
            return str(result.model_dump())[:4000]
        except Exception as e:
            return f"❌ Sigorta Tahkim arama hatası: {str(e)}"

if MODULES_AVAILABLE.get("uyusmazlik"):
    @app.tool(description="Uyuşmazlık Mahkemesi kararlarında arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def search_uyusmazlik(keyword: str = "", page: int = 1) -> str:
        try:
            request = UyusmazlikSearchRequest(icerik=keyword)
            result = await uyusmazlik_client.search_decisions(request)
            return str(result.model_dump())[:4000]
        except Exception as e:
            return f"❌ Uyuşmazlık arama hatası: {str(e)}"

if MODULES_AVAILABLE.get("emsal"):
    @app.tool(description="EMSAL (UYAP Örnek) kararlarda arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def search_emsal(keyword: str = "", page: int = 1) -> str:
        try:
            request = EmsalSearchRequest(keyword=keyword, page_number=page, page_size=10)
            result = await emsal_client.search_detailed_decisions(request)
            if result.data and result.data.data:
                output = f"# EMSAL Arama\n\n**Toplam:** {result.data.recordsTotal} sonuç\n\n"
                for d in result.data.data[:10]:
                    output += f"- **{d.daire or '-'}** | Esas: {d.esasNo or '-'} | Karar: {d.kararNo or '-'}\n"
                return output
            return "Sonuç bulunamadı."
        except Exception as e:
            return f"❌ Emsal arama hatası: {str(e)}"

# ============================================================
# İHALE ARAÇLARI
# ============================================================

if MODULES_AVAILABLE.get("ihale"):
    @app.tool(description="Kamu ihalelerinde arama (EKAP v2).", annotations={"readOnlyHint": True, "openWorldHint": True})
    async def search_tenders(search_text: str = "", limit: int = 10) -> str:
        try:
            result = await ekap_client.search_tenders(search_text=search_text, limit=limit)
            if "error" in result: return f"❌ İhale arama hatası: {result['error']}"
            tenders = result.get("tenders", [])
            total = result.get("total_count", 0)
            output = f"# Kamu İhale Arama\n\n**Toplam:** {total} ihale\n\n"
            for t in tenders[:10]:
                name = t.get("name", "-")
                ikn = t.get("ikn", "-")
                ttype = t.get("type", {})
                tdesc = ttype.get("description", "-") if isinstance(ttype, dict) else "-"
                output += f"- **{name}** | İKN: {ikn} | Tür: {tdesc}\n"
            return output
        except Exception as e:
            return f"❌ İhale arama hatası: {str(e)}"

    @app.tool(description="Son N günün ihalelerini getirir.", annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_recent_tenders(days: int = 7, limit: int = 10) -> str:
        try:
            start_date = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")
            end_date = date.today().strftime("%Y-%m-%d")
            result = await ekap_client.search_tenders(search_text="", announcement_date_start=start_date, announcement_date_end=end_date, order_by="ihaleTarihi", sort_order="desc", limit=limit)
            tenders = result.get("tenders", [])
            output = f"# Son {days} Günün İhaleleri\n\n"
            for t in tenders[:10]:
                output += f"- **{t.get('name', '-')}** | İKN: {t.get('ikn', '-')}\n"
            return output
        except Exception as e:
            return f"❌ Son ihaleler hatası: {str(e)}"

    @app.tool(description="Resmi duyuru ve ilan arama (ilan.gov.tr).", annotations={"readOnlyHint": True, "openWorldHint": True})
    async def search_ilan_ads(search_text: str = "", max_result_count: int = 12) -> str:
        try:
            result = await ilan_client_inst.search_ads(search_text=search_text, max_result_count=max_result_count)
            ads = result.get("ads", result.get("ilanlar", []))
            total = result.get("total_count", result.get("toplam", 0))
            output = f"# Resmi İlan Arama\n\n**Toplam:** {total} ilan\n\n"
            for ad in ads[:10]:
                title = ad.get("title", ad.get("baslik", "-"))
                output += f"- **{title}**\n"
            return output
        except Exception as e:
            return f"❌ İlan arama hatası: {str(e)}"

# ============================================================
# BORSA ARAÇLARI
# ============================================================

if MODULES_AVAILABLE.get("borsa"):
    @app.tool(description="BIST hisse verilerini getirir.", annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_bist_stock(symbol: str) -> str:
        try:
            result = await borsa_client.get_bist_stock(symbol)
            return str(result)[:4000]
        except Exception as e:
            return f"❌ BIST hisse hatası: {str(e)}"

    @app.tool(description="Döviz kurlarını getirir.", annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_fx_rates() -> str:
        try:
            result = await borsa_client.get_fx_rates()
            return str(result)[:4000]
        except Exception as e:
            return f"❌ Döviz kuru hatası: {str(e)}"

    @app.tool(description="Kripto para verilerini getirir.", annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_crypto(symbol: str) -> str:
        try:
            result = await borsa_client.get_crypto(symbol)
            return str(result)[:4000]
        except Exception as e:
            return f"❌ Kripto hatası: {str(e)}"

# ============================================================
# SAĞLIK KONTROLÜ
# ============================================================

@app.tool(description="Tüm veri kaynaklarının sağlık durumunu kontrol eder.", annotations={"readOnlyHint": True, "openWorldHint": False, "idempotentHint": True})
async def check_health() -> str:
    available = [k for k, v in MODULES_AVAILABLE.items() if v]
    unavailable = [k for k, v in MODULES_AVAILABLE.items() if not v]
    result = f"# Türkiye MCP Sağlık Kontrolü\n\n**Tarih:** {date.today().strftime('%d.%m.%Y')}\n\n"
    result += f"**Aktif Modüller ({len(available)}):**\n"
    for m in available: result += f"- ✅ {m}\n"
    if unavailable:
        result += f"\n**Devre Dışı Modüller ({len(unavailable)}):**\n"
        for m in unavailable: result += f"- ❌ {m}\n"
    return result


def main():
    logger.info("Türkiye MCP Server başlatılıyor...")
    available_count = sum(1 for v in MODULES_AVAILABLE.values() if v)
    total_count = len(MODULES_AVAILABLE)
    logger.info(f"Modüller: {available_count}/{total_count} aktif")
    app.run(transport="sse", host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))

if __name__ == "__main__":
    main()