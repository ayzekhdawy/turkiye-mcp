#!/usr/bin/env python3
"""Türkiye MCP Server - ASGI Application with Web Dashboard.

Railway deployment için ASGI uygulaması:
- / → Web dashboard (tüm araçlar ve kullanım bilgisi)
- /sse → MCP SSE endpoint
- /messages → MCP message endpoint
- /health → JSON health check
"""

import os
import json
import logging
import time
from collections import defaultdict
from datetime import date
from typing import Optional, List
from datetime import date, timedelta

import httpx
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import HTMLResponse, JSONResponse
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastMCP(name="Türkiye MCP Server", version="1.0.0")

# ============================================================
# MODÜL İÇERİKLERİNİ YÜKLE
# ============================================================
MODULES_AVAILABLE = {}

# --- MALİ MÜŞAVİR MODÜLLERİ ---
try:
    from resmi_gazete_module import ResmiGazeteClient
    from resmi_gazete_module.models import BelgeTuru, ResmiGazeteSearchRequest
    resmi_gazete_client = ResmiGazeteClient()
    MODULES_AVAILABLE["resmi_gazete"] = True
except Exception as e:
    logger.warning(f"❌ Resmi Gazete: {e}")
    MODULES_AVAILABLE["resmi_gazete"] = False

try:
    from mevzuat_module import MevzuatClient
    from mevzuat_module.models import MevzuatSearchRequest, MevzuatTuru
    mevzuat_client = MevzuatClient()
    MODULES_AVAILABLE["mevzuat"] = True
except Exception as e:
    logger.warning(f"❌ Mevzuat: {e}")
    MODULES_AVAILABLE["mevzuat"] = False

try:
    from gib_module import GibClient
    from gib_module.models import GibSirkulerSearchRequest, SirkulerTuru
    gib_client = GibClient()
    MODULES_AVAILABLE["gib"] = True
except Exception as e:
    logger.warning(f"❌ GİB: {e}")
    MODULES_AVAILABLE["gib"] = False

try:
    from ivd_module import IvdClient
    from ivd_module.models import FaturaDogrulama
    ivd_client = IvdClient()
    MODULES_AVAILABLE["ivd"] = True
except Exception as e:
    logger.warning(f"❌ İVD: {e}")
    MODULES_AVAILABLE["ivd"] = False

try:
    from sgk_module import SgkClient
    from sgk_module.models import SgkGenelgeSearchRequest
    sgk_client = SgkClient()
    MODULES_AVAILABLE["sgk"] = True
except Exception as e:
    logger.warning(f"❌ SGK: {e}")
    MODULES_AVAILABLE["sgk"] = False

try:
    from iskur_module import IskurClient
    from iskur_module.models import IskurDuyuruSearchRequest
    iskur_client = IskurClient()
    MODULES_AVAILABLE["iskur"] = True
except Exception as e:
    logger.warning(f"❌ İŞKUR: {e}")
    MODULES_AVAILABLE["iskur"] = False

try:
    from turmob_module import TurmobClient
    from turmob_module.models import TurmobSirkulerSearchRequest
    turmob_client = TurmobClient()
    MODULES_AVAILABLE["turmob"] = True
except Exception as e:
    logger.warning(f"❌ TÜRMOB: {e}")
    MODULES_AVAILABLE["turmob"] = False

try:
    from ismmmo_module import IsmmmoClient
    from ismmmo_module.models import IsmmmoRehberSearchRequest
    ismmmo_client = IsmmmoClient()
    MODULES_AVAILABLE["ismmmo"] = True
except Exception as e:
    logger.warning(f"❌ İSMMMO: {e}")
    MODULES_AVAILABLE["ismmmo"] = False

# --- YARGI MODÜLLERİ ---
try:
    from bedesten_mcp_module.client import BedestenApiClient
    from bedesten_mcp_module.models import BedestenSearchRequest, BedestenSearchData, BedestenCourtTypeEnum
    bedesten_client = BedestenApiClient()
    MODULES_AVAILABLE["bedesten"] = True
except Exception as e:
    logger.warning(f"❌ Bedesten: {e}")
    MODULES_AVAILABLE["bedesten"] = False

try:
    from anayasa_mcp_module.unified_client import AnayasaUnifiedClient
    from anayasa_mcp_module.models import AnayasaUnifiedSearchRequest
    anayasa_client = AnayasaUnifiedClient()
    MODULES_AVAILABLE["anayasa"] = True
except Exception as e:
    logger.warning(f"❌ Anayasa: {e}")
    MODULES_AVAILABLE["anayasa"] = False

try:
    from kik_mcp_module.client_v2 import KikV2ApiClient
    from kik_mcp_module.models_v2 import KikV2DecisionType
    kik_client = KikV2ApiClient()
    MODULES_AVAILABLE["kik"] = True
except Exception as e:
    logger.warning(f"❌ KİK: {e}")
    MODULES_AVAILABLE["kik"] = False

try:
    from rekabet_mcp_module.client import RekabetKurumuApiClient
    from rekabet_mcp_module.models import RekabetKurumuSearchRequest
    rekabet_client = RekabetKurumuApiClient()
    MODULES_AVAILABLE["rekabet"] = True
except Exception as e:
    logger.warning(f"❌ Rekabet: {e}")
    MODULES_AVAILABLE["rekabet"] = False

try:
    from sayistay_mcp_module.unified_client import SayistayUnifiedClient
    from sayistay_mcp_module.models import SayistayUnifiedSearchRequest
    sayistay_client = SayistayUnifiedClient()
    MODULES_AVAILABLE["sayistay"] = True
except Exception as e:
    logger.warning(f"❌ Sayıştay: {e}")
    MODULES_AVAILABLE["sayistay"] = False

try:
    from bddk_mcp_module.client import BddkApiClient
    from bddk_mcp_module.models import BddkSearchRequest
    bddk_client = BddkApiClient()
    MODULES_AVAILABLE["bddk"] = True
except Exception as e:
    logger.warning(f"❌ BDDK: {e}")
    MODULES_AVAILABLE["bddk"] = False

try:
    from kvkk_mcp_module.client import KvkkApiClient
    from kvkk_mcp_module.models import KvkkSearchRequest
    kvkk_client = KvkkApiClient()
    MODULES_AVAILABLE["kvkk"] = True
