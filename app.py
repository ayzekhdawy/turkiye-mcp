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

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Turkiye MCP</title>
<style>
:root {
  --bg-primary: #0a0f1a;
  --bg-secondary: #111827;
  --bg-card: #1a2236;
  --bg-card-hover: #1e2a42;
  --bg-input: #0d1322;
  --border: #2a3548;
  --text-primary: #e2e8f0;
  --text-secondary: #94a3b8;
  --text-muted: #64748b;
  --accent: #6366f1;
  --accent-hover: #818cf8;
  --accent-gradient: linear-gradient(135deg, #6366f1, #8b5cf6);
  --success: #10b981;
  --warning: #f59e0b;
  --danger: #ef4444;
  --sidebar-width: 280px;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg-primary); color: var(--text-primary); height: 100vh; overflow: hidden; }

/* Layout */
.app-container { display: flex; height: 100vh; }

/* Sidebar */
.sidebar {
  width: var(--sidebar-width); min-width: var(--sidebar-width);
  background: var(--bg-secondary); border-right: 1px solid var(--border);
  display: flex; flex-direction: column; overflow: hidden;
}
.sidebar-header {
  padding: 1rem; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 0.75rem;
}
.sidebar-header h1 {
  font-size: 1.1rem; font-weight: 700;
  background: var(--accent-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.sidebar-header .logo { font-size: 1.5rem; }

.new-chat-btn {
  margin: 0.75rem; padding: 0.6rem 1rem;
  background: var(--accent-gradient); color: #fff; border: none; border-radius: 10px;
  font-size: 0.85rem; font-weight: 600; cursor: pointer;
  display: flex; align-items: center; gap: 0.5rem; transition: all 0.2s;
}
.new-chat-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(99,102,241,0.4); }

.chat-list { flex: 1; overflow-y: auto; padding: 0.5rem; }
.chat-list::-webkit-scrollbar { width: 4px; }
.chat-list::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }

.chat-item {
  padding: 0.6rem 0.75rem; border-radius: 8px; cursor: pointer;
  display: flex; align-items: center; gap: 0.5rem;
  font-size: 0.85rem; color: var(--text-secondary); transition: all 0.15s;
  margin-bottom: 2px;
}
.chat-item:hover { background: var(--bg-card); color: var(--text-primary); }
.chat-item.active { background: var(--bg-card); color: var(--text-primary); border-left: 3px solid var(--accent); }
.chat-item .icon { font-size: 0.9rem; opacity: 0.7; }
.chat-item .title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.chat-item .delete-chat { opacity: 0; cursor: pointer; font-size: 0.75rem; }
.chat-item:hover .delete-chat { opacity: 0.5; }
.chat-item:hover .delete-chat:hover { opacity: 1; }

.chat-date { padding: 0.5rem 0.75rem; font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }

/* Sidebar footer - Modules */
.sidebar-footer { border-top: 1px solid var(--border); padding: 0.75rem; max-height: 200px; overflow-y: auto; }
.sidebar-footer h3 { font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
.module-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 3px; }
.module-item { font-size: 0.7rem; padding: 2px 4px; border-radius: 4px; color: var(--text-muted); }
.module-item.ok { color: var(--success); }
.module-item.fail { color: var(--danger); }

/* Main Area */
.main-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

