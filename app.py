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
import re
import tempfile
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

# --- UYAP EYP/UDF MODÜLÜ ---
try:
    from uyap_module.parser import UyapParser
    uyap_parser = UyapParser()
    MODULES_AVAILABLE["uyap"] = True
except Exception as e:
    logger.warning(f"❌ UYAP: {e}")
    MODULES_AVAILABLE["uyap"] = False

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

DASHBOARD_HTML = """<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Türkiye MCP</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,600;12..96,700&family=Be+Vietnam+Pro:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#0b0d10;--titlebar:#08090b;--s1:#121519;--s2:#181c22;--s3:#1f242b;
  --border:rgba(255,255,255,.07);--border-strong:rgba(255,255,255,.12);
  --text:#e8eaed;--dim:#9aa1aa;--faint:#6b727b;
  --accent:#e23b4e;--accent-hi:#f04458;--accent-soft:rgba(226,59,78,.12);
  --green:#2fbf71;--amber:#e0a92e;--red:#e23b4e;
  --radius:14px;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{background:var(--bg);color:var(--text);font-family:"Be Vietnam Pro",system-ui,sans-serif;font-size:14px;-webkit-font-smoothing:antialiased;overflow:hidden}
.display{font-family:"Bricolage Grotesque",system-ui,sans-serif;letter-spacing:-.01em}

/* ---- title bar ---- */
.titlebar{height:38px;background:var(--titlebar);display:flex;align-items:center;justify-content:space-between;padding:0 6px 0 14px;-webkit-app-region:drag;user-select:none;border-bottom:1px solid var(--border)}
.titlebar .tb-left{display:flex;align-items:center;gap:9px;color:var(--faint);font-size:12px;font-weight:500}
.tb-flag{width:17px;height:12px;border-radius:2px;background:var(--accent);position:relative;flex:0 0 auto}
.tb-flag::after{content:"";position:absolute;inset:0;background:radial-gradient(circle at 38% 50%,#fff 1.9px,transparent 2px),radial-gradient(circle at 46% 50%,var(--accent) 1.5px,transparent 1.6px);opacity:.92}
.tb-controls{display:flex;-webkit-app-region:no-drag}
.tb-btn{width:42px;height:30px;display:grid;place-items:center;border:none;background:transparent;color:var(--dim);cursor:pointer;border-radius:6px}
.tb-btn:hover{background:var(--s2);color:var(--text)}
.tb-btn.close:hover{background:var(--accent);color:#fff}

/* ---- shell ---- */
.shell{display:flex;height:calc(100vh - 38px)}

/* ---- sidebar ---- */
.sidebar{width:264px;flex:0 0 264px;background:var(--s1);border-right:1px solid var(--border);display:flex;flex-direction:column;padding:16px 14px;gap:16px}
.brand{display:flex;align-items:center;gap:11px;padding:2px 4px}
.brand-mark{width:34px;height:34px;border-radius:10px;background:linear-gradient(150deg,var(--accent),#a02233);display:grid;place-items:center;font-family:"Bricolage Grotesque";font-weight:700;color:#fff;font-size:14px;box-shadow:0 4px 14px rgba(226,59,78,.25)}
.brand-name{font-family:"Bricolage Grotesque";font-weight:600;font-size:16px}
.brand-sub{font-size:11px;color:var(--faint);margin-top:1px}

.new-chat{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;padding:11px;border-radius:11px;border:1px solid var(--border-strong);background:var(--s2);color:var(--text);font-family:inherit;font-size:13.5px;font-weight:600;cursor:pointer;transition:.15s}
.new-chat:hover{background:var(--s3);border-color:rgba(255,255,255,.18)}
.new-chat svg{width:16px;height:16px}

.sb-label{font-size:11px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--faint);padding:0 4px;margin-bottom:8px}
.chats{display:flex;flex-direction:column;gap:2px;overflow-y:auto;flex:0 1 auto}
.chat-item{display:flex;align-items:center;gap:9px;padding:9px 10px;border-radius:9px;color:var(--dim);cursor:pointer;font-size:13px;transition:.12s}
.chat-item:hover{background:var(--s2);color:var(--text)}
.chat-item.active{background:var(--s2);color:var(--text)}
.chat-item .dot{width:5px;height:5px;border-radius:50%;background:var(--faint);flex:0 0 auto}
.chat-item span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.chat-item .del-btn{opacity:0;margin-left:auto;cursor:pointer;font-size:11px;color:var(--faint)}
.chat-item:hover .del-btn{opacity:.7}
.chat-item:hover .del-btn:hover{opacity:1;color:var(--accent)}

.modules{margin-top:auto}
.mod{display:flex;align-items:center;justify-content:space-between;padding:8px 10px;border-radius:9px;cursor:default;font-size:12.5px}
.mod:hover{background:var(--s2)}
.mod-left{display:flex;align-items:center;gap:9px;color:var(--dim)}
.mod .sdot{width:6px;height:6px;border-radius:50%;background:var(--green);box-shadow:0 0 0 3px rgba(47,191,113,.13)}
.mod .sdot.off{background:var(--red);box-shadow:0 0 0 3px rgba(226,59,78,.13)}
.mod-count{font-size:11px;color:var(--faint);font-variant-numeric:tabular-nums}

/* ---- main ---- */
.main{flex:1;display:flex;flex-direction:column;min-width:0;background:radial-gradient(900px 500px at 70% -10%,rgba(226,59,78,.05),transparent 60%),var(--bg)}

.topbar{height:54px;flex:0 0 54px;display:flex;align-items:center;justify-content:space-between;padding:0 20px;border-bottom:1px solid var(--border)}
.status{display:flex;align-items:center;gap:8px;font-size:12.5px;color:var(--dim)}
.status .sdot{width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 0 3px rgba(47,191,113,.15)}
.status.off .sdot{background:var(--amber);box-shadow:0 0 0 3px rgba(224,169,46,.15)}
.topbar-right{display:flex;align-items:center;gap:8px}
.model-chip{display:flex;align-items:center;gap:8px;padding:7px 12px;border-radius:9px;background:var(--s2);border:1px solid var(--border);font-size:12.5px;color:var(--dim);cursor:pointer;transition:.12s}
.model-chip:hover{border-color:var(--border-strong);color:var(--text)}
.model-chip.warn{color:var(--accent);border-color:rgba(226,59,78,.35);background:var(--accent-soft)}
.model-chip svg{width:14px;height:14px;opacity:.8}
.icon-btn{width:36px;height:36px;border-radius:9px;border:1px solid var(--border);background:var(--s2);color:var(--dim);display:grid;place-items:center;cursor:pointer;transition:.12s}
.icon-btn:hover{color:var(--text);border-color:var(--border-strong)}
.icon-btn svg{width:17px;height:17px}

/* ---- chat area ---- */
.canvas{flex:1;overflow-y:auto;display:flex;flex-direction:column;padding:20px 24px}
.canvas::-webkit-scrollbar{width:6px}
.canvas::-webkit-scrollbar-thumb{background:var(--s3);border-radius:6px}

.hero{width:100%;max-width:680px;text-align:center;margin:auto;animation:rise .5s cubic-bezier(.2,.7,.2,1) both}
.hero h1{font-family:"Bricolage Grotesque";font-weight:700;font-size:33px;line-height:1.1}
.hero h1 .ac{color:var(--accent)}
.hero p{color:var(--dim);font-size:14.5px;line-height:1.6;margin:14px auto 30px;max-width:520px}
.cards{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.card{text-align:left;padding:18px;border-radius:var(--radius);background:var(--s1);border:1px solid var(--border);cursor:pointer;transition:.16s;animation:rise .5s cubic-bezier(.2,.7,.2,1) both}
.card:nth-child(1){animation-delay:.05s}.card:nth-child(2){animation-delay:.1s}.card:nth-child(3){animation-delay:.15s}.card:nth-child(4){animation-delay:.2s}
.card:hover{transform:translateY(-2px);border-color:var(--border-strong);background:var(--s2)}
.card-ic{width:38px;height:38px;border-radius:10px;background:var(--s3);display:grid;place-items:center;margin-bottom:14px;color:var(--accent)}
.card-ic svg{width:19px;height:19px}
.card h3{font-family:"Bricolage Grotesque";font-weight:600;font-size:15px;margin-bottom:4px}
.card .desc{color:var(--faint);font-size:12.5px;line-height:1.5}

/* ---- messages ---- */
.messages{max-width:760px;width:100%;margin:0 auto}
.msg{margin-bottom:16px;display:flex;gap:10px;animation:rise .3s ease}
.msg.user{justify-content:flex-end}
.msg.assistant{justify-content:flex-start}
.msg-bubble{padding:12px 16px;border-radius:16px;font-size:14px;line-height:1.65;max-width:85%;word-wrap:break-word}
.msg.user .msg-bubble{background:var(--accent);color:#fff;border-radius:16px 16px 4px 16px}
.msg.assistant .msg-bubble{background:var(--s2);border:1px solid var(--border);border-radius:16px 16px 16px 4px}
.msg.system .msg-bubble{background:var(--s1);border:1px solid var(--border-strong);color:var(--amber);font-size:13px;text-align:center;margin:0 auto;border-radius:12px;max-width:60%}

.msg-content{white-space:normal}
.msg-content h2,.msg-content h3,.msg-content h4{margin:.5rem 0 .25rem;color:var(--text)}
.msg-content h2{font-size:1.1rem}.msg-content h3{font-size:1rem}.msg-content h4{font-size:.95rem}
.msg-content ul,.msg-content ol{padding-left:1.5rem;margin:.5rem 0}
.msg-content li{margin:.2rem 0}
.msg-content hr{border:none;border-top:1px solid var(--border);margin:.75rem 0}
.msg-content a{color:var(--accent-hi);text-decoration:underline}
.msg-content em{color:var(--accent-hi)}
.msg-content strong{color:var(--accent-hi)}
.md-table{width:100%;border-collapse:collapse;margin:.5rem 0;font-size:.85rem}
.md-table th{background:rgba(226,59,78,.2);color:var(--text);padding:.4rem .6rem;text-align:left;border:1px solid var(--border);font-weight:600}
.md-table td{padding:.35rem .6rem;border:1px solid var(--border);color:var(--dim)}
.md-table tr:hover td{background:var(--s3)}

.msg-actions{display:flex;gap:4px;margin-top:8px;opacity:.4;transition:opacity .2s}
.msg.assistant:hover .msg-actions{opacity:1}
.msg-actions button{background:var(--s1);border:1px solid var(--border);border-radius:6px;padding:3px 8px;cursor:pointer;font-size:12px;color:var(--dim);transition:all .15s}
.msg-actions button:hover{background:var(--s3);color:var(--text);border-color:var(--accent)}

.sources{display:flex;flex-wrap:wrap;gap:4px;margin-top:8px}
.source-tag{background:var(--accent-soft);color:var(--accent-hi);padding:2px 8px;border-radius:9999px;font-size:11px}

.typing-indicator{display:flex;gap:4px;padding:12px 16px}
.typing-indicator span{width:8px;height:8px;background:var(--faint);border-radius:50%;animation:blink 1.4s infinite both}
.typing-indicator span:nth-child(2){animation-delay:.2s}
.typing-indicator span:nth-child(3){animation-delay:.4s}
@keyframes blink{0%,80%,100%{opacity:.3}40%{opacity:1}}

/* ---- composer ---- */
.composer{padding:14px 20px 20px;display:flex;justify-content:center}
.composer-inner{width:100%;max-width:760px;display:flex;align-items:flex-end;gap:8px;background:var(--s1);border:1px solid var(--border-strong);border-radius:16px;padding:8px 8px 8px 12px;transition:.15s}
.composer-inner:focus-within{border-color:rgba(226,59,78,.45);box-shadow:0 0 0 4px var(--accent-soft)}
.attach{width:38px;height:38px;flex:0 0 auto;border-radius:10px;border:none;background:transparent;color:var(--faint);display:grid;place-items:center;cursor:pointer;transition:.12s}
.attach:hover{color:var(--text);background:var(--s2)}
.attach svg{width:18px;height:18px}
.composer textarea{flex:1;border:none;background:transparent;color:var(--text);font-family:inherit;font-size:14.5px;resize:none;outline:none;padding:9px 4px;max-height:140px;line-height:1.5}
.composer textarea::placeholder{color:var(--faint)}
.send{width:40px;height:40px;flex:0 0 auto;border-radius:11px;border:none;background:var(--accent);color:#fff;display:grid;place-items:center;cursor:pointer;transition:.15s}
.send:hover{background:var(--accent-hi)}
.send:disabled{opacity:.4;cursor:not-allowed}
.send svg{width:18px;height:18px}
.composer-hint{text-align:center;font-size:11px;color:var(--faint);margin-top:9px}

/* ---- file drop ---- */
.file-drop-overlay{display:none;position:fixed;inset:0;z-index:1000;background:rgba(226,59,78,.1);border:3px dashed var(--accent);backdrop-filter:blur(4px);justify-content:center;align-items:center;font-size:1.5rem;color:var(--accent)}
.file-drop-overlay.active{display:flex}

/* ---- settings modal ---- */
.overlay{position:fixed;inset:0;background:rgba(0,0,0,.55);backdrop-filter:blur(3px);display:none;align-items:center;justify-content:center;z-index:50}
.overlay.open{display:flex;animation:fade .2s both}
.modal{width:440px;max-width:92vw;background:var(--s1);border:1px solid var(--border-strong);border-radius:18px;padding:24px;animation:rise .25s cubic-bezier(.2,.7,.2,1) both}
.modal h2{font-family:"Bricolage Grotesque";font-weight:600;font-size:19px;margin-bottom:4px}
.modal .modal-sub{color:var(--faint);font-size:12.5px;margin-bottom:20px}
.field{margin-bottom:15px}
.field label{display:block;font-size:12px;font-weight:600;color:var(--dim);margin-bottom:7px}
.field select,.field input{width:100%;padding:11px 12px;border-radius:10px;background:var(--s2);border:1px solid var(--border);color:var(--text);font-family:inherit;font-size:13.5px;outline:none;transition:.12s}
.field select:focus,.field input:focus{border-color:rgba(226,59,78,.45);box-shadow:0 0 0 3px var(--accent-soft)}
.note{display:flex;gap:9px;align-items:flex-start;padding:11px 12px;border-radius:10px;background:var(--accent-soft);border:1px solid rgba(226,59,78,.2);font-size:12px;color:var(--dim);line-height:1.5;margin-bottom:20px}
.note svg{width:15px;height:15px;flex:0 0 auto;margin-top:1px;color:var(--accent)}
.modal-actions{display:flex;gap:10px;justify-content:flex-end}
.btn-ghost,.btn-primary{padding:10px 18px;border-radius:10px;font-family:inherit;font-size:13.5px;font-weight:600;cursor:pointer;border:1px solid transparent}
.btn-ghost{background:transparent;border-color:var(--border-strong);color:var(--dim)}
.btn-ghost:hover{color:var(--text)}
.btn-primary{background:var(--accent);color:#fff}
.btn-primary:hover{background:var(--accent-hi)}

@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
.chats::-webkit-scrollbar{width:4px}
.chats::-webkit-scrollbar-thumb{background:var(--s3);border-radius:4px}

@media(max-width:768px){
  .sidebar{width:60px;flex:0 0 60px;padding:12px 8px}
  .brand-name,.brand-sub,.sb-label,.chat-item span,.new-chat span,.mod-left span,.mod-count{display:none}
  .new-chat{padding:11px;border-radius:11px}
}
</style>
</head>
<body>

<!-- title bar -->
<div class="titlebar">
  <div class="tb-left"><span class="tb-flag"></span> Türkiye MCP</div>
  <div class="tb-controls">
    <button class="tb-btn" title="Küçült">&#8211;</button>
    <button class="tb-btn" title="Büyüt">&#9633;</button>
    <button class="tb-btn close" title="Kapat">&#10005;</button>
  </div>
</div>

<div class="shell">
  <!-- sidebar -->
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-mark">TR</div>
      <div>
        <div class="brand-name">Türkiye MCP</div>
        <div class="brand-sub">Yerel · veriler cihazınızda</div>
      </div>
    </div>

    <button class="new-chat" onclick="newChat()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
      Yeni Sohbet
    </button>

    <div>
      <div class="sb-label">Son Sohbetler</div>
      <div class="chats" id="chat-list"></div>
    </div>

    <div class="modules">
      <div class="sb-label">Modüller</div>
      <div id="module-list"></div>
    </div>
  </aside>

  <!-- main -->
  <main class="main">
    <div class="topbar">
      <div class="status" id="server-status"><span class="sdot"></span><span>Bağlanıyor...</span></div>
      <div class="topbar-right">
        <button class="model-chip warn" id="model-chip" onclick="openSettings()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.2 4.2l2.8 2.8M17 17l2.8 2.8M1 12h4M19 12h4M4.2 19.8 7 17M17 7l2.8-2.8"/></svg>
          <span id="model-chip-text">API anahtarı gerekli</span>
        </button>
        <button class="icon-btn" title="Ayarlar" onclick="openSettings()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        </button>
      </div>
    </div>

    <div class="canvas" id="chat-area">
      <!-- welcome screen shown when no active chat -->
      <div class="hero" id="welcome-screen">
        <h1 class="display">Türkiye MCP <span class="ac">Asistanı</span></h1>
        <p>Türk hukuk, mali, ihale ve piyasa verileri hakkında soru sorun. PDF veya EYP/UDF dosyası yükleyip detayları çektirebilirsiniz.</p>
        <div class="cards">
          <div class="card" onclick="fill('2025 asgari ücret brüt ve net olarak ne kadar?')">
            <div class="card-ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg></div>
            <h3>Asgari Ücret</h3>
            <div class="desc">2025 asgari ücret ve prim bilgisi</div>
          </div>
          <div class="card" onclick="fill('Yargıtay mülkiyet hakkı ile ilgili kararları ara')">
            <div class="card-ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 3v18M5 7h14M7 7l-3 7a4 4 0 0 0 6 0L7 7zM17 7l-3 7a4 4 0 0 0 6 0l-3-7zM7 21h10"/></svg></div>
            <h3>Yargıtay Kararları</h3>
            <div class="desc">Mülkiyet hakkı içtihatları</div>
          </div>
          <div class="card" onclick="fill('Ankara\\'daki aktif kamu ihalelerini listele')">
            <div class="card-ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 21h18M5 21V8l7-4 7 4v13M9 21v-6h6v6"/></svg></div>
            <h3>İhale Arama</h3>
            <div class="desc">Ankara'daki kamu ihaleleri</div>
          </div>
          <div class="card" onclick="document.getElementById('file-input').click()">
            <div class="card-ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M9 13h6M9 17h6"/></svg></div>
            <h3>Belge Yükle</h3>
            <div class="desc">PDF veya EYP/UDF dosyası</div>
          </div>
        </div>
      </div>
    </div>

    <!-- file drop overlay -->
    <div class="file-drop-overlay" id="file-drop-overlay">📄 Dosya yüklemek için bırakın</div>
    <input type="file" id="file-input" accept=".pdf,.eyp,.udf" style="display:none" onchange="handleFileUpload(this)">

    <!-- composer -->
    <div class="composer">
      <div style="width:100%;max-width:760px">
        <div class="composer-inner">
          <button class="attach" title="Dosya ekle" onclick="document.getElementById('file-input').click()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21.44 11.05 12.25 20.24a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg></button>
          <textarea id="chat-input" rows="1" placeholder="Soru sorun veya dosya yükleyin..." onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendMessage()}" oninput="autoResize(this)"></textarea>
          <button class="send" id="send-btn" onclick="sendMessage()" title="Gönder"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg></button>
        </div>
        <div class="composer-hint">Yanıtlar yapay zekâ tarafından üretilir; nihai karar için teyit edin.</div>
      </div>
    </div>
  </main>
</div>

<!-- settings modal -->
<div class="overlay" id="overlay">
  <div class="modal">
    <h2 class="display">Bağlantı Ayarları</h2>
    <div class="modal-sub">Sağlayıcınızı ve API anahtarınızı girin.</div>
    <div class="field">
      <label>Sağlayıcı</label>
      <select id="llm-provider" onchange="onProviderChange()">
        <option value="openrouter">OpenRouter</option>
        <option value="openai">OpenAI</option>
        <option value="anthropic">Anthropic</option>
        <option value="gemini">Google Gemini</option>
        <option value="ollama">Ollama (Yerel)</option>
      </select>
    </div>
    <div class="field">
      <label>Model</label>
      <select id="llm-model"></select>
    </div>
    <div class="field">
      <label>API Anahtarı</label>
      <input type="password" id="llm-api-key" placeholder="sk-..." />
    </div>
    <div class="note">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
      Anahtarınız yalnızca bu cihazda saklanır, hiçbir sunucuya gönderilmez.
    </div>
    <div class="modal-actions">
      <button class="btn-ghost" onclick="closeSettings()">Vazgeç</button>
      <button class="btn-primary" onclick="saveConfig()">Kaydet</button>
    </div>
  </div>
</div>

<script>
// ===== State =====
const PROVIDERS = {
  openrouter: { name: "OpenRouter", needs_key: true, models: ["openai/gpt-4o-mini","anthropic/claude-3.5-sonnet","google/gemini-2.0-flash","meta-llama/llama-3.1-8b-instruct"], default_model: "openai/gpt-4o-mini" },
  openai: { name: "OpenAI", needs_key: true, models: ["gpt-4o-mini","gpt-4o","gpt-4-turbo"], default_model: "gpt-4o-mini" },
  anthropic: { name: "Anthropic", needs_key: true, models: ["claude-sonnet-4-20250514","claude-haiku-4-20250414"], default_model: "claude-haiku-4-20250414" },
  gemini: { name: "Google Gemini", needs_key: true, models: ["gemini-2.0-flash","gemini-1.5-pro"], default_model: "gemini-2.0-flash" },
  ollama: { name: "Ollama (Yerel)", needs_key: false, models: ["llama3.2","llama3.1","mistral","qwen2.5","gemma2"], default_model: "llama3.2" },
};

let chats = JSON.parse(localStorage.getItem('turkiye_mcp_chats') || '[]');
let activeChatId = localStorage.getItem('turkiye_mcp_active_chat') || null;
let currentProvider = localStorage.getItem('llm-provider') || 'openrouter';
let currentModel = localStorage.getItem('llm-model') || '';
let savedApiKey = localStorage.getItem('llm-api-key') || '';
let isSending = false;

// ===== Server Status =====
async function checkServerStatus() {
  try {
    const res = await fetch('/health', {signal: AbortSignal.timeout(3000)});
    const data = await res.json();
    const el = document.getElementById('server-status');
    el.className = 'status';
    el.innerHTML = '<span class="sdot"></span><span>' + (data.active_count||'?') + '/' + (data.total_count||'?') + ' modül aktif</span>';
  } catch(e) {
    const el = document.getElementById('server-status');
    el.className = 'status off';
    el.innerHTML = '<span class="sdot"></span><span>Bağlantı hatası</span>';
  }
}
checkServerStatus();
setInterval(checkServerStatus, 30000);

// ===== Chat Management =====
function generateId() { return Date.now().toString(36) + Math.random().toString(36).substr(2, 5); }

function generateTitle(msg) {
  const lower = msg.toLowerCase();
  const titleMap = {
    'yargitay':'Yargıtay Kararları','danistay':'Danıştay Kararları',
    'anayasa':'Anayasa Mahkemesi','asgari':'Asgari Ücret','resmi gazete':'Resmi Gazete',
    'ihale':'İhale Arama','borsa':'Borsa Verileri','doviz':'Döviz Kurları',
    'emsal':'Emsal Kararlar','sgk':'SGK Sorgulama','iskur':'İŞKUR Duyuruları',
    'mevzuat':'Mevzuat Arama','gib':'GİB Sirküler','kvkk':'KVKK Kararları',
    'kik':'KİK Kararları','sayistay':'Sayıştay Kararları',
  };
  for (const [kw, title] of Object.entries(titleMap)) {
    if (lower.includes(kw)) return title;
  }
  return msg.length > 35 ? msg.substring(0, 35) + '...' : msg;
}

function getActiveChat() { return chats.find(c => c.id === activeChatId); }

function newChat() {
  const chat = { id: generateId(), title: 'Yeni Sohbet', messages: [], created: Date.now() };
  chats.unshift(chat);
  activeChatId = chat.id;
  saveChats();
  renderChatList();
  renderChat();
}

function saveChats() {
  localStorage.setItem('turkiye_mcp_chats', JSON.stringify(chats));
  localStorage.setItem('turkiye_mcp_active_chat', activeChatId || '');
}

function renderChatList() {
  const list = document.getElementById('chat-list');
  if (!list) return;
  if (chats.length === 0) {
    list.innerHTML = '<div style="text-align:center;color:var(--faint);font-size:12px;padding:1rem">Henüz sohbet yok</div>';
    return;
  }
  list.innerHTML = chats.map(c =>
    '<div class="chat-item' + (c.id === activeChatId ? ' active' : '') + '" onclick="selectChat(\'' + c.id + '\')">' +
    '<span class="dot"></span><span>' + escapeHtml(c.title) + '</span>' +
    '<span class="del-btn" onclick="event.stopPropagation();deleteChat(\'' + c.id + '\')">×</span></div>'
  ).join('');
}

function selectChat(id) { activeChatId = id; saveChats(); renderChatList(); renderChat(); }
function deleteChat(id) { chats = chats.filter(c => c.id !== id); if (activeChatId === id) activeChatId = null; saveChats(); renderChatList(); renderChat(); }

function renderChat() {
  const area = document.getElementById('chat-area');
  const welcome = document.getElementById('welcome-screen');
  const chat = getActiveChat();

  if (!chat || chat.messages.length === 0) {
    welcome.style.display = 'flex';
    area.querySelectorAll('.msg').forEach(el => el.remove());
    return;
  }

  welcome.style.display = 'none';
  area.querySelectorAll('.msg').forEach(el => el.remove());

  chat.messages.forEach(m => {
    const div = document.createElement('div');
    div.className = 'msg ' + m.role;
    if (m.role === 'assistant') {
      div.innerHTML = '<div class="msg-bubble"><div class="msg-content">' + renderMarkdown(m.text) + '</div>' +
        (m.sources ? renderSources(m.sources) : '') +
        '<div class="msg-actions"><button onclick="copyMessage(this)" title="Kopyala">📋</button><button onclick="exportWord(this)" title="Word\'e Aktar">📄</button></div></div>';
    } else {
      div.innerHTML = '<div class="msg-bubble">' + escapeHtml(m.text) + (m.sources ? renderSources(m.sources) : '') + '</div>';
    }
    area.appendChild(div);
  });
  area.scrollTop = area.scrollHeight;
}

function renderSources(sources) {
  if (!sources || sources.length === 0) return '';
  return '<div class="sources">' + sources.map(s => '<span class="source-tag">' + s + '</span>').join('') + '</div>';
}

function escapeHtml(text) {
  return text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ===== Markdown Render =====
function renderMarkdown(text) {
  if (!text) return '';
  let html = escapeHtml(text);
  html = html.replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>');
  html = html.replace(/\\*(.*?)\\*/g, '<em>$1</em>');
  html = html.replace(/^### (.*?)(?:\n|$)/gm, '<h4>$1</h4>');
  html = html.replace(/^## (.*?)(?:\n|$)/gm, '<h3>$1</h3>');
  html = html.replace(/^# (.*?)(?:\n|$)/gm, '<h2>$1</h2>');
  // Tables
  html = html.replace(/\n\|(.+)\|\n\|[-| :]+\|\n((?:\|.+\|\n?)+)/g, function(match, header, body) {
    const ths = header.split('|').map(s=>s.trim()).filter(Boolean).map(s=>'<th>'+s+'</th>').join('');
    const rows = body.trim().split('\n').map(row=>{
      const tds = row.split('|').map(s=>s.trim()).filter(Boolean).map(s=>'<td>'+s+'</td>').join('');
      return '<tr>'+tds+'</tr>';
    }).join('');
    return '<table class="md-table"><thead><tr>'+ths+'</tr></thead><tbody>'+rows+'</tbody></table>';
  });
  html = html.replace(/^- (.*?)(?:\n|$)/gm, '<li>$1</li>');
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');
  html = html.replace(/^\d+\. (.*?)(?:\n|$)/gm, '<li>$1</li>');
  html = html.replace(/^---$/gm, '<hr>');
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  html = html.replace(/\n/g, '<br>');
  html = html.replace(/(<\/h[234]>)<br>/g, '$1');
  html = html.replace(/(<\/table>)<br>/g, '$1');
  html = html.replace(/(<\/ul>)<br>/g, '$1');
  html = html.replace(/(<hr>)<br>/g, '$1');
  return html;
}

// ===== Copy & Export =====
function copyMessage(btn) {
  const bubble = btn.closest('.msg-bubble');
  const content = bubble.querySelector('.msg-content');
  const text = content ? content.innerText : bubble.innerText;
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = '✓';
    setTimeout(() => btn.textContent = '📋', 1500);
  });
}

function exportWord(btn) {
  const bubble = btn.closest('.msg-bubble');
  const content = bubble.querySelector('.msg-content');
  const htmlContent = content ? content.innerHTML : bubble.innerHTML;
  const chat = getActiveChat();
  const title = chat ? chat.title : 'TurkiyeMCP';
  const fullHtml = '<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40"><head><meta charset="utf-8"><title>' + escapeHtml(title) + '</title><style>body{font-family:"Segoe UI",Tahoma,sans-serif;font-size:11pt;color:#1a1a2e}table{border-collapse:collapse;width:100%;margin:8pt 0}th,td{border:1px solid #ccc;padding:4pt 8pt;font-size:10pt}th{background:#6366f1;color:#fff}h2{color:#6366f1}h3{color:#818cf8}h4{color:#a5b4fc}code{background:#f1f5f9;padding:1pt 3pt;border-radius:3pt;font-size:10pt}strong{color:#6366f1}em{color:#8b5cf6}</style></head><body>' + htmlContent + '</body></html>';
  const blob = new Blob(['﻿', fullHtml], {type: 'application/msword'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = title.replace(/[^a-zA-Z0-9À-ÿ]/g, '_') + '.doc';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  btn.textContent = '✓';
  setTimeout(() => btn.textContent = '📄', 1500);
}

// ===== Send Message =====
function fill(msg) { document.getElementById('chat-input').value = msg; document.getElementById('chat-input').focus(); autoResize(document.getElementById('chat-input')); }
function autoResize(el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 140) + 'px'; }

async function sendMessage() {
  const input = document.getElementById('chat-input');
  const msg = input.value.trim();
  if (!msg || isSending) return;
  input.value = '';
  autoResize(input);

  if (!activeChatId) newChat();
  let chat = getActiveChat();
  if (!chat) { newChat(); chat = getActiveChat(); }

  if (chat.messages.length === 0) {
    chat.title = generateTitle(msg);
    renderChatList();
  }

  chat.messages.push({ role: 'user', text: msg });
  renderChat();
  saveChats();

  isSending = true;
  document.getElementById('send-btn').disabled = true;
  const typingDiv = document.createElement('div');
  typingDiv.className = 'msg assistant';
  typingDiv.id = 'typing-indicator';
  typingDiv.innerHTML = '<div class="msg-bubble"><div class="typing-indicator"><span></span><span></span><span></span></div></div>';
  document.getElementById('chat-area').appendChild(typingDiv);
  document.getElementById('chat-area').scrollTop = document.getElementById('chat-area').scrollHeight;

  try {
    const provider = document.getElementById('llm-provider').value;
    const model = document.getElementById('llm-model').value;
    const apiKey = savedApiKey || localStorage.getItem('llm-api-key') || '';

    const headers = {'Content-Type': 'application/json'};
    if (apiKey && PROVIDERS[provider].needs_key) {
      headers['X-API-Key'] = apiKey;
      headers['X-LLM-Provider'] = provider;
      headers['X-LLM-Model'] = model;
    } else if (!PROVIDERS[provider].needs_key) {
      headers['X-LLM-Provider'] = provider;
      headers['X-LLM-Model'] = model;
    }

    const res = await fetch('/api/chat', { method: 'POST', headers, body: JSON.stringify({message: msg, provider, api_key: apiKey, model}) });
    const data = await res.json();

    const ti = document.getElementById('typing-indicator');
    if (ti) ti.remove();

    if (data.error) {
      chat.messages.push({ role: 'system', text: 'Hata: ' + data.error });
    } else {
      chat.messages.push({ role: 'assistant', text: data.response, sources: data.sources || [] });
    }
  } catch(e) {
    const ti = document.getElementById('typing-indicator');
    if (ti) ti.remove();
    chat.messages.push({ role: 'system', text: 'Bağlantı hatası.' });
  }

  isSending = false;
  document.getElementById('send-btn').disabled = false;
  renderChat();
  saveChats();
}

// ===== File Upload =====
function handleFileUpload(input) {
  const file = input.files[0];
  if (!file) return;
  const formData = new FormData();
  formData.append('file', file);
  const isPDF = file.name.toLowerCase().endsWith('.pdf');
  const endpoint = isPDF ? '/api/upload/pdf' : '/api/upload/uyap';

  fetch(endpoint, { method: 'POST', body: formData })
    .then(res => res.json())
    .then(data => {
      if (!activeChatId) newChat();
      const chat = getActiveChat();
      if (data.error) {
        chat.messages.push({ role: 'system', text: 'Dosya hatası: ' + data.error });
      } else {
        const text = isPDF ? (data.text || data.markdown || '').substring(0, 2000) : (data.markdown || '').substring(0, 2000);
        chat.messages.push({ role: 'system', text: '📄 Dosya yüklendi: ' + file.name + '\\n' + text });
        if (chat.messages.length === 1) { chat.title = file.name; renderChatList(); }
      }
      renderChat();
      saveChats();
    })
    .catch(e => {
      const chat = getActiveChat();
      if (chat) { chat.messages.push({ role: 'system', text: 'Dosya yükleme hatası.' }); renderChat(); }
    });
  input.value = '';
}

// Drag & drop
const mainArea = document.querySelector('.main');
mainArea.addEventListener('dragover', e => { e.preventDefault(); document.getElementById('file-drop-overlay').classList.add('active'); });
mainArea.addEventListener('dragleave', e => { e.preventDefault(); document.getElementById('file-drop-overlay').classList.remove('active'); });
mainArea.addEventListener('drop', e => {
  e.preventDefault();
  document.getElementById('file-drop-overlay').classList.remove('active');
  if (e.dataTransfer.files.length) {
    document.getElementById('file-input').files = e.dataTransfer.files;
    handleFileUpload(document.getElementById('file-input'));
  }
});

// ===== Settings =====
function openSettings() { document.getElementById('overlay').classList.add('open'); loadConfig(); }
function closeSettings() { document.getElementById('overlay').classList.remove('open'); }
function loadConfig() {
  const prov = document.getElementById('llm-provider');
  prov.value = currentProvider;
  onProviderChange();
  if (currentModel) document.getElementById('llm-model').value = currentModel;
  document.getElementById('llm-api-key').value = savedApiKey || '';
  updateModelChip();
}
async function saveConfig() {
  currentProvider = document.getElementById('llm-provider').value;
  currentModel = document.getElementById('llm-model').value;
  savedApiKey = document.getElementById('llm-api-key').value;
  localStorage.setItem('llm-provider', currentProvider);
  localStorage.setItem('llm-model', currentModel);
  localStorage.setItem('llm-api-key', savedApiKey);

  // Save to keyring if local
  const isLocal = document.getElementById('server-status')?.classList?.contains('off') === false;
  if (isLocal) {
    try {
      await fetch('/api/chat/configure', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({provider: currentProvider, api_key: savedApiKey, model: currentModel})
      });
    } catch(e) {}
  }
  updateModelChip();
  closeSettings();
}

function onProviderChange() {
  const prov = document.getElementById('llm-provider').value;
  const modelSel = document.getElementById('llm-model');
  const config = PROVIDERS[prov];
  modelSel.innerHTML = config.models.map(m => '<option value="' + m + '">' + m + '</option>').join('');
  if (!currentModel || !config.models.includes(currentModel)) {
    currentModel = config.default_model;
  }
  modelSel.value = currentModel;
}

function updateModelChip() {
  const chip = document.getElementById('model-chip');
  const chipText = document.getElementById('model-chip-text');
  const prov = PROVIDERS[currentProvider];
  const hasKey = !prov.needs_key || savedApiKey;
  chip.className = 'model-chip' + (hasKey ? '' : ' warn');
  chipText.textContent = hasKey ? (prov.name + ' · ' + (currentModel || prov.default_model)) : 'API anahtarı gerekli';
}

// ===== Modules =====
async function loadModules() {
  try {
    const res = await fetch('/health');
    const data = await res.json();
    const moduleList = document.getElementById('module-list');
    if (!moduleList || !data.modules) return;
    const groups = {
      'Hukuk': ['resmi_gazete','mevzuat','bedesten','anayasa','kik','rekabet','sayistay','kvkk','sigorta_tahkim','uyusmazlik','emsal','ihale'],
      'Mali': ['gib','ivd','sgk','iskur','turmob','ismmmo'],
      'İhale': ['ihale'],
      'Borsa': ['borsa'],
    };
    let html = '';
    for (const [label, keys] of Object.entries(groups)) {
      const active = keys.filter(k => data.modules[k]).length;
      html += '<div class="mod"><div class="mod-left"><span class="sdot' + (active > 0 ? '' : ' off') + '"></span> ' + label + '</div><span class="mod-count">' + active + '/' + keys.length + '</span></div>';
    }
    moduleList.innerHTML = html;
  } catch(e) {}
}
loadModules();

// ===== Init =====
renderChatList();
if (activeChatId) { selectChat(activeChatId); } else { renderChat(); }
loadConfig();
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


# --- UYAP EYP/UDF ARAÇLARI ---
if MODULES_AVAILABLE.get("uyap"):
    @app.tool(description="UYAP EYP/UDF belge dosyasini cozumler. Dosya yolu veya base64 encoded veri alir.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def parse_uyap_document(file_path: str = "", base64_data: str = "") -> str:
        """UYAP EYP/UDF belgesini parse eder.

        Args:
            file_path: EYP/UDF dosya yolu (yerel dosya)
            base64_data: EYP/UDF dosya icerigi (base64 encoded)
        """
        import base64
        try:
            if file_path:
                belge = uyap_parser.parse_eyp(file_path)
            elif base64_data:
                data = base64.b64decode(base64_data)
                belge = uyap_parser.parse_eyp(data)
            else:
                return "Hata: file_path veya base64_data gerekli."

            md = uyap_parser.to_markdown(belge)
            return md

        except Exception as e:
            return f"UYAP parse hatasi: {str(e)}"

    @app.tool(description="UYAP EYP/UDF belgesindeki taraflari listeler.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def get_uyap_parties(file_path: str = "", base64_data: str = "") -> str:
        """UYAP EYP/UDF belgesindeki taraflari (sanik, musteki, mudafii vb.) listeler.

        Args:
            file_path: EYP/UDF dosya yolu (yerel dosya)
            base64_data: EYP/UDF dosya icerigi (base64 encoded)
        """
        import base64
        try:
            if file_path:
                belge = uyap_parser.parse_eyp(file_path)
            elif base64_data:
                data = base64.b64decode(base64_data)
                belge = uyap_parser.parse_eyp(data)
            else:
                return "Hata: file_path veya base64_data gerekli."

            result = "# Taraflar\n\n"
            if belge.taraflar:
                for t in belge.taraflar:
                    rol = f" ({t.rol})" if t.rol else ""
                    result += f"- **{t.ad}**{rol} — TCKN: {t.tckn}\n"
            if belge.dagitim_taraflar:
                result += "\n## Dagıtım Listesi\n\n"
                for t in belge.dagitim_taraflar:
                    result += f"- **{t.ad}** — TCKN: {t.tckn}\n"

            if belge.dosya_bilgisi:
                db = belge.dosya_bilgisi
                result += f"\n## Dosya Bilgileri\n\n"
                result += f"- **Dosya No:** {db.dosya_no}\n"
                result += f"- **Dosya Türü:** {db.dosya_tur}\n"
                result += f"- **Birim:** {db.birim_adi}\n"

            return result if result.strip() != "# Taraflar" else "Taraflar bilgisi bulunamadi."

        except Exception as e:
            return f"UYAP parse hatasi: {str(e)}"

    @app.tool(description="UYAP EYP/UDF belgesindeki hukuki referans numaralarini tespit eder.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    async def get_uyap_references(file_path: str = "", base64_data: str = "") -> str:
        """UYAP EYP/UDF belgesindeki hukuki referans numaralarini (esas no, karar no, RG sayisi vb.) tespit eder.

        Args:
            file_path: EYP/UDF dosya yolu (yerel dosya)
            base64_data: EYP/UDF dosya icerigi (base64 encoded)
        """
        import base64
        try:
            if file_path:
                belge = uyap_parser.parse_eyp(file_path)
            elif base64_data:
                data = base64.b64decode(base64_data)
                belge = uyap_parser.parse_eyp(data)
            else:
                return "Hata: file_path veya base64_data gerekli."

            if not belge.referanslar:
                return "Hukuki referans bulunamadi."

            result = "# Tespit Edilen Referanslar\n\n"
            for ref in belge.referanslar:
                result += f"- **{ref['label']}:** {ref['value']} (arama: {ref['search_term']})\n"

            return result

        except Exception as e:
            return f"UYAP parse hatasi: {str(e)}"


# ============================================================
# CHAT ENDPOINT — BYOK LLM + MCP araçları
# ============================================================

# BYOK: Bring Your Own Key — kullanıcı kendi API anahtarını sağlar
# 1. Environment variable: OPENROUTER_API_KEY (geriye uyumluluk)
# 2. Request header: X-API-Key veya X-LLM-Provider + X-API-Key
# 3. keyring: Yerel EXE modunda Windows Credential Manager'da saklanır
# 4. Ollama: Yerel LLM (API key gerektirmez)

# Sağlayıcı yapılandırması
LLM_PROVIDERS = {
    "openrouter": {
        "name": "OpenRouter",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "models": ["openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet", "google/gemini-2.0-flash", "meta-llama/llama-3.1-8b-instruct"],
        "default_model": "openai/gpt-4o-mini",
        "needs_key": True,
    },
    "openai": {
        "name": "OpenAI",
        "url": "https://api.openai.com/v1/chat/completions",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"],
        "default_model": "gpt-4o-mini",
        "needs_key": True,
    },
    "anthropic": {
        "name": "Anthropic",
        "url": "https://api.anthropic.com/v1/messages",
        "models": ["claude-sonnet-4-20250514", "claude-haiku-4-20250414"],
        "default_model": "claude-haiku-4-20250414",
        "needs_key": True,
        "is_anthropic": True,  # Farklı API formatı
    },
    "gemini": {
        "name": "Google Gemini",
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "models": ["gemini-2.0-flash", "gemini-1.5-pro"],
        "default_model": "gemini-2.0-flash",
        "needs_key": True,
    },
    "ollama": {
        "name": "Ollama (Yerel)",
        "url": "http://localhost:11434/v1/chat/completions",
        "models": ["llama3.2", "llama3.1", "mistral", "qwen2.5", "gemma2"],
        "default_model": "llama3.2",
        "needs_key": False,
    },
}

# Geriye uyumluluk: OPENROUTER_API_KEY environment variable
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
RATE_LIMIT_PER_IP = 10  # IP başına günlük istek limiti
ip_rate_limits: dict[str, list[float]] = defaultdict(list)

SYSTEM_PROMPT = """Sen Türkiye MCP asistanısın. Türk hukuk, mali, ihale ve piyasa verileri konusunda uzmansın.