except Exception as e:
    logger.warning(f"❌ KVKK: {e}")
    MODULES_AVAILABLE["kvkk"] = False

try:
    from sigorta_tahkim_mcp_module.client import SigortaTahkimApiClient
    from sigorta_tahkim_mcp_module.models import SigortaTahkimSearchRequest
    sigorta_tahkim_client = SigortaTahkimApiClient()
    MODULES_AVAILABLE["sigorta_tahkim"] = True
except Exception as e:
    logger.warning(f"❌ Sigorta Tahkim: {e}")
    MODULES_AVAILABLE["sigorta_tahkim"] = False

try:
    from uyusmazlik_mcp_module.client import UyusmazlikApiClient
    from uyusmazlik_mcp_module.models import UyusmazlikSearchRequest
    uyusmazlik_client = UyusmazlikApiClient()
    MODULES_AVAILABLE["uyusmazlik"] = True
except Exception as e:
    logger.warning(f"❌ Uyuşmazlık: {e}")
    MODULES_AVAILABLE["uyusmazlik"] = False

try:
    from emsal_mcp_module.client import EmsalApiClient
    from emsal_mcp_module.models import EmsalSearchRequest
    emsal_client = EmsalApiClient()
    MODULES_AVAILABLE["emsal"] = True
except Exception as e:
    logger.warning(f"❌ Emsal: {e}")
    MODULES_AVAILABLE["emsal"] = False

# --- İHALE MODÜLÜ ---
try:
    from ihale_module.ihale_client import EKAPClient
    from ihale_module.ilan_client import IlanClient
    ekap_client = EKAPClient()
    ilan_client_inst = IlanClient()
    MODULES_AVAILABLE["ihale"] = True
except Exception as e:
    logger.warning(f"❌ İhale: {e}")
    MODULES_AVAILABLE["ihale"] = False

# --- BORSA MODÜLÜ ---
try:
    from borsa_module.borsa_client import BorsaApiClient
    borsa_client = BorsaApiClient()
    MODULES_AVAILABLE["borsa"] = True
except Exception as e:
    logger.warning(f"❌ Borsa: {e}")
    MODULES_AVAILABLE["borsa"] = False

# ============================================================
# MCP ARAÇLARI (aynı server.py'deki gibi)
# ============================================================