/* Top Bar */
.top-bar {
  padding: 0.75rem 1.5rem; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 1rem; background: var(--bg-secondary);
}
.provider-select {
  padding: 0.4rem 0.75rem; border-radius: 8px; border: 1px solid var(--border);
  background: var(--bg-input); color: var(--text-primary); font-size: 0.85rem; min-width: 140px;
}
.model-select {
  padding: 0.4rem 0.75rem; border-radius: 8px; border: 1px solid var(--border);
  background: var(--bg-input); color: var(--text-primary); font-size: 0.85rem; min-width: 180px;
}
.api-key-input {
  padding: 0.4rem 0.75rem; border-radius: 8px; border: 1px solid var(--border);
  background: var(--bg-input); color: var(--text-primary); font-size: 0.85rem; width: 200px;
}
.save-btn {
  padding: 0.4rem 1rem; border-radius: 8px; border: none;
  background: var(--success); color: #fff; font-size: 0.85rem; font-weight: 600; cursor: pointer;
}
.llm-status {
  padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.7rem; font-weight: 600;
}
.llm-status.connected { background: #064e3b; color: #34d399; }
.llm-status.disconnected { background: #450a0a; color: #f87171; }
.llm-status.local { background: #1e3a5f; color: #60a5fa; }

/* Chat Area */
.chat-area { flex: 1; overflow-y: auto; padding: 1.5rem; }
.chat-area::-webkit-scrollbar { width: 6px; }
.chat-area::-webkit-scrollbar-thumb { background: var(--border); border-radius: 6px; }

.message { margin-bottom: 1rem; display: flex; gap: 0.75rem; animation: fadeIn 0.3s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

.message.user { justify-content: flex-end; }
.message.user .bubble { background: var(--accent); color: #fff; border-radius: 16px 16px 4px 16px; max-width: 70%; }
.message.assistant .bubble { background: var(--bg-card); border: 1px solid var(--border); border-radius: 16px 16px 16px 4px; max-width: 80%; }
.message.system .bubble { background: var(--bg-secondary); border: 1px solid var(--border); border-radius: 12px; color: var(--text-muted); font-style: italic; max-width: 60%; text-align: center; margin: 0 auto; }
.bubble { padding: 0.75rem 1rem; font-size: 0.9rem; line-height: 1.6; white-space: pre-wrap; word-wrap: break-word; }
.bubble code { background: rgba(255,255,255,0.1); padding: 0.1rem 0.3rem; border-radius: 4px; font-size: 0.85em; }
.bubble strong { color: var(--accent-hover); }
.bubble .msg-content { white-space: normal; }
.bubble .msg-content h2,.bubble .msg-content h3,.bubble .msg-content h4 { margin: 0.5rem 0 0.25rem; color: var(--text-primary); }
.bubble .msg-content h2 { font-size: 1.1rem; }
.bubble .msg-content h3 { font-size: 1rem; }
.bubble .msg-content h4 { font-size: 0.95rem; }
.bubble .msg-content ul,.bubble .msg-content ol { padding-left: 1.5rem; margin: 0.5rem 0; }
.bubble .msg-content li { margin: 0.2rem 0; }
.bubble .msg-content hr { border: none; border-top: 1px solid var(--border); margin: 0.75rem 0; }
.bubble .msg-content a { color: var(--accent-hover); text-decoration: underline; }
.bubble .msg-content em { color: var(--accent-hover); }
.msg-actions { display: flex; gap: 0.25rem; margin-top: 0.5rem; opacity: 0.5; transition: opacity 0.2s; }
.msg-actions:hover { opacity: 1; }
.msg-actions button { background: none; border: 1px solid var(--border); border-radius: 6px; padding: 0.2rem 0.4rem; cursor: pointer; font-size: 0.75rem; color: var(--text-secondary); transition: all 0.2s; }
.msg-actions button:hover { background: var(--bg-card-hover); color: var(--text-primary); border-color: var(--accent); }

/* Markdown Table */
.md-table { width: 100%; border-collapse: collapse; margin: 0.5rem 0; font-size: 0.85rem; }
.md-table th { background: rgba(99,102,241,0.3); color: var(--text-primary); padding: 0.4rem 0.6rem; text-align: left; border: 1px solid var(--border); font-weight: 600; }
.md-table td { padding: 0.35rem 0.6rem; border: 1px solid var(--border); color: var(--text-secondary); }
.md-table tr:hover td { background: var(--bg-card-hover); }

/* Settings Panel */
.settings-panel { display: none; padding: 1.5rem; overflow-y: auto; }
.settings-panel.active { display: block; }
.settings-section { margin-bottom: 1.5rem; }
.settings-section h3 { font-size: 0.95rem; color: var(--text-primary); margin-bottom: 0.75rem; }
.settings-row { display: flex; gap: 0.75rem; align-items: center; margin-bottom: 0.5rem; }
.settings-row label { font-size: 0.85rem; color: var(--text-secondary); min-width: 100px; }
.settings-row select,.settings-row input { flex: 1; }
.server-status { display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 0.75rem; border-radius: 8px; background: var(--bg-card); font-size: 0.8rem; }
.server-dot { width: 8px; height: 8px; border-radius: 50%; }
.server-dot.ok { background: var(--success); }
.server-dot.err { background: var(--danger); }

/* Sources */
.sources { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-top: 0.5rem; }
.source-tag { background: rgba(99,102,241,0.2); color: var(--accent-hover); padding: 0.15rem 0.5rem; border-radius: 9999px; font-size: 0.7rem; }

/* Input Area */
.input-area {
  padding: 1rem 1.5rem; border-top: 1px solid var(--border);
  background: var(--bg-secondary);
}
.input-row { display: flex; gap: 0.5rem; align-items: flex-end; }
.chat-input {
  flex: 1; padding: 0.75rem 1rem; border-radius: 12px; border: 1px solid var(--border);
  background: var(--bg-input); color: var(--text-primary); font-size: 0.95rem; resize: none;
  min-height: 44px; max-height: 120px; transition: border-color 0.2s;
}
.chat-input:focus { outline: none; border-color: var(--accent); }
.chat-input::placeholder { color: var(--text-muted); }

.send-btn {
  padding: 0.75rem 1.25rem; border-radius: 12px; border: none;
  background: var(--accent-gradient); color: #fff; font-size: 1.1rem;
  cursor: pointer; transition: all 0.2s; display: flex; align-items: center;
}
.send-btn:hover { transform: scale(1.05); box-shadow: 0 4px 12px rgba(99,102,241,0.4); }
.send-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

.upload-btn {
  padding: 0.75rem; border-radius: 12px; border: 1px solid var(--border);
  background: var(--bg-card); color: var(--text-secondary); font-size: 1.1rem;
  cursor: pointer; transition: all 0.2s;
}
.upload-btn:hover { background: var(--bg-card-hover); color: var(--text-primary); }

.input-footer { display: flex; justify-content: space-between; margin-top: 0.5rem; font-size: 0.75rem; color: var(--text-muted); }

/* File Upload Overlay */
.file-drop-overlay {
  display: none; position: fixed; inset: 0; z-index: 1000;
  background: rgba(99,102,241,0.1); border: 3px dashed var(--accent);
  backdrop-filter: blur(4px);
  justify-content: center; align-items: center; font-size: 1.5rem; color: var(--accent);
}
.file-drop-overlay.active { display: flex; }

/* Welcome Screen */
.welcome { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; text-align: center; padding: 2rem; }
.welcome h2 { font-size: 2rem; margin-bottom: 0.5rem; background: var(--accent-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.welcome p { color: var(--text-secondary); max-width: 500px; margin-bottom: 1.5rem; }
.quick-actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.75rem; max-width: 600px; width: 100%; }
.quick-action {
  padding: 1rem; border-radius: 12px; border: 1px solid var(--border);
  background: var(--bg-card); cursor: pointer; transition: all 0.2s; text-align: left;
}
.quick-action:hover { border-color: var(--accent); background: var(--bg-card-hover); transform: translateY(-2px); }
.quick-action .qa-icon { font-size: 1.5rem; margin-bottom: 0.5rem; }
.quick-action .qa-title { font-size: 0.85rem; font-weight: 600; color: var(--text-primary); }
.quick-action .qa-desc { font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem; }

/* Responsive */
@media (max-width: 768px) {
  .sidebar { width: 60px; min-width: 60px; }
  .sidebar .chat-item .title, .sidebar .new-chat-btn span, .sidebar-footer { display: none; }
  .sidebar-header h1 { display: none; }
  .api-key-input, .model-select { display: none; }
}
</style>
</head>
<body>
<div class="app-container">
  <!-- Sidebar -->
  <div class="sidebar">
    <div class="sidebar-header">
      <span class="logo">&#127479;&#127480;</span>
      <h1>Turkiye MCP</h1>
    </div>
    <button class="new-chat-btn" onclick="newChat()">&#10010; <span>Yeni Sohbet</span></button>
    <div class="chat-list" id="chat-list"></div>
    <div class="sidebar-footer">
      <h3>Moduller</h3>
      <div class="module-grid" id="module-grid"></div>
    </div>
  </div>

  <!-- Main Area -->
  <div class="main-area">
    <!-- Top Bar -->
    <div class="top-bar">
      <div class="server-status"><span class="server-dot ok" id="server-dot"></span><span id="server-status-text">Baglaniyor...</span></div>
      <select class="provider-select" id="llm-provider" onchange="onProviderChange()">
        <option value="openrouter">OpenRouter</option>
        <option value="openai">OpenAI</option>
        <option value="anthropic">Anthropic</option>
        <option value="gemini">Google Gemini</option>
        <option value="ollama">Ollama (Yerel)</option>
      </select>
      <select class="model-select" id="llm-model"></select>
      <input type="password" class="api-key-input" id="llm-api-key" placeholder="API anahtari..." />
      <button class="save-btn" onclick="saveConfig()">Kaydet</button>
      <span class="llm-status disconnected" id="llm-status-badge">API Key Gerekli</span>
    </div>

    <!-- Chat Area -->
    <div class="chat-area" id="chat-area">
      <!-- Welcome Screen -->
      <div class="welcome" id="welcome-screen">
        <h2>Turkiye MCP Asistani</h2>
        <p>Turk hukuk, mali, ihale ve piyasa verileri hakkinda soru sorun. PDF veya EYP/UDF dosyasi yukleyebilirsiniz.</p>
        <div class="quick-actions">
          <div class="quick-action" onclick="sendQuick('2025 asgari ucret ne kadar?')">
            <div class="qa-icon">&#128176;</div>
            <div class="qa-title">Asgari Ucret</div>
            <div class="qa-desc">2025 asgari ucret bilgisi</div>
          </div>
          <div class="quick-action" onclick="sendQuick('Yargitay mulkiyet hakki kararlari')">
            <div class="qa-icon">&#9878;</div>
            <div class="qa-title">Yargitay Kararlari</div>
            <div class="qa-desc">Mulkiyet hakki ictihatlar</div>
          </div>
          <div class="quick-action" onclick="sendQuick('Ankara\'daki aktif ihaleler')">
            <div class="qa-icon">&#127959;</div>
            <div class="qa-title">Ihale Arama</div>
            <div class="qa-desc">Ankara\'daki kamu ihaleleri</div>
          </div>
          <div class="quick-action" onclick="document.getElementById('file-input').click()">
            <div class="qa-icon">&#128196;</div>
            <div class="qa-title">Belge Yukle</div>
            <div class="qa-desc">PDF veya EYP/UDF dosyasi</div>
          </div>
        </div>
      </div>
    </div>

    <!-- File Drop Overlay -->
    <div class="file-drop-overlay" id="file-drop-overlay">&#128196; Dosya yuklemek icin birakin</div>

    <!-- Input Area -->
    <div class="input-area">
      <div class="input-row">
        <button class="upload-btn" onclick="document.getElementById('file-input').click()" title="Dosya yukle">&#128206;</button>
        <input type="file" id="file-input" accept=".pdf,.eyp,.udf" style="display:none" onchange="handleFileUpload(this.files[0])" />
        <textarea class="chat-input" id="chat-input" placeholder="Soru sorun veya dosya yukleyin..." rows="1" onkeydown="handleKeyDown(event)" oninput="autoResize(this)"></textarea>
        <button class="send-btn" id="send-btn" onclick="sendMessage()">&#10148;</button>
      </div>
      <div class="input-footer">
        <span id="char-count"></span>
        <span id="rate-limit"></span>
      </div>
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
    document.getElementById('server-dot').className = 'server-dot ok';
    document.getElementById('server-status-text').textContent = `${data.active_count || '?'}/${data.total_count || '?'} modul aktif`;
  } catch(e) {
    document.getElementById('server-dot').className = 'server-dot err';
    document.getElementById('server-status-text').textContent = 'Sunucuya baglanilamiyor';
  }
}
checkServerStatus();
setInterval(checkServerStatus, 30000);

// ===== Chat Management =====
function generateId() { return Date.now().toString(36) + Math.random().toString(36).substr(2, 5); }

function generateTitle(msg) {
  const lower = msg.toLowerCase();
  const titleMap = {
    'yargitay': 'Yargitay Kararlari', 'danistay': 'Danistay Kararlari',
    'anayasa': 'Anayasa Mahkemesi', 'asgari': 'Asgari Ucret', 'resmi gazete': 'Resmi Gazete',
    'ihale': 'Ihale Arama', 'borsa': 'Borsa Verileri', 'doviz': 'Doviz Kurlari',
    'kripto': 'Kripto Para', 'vergi': 'Vergi Sirkuleri', 'sgk': 'SGK Bilgileri',
    'efatura': 'e-Fatura Sorgulama', 'mevzuat': 'Mevzuat Arama',
  };
  for (const [key, title] of Object.entries(titleMap)) {
    if (lower.includes(key)) return title;
  }
  return msg.substring(0, 35) + (msg.length > 35 ? '...' : '');
}

function newChat() {
  const chat = { id: generateId(), title: 'Yeni Sohbet', messages: [], created: Date.now() };
  chats.unshift(chat);
  activeChatId = chat.id;
  saveChats();
  renderChatList();
  renderChat();
}

function switchChat(id) {
  activeChatId = id;
  localStorage.setItem('turkiye_mcp_active_chat', id);
  renderChatList();
  renderChat();
}

function deleteChat(id, e) {
  e.stopPropagation();
  chats = chats.filter(c => c.id !== id);
  if (activeChatId === id) {
    activeChatId = chats.length > 0 ? chats[0].id : null;
  }
  saveChats();
  renderChatList();
  renderChat();
}

function saveChats() {
  localStorage.setItem('turkiye_mcp_chats', JSON.stringify(chats));
  localStorage.setItem('turkiye_mcp_active_chat', activeChatId || '');
}

function getActiveChat() { return chats.find(c => c.id === activeChatId); }

// ===== Rendering =====
function renderChatList() {
  const list = document.getElementById('chat-list');
  if (chats.length === 0) {
    list.innerHTML = '<div style="text-align:center;color:var(--text-muted);font-size:0.8rem;padding:1rem;">Henuz sohbet yok</div>';
    return;
  }
  let html = '';
  const today = new Date().toDateString();
  const yesterday = new Date(Date.now() - 86400000).toDateString();
  let lastDate = '';

  chats.forEach(c => {
    const d = new Date(c.created).toDateString();
    const dateLabel = d === today ? 'Bugun' : d === yesterday ? 'Dun' : new Date(c.created).toLocaleDateString('tr-TR', {day:'numeric',month:'short'});
    if (d !== lastDate) {
      html += `<div class="chat-date">${dateLabel}</div>`;
      lastDate = d;
    }
    const active = c.id === activeChatId ? 'active' : '';
    html += `<div class="chat-item ${active}" onclick="switchChat('${c.id}')">
      <span class="icon">&#128172;</span>
      <span class="title">${c.title}</span>
      <span class="delete-chat" onclick="deleteChat('${c.id}', event)">&#10005;</span>
    </div>`;
  });
  list.innerHTML = html;
}

function renderChat() {
  const area = document.getElementById('chat-area');
  const welcome = document.getElementById('welcome-screen');
  const chat = getActiveChat();

  if (!chat || chat.messages.length === 0) {
    welcome.style.display = 'flex';
    // Remove message elements
    area.querySelectorAll('.message').forEach(el => el.remove());
    return;
  }

  welcome.style.display = 'none';
  // Clear old messages
  area.querySelectorAll('.message').forEach(el => el.remove());

  chat.messages.forEach(m => {
    const div = document.createElement('div');
    div.className = `message ${m.role}`;
    if (m.role === 'assistant') {
      div.innerHTML = `<div class="bubble"><div class="msg-content">${renderMarkdown(m.text)}</div>${m.sources ? renderSources(m.sources) : ''}<div class="msg-actions"><button onclick="copyMessage(this)" title="Kopyala">📋</button><button onclick="exportWord(this)" title="Word'e Aktar">📄</button></div></div>`;
    } else {
      div.innerHTML = `<div class="bubble">${escapeHtml(m.text)}${m.sources ? renderSources(m.sources) : ''}</div>`;
    }
    area.appendChild(div);
  });
  area.scrollTop = area.scrollHeight;
}

function renderSources(sources) {
  if (!sources || sources.length === 0) return '';
  return `<div class="sources">${sources.map(s => `<span class="source-tag">${s}</span>`).join('')}</div>`;
}

function escapeHtml(text) {
  return text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ===== Markdown Render =====
function renderMarkdown(text) {
  if (!text) return '';
  let html = escapeHtml(text);
  // Bold
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Italic
  html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
  // Headers
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
  // Unordered lists
  html = html.replace(/^- (.*?)(?:\n|$)/gm, '<li>$1</li>');
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');
  // Ordered lists
  html = html.replace(/^\d+\. (.*?)(?:\n|$)/gm, '<li>$1</li>');
  // Horizontal rule
  html = html.replace(/^---$/gm, '<hr>');
  // Links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Line breaks
  html = html.replace(/\n/g, '<br>');
  // Clean up double <br> after block elements
  html = html.replace(/(<\/h[234]>)<br>/g, '$1');
  html = html.replace(/(<\/table>)<br>/g, '$1');
  html = html.replace(/(<\/ul>)<br>/g, '$1');
  html = html.replace(/(<hr>)<br>/g, '$1');
  return html;
}

// ===== Copy & Export =====
function copyMessage(btn) {
  const bubble = btn.closest('.bubble');
  const content = bubble.querySelector('.msg-content');
  const text = content ? content.innerText : bubble.innerText;
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = '✓';
    setTimeout(() => btn.textContent = '📋', 1500);
  });
}

function exportWord(btn) {
  const bubble = btn.closest('.bubble');
  const content = bubble.querySelector('.msg-content');
  const htmlContent = content ? content.innerHTML : bubble.innerHTML;
  const chat = getActiveChat();
  const title = chat ? chat.title : 'TurkiyeMCP';
  const fullHtml = `
    <html xmlns:o='urn:schemas-microsoft-com:office:office' xmlns:w='urn:schemas-microsoft-com:office:word' xmlns='http://www.w3.org/TR/REC-html40'>
    <head><meta charset='utf-8'><title>${escapeHtml(title)}</title>
    <style>body{font-family:'Segoe UI',Tahoma,sans-serif;font-size:11pt;color:#1a1a2e}
    table{border-collapse:collapse;width:100%;margin:8pt 0}th,td{border:1px solid #ccc;padding:4pt 8pt;font-size:10pt}th{background:#6366f1;color:#fff}
    h2{color:#6366f1}h3{color:#818cf8}h4{color:#a5b4fc}code{background:#f1f5f9;padding:1pt 3pt;border-radius:3pt;font-size:10pt}
    strong{color:#6366f1}em{color:#8b5cf6}</style></head>
    <body>${htmlContent}</body></html>`;
  const blob = new Blob(['﻿', fullHtml], {type: 'application/msword'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = `${title.replace(/[^a-zA-Z0-9À-ɏ]/g,'_')}.doc`;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
  btn.textContent = '✓'; setTimeout(() => btn.textContent = '📄', 1500);
}

// ===== Send Message =====
function sendQuick(msg) {
  document.getElementById('chat-input').value = msg;
  sendMessage();
}

async function sendMessage() {
  const input = document.getElementById('chat-input');
  const msg = input.value.trim();
  if (!msg || isSending) return;
  input.value = '';
  autoResize(input);

  // Ensure we have an active chat
  if (!activeChatId) newChat();
  let chat = getActiveChat();
  if (!chat) { newChat(); chat = getActiveChat(); }

  // Update title on first message
  if (chat.messages.length === 0) {
    chat.title = generateTitle(msg);
    renderChatList();
  }

  // Add user message
  chat.messages.push({ role: 'user', text: msg });
  renderChat();
  saveChats();

  // Show typing indicator
  isSending = true;
  document.getElementById('send-btn').disabled = true;
  const typingDiv = document.createElement('div');
  typingDiv.className = 'message assistant';
  typingDiv.id = 'typing-indicator';
  typingDiv.innerHTML = '<div class="bubble" style="color:var(--text-muted);">Yaziyor...</div>';
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

    const res = await fetch('/api/chat', {
      method: 'POST', headers,
      body: JSON.stringify({message: msg, provider, api_key: apiKey, model})
    });
    const data = await res.json();

    // Remove typing indicator
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
    chat.messages.push({ role: 'system', text: 'Baglanti hatasi.' });
  }

  isSending = false;
  document.getElementById('send-btn').disabled = false;
  renderChat();
  saveChats();

  // Update rate limit
  const rateEl = document.getElementById('rate-limit');
  if (chat.messages.length > 0) {
    const last = chat.messages[chat.messages.length - 1];
    // rate info from last response is not stored, just show chat count
  }
}

// ===== File Upload =====
async function handleFileUpload(file) {
  if (!file) return;
  const isUyap = file.name.toLowerCase().endsWith('.eyp') || file.name.toLowerCase().endsWith('.udf');
  const endpoint = isUyap ? '/api/upload/uyap' : '/api/upload/pdf';

  if (!activeChatId) newChat();
  let chat = getActiveChat();
  if (!chat) { newChat(); chat = getActiveChat(); }

  if (chat.messages.length === 0) {
    chat.title = 'Belge: ' + file.name;
    renderChatList();
  }

  chat.messages.push({ role: 'system', text: `Dosya yukleniyor: ${file.name}...` });
  renderChat();
  saveChats();

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch(endpoint, { method: 'POST', body: formData });
    const data = await res.json();

    // Remove the loading message
    chat.messages = chat.messages.filter(m => !m.text.startsWith('Dosya yukleniyor'));

    if (data.error) {
      chat.messages.push({ role: 'system', text: 'Hata: ' + data.error });
    } else if (isUyap) {
      const b = data.belge || {};
      let text = `Belge analizi: ${data.filename}\n`;
      if (b.konu) text += `Konu: ${b.konu}\n`;
      if (b.dosya_bilgisi) text += `Dosya: ${b.dosya_bilgisi.dosya_no || ''} | ${b.dosya_bilgisi.dosya_tur || ''}\n`;
      if (b.taraflar && b.taraflar.length > 0) text += `Taraflar: ${b.taraflar.map(t => t.ad + ' (' + t.rol + ')').join(', ')}\n`;
      if (data.referanslar && data.referanslar.length > 0) {
        text += `\nReferanslar:\n`;
        data.referanslar.forEach(r => text += `- ${r.label}: ${r.value}\n`);
      }
      chat.messages.push({ role: 'assistant', text });
      if (chat.title === 'Yeni Sohbet') {
        chat.title = `EYP: ${b.dosya_bilgisi?.dosya_no || file.name}`;
        renderChatList();
      }
    } else {
      let text = `PDF: ${data.filename} (${data.metadata?.pages || '?'} sayfa)\n`;
      text += `Metin uzunlugu: ${data.full_text_length || 0} karakter\n`;
      if (data.references && data.references.length > 0) {
        text += `\nReferanslar:\n`;
        data.references.forEach(r => text += `- ${r.label}: ${r.value}\n`);
      }
      chat.messages.push({ role: 'assistant', text });
      if (chat.title === 'Yeni Sohbet') {
        chat.title = `PDF: ${file.name}`;
        renderChatList();
      }
    }
  } catch(e) {
    chat.messages = chat.messages.filter(m => !m.text.startsWith('Dosya yukleniyor'));
    chat.messages.push({ role: 'system', text: 'Yukleme hatasi.' });
  }

  renderChat();
  saveChats();
}

// ===== Provider/Model Config =====
function onProviderChange() {
  currentProvider = document.getElementById('llm-provider').value;
  updateModelDropdown();
  updateApiKeyVisibility();
  localStorage.setItem('llm-provider', currentProvider);
}

function updateModelDropdown() {
  const sel = document.getElementById('llm-model');
  const provider = PROVIDERS[currentProvider];
  sel.innerHTML = '';
  provider.models.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m; opt.textContent = m;
    if (m === (currentModel || provider.default_model)) opt.selected = true;
    sel.appendChild(opt);
  });
  currentModel = sel.value;
  localStorage.setItem('llm-model', currentModel);
}

function updateApiKeyVisibility() {
  const provider = PROVIDERS[currentProvider];
  const keyInput = document.getElementById('llm-api-key');
  const saveBtn = document.querySelector('.save-btn');
  if (provider.needs_key) {
    keyInput.style.display = 'block';
    saveBtn.style.display = 'block';
  } else {
    keyInput.style.display = 'none';
    saveBtn.style.display = 'none';
  }
  updateStatusBadge();
}

function updateStatusBadge() {
  const badge = document.getElementById('llm-status-badge');
  const provider = PROVIDERS[currentProvider];
  if (!provider.needs_key) {
    badge.textContent = 'Yerel LLM';
    badge.className = 'llm-status local';
  } else if (savedApiKey) {
    badge.textContent = provider.name;
    badge.className = 'llm-status connected';
  } else {
    badge.textContent = 'API Key Gerekli';
    badge.className = 'llm-status disconnected';
  }
}

async function saveConfig() {
  const provider = document.getElementById('llm-provider').value;
  const model = document.getElementById('llm-model').value;
  const apiKey = document.getElementById('llm-api-key').value.trim();

  if (PROVIDERS[provider].needs_key && !apiKey && !savedApiKey) {
    alert('Bu saglayici icin API anahtari gerekli!');
    return;
  }

  try {
    await fetch('/api/chat/configure', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ provider, api_key: apiKey, model })
    });
  } catch(e) {}

  if (apiKey) {
    savedApiKey = apiKey;
    localStorage.setItem('llm-api-key', apiKey);
  }
  currentProvider = provider;
  currentModel = model;
  localStorage.setItem('llm-provider', provider);
  localStorage.setItem('llm-model', model);
  document.getElementById('llm-api-key').value = '';
  updateStatusBadge();
}