Kullanıcıya Türkçe yanıt ver. Eldeki MCP araç sonuçlarını kullanarak doğru ve özlü cevaplar ver.

YANIT FORMATI KURALLARI:
1. Her araç sonucunu açıklayıcı bir şekilde sun — raw tablo YERİNE:
   - Karar/kayıt için: Mahkeme/kurum adı, karar no, esas no, tarih, konu ÖZETİ
   - Her sonucun "ne anlama geldiğini" ve "hukuki sonuçlarını" açıkla
   - Kaynak belirt (hangi MCP aracı kullanıldı, hangi veri tabanı)
2. Sonuçları markdown formatında sun — tablo, liste, kalın yazı kullan
3. Hukuki terimleri açıkla (örn: "istinaf", "temyiz", "esas no" vb.)
4. İlgili mevzuat, yönetmelik ve kanun atıfları ekle
5. Sonuç yoksa genel bilgilendirme yap ama "veriyi şimdi kontrol edemiyorum" diye belirt
6. Her yanıtın sonunda 📋 Kaynak bölümü ekle — hangi araç/veri tabanı kullanıldığını belirt"""


def _get_llm_config(request) -> tuple[str, str, str]:
    """İstekten LLM yapılandırmasını al.

    Returns:
        (provider_id, api_key, model) tuple'ı
    """
    # 1. Header'dan provider ve key
    provider_id = request.headers.get("X-LLM-Provider", "").lower()
    api_key = request.headers.get("X-API-Key", "")
    model = request.headers.get("X-LLM-Model", "")

    # 2. keyring'den yerel key okuma (sadece yerel modda)
    is_local = os.environ.get("TURKIYE_MCP_LOCAL") == "1"
    if is_local and not api_key:
        try:
            import keyring
            stored_key = keyring.get_password("turkiye-mcp", "llm-api-key")
            stored_provider = keyring.get_password("turkiye-mcp", "llm-provider") or "openrouter"
            stored_model = keyring.get_password("turkiye-mcp", "llm-model") or ""
            if stored_key:
                api_key = stored_key
                if not provider_id:
                    provider_id = stored_provider
                if not model:
                    model = stored_model
        except Exception:
            pass

    # 3. Geriye uyumluluk: OPENROUTER_API_KEY environment variable
    if not api_key and OPENROUTER_API_KEY:
        api_key = OPENROUTER_API_KEY
        if not provider_id:
            provider_id = "openrouter"

    # Varsayılanlar
    if not provider_id:
        provider_id = "openrouter"

    # Provider geçerli mi?
    if provider_id not in LLM_PROVIDERS:
        provider_id = "openrouter"

    provider_config = LLM_PROVIDERS[provider_id]
    if not model:
        model = provider_config["default_model"]

    return provider_id, api_key, model

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


async def providers_endpoint(request):
    """Desteklenen LLM sağlayıcılarını listeler."""
    return JSONResponse({
        "providers": {k: {"name": v["name"], "needs_key": v["needs_key"], "models": v["models"], "default_model": v["default_model"]} for k, v in LLM_PROVIDERS.items()},
    })


async def configure_llm_endpoint(request):
    """LLM yapılandırmasını kaydet (keyring ile yerel modda).

    Body: {"provider": "openrouter", "api_key": "sk-...", "model": "openai/gpt-4o-mini"}
    """
    is_local = os.environ.get("TURKIYE_MCP_LOCAL") == "1"
    if not is_local:
        return JSONResponse({"error": "Yapılandırma kaydı sadece yerel modda desteklenir."}, status_code=400)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Geçersiz istek."}, status_code=400)

    provider_id = body.get("provider", "").lower()
    api_key = body.get("api_key", "")
    model = body.get("model", "")

    if provider_id not in LLM_PROVIDERS:
        return JSONResponse({"error": f"Bilinmeyen sağlayıcı: {provider_id}"}, status_code=400)

    try:
        import keyring
        if api_key:
            keyring.set_password("turkiye-mcp", "llm-api-key", api_key)
        if provider_id:
            keyring.set_password("turkiye-mcp", "llm-provider", provider_id)
        if model:
            keyring.set_password("turkiye-mcp", "llm-model", model)
    except Exception as e:
        return JSONResponse({"error": f"Keyring hatası: {str(e)}"}, status_code=500)

    return JSONResponse({"status": "ok", "provider": provider_id, "model": model or LLM_PROVIDERS[provider_id]["default_model"]})


async def llm_status_endpoint(request):
    """Mevcut LLM yapılandırmasını getir."""
    is_local = os.environ.get("TURKIYE_MCP_LOCAL") == "1"
    provider_id = ""
    model = ""
    has_key = False

    # Environment variable'dan
    if OPENROUTER_API_KEY:
        provider_id = "openrouter"
        has_key = True

    # keyring'den (yerel mod)
    if is_local:
        try:
            import keyring
            stored_key = keyring.get_password("turkiye-mcp", "llm-api-key")
            stored_provider = keyring.get_password("turkiye-mcp", "llm-provider")
            stored_model = keyring.get_password("turkiye-mcp", "llm-model")
            if stored_key:
                has_key = True
                api_key = stored_key
            if stored_provider:
                provider_id = stored_provider
            if stored_model:
                model = stored_model
        except Exception:
            pass

    # Header'dan
    h_provider = request.headers.get("X-LLM-Provider", "")
    h_key = request.headers.get("X-API-Key", "")
    if h_provider:
        provider_id = h_provider
    if h_key:
        has_key = True

    return JSONResponse({
        "is_local": is_local,
        "provider": provider_id or "none",
        "model": model or (LLM_PROVIDERS.get(provider_id, {}).get("default_model", "") if provider_id else ""),
        "has_key": has_key,
        "env_key_set": bool(OPENROUTER_API_KEY),
    })


# ============================================================
# PDF UPLOAD — Belge yükleme ve metin çıkarma
# ============================================================

# Belge numarası regex kalıpları (hukuk belgelerinde arama için)
DOCUMENT_REGEX_PATTERS = [
    # Esas numarası: "Esas No:" veya "Esas Sayısı:" ile başlayan (4 haneli yıl zorunlu)
    (r"(?:esas\s*(?:say[ıi]s[ıi]?\s*)?(?:no[:\.]?\s*)?)(\d{4}[/-]\d{1,6})", "esas_no"),
    # Karar numarası: K.2023/1234 (K veya Karar öneki zorunlu)
    (r"[Kk](?:arar)?[\.\s:]*(\d{4}[/-]\d{1,6})", "karar_no"),
    # Resmi Gazete sayısı: "Resmi Gazete" veya "RG" öneki zorunlu
    (r"(?:resmi\s*gazete|RG)\s*(?:say[ıi]s[ıi]?\s*)?(?:no[:\.]?\s*)?(\d{5,6})", "rg_sayi"),
    # VKN/TCKN: tam 10 veya 11 haneli numara
    (r"\b(\d{10}|\d{11})\b", "vkn_tckn"),
    # Kanun numarası: 4721 sayılı kanun
    (r"(\d{1,5})\s*(?:say[ıi]l[ıi]\s*kanun|say[0134]l[0134]\s*kanun)", "kanun_no"),
    # İhale kayıt no: "İhale" öneki zorunlu
    (r"[İi]hale\s*(?:kay[ıi]t\s*)?(?:no[:\.]?\s*)?(\d{4}[/-]\d{4,8})", "ihale_no"),
    # Dosya numarası: "D:" veya "Dosya No:" ile başlayan
    (r"[Dd](?:osya)?[\.\s:]*(?:no[:\.]?\s*)?(\d{4}[/-]\d{1,6})", "dosya_no"),
]


def _extract_document_refs(text: str) -> list[dict]:
    """Belge metninden hukuki referans numaralarını çıkar.

    Returns:
        List of {"type": str, "value": str, "search_term": str} dicts
    """
    refs = []
    seen = set()

    for pattern, ref_type in DOCUMENT_REGEX_PATTERS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            value = match.group(1) if match.lastindex else match.group(0)
            key = f"{ref_type}:{value}"
            if key in seen:
                continue
            seen.add(key)

            # Arama terimi oluştur
            if ref_type == "esas_no":
                search_term = value
            elif ref_type == "karar_no":
                search_term = value
            elif ref_type == "rg_sayi":
                search_term = f"resmi gazete {value}"
            elif ref_type == "vkn_tckn":
                search_term = value
            elif ref_type == "kanun_no":
                search_term = f"{value} sayılı kanun"
            elif ref_type == "ihale_no":
                search_term = value
            elif ref_type == "dosya_no":
                search_term = value
            else:
                search_term = value

            refs.append({
                "type": ref_type,
                "value": value,
                "search_term": search_term,
                "label": {
                    "esas_no": "Esas No",
                    "karar_no": "Karar No",
                    "rg_sayi": "Resmi Gazete Sayısı",
                    "vkn_tckn": "VKN/TCKN",
                    "kanun_no": "Kanun No",
                    "ihale_no": "İhale Kayıt No",
                    "dosya_no": "Dosya No",
                }.get(ref_type, ref_type),
            })

    return refs[:20]  # Maksimum 20 referans


def _extract_text_from_pdf(content: bytes) -> tuple[str, dict]:
    """PDF dosyasından metin çıkar.

    Returns:
        (text, metadata) tuple. metadata sayfa sayısı vs. içerir.
    """
    metadata = {"pages": 0, "method": "pymupdf", "ocr_used": False}

    try:
        import pymupdf
        doc = pymupdf.open(stream=content, filetype="pdf")
        metadata["pages"] = len(doc)

        text_parts = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if text.strip():
                text_parts.append(f"--- Sayfa {page_num + 1} ---\n{text}")

        doc.close()

        full_text = "\n\n".join(text_parts)

        # Eğer pymupdf çok az metin çıkardıysa, OCR fallback dene
        if len(full_text.strip()) < 50 and metadata["pages"] > 0:
            try:
                ocr_text = _extract_text_with_ocr(content)
                if ocr_text and len(ocr_text) > len(full_text):
                    full_text = ocr_text
                    metadata["method"] = "tesseract_ocr"
                    metadata["ocr_used"] = True
            except Exception as e:
                logger.warning(f"OCR fallback basarisiz: {e}")

        return full_text, metadata

    except ImportError:
        logger.warning("pymupdf yuklu degil, OCR deneniyor...")
        try:
            ocr_text = _extract_text_with_ocr(content)
            metadata["method"] = "tesseract_ocr"
            metadata["ocr_used"] = True
            return ocr_text, metadata
        except Exception as e:
            metadata["error"] = str(e)
            return "", metadata
    except Exception as e:
        metadata["error"] = str(e)
        return "", metadata


def _extract_text_with_ocr(content: bytes) -> str:
    """Tesseract OCR ile PDF'den metin çıkar (fallback)."""
    try:
        from pdf2image import convert_from_bytes
        import pytesseract

        images = convert_from_bytes(content, dpi=200)
        text_parts = []

        for i, img in enumerate(images):
            # Turkce dil destegi ile OCR
            try:
                text = pytesseract.image_to_string(img, lang="tur+eng")
            except Exception:
                # Turkiye dili yoksa sadece Ingilizce dene
                text = pytesseract.image_to_string(img, lang="eng")
            text_parts.append(f"--- Sayfa {i + 1} (OCR) ---\n{text}")

        return "\n\n".join(text_parts)

    except ImportError as e:
        raise ImportError(f"OCR kutuphaneleri yuklu degil: {e}")