if MODULES_AVAILABLE.get("resmi_gazete"):
    @app.tool(description="Resmi Gazete'de belge arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def search_resmi_gazete(anahtar_kelime: str, belge_turu: str = "", baslangic_tarihi: str = "", bitis_tarihi: str = "", sayfa: int = 1) -> str:
        try:
            tur_map = {"kanun": BelgeTuru.KANUN, "khk": BelgeTuru.KANUN_HUKMUNDE_KARARNAME, "cbk": BelgeTuru.CUMHURBASKANLIKI_KARAR, "yonetmelik": BelgeTuru.YONETMELIK, "teblig": BelgeTuru.TEBLIG, "sirkuler": BelgeTuru.SIRKULER, "genelge": BelgeTuru.GENELGE}
            request = ResmiGazeteSearchRequest(anahtar_kelime=anahtar_kelime, belge_turu=tur_map.get(belge_turu.lower()) if belge_turu else None, baslangic_tarihi=date.fromisoformat(baslangic_tarihi) if baslangic_tarihi else None, bitis_tarihi=date.fromisoformat(bitis_tarihi) if bitis_tarihi else None, sayfa=sayfa)
            response = await resmi_gazete_client.search(request)
            result = f"# Resmi Gazete Arama\n\n**Toplam:** {response.toplam_sonuc} sonuç\n\n"
            for item in response.sonuclar: result += f"- **{item.baslik}** ({item.belge_turu}) - {item.tarihi}\n"
            return result
        except Exception as e: return f"❌ Hata: {str(e)}"

    @app.tool(description="Günlük Resmi Gazete bültenlerini getirir.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def get_daily_bulletin(tarih: str = "") -> str:
        try:
            target_date = date.fromisoformat(tarih) if tarih else date.today()
            bultens = await resmi_gazete_client.get_daily_bulletin(target_date)
            result = f"# Resmi Gazete - {target_date.strftime('%d.%m.%Y')}\n\n**Toplam:** {len(bultens)} belge\n\n"
            for item in bultens: result += f"- **{item.baslik}** ({item.belge_turu})\n"
            return result if bultens else "Bülten bulunamadı."
        except Exception as e: return f"❌ Hata: {str(e)}"

    @app.tool(description="Son N günün mali belgelerini getirir.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def get_recent_mali_changes(gun: int = 7) -> str:
        try:
            bultens = await resmi_gazete_client.get_recent_changes(days=gun)
            if not bultens: return f"Son {gun} günde belge yok."
            result = f"# Son {gun} Gün Mali Belgeler\n\n"
            for item in bultens: result += f"- **{item.baslik}** ({item.tarihi})\n"
            return result
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("gib"):
    @app.tool(description="GİB sirkülerlerinde arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def search_gib_sirkuler(anahtar_kelime: str, sirkuler_turu: str = "", yil: int = None, sayfa: int = 1) -> str:
        try:
            tur_map = {"vergi_sirkuleri": SirkulerTuru.VERGI_SIRKULERI, "ic_genelge": SirkulerTuru.ICGENELGE, "duyuru": SirkulerTuru.DUYURU, "teblig": SirkulerTuru.TEBLIG}
            request = GibSirkulerSearchRequest(anahtar_kelime=anahtar_kelime, sirkuler_turu=tur_map.get(sirkuler_turu.lower()) if sirkuler_turu else None, yil=yil, sayfa=sayfa)
            response = await gib_client.search_sirkuler(request)
            result = f"# GİB Sirküler\n\n**Toplam:** {response.toplam_sonuc}\n\n"
            for item in response.sonuclar: result += f"- **{item.baslik}** | No: {item.sirkuler_no or '-'}\n"
            return result
        except Exception as e: return f"❌ Hata: {str(e)}"

    @app.tool(description="Vergi takvimi bilgileri.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def get_tax_calendar(yil: int = None) -> str:
        try:
            donemler = await gib_client.get_tax_calendar(yil)
            result = f"# {(yil or date.today().year)} Vergi Takvimi\n\n"
            for donem in donemler:
                result += f"## {donem.ay}\n"
                for oge in donem.ogeler: result += f"- **{oge.vergi_turu}**: {oge.beyanname_tarihi.strftime('%d.%m')}/{oge.odeme_tarihi.strftime('%d.%m')}\n"
            return result
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("ivd"):
    @app.tool(description="VKN/TCKN ile e-Fatura mükellef sorgulama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def check_efatura_taxpayer(vergi_kimlik_no: str) -> str:
        try:
            result = await ivd_client.check_efatura_taxpayer(vergi_kimlik_no)
            return f"# e-Fatura Sorgulama\n\n**VKN/TCKN:** {result.vergi_kimlik_no}\n**Unvan:** {result.unvan or '-'}\n**e-Fatura:** {'✅' if result.efatura_mukellef else '❌'}\n**e-İrsaliye:** {'✅' if result.eirsaliye_mukellef else '❌'}"
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("sgk"):
    @app.tool(description="Asgari ücret bilgileri.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def get_asgari_ucret(yil: int = None) -> str:
        try:
            data = await sgk_client.get_asgari_ucret(yil)
            return f"# Asgari Ücret - {data.yil}\n\n| | Tutar |\n|---|---|\n| Aylık Brüt | {data.aylik_brut:,.2f} TL |\n| Aylık Net | {data.aylik_net:,.2f} TL |\n| Saatlik | {data.saatlik_brut:,.2f} TL |"
        except Exception as e: return f"❌ Hata: {str(e)}"

    @app.tool(description="SGK prim matrahı ve oranları.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def get_prim_matrahi(yil: int = None) -> str:
        try:
            data = await sgk_client.get_prim_matrahi(yil)
            return f"# SGK Prim - {data.yil}\n\n| | Oran |\n|---|---|\n| SGK İşçi | %{data.sgk_isci_premi} |\n| SGK İşveren | %{data.sgk_isveren_premi} |\n| İşsizlik İşçi | %{data.issizlik_isci_premi} |\n| İşsizlik İşveren | %{data.issizlik_isveren_premi} |"
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("turmob"):
    @app.tool(description="TÜRMOB pratik bilgileri.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def get_turmob_pratik_bilgiler(kategori: str = "") -> str:
        try:
            bilgiler = await turmob_client.get_pratik_bilgiler(kategori if kategori else None)
            result = "# TÜRMOB Pratik Bilgiler\n\n"
            for b in bilgiler: result += f"{b.icerik}\n\n---\n\n"
            return result
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("ismmmo"):
    @app.tool(description="İSMMMO pratik bilgileri.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def get_ismmmo_pratik_bilgiler(kategori: str = "") -> str:
        try:
            bilgiler = await ismmmo_client.get_pratik_bilgiler(kategori if kategori else None)
            result = "# İSMMMO Pratik Bilgiler\n\n"
            for b in bilgiler: result += f"## {b.baslik}\n\n{b.icerik}\n\n---\n\n"
            return result
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("bedesten"):
    @app.tool(description="Birden fazla Türk mahkemesinde birleştirilmiş arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def search_bedesten_unified(keyword: str, court_types: List[str] = None, page_number: int = 1) -> str:
        try:
            if court_types is None: court_types = ["YARGITAYKARARI", "DANISTAYKARAR"]
            search_data = BedestenSearchData(pageSize=10, pageNumber=page_number, itemTypeList=court_types, phrase=keyword)
            response = await bedesten_client.search_documents(BedestenSearchRequest(data=search_data))
            if response.data and response.data.emsalKararList:
                result = f"# Bedesten Arama\n\n**Toplam:** {response.data.total}\n\n"
                for d in response.data.emsalKararList[:10]: result += f"- **{d.birimAdi or '-'}** | Esas: {d.esasNo or '-'} | Karar: {d.kararNo or '-'} | ID: `{d.documentId}`\n"
                return result
            return "Sonuç bulunamadı."
        except Exception as e: return f"❌ Hata: {str(e)}"

    @app.tool(description="Bedesten'den karar metnini getirir.", annotations={"readOnlyHint": True, "openWorldHint": False, "idempotentHint": True})
    async def get_bedesten_document(document_id: str) -> str:
        try:
            doc = await bedesten_client.get_document_as_markdown(document_id)
            if doc and doc.markdown_content: return doc.markdown_content[:8000]
            return "Belge bulunamadı."
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("anayasa"):
    @app.tool(description="Anayasa Mahkemesi kararlarında arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def search_anayasa_unified(keywords: str, decision_type: str = "bireysel_basvuru", page: int = 1) -> str:
        try:
            request = AnayasaUnifiedSearchRequest(decision_type=decision_type, keywords=[keywords], page_to_fetch=page, results_per_page=10)
            result = await anayasa_client.search_unified(request)
            return str(result.model_dump())[:4000]
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("kik"):
    @app.tool(description="KİK kararlarında arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def search_kik_v2_decisions(decision_type: str = "uyusmazlik", keyword: str = "", karar_no: str = "") -> str:
        try:
            response = await kik_client.search_decisions(decision_type=KikV2DecisionType(decision_type), karar_metni=keyword, karar_no=karar_no)
            result = f"# KİK ({decision_type})\n\n**Toplam:** {response.total_records}\n\n"
            for d in response.decisions[:10]: result += f"- **{d.kararNo or '-'}** | {d.basvuran or '-'}\n"
            return result
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("rekabet"):
    @app.tool(description="Rekabet Kurumu kararlarında arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def search_rekabet_kurumu(keyword: str = "", page: int = 1) -> str:
        try:
            result = await rekabet_client.search_decisions(RekabetKurumuSearchRequest(sayfaAdi=keyword, page=page))
            return str(result.model_dump())[:4000]
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("sayistay"):
    @app.tool(description="Sayıştay kararlarında arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def search_sayistay_unified(decision_type: str = "genel_kurul", keyword: str = "", page: int = 1) -> str:
        try:
            result = await sayistay_client.search_unified(SayistayUnifiedSearchRequest(decision_type=decision_type, start=(page-1)*10, length=10, karar_tamami=keyword))
            return str(result.model_dump())[:4000]
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("kvkk"):
    @app.tool(description="KVKK kararlarında arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def search_kvkk_decisions(keyword: str = "", page: int = 1) -> str:
        try:
            result = await kvkk_client.search_decisions(KvkkSearchRequest(keywords=keyword, page=page))
            return str(result.model_dump())[:4000]
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("bddk"):
    @app.tool(description="BDDK kararlarında arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def search_bddk_decisions(keyword: str = "", page: int = 1) -> str:
        try:
            result = await bddk_client.search_decisions(BddkSearchRequest(keywords=keyword, page=page))
            return str(result.model_dump())[:4000]
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("sigorta_tahkim"):
    @app.tool(description="Sigorta Tahkim kararlarında arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def search_sigorta_tahkim(keyword: str = "", page: int = 1) -> str:
        try:
            result = await sigorta_tahkim_client.search_decisions(SigortaTahkimSearchRequest(keywords=keyword, page=page))
            return str(result.model_dump())[:4000]
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("uyusmazlik"):
    @app.tool(description="Uyuşmazlık Mahkemesi kararlarında arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def search_uyusmazlik(keyword: str = "", page: int = 1) -> str:
        try:
            result = await uyusmazlik_client.search_decisions(UyusmazlikSearchRequest(icerik=keyword))
            return str(result.model_dump())[:4000]
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("emsal"):
    @app.tool(description="EMSAL kararlarda arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def search_emsal(keyword: str = "", page: int = 1) -> str:
        try:
            result = await emsal_client.search_detailed_decisions(EmsalSearchRequest(keyword=keyword, page_number=page, page_size=10))
            if result.data and result.data.data:
                output = f"# EMSAL\n\n**Toplam:** {result.data.recordsTotal}\n\n"
                for d in result.data.data[:10]: output += f"- **{d.daire or '-'}** | {d.esasNo or '-'} | {d.kararNo or '-'}\n"
                return output
            return "Sonuç yok."
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("ihale"):
    @app.tool(description="Kamu ihalelerinde arama (EKAP v2).", annotations={"readOnlyHint": True, "openWorldHint": True})
    async def search_tenders(search_text: str = "", limit: int = 10) -> str:
        try:
            result = await ekap_client.search_tenders(search_text=search_text, limit=limit)
            if "error" in result: return f"❌ {result['error']}"
            tenders = result.get("tenders", [])
            output = f"# Kamu İhale\n\n**Toplam:** {result.get('total_count', 0)}\n\n"
            for t in tenders[:10]: output += f"- **{t.get('name', '-')}** | İKN: {t.get('ikn', '-')}\n"
            return output
        except Exception as e: return f"❌ Hata: {str(e)}"

    @app.tool(description="Son N günün ihalelerini getirir.", annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_recent_tenders(days: int = 7, limit: int = 10) -> str:
        try:
            start_date = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")
            result = await ekap_client.search_tenders(search_text="", announcement_date_start=start_date, announcement_date_end=date.today().strftime("%Y-%m-%d"), order_by="ihaleTarihi", sort_order="desc", limit=limit)
            tenders = result.get("tenders", [])
            output = f"# Son {days} Gün İhaleleri\n\n"
            for t in tenders[:10]: output += f"- **{t.get('name', '-')}**\n"
            return output
        except Exception as e: return f"❌ Hata: {str(e)}"

    @app.tool(description="Resmi ilan arama (ilan.gov.tr).", annotations={"readOnlyHint": True, "openWorldHint": True})
    async def search_ilan_ads(search_text: str = "", max_result_count: int = 12) -> str:
        try:
            result = await ilan_client_inst.search_ads(search_text=search_text, max_result_count=max_result_count)
            ads = result.get("ads", result.get("ilanlar", []))
            output = f"# Resmi İlanlar\n\n**Toplam:** {result.get('total_count', 0)}\n\n"
            for ad in ads[:10]: output += f"- **{ad.get('title', ad.get('baslik', '-'))}**\n"
            return output
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("borsa"):
    @app.tool(description="BIST hisse verileri.", annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_bist_stock(symbol: str) -> str:
        try:
            return str(await borsa_client.get_bist_stock(symbol))[:4000]
        except Exception as e: return f"❌ Hata: {str(e)}"

    @app.tool(description="Döviz kurları.", annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_fx_rates() -> str:
        try:
            return str(await borsa_client.get_fx_rates())[:4000]
        except Exception as e: return f"❌ Hata: {str(e)}"

    @app.tool(description="Kripto para verileri.", annotations={"readOnlyHint": True, "openWorldHint": True})
    async def get_crypto(symbol: str) -> str:
        try:
            return str(await borsa_client.get_crypto(symbol))[:4000]
        except Exception as e: return f"❌ Hata: {str(e)}"

@app.tool(description="Tüm modüllerin sağlık durumu.", annotations={"readOnlyHint": True, "openWorldHint": False, "idempotentHint": True})
async def check_health() -> str:
    available = [k for k, v in MODULES_AVAILABLE.items() if v]
    unavailable = [k for k, v in MODULES_AVAILABLE.items() if not v]
    result = f"# Sağlık Kontrolü\n\n**Aktif ({len(available)}):**\n"
    for m in available: result += f"- ✅ {m}\n"
    if unavailable:
        result += f"\n**Devre Dışı ({len(unavailable)}):**\n"
        for m in unavailable: result += f"- ❌ {m}\n"
    return result


# ============================================================
# WEB DASHBOARD
# ============================================================

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🇹🇷 Türkiye MCP Server</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; line-height: 1.6; }
  .container { max-width: 1100px; margin: 0 auto; padding: 2rem 1rem; }
  header { text-align: center; padding: 3rem 0 2rem; border-bottom: 1px solid #1e293b; margin-bottom: 2rem; }
  header h1 { font-size: 2.5rem; margin-bottom: 0.5rem; }
  header h1 span { background: linear-gradient(135deg, #e11d48, #f59e0b); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  header p { color: #94a3b8; font-size: 1.1rem; }
  .badge { display: inline-block; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.8rem; font-weight: 600; margin: 0.25rem; }
  .badge-green { background: #064e3b; color: #34d399; }
  .badge-red { background: #450a0a; color: #f87171; }
  .badge-blue { background: #1e3a5f; color: #60a5fa; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }
  .card { background: #1e293b; border-radius: 12px; padding: 1.5rem; border: 1px solid #334155; }
  .card h2 { font-size: 1.2rem; margin-bottom: 0.75rem; display: flex; align-items: center; gap: 0.5rem; }
  .card ul { list-style: none; }
  .card li { padding: 0.35rem 0; padding-left: 1.5rem; position: relative; color: #cbd5e1; font-size: 0.9rem; }
  .card li::before { content: '→'; position: absolute; left: 0; color: #475569; }
  .code-block { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 1rem; margin: 1rem 0; font-family: 'Fira Code', Consolas, monospace; font-size: 0.85rem; overflow-x: auto; white-space: pre; color: #a5f3fc; }
  .status-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 0.5rem; margin: 1rem 0; }
  .status-item { padding: 0.5rem 0.75rem; border-radius: 8px; font-size: 0.85rem; font-weight: 500; }
  .status-ok { background: #064e3b; color: #34d399; }
  .status-fail { background: #450a0a; color: #f87171; }
  .section { margin-bottom: 2.5rem; }
  .section h2 { font-size: 1.5rem; margin-bottom: 1rem; color: #f1f5f9; border-bottom: 1px solid #334155; padding-bottom: 0.5rem; }
  .section h3 { font-size: 1.1rem; margin: 1rem 0 0.5rem; color: #93c5fd; }
  .section p { color: #94a3b8; margin-bottom: 0.75rem; }
  footer { text-align: center; padding: 2rem 0; border-top: 1px solid #1e293b; color: #64748b; font-size: 0.85rem; }
  a { color: #38bdf8; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .emoji { font-style: normal; }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1><span>🇹🇷 Türkiye MCP Server</span></h1>
    <p>Türkiye Hukuk, Mali, İhale ve Piyasa Verileri — Birleştirilmiş MCP Sunucusu</p>
    <div style="margin-top:1rem">
      <span class="badge badge-green">MCP Protocol</span>
      <span class="badge badge-blue">SSE Transport</span>
      <span class="badge badge-green">v1.0.0</span>
    </div>
  </header>

  <div class="section">
    <h2>📡 Bağlantı</h2>
    <div class="card">
      <h2>SSE Endpoint</h2>
      <div class="code-block" id="sse-url">Yükleniyor...</div>
      <h3>Claude Desktop</h3>
      <div class="code-block">{
  "mcpServers": {
    "turkiye": {
      "url": "<span id="sse-url-inline">...</span>/sse"
    }
  }
}</div>
      <h3>Claude Code (CLI)</h3>
      <div class="code-block">claude mcp add turkiye --transport sse <span id="sse-url-cli">...</span>/sse</div>
      <h3>Cursor / VS Code</h3>
      <div class="code-block">{
  "mcp": {
    "servers": {
      "turkiye": {
        "url": "<span id="sse-url-cursor">...</span>/sse"
      }
    }
  }
}</div>
    </div>
  </div>

  <div class="section">
    <h2>🩺 Modül Durumu</h2>
    <div class="status-grid" id="status-grid">Yükleniyor...</div>
  </div>

  <div class="grid">
    <div class="card">
      <h2>⚖️ Yargı (Hukuk)</h2>
      <ul>
        <li>search_bedesten_unified — Birden fazla mahkeme arama</li>
        <li>get_bedesten_document — Karar metni getirme</li>
        <li>search_anayasa_unified — Anayasa Mahkemesi</li>
        <li>search_kik_v2_decisions — KİK kararları</li>
        <li>search_rekabet_kurumu — Rekabet Kurumu</li>
        <li>search_sayistay_unified — Sayıştay</li>
        <li>search_kvkk_decisions — KVKK</li>
        <li>search_bddk_decisions — BDDK</li>
        <li>search_sigorta_tahkim — Sigorta Tahkim</li>
        <li>search_uyusmazlik — Uyuşmazlık Mahkemesi</li>
        <li>search_emsal — EMSAL (UYAP Örnek)</li>
      </ul>
    </div>

    <div class="card">
      <h2>💰 Mali Müşavir</h2>
      <ul>
        <li>search_resmi_gazete — Resmi Gazete arama</li>
        <li>get_daily_bulletin — Günlük bülten</li>
        <li>get_recent_mali_changes — Son mali değişiklikler</li>
        <li>search_gib_sirkuler — GİB sirküler arama</li>
        <li>get_tax_calendar — Vergi takvimi</li>
        <li>check_efatura_taxpayer — e-Fatura sorgulama</li>
        <li>get_asgari_ucret — Asgari ücret</li>
        <li>get_prim_matrahi — SGK prim oranları</li>
        <li>get_turmob_pratik_bilgiler — TÜRMOB bilgileri</li>
        <li>get_ismmmo_pratik_bilgiler — İSMMMO bilgileri</li>
      </ul>
    </div>

    <div class="card">
      <h2>🏗️ İhale</h2>
      <ul>
        <li>search_tenders — Kamu ihale arama (EKAP v2)</li>
        <li>get_recent_tenders — Son ihaleler</li>
        <li>search_ilan_ads — Resmi ilan arama</li>
      </ul>
    </div>

    <div class="card">
      <h2>📈 Borsa</h2>
      <ul>
        <li>get_bist_stock — BIST hisse verileri</li>
        <li>get_fx_rates — Döviz kurları</li>
        <li>get_crypto — Kripto para verileri</li>
      </ul>
    </div>
  </div>

  <div class="section">
    <h2>📖 Kullanım Kılavuzu</h2>
    <div class="card">
      <h3>Örnek Sorgular (Claude ile)</h3>
      <div class="code-block">"2025 asgari ücret ne kadar?"
"Yargıtay 'mülkiyet hakkı' kararlarını ara"
"Son 7 günde yayımlanan mali belgeler"
"Ankara'daki aktif ihaleler"
"BIST THYAO hisse verisi"
"GİB vergi sirküleri 'KDV' ara"
"e-Fatura 1234567890 mükellef mi?"
"KİK uyuşmazlık kararlarını listele"
"Bugünkü döviz kurları"</div>
      <h3>Bedesten Mahkeme Türleri</h3>
      <div class="code-block">YARGITAYKARARI    — Yargıtay (Temyiz)
DANISTAYKARAR    — Danıştay (İdari)
YERELHUKUK       — Yerel Hukuk Mahkemeleri
ISTINAFHUKUK     — İstinaf Mahkemeleri
KYB              — Kanun Yararına Bozma</div>
      <h3>İhale Türleri</h3>
      <div class="code-block">1 = Mal (Goods/Hizmet)
2 = Yapım (Construction)
3 = Hizmet (Service)
4 = Danışmanlık (Consultancy)</div>
    </div>
  </div>

  <div class="section">
    <h2>🔗 Kaynaklar</h2>
    <div class="card">
      <ul style="list-style:none; padding:0;">
        <li style="margin-bottom:0.5rem">📦 <a href="https://github.com/ayzekhdawy/turkiye-mcp">GitHub Repository</a></li>
        <li style="margin-bottom:0.5rem">⚖️ <a href="https://github.com/saidsurucu/yargi-mcp">yargi-mcp</a> — Türk hukuk veritabanları</li>
        <li style="margin-bottom:0.5rem">📋 <a href="https://github.com/saidsurucu/mevzuat-mcp">mevzuat-mcp</a> — Mevzuat Bilgi Sistemi</li>
        <li style="margin-bottom:0.5rem">🏗️ <a href="https://github.com/saidsurucu/ihale-mcp">ihale-mcp</a> — Kamu ihale arama</li>
        <li style="margin-bottom:0.5rem">📈 <a href="https://github.com/saidsurucu/borsa-mcp">borsa-mcp</a> — Borsa verileri</li>
        <li style="margin-bottom:0.5rem">💰 <a href="https://github.com/ayzekhdawy/musavir-mcp">musavir-mcp</a> — Mali müşavir araçları</li>
      </ul>
    </div>
  </div>

  <div class="section">
    <h2>💬 Soru Sor (AI Asistan)</h2>
    <div class="card" id="chat-section">
      <p style="color:#94a3b8;margin-bottom:1rem;">Türk hukuk, mali, ihale ve piyasa verileri hakkında soru sorun. MCP araçları ile veri toplanır, OpenRouter AI ile yanıtlanır.</p>
      <div id="chat-messages" style="max-height:400px;overflow-y:auto;margin-bottom:1rem;padding:0.5rem;background:#0f172a;border-radius:8px;min-height:100px;"></div>
      <div style="display:flex;gap:0.5rem;">
        <input type="text" id="chat-input" placeholder='Örnek: "2025 asgari ücret ne kadar?" veya "Yargıtay mülkiyet kararları"' style="flex:1;padding:0.75rem;border-radius:8px;border:1px solid #334155;background:#1e293b;color:#e2e8f0;font-size:0.95rem;" maxlength="500" />
        <button id="chat-btn" onclick="sendChat()" style="padding:0.75rem 1.5rem;border-radius:8px;border:none;background:linear-gradient(135deg,#e11d48,#f59e0b);color:#fff;font-weight:600;cursor:pointer;font-size:0.95rem;">Gönder</button>
      </div>
      <div id="chat-limit" style="margin-top:0.5rem;font-size:0.8rem;color:#64748b;"></div>
    </div>
  </div>

  <footer>
    <p>🇹🇷 Türkiye MCP Server v1.0.0 — <a href="https://github.com/ayzekhdawy/turkiye-mcp">GitHub</a></p>
  </footer>
</div>

<script>
const base = window.location.origin;
document.getElementById('sse-url').textContent = base + '/sse';
document.getElementById('sse-url-inline').textContent = base;
document.getElementById('sse-url-cli').textContent = base;
document.getElementById('sse-url-cursor').textContent = base;

// Module status
(async function() {
  try {
    const res = await fetch('/health');
    const data = await res.json();
    const grid = document.getElementById('status-grid');
    grid.innerHTML = '';
    if (data.modules) {
      for (const [name, ok] of Object.entries(data.modules)) {
        const div = document.createElement('div');
        div.className = 'status-item ' + (ok ? 'status-ok' : 'status-fail');
        div.textContent = (ok ? '✅ ' : '❌ ') + name;
        grid.appendChild(div);
      }
    }
  } catch(e) {
    document.getElementById('status-grid').innerHTML = '<div class="status-fail">Sunucu durumu alınamadı</div>';
  }
})();

// Chat
let chatRemaining = null;
const chatInput = document.getElementById('chat-input');
const chatBtn = document.getElementById('chat-btn');
const chatMessages = document.getElementById('chat-messages');
const chatLimit = document.getElementById('chat-limit');

function addMsg(role, text) {
  const div = document.createElement('div');
  div.style.cssText = 'margin:0.5rem 0;padding:0.75rem;border-radius:8px;white-space:pre-wrap;font-size:0.9rem;max-width:90%;' + (role==='user' ? 'background:#1e3a5f;margin-left:auto;text-align:right;' : 'background:#1a2744;margin-right:auto;');
  div.textContent = text;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function sendChat() {
  const msg = chatInput.value.trim();
  if (!msg) return;
  chatInput.value = '';
  addMsg('user', msg);
  chatBtn.disabled = true;
  chatBtn.textContent = '...';
  addMsg('system', '⏳ Veriler alınıyor...');
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({message: msg})
    });
    const data = await res.json();
    chatMessages.lastChild.remove(); // remove loading
    if (data.error) {
      addMsg('assistant', '❌ ' + data.error);
    } else {
      addMsg('assistant', data.response);
    }
    chatRemaining = data.remaining;
    chatLimit.textContent = data.remaining !== undefined ? `Kalan istek hakkı: ${data.remaining}/${10}` : '';
  } catch(e) {
    chatMessages.lastChild.remove();
    addMsg('assistant', '❌ Bağlantı hatası.');
  }
  chatBtn.disabled = false;
  chatBtn.textContent = 'Gönder';
}

chatInput.addEventListener('keydown', function(e) {
  if (e.key === 'Enter') sendChat();
});
</script>
</body>
</html>"""


async def homepage(request):
    return HTMLResponse(DASHBOARD_HTML)


async def health_endpoint(request):
    return JSONResponse({
        "status": "ok",
        "version": "1.0.0",
        "modules": MODULES_AVAILABLE,
        "active_count": sum(1 for v in MODULES_AVAILABLE.values() if v),
        "total_count": len(MODULES_AVAILABLE),
        "date": date.today().isoformat(),
    })


# ============================================================
# CHAT ENDPOINT — OpenRouter + MCP araçları
# ============================================================

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
CHAT_MODEL = "openai/gpt-4o-mini"
RATE_LIMIT_PER_IP = 10  # IP başına günlük istek limiti
ip_rate_limits: dict[str, list[float]] = defaultdict(list)

SYSTEM_PROMPT = """Sen Türkiye MCP asistanısın. Türk hukuk, mali, ihale ve piyasa verileri konusunda uzmansın.
Kullanıcıya Türkçe yanıt ver. Eldeki MCP araç sonuçlarını kullanarak doğru ve özlü cevaplar ver.
Eğer araç sonucu yoksa genel bilgilendirme yap ama "veriyi şimdi kontrol edemiyorum" diye belirt.
Sonuçları tablo veya liste halinde düzenle. Kaynağı belirt."""

TOOL_ROUTING = {
    # Hukuk — uzun eşleşmeler önce (öncelik sırası önemli)
    "yargıtay": "search_bedesten_unified", "yargitay": "search_bedesten_unified",
    "danıştay": "search_bedesten_unified", "danistay": "search_bedesten_unified",
    "anayasa mahkemesi": "search_anayasa_unified", "anayasa": "search_anayasa_unified",
    "kik kararı": "search_kik_v2_decisions", "kik": "search_kik_v2_decisions",
    "rekabet kurumu": "search_rekabet_kurumu", "rekabet": "search_rekabet_kurumu",
    "sayıştay": "search_sayistay_unified", "sayistay": "search_sayistay_unified",
    "bddk": "search_bddk_decisions", "bankacılık": "search_bddk_decisions",
    "kvkk": "search_kvkk_decisions", "kişisel veri": "search_kvkk_decisions",
    "sigorta tahkim": "search_sigorta_tahkim",
    "uyuşmazlık": "search_uyusmazlik", "uyusmazlik": "search_uyusmazlik",
    "emsal karar": "search_emsal", "emsal": "search_emsal",
    "mahkeme": "search_bedesten_unified", "hukuk": "search_bedesten_unified",
    "dava": "search_bedesten_unified", "ictihat": "search_bedesten_unified",
    # Mali
    "asgari ücret": "get_asgari_ucret", "asgari": "get_asgari_ucret",
    "prim": "get_prim_matrahi", "sgk prim": "get_prim_matrahi",
    "resmi gazete": "search_resmi_gazete", "mevzuat": "search_resmi_gazete",
    "genelge": "search_resmi_gazete",
    "sirküler": "search_gib_sirkuler", "vergi": "search_gib_sirkuler",
    "gib": "search_gib_sirkuler", "kdv": "search_gib_sirkuler",
    "e-fatura": "check_efatura_taxpayer", "mükellef": "check_efatura_taxpayer",
    # İhale
    "ihale": "search_tenders", "kamu ihale": "search_tenders",
    "ilan": "search_ilan_ads", "resmi ilan": "search_ilan_ads",
    # Borsa
    "borsa": "get_bist_stock", "hisse": "get_bist_stock", "döviz": "get_fx_rates",
    "kripto": "get_crypto", "bitcoin": "get_crypto",
    # Genel (en düşük öncelik)
    "kanun": "search_resmi_gazete", "karar": "search_bedesten_unified",
}


async def _call_tool(tool_name: str, **kwargs) -> str:
    """MCP araç fonksiyonunu doğrudan çağır."""
    import asyncio
    try:
        # Global değişkenlerden araç fonksiyonunu bul
        func = globals().get(tool_name)
        if func and callable(func):
            return await func(**kwargs)
    except Exception as e:
        return f"[Hata: {e}]"
    return "[Araç bulunamadı]"


async def _route_and_call(message: str) -> str:
    """Kullanıcı mesajına göre ilgili MCP araçlarını çağır."""
    msg_lower = message.lower()
    results = []
    called = set()

    # Arama terimini çıkar — eşleşen keyword'ü mesajdan çıkar
    def extract_search_term(msg, kw):
        """Keyword'ü mesajdan çıkarıp arama terimini döndür."""
        term = msg.lower().replace(kw, "").strip()
        # Stopword'leri temizle
        for sw in ["hakkı", "hakki", "kanunu", "kanun", "kararları", "kararlari", "kararı", "karari",
                    "arasında", "arasında", "hakkında", "hakkinda", "ile", "ve", "için", "icin",
                    "nedir", "ne kadar", "kaç", "kac", "bul", "ara", "getir", "göster", "goster",
                    "bak", "söyle", "soyle", "listele", "son", "güncel", "guncel"]:
            term = term.replace(sw, "").strip()
        return term[:80] if term else kw

    for keyword, tool_name in TOOL_ROUTING.items():
        if keyword in msg_lower and tool_name not in called:
            called.add(tool_name)
            search_term = extract_search_term(message, keyword)
            try:
                if tool_name == "get_asgari_ucret":
                    r = await _call_tool(tool_name, yil=2025)
                elif tool_name == "get_prim_matrahi":
                    r = await _call_tool(tool_name, yil=2025)
                elif tool_name == "get_fx_rates":
                    r = await _call_tool(tool_name)
                elif tool_name == "search_bedesten_unified":
                    r = await _call_tool(tool_name, keyword=search_term or keyword, court_types=["YARGITAYKARARI", "DANISTAYKARAR"], page_number=1)
                elif tool_name == "search_anayasa_unified":
                    r = await _call_tool(tool_name, keywords=message[:100], decision_type="bireysel_basvuru", page=1)
                elif tool_name in ("search_gib_sirkuler",):
                    r = await _call_tool(tool_name, anahtar_kelime=message[:60])
                elif tool_name in ("search_resmi_gazete",):
                    r = await _call_tool(tool_name, anahtar_kelime=message[:60])
                elif tool_name in ("search_tenders",):
                    r = await _call_tool(tool_name, search_text=message[:60])
                elif tool_name in ("search_ilan_ads",):
                    r = await _call_tool(tool_name, search_text=message[:60])
                elif tool_name in ("get_bist_stock",):
                    # Hisse sembolünü çıkarmaya çalış
                    words = message.upper().split()
                    symbol = next((w for w in words if w.isalpha() and len(w) <= 5 and w in
                        ["THYAO","GARAN","AKBNK","ISCTR","SAHOL","EREGL","FROTO","TUPRS",
                         "KCHOL","ASELS","ENKAI","BIMAS","PGSUS","TKFEN","YKBNK","CCOLA"]), None)
                    if symbol:
                        r = await _call_tool(tool_name, symbol=symbol)
                    else:
                        r = "[Hisse sembolü bulunamadı. Örnek: THYAO, GARAN, AKBNK]"
                elif tool_name in ("get_crypto",):
                    words = message.upper().split()
                    symbol = next((w for w in words if w in ["BTC","ETH","USDT","BNB","XRP","DOGE","SOL"]), None) or "BTC"
                    r = await _call_tool(tool_name, symbol=symbol)
                elif tool_name == "check_efatura_taxpayer":
                    import re
                    nums = re.findall(r'\b\d{10,11}\b', message)
                    if nums:
                        r = await _call_tool(tool_name, vergi_kimlik_no=nums[0])
                    else:
                        r = "[VKN/TCKN bulunamadı. 10 veya 11 haneli numara girin.]"
                elif tool_name in ("search_kik_v2_decisions",):
                    r = await _call_tool(tool_name, decision_type="uyusmazlik", keyword=message[:60])
                elif tool_name in ("search_rekabet_kurumu",):
                    r = await _call_tool(tool_name, keyword=message[:60])
                elif tool_name in ("search_sayistay_unified",):
                    r = await _call_tool(tool_name, decision_type="genel_kurul", keyword=message[:60])
                elif tool_name in ("search_bddk_decisions", "search_kvkk_decisions", "search_sigorta_tahkim"):
                    r = await _call_tool(tool_name, keyword=message[:60])
                elif tool_name in ("search_uyusmazlik",):
                    r = await _call_tool(tool_name, keyword=message[:60])
                elif tool_name in ("search_emsal",):
                    r = await _call_tool(tool_name, keyword=message[:60])
                else:
                    continue
                results.append(f"### {tool_name}\n{r}\n")
            except Exception as e:
                results.append(f"### {tool_name}\n[Hata: {e}]\n")

    return "\n---\n".join(results) if results else "", called


async def chat_endpoint(request):
    """Chat endpoint — OpenRouter + MCP araçları ile yanıt üretir."""
    if not OPENROUTER_API_KEY:
        return JSONResponse({"error": "Chat özelliği yapılandırılmamış. OPENROUTER_API_KEY ortam değişkeni gerekli."}, status_code=503)

    # IP rate limiting
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    day_ago = now - 86400
    ip_rate_limits[client_ip] = [t for t in ip_rate_limits[client_ip] if t > day_ago]
    if len(ip_rate_limits[client_ip]) >= RATE_LIMIT_PER_IP:
        return JSONResponse({"error": f"Günlük limit aşıldı ({RATE_LIMIT_PER_IP} istek/IP). Yarın tekrar deneyin.", "remaining": 0}, status_code=429)
    ip_rate_limits[client_ip].append(now)

    try:
        body = await request.json()
        message = body.get("message", "").strip()[:500]
        if not message:
            return JSONResponse({"error": "Mesaj boş olamaz."}, status_code=400)
    except Exception:
        return JSONResponse({"error": "Geçersiz istek."}, status_code=400)

    # MCP araçlarını çağır
    tool_context, called_tools = await _route_and_call(message)

    # OpenRouter'a gönder
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if tool_context:
        messages.append({"role": "system", "content": f"MCP araç sonuçları:\n\n{tool_context}"})
    messages.append({"role": "user", "content": message})

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                OPENROUTER_API_URL,
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json",
                          "HTTP-Referer": "https://turkiye-mcp.up.railway.app"},
                json={"model": CHAT_MODEL, "messages": messages, "max_tokens": 1024},
            )
            resp.raise_for_status()
            data = resp.json()
            reply = data.get("choices", [{}])[0].get("message", {}).get("content", "Yanıt alınamadı.")
            sources = list(called_tools)[:5]
    except httpx.HTTPStatusError as e:
        return JSONResponse({"error": f"LLM hatası: {e.response.status_code}", "remaining": RATE_LIMIT_PER_IP - len(ip_rate_limits[client_ip])}, status_code=502)
    except Exception as e:
        return JSONResponse({"error": f"Beklenmeyen hata: {str(e)}"}, status_code=500)

    remaining = RATE_LIMIT_PER_IP - len(ip_rate_limits[client_ip])
    return JSONResponse({"response": reply, "sources": sources[:5], "remaining": remaining})


# ============================================================
# ASGI APPLICATION
# ============================================================

# Get FastMCP's ASGI app via http_app(transport="sse")
# http_app() supports transport="http" | "streamable-http" | "sse"
mcp_asgi = app.http_app(transport="sse")

# Build Starlette app with dashboard + MCP mount
# IMPORTANT: pass mcp_asgi.lifespan so FastMCP session manager starts properly
starlette_app = Starlette(
    middleware=[
        Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]),
    ],
    routes=[
        Route("/", homepage),
        Route("/health", health_endpoint),
        Route("/api/chat", chat_endpoint, methods=["POST"]),
        Mount("/", app=mcp_asgi),
    ],
    lifespan=mcp_asgi.lifespan if hasattr(mcp_asgi, 'lifespan') else None,
)


def main():
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    logger.info(f"🇹🇷 Türkiye MCP Server başlatılıyor... Host: {host}, Port: {port}")
    available = sum(1 for v in MODULES_AVAILABLE.values() if v)
    logger.info(f"Modüller: {available}/{len(MODULES_AVAILABLE)} aktif")
    uvicorn.run(starlette_app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()