// ===== Drag & Drop =====
const dropOverlay = document.getElementById('file-drop-overlay');
document.addEventListener('dragover', e => { e.preventDefault(); dropOverlay.classList.add('active'); });
document.addEventListener('dragleave', e => { if (e.relatedTarget === null) dropOverlay.classList.remove('active'); });
document.addEventListener('drop', e => {
  e.preventDefault();
  dropOverlay.classList.remove('active');
  const file = e.dataTransfer.files[0];
  if (file) handleFileUpload(file);
});

// ===== Input Handling =====
function handleKeyDown(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

// ===== Module Status =====
(async function() {
  try {
    const res = await fetch('/health');
    const data = await res.json();
    const grid = document.getElementById('module-grid');
    grid.innerHTML = '';
    if (data.modules) {
      for (const [name, ok] of Object.entries(data.modules)) {
        const div = document.createElement('div');
        div.className = 'module-item ' + (ok ? 'ok' : 'fail');
        div.textContent = (ok ? '' : '') + ' ' + name;
        grid.appendChild(div);
      }
    }
  } catch(e) {
    document.getElementById('module-grid').innerHTML = '<div style="color:var(--danger)">Sunucu durumu alinamadi</div>';
  }
})();

// ===== Init =====
document.getElementById('llm-provider').value = currentProvider;
updateModelDropdown();
updateApiKeyVisibility();

if (activeChatId) {
  renderChatList();
  renderChat();
} else if (chats.length > 0) {
  activeChatId = chats[0].id;
  localStorage.setItem('turkiye_mcp_active_chat', activeChatId);
  renderChatList();
  renderChat();
}

document.getElementById('llm-model').addEventListener('change', function() {
  currentModel = this.value;
  localStorage.setItem('llm-model', currentModel);
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