async def upload_pdf_endpoint(request):
    """PDF yukleme endpoint'i.

    Multipart form-data ile PDF dosyasi yuklenir.
    Yanit: metin icerigi + cikarilan referans numaralari.
    """
    try:
        form = await request.form()
    except Exception:
        return JSONResponse({"error": "Gecersiz form verisi."}, status_code=400)

    file = form.get("file")
    if not file:
        return JSONResponse({"error": "Dosya bulunamadi. 'file' alani gerekli."}, status_code=400)

    # Dosya boyutu kontrolu (maks 20MB)
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        return JSONResponse({"error": "Dosya boyutu 20MB'dan buyuk olamaz."}, status_code=400)

    filename = file.filename or "document.pdf"
    if not filename.lower().endswith(".pdf"):
        return JSONResponse({"error": "Sadece PDF dosyalari yuklenebilir."}, status_code=400)

    # PDF'den metin cikar
    text, metadata = _extract_text_from_pdf(content)

    if not text.strip():
        return JSONResponse({
            "error": "PDF'den metin cikarilamadi. Dosya taranmis goruntu iceriyor olabilir.",
            "metadata": metadata,
        }, status_code=422)

    # Belge referanslarini cikar
    refs = _extract_document_refs(text)

    # Metni kisalt (maks 10000 karakter)
    truncated = len(text) > 10000
    display_text = text[:10000] + ("..." if truncated else "")

    return JSONResponse({
        "filename": filename,
        "text": display_text,
        "full_text_length": len(text),
        "truncated": truncated,
        "metadata": metadata,
        "references": refs,
    })


async def search_document_refs_endpoint(request):
    """Belge referans numaralarini MCP araclariyla arar.

    Body: {"references": [...], "provider": "openrouter", "api_key": "sk-..."}
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Gecersiz istek."}, status_code=400)

    refs = body.get("references", [])
    if not refs:
        return JSONResponse({"error": "Referans numaralari gerekli."}, status_code=400)

    results = []
    for ref in refs[:10]:  # Maks 10 referans
        search_term = ref.get("search_term", "")
        ref_type = ref.get("type", "")
        ref_value = ref.get("value", "")

        try:
            # Referans tipine gore ilgili MCP aracini cagir
            if ref_type in ("esas_no", "karar_no", "dosya_no"):
                tool_result, _ = await _route_and_call(search_term)
                results.append({"ref": ref, "result": tool_result[:2000] if tool_result else "Sonuc bulunamadi."})
            elif ref_type == "rg_sayi":
                tool_result, _ = await _route_and_call(f"resmi gazete {ref_value}")
                results.append({"ref": ref, "result": tool_result[:2000] if tool_result else "Sonuc bulunamadi."})
            elif ref_type == "vkn_tckn":
                if MODULES_AVAILABLE.get("ivd"):
                    result = await check_efatura_taxpayer(vergi_kimlik_no=ref_value)
                    results.append({"ref": ref, "result": result[:2000]})
                else:
                    results.append({"ref": ref, "result": "IVD modulu yuklu degil."})
            elif ref_type == "kanun_no":
                tool_result, _ = await _route_and_call(search_term)
                results.append({"ref": ref, "result": tool_result[:2000] if tool_result else "Sonuc bulunamadi."})
            elif ref_type == "ihale_no":
                tool_result, _ = await _route_and_call(f"ihale {ref_value}")
                results.append({"ref": ref, "result": tool_result[:2000] if tool_result else "Sonuc bulunamadi."})
            else:
                tool_result, _ = await _route_and_call(search_term)
                results.append({"ref": ref, "result": tool_result[:2000] if tool_result else "Sonuc bulunamadi."})
        except Exception as e:
            results.append({"ref": ref, "result": f"Hata: {str(e)}"})

    return JSONResponse({"results": results})


async def upload_uyap_endpoint(request):
    """UYAP EYP/UDF dosya yukleme endpoint'i.

    Multipart form-data ile .eyp veya .udf dosyasi yuklenir.
    Yanit: belge analizi + referans numaralari.
    """
    try:
        form = await request.form()
    except Exception:
        return JSONResponse({"error": "Gecersiz form verisi."}, status_code=400)

    file = form.get("file")
    if not file:
        return JSONResponse({"error": "Dosya bulunamadi. 'file' alani gerekli."}, status_code=400)

    content_bytes = await file.read()
    if len(content_bytes) > 50 * 1024 * 1024:  # 50MB max
        return JSONResponse({"error": "Dosya boyutu 50MB'dan buyuk olamaz."}, status_code=400)

    filename = file.filename or "document.eyp"
    if not (filename.lower().endswith(".eyp") or filename.lower().endswith(".udf")):
        return JSONResponse({"error": "Sadece .eyp ve .udf dosyalari yuklenebilir."}, status_code=400)

    try:
        belge = uyap_parser.parse_eyp(content_bytes)
        md = uyap_parser.to_markdown(belge)

        return JSONResponse({
            "filename": filename,
            "markdown": md[:10000],
            "full_markdown_length": len(md),
            "belge": {
                "konu": belge.konu,
                "belge_no": belge.belge_no,
                "tarih": belge.tarih,
                "olusturan_adi": belge.olusturan_adi,
                "taraflar": [{"ad": t.ad, "tckn": t.tckn, "rol": t.rol} for t in belge.taraflar],
                "imzalar": [{"ad": i.imzalayan_ad + " " + i.imzalayan_soyad, "makam": i.makam, "tarih": i.tarih} for i in belge.imzalar],
                "ekler": [{"dosya_adi": e.dosya_adi, "tur": e.tur, "mime": e.mime_turu} for e in belge.ekler],
                "dosya_bilgisi": {"dosya_no": belge.dosya_bilgisi.dosya_no, "dosya_tur": belge.dosya_bilgisi.dosya_tur, "birim": belge.dosya_bilgisi.birim_adi} if belge.dosya_bilgisi else None,
                "referanslar": belge.referanslar,
                "ust_yazi_metin_length": len(belge.ust_yazi_metin),
                "ek_metin_count": len(belge.ek_metinler),
            },
        })
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": f"UYAP parse hatasi: {str(e)}"}, status_code=500)


async def chat_endpoint(request):
    """Chat endpoint — BYOK LLM + MCP araçları ile yanıt üretir.

    Header'lar:
      X-LLM-Provider: openrouter|openai|anthropic|gemini|ollama
      X-API-Key: API anahtarı (ollama hariç)
      X-LLM-Model: Model adı (opsiyonel)

    Veya body'de:
      provider, api_key, model alanları
    """
    # LLM yapılandırmasını al
    provider_id, api_key, model = _get_llm_config(request)

    # Body'den de alabilir (frontend'den)
    try:
        body = await request.json()
    except Exception:
        body = {}

    if body.get("provider"):
        provider_id = body["provider"].lower()
    if body.get("api_key"):
        api_key = body["api_key"]
    if body.get("model"):
        model = body["model"]

    # Provider geçerli mi?
    if provider_id not in LLM_PROVIDERS:
        return JSONResponse({"error": f"Bilinmeyen sağlayıcı: {provider_id}. Geçerli: {', '.join(LLM_PROVIDERS.keys())}"}, status_code=400)

    provider_config = LLM_PROVIDERS[provider_id]

    # API key gerekli mi?
    if provider_config["needs_key"] and not api_key:
        return JSONResponse({
            "error": "API anahtarı gerekli.",
            "needs_key": True,
            "provider": provider_id,
            "providers": {k: {"name": v["name"], "needs_key": v["needs_key"], "models": v["models"], "default_model": v["default_model"]} for k, v in LLM_PROVIDERS.items()},
        }, status_code=401)

    # IP rate limiting (sadece bulut sağlayıcılar için)
    if provider_config["needs_key"]:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        day_ago = now - 86400
        ip_rate_limits[client_ip] = [t for t in ip_rate_limits[client_ip] if t > day_ago]
        if len(ip_rate_limits[client_ip]) >= RATE_LIMIT_PER_IP:
            return JSONResponse({"error": f"Gunluk limit asildi ({RATE_LIMIT_PER_IP} istek/IP). Yarin tekrar deneyin.", "remaining": 0}, status_code=429)
        ip_rate_limits[client_ip].append(now)

    message = (body.get("message", "") or "").strip()[:500]
    if not message:
        return JSONResponse({"error": "Mesaj bos olamaz."}, status_code=400)

    # MCP araçlarını çağır
    tool_context, called_tools = await _route_and_call(message)

    # LLM'e gönder
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if tool_context:
        messages.append({"role": "system", "content": f"MCP araç sonuçları:\n\n{tool_context}"})
    messages.append({"role": "user", "content": message})

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            if provider_config.get("is_anthropic"):
                # Anthropic API formatı farklı
                resp = await client.post(
                    provider_config["url"],
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "max_tokens": 1024,
                        "system": SYSTEM_PROMPT + ("\n\nMCP araç sonuçları:\n\n" + tool_context if tool_context else ""),
                        "messages": [{"role": "user", "content": message}],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                reply = data.get("content", [{}])[0].get("text", "Yanit alinamadi.")
            else:
                # OpenAI-uyumlu API formatı (OpenRouter, OpenAI, Gemini, Ollama)
                headers = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                if provider_id == "openrouter":
                    headers["HTTP-Referer"] = "https://turkiye-mcp.up.railway.app"

                resp = await client.post(
                    provider_config["url"],
                    headers=headers,
                    json={"model": model, "messages": messages, "max_tokens": 1024},
                )
                resp.raise_for_status()
                data = resp.json()
                reply = data.get("choices", [{}])[0].get("message", {}).get("content", "Yanit alinamadi.")

            sources = list(called_tools)[:5]
    except httpx.HTTPStatusError as e:
        return JSONResponse({"error": f"LLM hatasi: {e.response.status_code} - {e.response.text[:200]}", "remaining": RATE_LIMIT_PER_IP - len(ip_rate_limits.get(request.client.host if request.client else "unknown", []))}, status_code=502)
    except httpx.ConnectError:
        if provider_id == "ollama":
            return JSONResponse({"error": "Ollama baglantisi kurulamadi. Ollama'in calistigindan emin olun (localhost:11434).", "remaining": RATE_LIMIT_PER_IP - len(ip_rate_limits.get(request.client.host if request.client else "unknown", []))}, status_code=502)
        return JSONResponse({"error": "LLM saglayicisina baglanilamadi.", "remaining": RATE_LIMIT_PER_IP - len(ip_rate_limits.get(request.client.host if request.client else "unknown", []))}, status_code=502)
    except Exception as e:
        return JSONResponse({"error": f"Beklenmeyen hata: {str(e)}"}, status_code=500)

    remaining = RATE_LIMIT_PER_IP - len(ip_rate_limits.get(request.client.host if request.client else "unknown", []))
    return JSONResponse({"response": reply, "sources": sources[:5], "remaining": remaining, "provider": provider_id, "model": model})


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
        Route("/api/chat/providers", providers_endpoint, methods=["GET"]),
        Route("/api/chat/configure", configure_llm_endpoint, methods=["POST"]),
        Route("/api/chat/status", llm_status_endpoint, methods=["GET"]),
        Route("/api/upload/pdf", upload_pdf_endpoint, methods=["POST"]),
        Route("/api/search/refs", search_document_refs_endpoint, methods=["POST"]),
        Route("/api/upload/uyap", upload_uyap_endpoint, methods=["POST"]),
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