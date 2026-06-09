#!/usr/bin/env python3
"""Türkiye MCP Server - ASGI Application with Web Dashboard.

Railway deployment için ASGI uygulaması:
- / → Web dashboard (tüm araçlar ve kullanım bilgisi)
- /sse → MCP SSE endpoint
- /messages → MCP message endpoint
- /health → JSON health check
"""

import os
import sys
import json
import logging
import time
import re
import hashlib
import tempfile
import threading
import functools
import pathlib
from collections import defaultdict
from datetime import date
from typing import Any, Dict, Optional, List
from datetime import date, timedelta

import httpx
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import HTMLResponse, JSONResponse, StreamingResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from fastmcp import FastMCP

try:
    import workspace  # Sunucu taraflı klasör/oturum/dosya kalıcılığı
    WORKSPACE_AVAILABLE = True
except Exception as _ws_err:  # pragma: no cover
    workspace = None
    WORKSPACE_AVAILABLE = False

try:
    import skills as skills_engine  # Uzmanlık yönergesi (skill) sistemi
    SKILLS_AVAILABLE = True
except Exception:
    skills_engine = None
    SKILLS_AVAILABLE = False

try:
    import memory as memory_mod
    MEMORY_AVAILABLE = True
except Exception:
    memory_mod = None
    MEMORY_AVAILABLE = False

try:
    import deadlines as deadlines_mod
    DEADLINES_AVAILABLE = True
except Exception:
    deadlines_mod = None
    DEADLINES_AVAILABLE = False

try:
    import computer_tools
    COMPUTER_TOOLS_AVAILABLE = True
except Exception:
    COMPUTER_TOOLS_AVAILABLE = False

try:
    import dava_kartlari as dava_mod
    DAVA_AVAILABLE = True
except Exception:
    dava_mod = None
    DAVA_AVAILABLE = False

try:
    import backup as backup_mod
    BACKUP_AVAILABLE = True
except Exception:
    backup_mod = None
    BACKUP_AVAILABLE = False

try:
    from gateway import LLMGateway  # Merkezi LLM yönlendirme + failover
    import gateway as gateway_mod
    GATEWAY_AVAILABLE = True
except Exception:
    LLMGateway = None
    GATEWAY_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastMCP(name="Türkiye MCP Server", version="1.0.0")

# ============================================================
# MERKEZİ TOOL ÖNBELLEĞİ (TTL bazlı)
# ============================================================
class ToolCache:
    """Merkezi TTL önbellek — MCP tool sonuçlarını saklar."""

    DEFAULT_TTL = 3600  # 1 saat
    TTL_OVERRIDES: Dict[str, int] = {
        # Borsa — hızlı değişen veriler
        "get_bist_stock": 300, "get_fx_rates": 300, "get_crypto": 120,
        "get_asgari_ucret": 86400, "get_prim_matrahi": 86400, "get_tax_calendar": 86400,
        # Hukuk — kararlar değişmez
        "search_bedesten_unified": 1800, "get_bedesten_document": 86400,
        "search_anayasa_unified": 1800, "get_anayasa_document": 86400,
        "search_emsal": 1800, "get_emsal_document": 86400,
        "search_kik_v2_decisions": 1800, "get_kik_document": 86400,
        "search_rekabet_kurumu": 1800, "get_rekabet_document": 86400,
        "search_sayistay_unified": 1800, "search_kvkk_decisions": 1800,
        "search_bddk_decisions": 1800, "search_sigorta_tahkim": 1800,
        "search_uyusmazlik": 1800,
        # Mevzuat — kanunlar değişmez
        "search_mevzuat_bedesten": 1800, "get_mevzuat_document": 86400,
        "get_mevzuat_article": 86400, "get_mevzuat_article_tree": 86400,
        "search_mevzuat": 1800,
        # Resmi Gazete — günlük
        "search_resmi_gazete": 1800, "get_daily_bulletin": 3600,
    }

    def __init__(self):
        self._store: Dict[str, tuple[float, Any]] = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    def _make_key(self, tool_name: str, args: dict) -> str:
        args_json = json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)
        args_hash = hashlib.sha256(args_json.encode()).hexdigest()[:12]
        return f"{tool_name}:{args_hash}"

    def get(self, tool_name: str, args: dict) -> Optional[str]:
        key = self._make_key(tool_name, args)
        ttl = self.TTL_OVERRIDES.get(tool_name, self.DEFAULT_TTL)
        with self._lock:
            if key in self._store:
                ts, value = self._store[key]
                if time.time() - ts < ttl:
                    self._hits += 1
                    return value
                del self._store[key]
            self._misses += 1
            return None

    def put(self, tool_name: str, args: dict, value: str) -> None:
        key = self._make_key(tool_name, args)
        with self._lock:
            self._store[key] = (time.time(), value)

    def clear(self) -> int:
        with self._lock:
            count = len(self._store)
            self._store.clear()
            self._hits = 0
            self._misses = 0
            return count

    def stats(self) -> dict:
        with self._lock:
            total = self._hits + self._misses
            return {
                "entries": len(self._store),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{self._hits / total * 100:.1f}%" if total > 0 else "0%",
            }

TOOL_CACHE = ToolCache()


def cached_tool(ttl: Optional[int] = None):
    """MCP tool sonuçlarını önbelleğe alan dekoratör.

    Kullanımı:
        @app.tool(description="...", annotations={...})
        @cached_tool()  # varsayılan TTL
        async def search_...(...) -> str:
            ...

    Hatalar (❌ ile başlayan) önbelleğe alınmaz.
    """
    def decorator(fn):
        tool_name = fn.__name__
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            cache_args = {k: v for k, v in kwargs.items()
                         if v is not None and v != "" and v != [] and v != {}}
            cached = TOOL_CACHE.get(tool_name, cache_args)
            if cached is not None:
                return cached
            result = await fn(*args, **kwargs)
            if result and not result.startswith("❌"):
                TOOL_CACHE.put(tool_name, cache_args, result)
            return result
        return wrapper
    return decorator


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
    from mevzuat_search_module.bedesten_client import BedestenClient as MevzuatBedestenClient
    from mevzuat_search_module.bedesten_models import BedSearchResult
    mevzuat_bedesten_client = MevzuatBedestenClient()
    MODULES_AVAILABLE["mevzuat_bedesten"] = True
except Exception as e:
    logger.warning(f"❌ Mevzuat Bedesten: {e}")
    MODULES_AVAILABLE["mevzuat_bedesten"] = False

try:
    from mevzuat_search_module.mevzuat_client import MevzuatApiClientNew
    from mevzuat_search_module.mevzuat_models import MevzuatSearchRequestNew
    mevzuat_new_client = MevzuatApiClientNew()
    MODULES_AVAILABLE["mevzuat_new"] = True
except Exception as e:
    logger.warning(f"❌ Mevzuat New: {e}")
    MODULES_AVAILABLE["mevzuat_new"] = False

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
    @cached_tool()
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
    @cached_tool()
    async def get_daily_bulletin(tarih: str = "") -> str:
        try:
            target_date = date.fromisoformat(tarih) if tarih else date.today()
            bultens = await resmi_gazete_client.get_daily_bulletin(target_date)
            result = f"# Resmi Gazete - {target_date.strftime('%d.%m.%Y')}\n\n**Toplam:** {len(bultens)} belge\n\n"
            for item in bultens: result += f"- **{item.baslik}** ({item.belge_turu})\n"
            return result if bultens else "Bülten bulunamadı."
        except Exception as e: return f"❌ Hata: {str(e)}"

    @app.tool(description="Son N günün mali belgelerini getirir.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    @cached_tool()
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
    @cached_tool()
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
    @cached_tool()
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
    @cached_tool()
    async def check_efatura_taxpayer(vergi_kimlik_no: str) -> str:
        try:
            result = await ivd_client.check_efatura_taxpayer(vergi_kimlik_no)
            return f"# e-Fatura Sorgulama\n\n**VKN/TCKN:** {result.vergi_kimlik_no}\n**Unvan:** {result.unvan or '-'}\n**e-Fatura:** {'✅' if result.efatura_mukellef else '❌'}\n**e-İrsaliye:** {'✅' if result.eirsaliye_mukellef else '❌'}"
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("sgk"):
    @app.tool(description="Asgari ücret bilgileri.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    @cached_tool()
    async def get_asgari_ucret(yil: int = None) -> str:
        try:
            data = await sgk_client.get_asgari_ucret(yil)
            return f"# Asgari Ücret - {data.yil}\n\n| | Tutar |\n|---|---|\n| Aylık Brüt | {data.aylik_brut:,.2f} TL |\n| Aylık Net | {data.aylik_net:,.2f} TL |\n| Saatlik | {data.saatlik_brut:,.2f} TL |"
        except Exception as e: return f"❌ Hata: {str(e)}"

    @app.tool(description="SGK prim matrahı ve oranları.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    @cached_tool()
    async def get_prim_matrahi(yil: int = None) -> str:
        try:
            data = await sgk_client.get_prim_matrahi(yil)
            return f"# SGK Prim - {data.yil}\n\n| | Oran |\n|---|---|\n| SGK İşçi | %{data.sgk_isci_premi} |\n| SGK İşveren | %{data.sgk_isveren_premi} |\n| İşsizlik İşçi | %{data.issizlik_isci_premi} |\n| İşsizlik İşveren | %{data.issizlik_isveren_premi} |"
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("turmob"):
    @app.tool(description="TÜRMOB pratik bilgileri.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    @cached_tool()
    async def get_turmob_pratik_bilgiler(kategori: str = "") -> str:
        try:
            bilgiler = await turmob_client.get_pratik_bilgiler(kategori if kategori else None)
            result = "# TÜRMOB Pratik Bilgiler\n\n"
            for b in bilgiler: result += f"{b.icerik}\n\n---\n\n"
            return result
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("ismmmo"):
    @app.tool(description="İSMMMO pratik bilgileri.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    @cached_tool()
    async def get_ismmmo_pratik_bilgiler(kategori: str = "") -> str:
        try:
            bilgiler = await ismmmo_client.get_pratik_bilgiler(kategori if kategori else None)
            result = "# İSMMMO Pratik Bilgiler\n\n"
            for b in bilgiler: result += f"## {b.baslik}\n\n{b.icerik}\n\n---\n\n"
            return result
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("bedesten"):
    @app.tool(description="Birden fazla Türk mahkemesinde birleştirilmiş arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    @cached_tool()
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
    @cached_tool()
    async def get_bedesten_document(document_id: str) -> str:
        try:
            doc = await bedesten_client.get_document_as_markdown(document_id)
            if doc and doc.markdown_content: return doc.markdown_content[:8000]
            return "Belge bulunamadı."
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("anayasa"):
    @app.tool(description="Anayasa Mahkemesi kararlarında arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    @cached_tool()
    async def search_anayasa_unified(keywords: str, decision_type: str = "bireysel_basvuru", page: int = 1) -> str:
        try:
            request = AnayasaUnifiedSearchRequest(decision_type=decision_type, keywords=[keywords], page_to_fetch=page, results_per_page=10)
            result = await anayasa_client.search_unified(request)
            return str(result.model_dump())[:4000]
        except Exception as e: return f"❌ Hata: {str(e)}"

    @app.tool(description="Anayasa Mahkemesi karar tam metnini getirir (sayfalı).", annotations={"readOnlyHint": True, "openWorldHint": False, "idempotentHint": True})
    @cached_tool()
    async def get_anayasa_document(document_url: str, page_number: int = 1) -> str:
        try:
            result = await anayasa_client.get_document_unified(document_url, page_number)
            parts = []
            if result.markdown_chunk:
                parts.append(result.markdown_chunk[:7500])
            if result.is_paginated:
                parts.append(f"\n\n---\nSayfa {result.current_page}/{result.total_pages}")
            content = "\n".join(p for p in parts if p)
            return content[:8000] if content else "Belge bulunamadı."
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("kik"):
    @app.tool(description="KİK kararlarında arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    @cached_tool()
    async def search_kik_v2_decisions(decision_type: str = "uyusmazlik", keyword: str = "", karar_no: str = "") -> str:
        try:
            response = await kik_client.search_decisions(decision_type=KikV2DecisionType(decision_type), karar_metni=keyword, karar_no=karar_no)
            result = f"# KİK ({decision_type})\n\n**Toplam:** {response.total_records}\n\n"
            for d in response.decisions[:10]: result += f"- **{d.kararNo or '-'}** | {d.basvuran or '-'}\n"
            return result
        except Exception as e: return f"❌ Hata: {str(e)}"

    @app.tool(description="KİK kurul kararı tam metnini getirir.", annotations={"readOnlyHint": True, "openWorldHint": False, "idempotentHint": True})
    @cached_tool()
    async def get_kik_document(document_id: str) -> str:
        try:
            result = await kik_client.get_document_markdown(document_id)
            if result and result.markdown_content:
                return result.markdown_content[:8000]
            if result and result.error_message:
                return f"❌ Hata: {result.error_message}"
            return "Belge bulunamadı."
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("rekabet"):
    @app.tool(description="Rekabet Kurumu kararlarında arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    @cached_tool()
    async def search_rekabet_kurumu(keyword: str = "", page: int = 1) -> str:
        try:
            result = await rekabet_client.search_decisions(RekabetKurumuSearchRequest(sayfaAdi=keyword, page=page))
            return str(result.model_dump())[:4000]
        except Exception as e: return f"❌ Hata: {str(e)}"

    @app.tool(description="Rekabet Kurumu karar tam metnini getirir (sayfalı PDF).", annotations={"readOnlyHint": True, "openWorldHint": False, "idempotentHint": True})
    @cached_tool()
    async def get_rekabet_document(karar_id: str, page: int = 1) -> str:
        try:
            result = await rekabet_client.get_decision_document(karar_id, page)
            parts = []
            if result.title_on_landing_page:
                parts.append(f"# {result.title_on_landing_page}")
            if result.markdown_chunk:
                parts.append(result.markdown_chunk[:7500])
            if result.is_paginated:
                parts.append(f"\n\n---\nSayfa {result.current_page}/{result.total_pages}")
            if result.error_message:
                parts.append(f"\n\n⚠️ {result.error_message}")
            content = "\n".join(p for p in parts if p)
            return content[:8000] if content else "Belge bulunamadı."
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("sayistay"):
    @app.tool(description="Sayıştay kararlarında arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    @cached_tool()
    async def search_sayistay_unified(decision_type: str = "genel_kurul", keyword: str = "", page: int = 1) -> str:
        try:
            result = await sayistay_client.search_unified(SayistayUnifiedSearchRequest(decision_type=decision_type, start=(page-1)*10, length=10, karar_tamami=keyword))
            return str(result.model_dump())[:4000]
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("kvkk"):
    @app.tool(description="KVKK kararlarında arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    @cached_tool()
    async def search_kvkk_decisions(keyword: str = "", page: int = 1) -> str:
        try:
            result = await kvkk_client.search_decisions(KvkkSearchRequest(keywords=keyword, page=page))
            return str(result.model_dump())[:4000]
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("bddk"):
    @app.tool(description="BDDK kararlarında arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    @cached_tool()
    async def search_bddk_decisions(keyword: str = "", page: int = 1) -> str:
        try:
            result = await bddk_client.search_decisions(BddkSearchRequest(keywords=keyword, page=page))
            return str(result.model_dump())[:4000]
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("sigorta_tahkim"):
    @app.tool(description="Sigorta Tahkim kararlarında arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    @cached_tool()
    async def search_sigorta_tahkim(keyword: str = "", page: int = 1) -> str:
        try:
            result = await sigorta_tahkim_client.search_decisions(SigortaTahkimSearchRequest(keywords=keyword, page=page))
            return str(result.model_dump())[:4000]
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("uyusmazlik"):
    @app.tool(description="Uyuşmazlık Mahkemesi kararlarında arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    @cached_tool()
    async def search_uyusmazlik(keyword: str = "", page: int = 1) -> str:
        try:
            result = await uyusmazlik_client.search_decisions(UyusmazlikSearchRequest(icerik=keyword))
            return str(result.model_dump())[:4000]
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("emsal"):
    @app.tool(description="EMSAL kararlarda arama.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    @cached_tool()
    async def search_emsal(keyword: str = "", page: int = 1) -> str:
        try:
            result = await emsal_client.search_detailed_decisions(EmsalSearchRequest(keyword=keyword, page_number=page, page_size=10))
            if result.data and result.data.data:
                output = f"# EMSAL\n\n**Toplam:** {result.data.recordsTotal}\n\n"
                for d in result.data.data[:10]: output += f"- **{d.daire or '-'}** | {d.esasNo or '-'} | {d.kararNo or '-'}\n"
                return output
            return "Sonuç yok."
        except Exception as e: return f"❌ Hata: {str(e)}"

    @app.tool(description="EMSAL karar tam metnini getirir.", annotations={"readOnlyHint": True, "openWorldHint": False, "idempotentHint": True})
    @cached_tool()
    async def get_emsal_document(id: str) -> str:
        try:
            doc = await emsal_client.get_decision_document_as_markdown(id)
            if doc and doc.markdown_content:
                return doc.markdown_content[:8000]
            return "Belge bulunamadı."
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("mevzuat_bedesten"):
    @app.tool(description="Mevzuat (kanun, KHK, yönetmelik vb.) araması.", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    @cached_tool()
    async def search_mevzuat_bedesten(phrase: str = "", mevzuat_adi: str = "", mevzuat_tur: str = "", page: int = 1) -> str:
        try:
            tur_list = [mevzuat_tur] if mevzuat_tur else None
            result = await mevzuat_bedesten_client.search_documents(
                phrase=phrase, mevzuat_adi=mevzuat_adi, mevzuat_tur_list=tur_list,
                page=page, page_size=10
            )
            if result.error_message:
                return f"❌ Hata: {result.error_message}"
            output = f"# Mevzuat Arama\n\n**Toplam:** {result.total_results}\n\n"
            for doc in result.documents[:10]:
                output += f"- **{doc.mevzuat_adi}** | No: {doc.mevzuat_no} | ID: `{doc.mevzuat_id}`\n"
            return output if result.documents else "Sonuç bulunamadı."
        except Exception as e: return f"❌ Hata: {str(e)}"

    @app.tool(description="Mevzuat tam metnini getirir.", annotations={"readOnlyHint": True, "openWorldHint": False, "idempotentHint": True})
    @cached_tool()
    async def get_mevzuat_document(mevzuat_id: str) -> str:
        try:
            doc = await mevzuat_bedesten_client.get_document_content(mevzuat_id)
            if doc.error_message:
                return f"❌ Hata: {doc.error_message}"
            if doc.content:
                return doc.content[:8000]
            return "Belge bulunamadı."
        except Exception as e: return f"❌ Hata: {str(e)}"

    @app.tool(description="Mevzuat belirli bir maddenin içeriğini getirir.", annotations={"readOnlyHint": True, "openWorldHint": False, "idempotentHint": True})
    @cached_tool()
    async def get_mevzuat_article(madde_id: str) -> str:
        try:
            doc = await mevzuat_bedesten_client.get_article_content(madde_id)
            if doc.error_message:
                return f"❌ Hata: {doc.error_message}"
            if doc.content:
                return doc.content[:8000]
            return "Madde bulunamadı."
        except Exception as e: return f"❌ Hata: {str(e)}"

    @app.tool(description="Mevzuat madde ağacını (içindekiler) getirir.", annotations={"readOnlyHint": True, "openWorldHint": False, "idempotentHint": True})
    @cached_tool()
    async def get_mevzuat_article_tree(mevzuat_id: str) -> str:
        try:
            nodes, error = await mevzuat_bedesten_client.get_article_tree(mevzuat_id)
            if error:
                return f"❌ Hata: {error}"
            if not nodes:
                return "Madde ağacı bulunamadı."
            lines = ["# Madde Ağacı\n"]
            def render_tree(node_list, indent=0):
                for node in node_list:
                    prefix = "  " * indent
                    title = node.madde_baslik or node.title or ""
                    madde_no = node.madde_no or ""
                    madde_id = node.madde_id or ""
                    label = f"{prefix}- **Madde {madde_no}** {title}" if madde_no else f"{prefix}- {title or '(başlıksız)'}"
                    if madde_id:
                        label += f" [ID: `{madde_id}`]"
                    lines.append(label)
                    if node.children:
                        render_tree(node.children, indent + 1)
            render_tree(nodes)
            return "\n".join(lines)[:8000]
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("mevzuat_new"):
    @app.tool(description="Mevzuat.gov.tr üzerinde kanun, KHK, yönetmelik araması (alternatif kaynak).", annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True})
    @cached_tool()
    async def search_mevzuat(keyword: str = "", mevzuat_tur: str = "Kanun", sayfa: int = 1) -> str:
        try:
            request = MevzuatSearchRequestNew(
                aranacak_ifade=keyword or None,
                mevzuat_tur=mevzuat_tur,
                page_number=sayfa,
                page_size=10
            )
            result = await mevzuat_new_client.search_documents(request)
            if result.error_message:
                return f"❌ Hata: {result.error_message}"
            output = f"# Mevzuat Arama (mevzuat.gov.tr)\n\n**Toplam:** {result.total_results}\n\n"
            for doc in result.documents[:10]:
                output += f"- **{doc.mev_adi}** | No: {doc.mevzuat_no} | Tür: {doc.mevzuat_tur}\n"
            return output if result.documents else "Sonuç bulunamadı."
        except Exception as e: return f"❌ Hata: {str(e)}"

if MODULES_AVAILABLE.get("ihale"):
    @app.tool(description="Kamu ihalelerinde arama (EKAP v2).", annotations={"readOnlyHint": True, "openWorldHint": True})
    @cached_tool()
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
    @cached_tool()
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
    @cached_tool()
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
    @cached_tool()
    async def get_bist_stock(symbol: str) -> str:
        try:
            return str(await borsa_client.get_bist_stock(symbol))[:4000]
        except Exception as e: return f"❌ Hata: {str(e)}"

    @app.tool(description="Döviz kurları.", annotations={"readOnlyHint": True, "openWorldHint": True})
    @cached_tool()
    async def get_fx_rates() -> str:
        try:
            return str(await borsa_client.get_fx_rates())[:4000]
        except Exception as e: return f"❌ Hata: {str(e)}"

    @app.tool(description="Kripto para verileri.", annotations={"readOnlyHint": True, "openWorldHint": True})
    @cached_tool()
    async def get_crypto(symbol: str) -> str:
        try:
            return str(await borsa_client.get_crypto(symbol))[:4000]
        except Exception as e: return f"❌ Hata: {str(e)}"

if DEADLINES_AVAILABLE:
    @app.tool(description="Hukuki süreleri listele.", annotations={"readOnlyHint": True, "idempotentHint": True})
    async def list_deadlines(status: str = "") -> str:
        try:
            dls = deadlines_mod.list_deadlines(status if status else None)
            if not dls:
                return "Süre bulunamadı."
            result = "# Hukuki Süreler\n\n"
            cat_labels = {k: v["label"] for k, v in deadlines_mod.CATEGORY_DEFAULTS.items()}
            for d in dls:
                cat = cat_labels.get(d["category"], d["category"])
                status_icon = {"active": "🟡", "completed": "✅", "expired": "🔴"}.get(d.get("status", "active"), "⚪")
                result += f"{status_icon} **{d['title']}** ({cat})\n   Başlangıç: {d['start_date']} | Bitiş: {d['deadline_date']} | Süre: {d['days_allowed']} gün | Durum: {d.get('status', 'active')}\n\n"
            return result[:4000]
        except Exception as e:
            return f"❌ Hata: {str(e)}"

    @app.tool(description="Yeni hukuki süre ekle.", annotations={"readOnlyHint": False, "idempotentHint": False})
    async def add_deadline(category: str, title: str, start_date: str, days_allowed: int = 0, description: str = "") -> str:
        try:
            dl = deadlines_mod.add_deadline(category, title, start_date, days_allowed if days_allowed > 0 else None, description)
            cat_labels = {k: v["label"] for k, v in deadlines_mod.CATEGORY_DEFAULTS.items()}
            return f"✅ Süre eklendi: **{dl['title']}** ({cat_labels.get(dl['category'], dl['category'])})\nBitiş tarihi: {dl['deadline_date']} ({dl['days_allowed']} gün)"
        except ValueError as e:
            return f"❌ Hata: {str(e)}"
        except Exception as e:
            return f"❌ Hata: {str(e)}"

    @app.tool(description="Süreyi tamamlandı olarak işaretle.", annotations={"readOnlyHint": False, "idempotentHint": False})
    async def complete_deadline(id: str) -> str:
        try:
            result = deadlines_mod.mark_completed(id)
            if result:
                return f"✅ Süre tamamlandı: **{result['title']}**"
            return "❌ Süre bulunamadı."
        except Exception as e:
            return f"❌ Hata: {str(e)}"

    @app.tool(description="Süreyi sil.", annotations={"readOnlyHint": False, "idempotentHint": False})
    async def delete_deadline(id: str) -> str:
        try:
            if deadlines_mod.delete_deadline(id):
                return "✅ Süre silindi."
            return "❌ Süre bulunamadı."
        except Exception as e:
            return f"❌ Hata: {str(e)}"

    @app.tool(description="Yaklaşan hukuki süreleri getir.", annotations={"readOnlyHint": True, "idempotentHint": True})
    async def get_upcoming_deadlines(days: int = 30) -> str:
        try:
            upcoming = deadlines_mod.get_upcoming(days)
            if not upcoming:
                return f"Önümüzdeki {days} gün içinde yaklaşan süre yok."
            result = f"# Yaklaşan Süreler ({days} gün)\n\n"
            cat_labels = {k: v["label"] for k, v in deadlines_mod.CATEGORY_DEFAULTS.items()}
            from datetime import date as _date
            today = _date.today()
            for d in upcoming:
                cat = cat_labels.get(d["category"], d["category"])
                try:
                    dl_date = _date.fromisoformat(d["deadline_date"])
                    days_left = (dl_date - today).days
                except Exception:
                    days_left = "?"
                result += f"- **{d['title']}** ({cat}) — bitiş: {d['deadline_date']} ({days_left} gün kaldı)\n"
            return result[:4000]
        except Exception as e:
            return f"❌ Hata: {str(e)}"

    @app.tool(description="Gecikmiş hukuki süreleri getir.", annotations={"readOnlyHint": True, "idempotentHint": True})
    async def get_overdue_deadlines() -> str:
        try:
            overdue = deadlines_mod.get_overdue()
            if not overdue:
                return "Gecikmiş süre yok."
            result = "# 🔴 Gecikmiş Süreler\n\n"
            cat_labels = {k: v["label"] for k, v in deadlines_mod.CATEGORY_DEFAULTS.items()}
            for d in overdue:
                cat = cat_labels.get(d["category"], d["category"])
                result += f"- **{d['title']}** ({cat}) — bitiş: {d['deadline_date']} (GECİKMİŞ!)\n"
            return result[:4000]
        except Exception as e:
            return f"❌ Hata: {str(e)}"

    @app.tool(description="Süre bitiş tarihini hesapla (kaydetmeden).", annotations={"readOnlyHint": True, "idempotentHint": True})
    async def compute_deadline(start_date: str, days: int) -> str:
        try:
            result = deadlines_mod.compute_deadline(start_date, days)
            return f"Bitiş tarihi: {result} (başlangıç: {start_date} + {days} gün, hafta sonu kaydırması dahil)"
        except Exception as e:
            return f"❌ Hata: {str(e)}"

if DAVA_AVAILABLE:
    @app.tool(description="Dava kartlarını listele. Durum veya tür filtresi uygula.", annotations={"readOnlyHint": True, "idempotentHint": True})
    async def list_dava_kartlari(durum: str = "", dava_turu: str = "") -> str:
        try:
            kartlar = dava_mod.list_kartlar(durum=durum if durum else None, dava_turu=dava_turu if dava_turu else None)
            if not kartlar:
                return "Dava kartı bulunamadı."
            lines = [f"**{k['esas_no']}** — {dava_mod.DAVA_TURLERI.get(k['dava_turu'], {}).get('label', k['dava_turu'])} | {dava_mod.DURUMLAR.get(k['durum'], {}).get('label', k['durum'])}"]
            for k in kartlar:
                tarafs = f"{k.get('taraf_muvekkil', '')} vs {k.get('taraf_karsi', '')}".strip(' vs')
                lines.append(f"- {k['esas_no']} | {k['dava_turu']} | {k['durum']} | {k.get('daire', '')} | {tarafs}")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Hata: {str(e)}"

    @app.tool(description="Yeni dava kartı ekle. Esas no ve dava türü zorunlu.", annotations={"readOnlyHint": False, "idempotentHint": False})
    async def add_dava_karti(esas_no: str, dava_turu: str, taraf_muvekkil: str = "", taraf_karsi: str = "", daire: str = "", konu: str = "", acilis_tarihi: str = "", notlar: str = "") -> str:
        try:
            k = dava_mod.add_kart(esas_no=esas_no, dava_turu=dava_turu, taraf_muvekkil=taraf_muvekkil, taraf_karsi=taraf_karsi, daire=daire, konu=konu, acilis_tarihi=acilis_tarihi, notlar=notlar)
            return f"✅ Dava kartı eklendi: {k['id']} — {k['esas_no']} ({dava_mod.DAVA_TURLERI.get(k['dava_turu'], {}).get('label', k['dava_turu'])})"
        except Exception as e:
            return f"❌ Hata: {str(e)}"

    @app.tool(description="Dava kartını güncelle. Durum, esas no, taraf vb. değiştir.", annotations={"readOnlyHint": False, "idempotentHint": False})
    async def update_dava_karti(id: str, durum: str = "", esas_no: str = "", taraf_muvekkil: str = "", taraf_karsi: str = "", daire: str = "", konu: str = "", acilis_tarihi: str = "", sonuc_tarihi: str = "", notlar: str = "", dava_turu: str = "") -> str:
        try:
            kwargs = {}
            if durum: kwargs["durum"] = durum
            if esas_no: kwargs["esas_no"] = esas_no
            if taraf_muvekkil: kwargs["taraf_muvekkil"] = taraf_muvekkil
            if taraf_karsi: kwargs["taraf_karsi"] = taraf_karsi
            if daire: kwargs["daire"] = daire
            if konu: kwargs["konu"] = konu
            if acilis_tarihi: kwargs["acilis_tarihi"] = acilis_tarihi
            if sonuc_tarihi: kwargs["sonuc_tarihi"] = sonuc_tarihi
            if notlar: kwargs["notlar"] = notlar
            if dava_turu: kwargs["dava_turu"] = dava_turu
            k = dava_mod.update_kart(id, **kwargs)
            if k:
                return f"✅ Güncellendi: {k['esas_no']} — durum: {dava_mod.DURUMLAR.get(k['durum'], {}).get('label', k['durum'])}"
            return "❌ Kart bulunamadı."
        except Exception as e:
            return f"❌ Hata: {str(e)}"

    @app.tool(description="Dava kartını sil.", annotations={"readOnlyHint": False, "idempotentHint": False})
    async def delete_dava_karti(id: str) -> str:
        try:
            if dava_mod.delete_kart(id):
                return f"✅ Dava kartı silindi: {id}"
            return "❌ Kart bulunamadı."
        except Exception as e:
            return f"❌ Hata: {str(e)}"

    @app.tool(description="ID ile tek dava kartı getir.", annotations={"readOnlyHint": True, "idempotentHint": True})
    async def get_dava_karti(id: str) -> str:
        try:
            k = dava_mod.get_kart(id)
            if k:
                tarafs = f"{k.get('taraf_muvekkil', '')} vs {k.get('taraf_karsi', '')}".strip(' vs')
                return f"**{k['esas_no']}** | {dava_mod.DAVA_TURLERI.get(k['dava_turu'], {}).get('label', k['dava_turu'])} | {dava_mod.DURUMLAR.get(k['durum'], {}).get('label', k['durum'])}\nMahkeme: {k.get('daire', '-')}\nTaraf: {tarafs or '-'}\nKonu: {k.get('konu', '-')}\nAçılış: {k.get('acilis_tarihi', '-')}\nSonuç: {k.get('sonuc_tarihi', '-')}"
            return "❌ Kart bulunamadı."
        except Exception as e:
            return f"❌ Hata: {str(e)}"

    @app.tool(description="Dava kartlarında arama. Esas no, daire, taraf, konu'da arar.", annotations={"readOnlyHint": True, "idempotentHint": True})
    async def search_dava_kartlari(query: str) -> str:
        try:
            kartlar = dava_mod.search_kartlar(query)
            if not kartlar:
                return f"'{query}' ile eşleşen dava kartı bulunamadı."
            lines = [f"**{len(kartlar)} sonuç:**"]
            for k in kartlar:
                lines.append(f"- {k['esas_no']} | {k['dava_turu']} | {k['durum']} | {k.get('taraf_muvekkil', '')} vs {k.get('taraf_karsi', '')}")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Hata: {str(e)}"

    @app.tool(description="Dava kartına süre bağla.", annotations={"readOnlyHint": False, "idempotentHint": False})
    async def link_deadline_to_dava(dava_id: str, deadline_id: str) -> str:
        try:
            k = dava_mod.link_deadline(dava_id, deadline_id)
            if k:
                return f"✅ Süre bağlandı: {k['esas_no']} ← {deadline_id}"
            return "❌ Kart veya süre bulunamadı."
        except Exception as e:
            return f"❌ Hata: {str(e)}"

if BACKUP_AVAILABLE:
    @app.tool(description="Veri yedeği oluştur. Çalışma alanı, bellek, süreler ve dava kartlarını .zip dosyasına yedekler.", annotations={"readOnlyHint": False, "idempotentHint": False})
    async def create_backup() -> str:
        try:
            result = backup_mod.create_backup()
            if result.get("ok"):
                size_str = backup_mod._format_size(result["size"])
                return f"✅ Yedek oluşturuldu: {result['filename']} ({size_str}, {result['files']} dosya)"
            return f"❌ Yedek oluşturulamadı: {result.get('error', 'Bilinmeyen hata')}"
        except Exception as e:
            return f"❌ Hata: {str(e)}"

    @app.tool(description="Mevcut yedek dosyalarını listele.", annotations={"readOnlyHint": True, "idempotentHint": True})
    async def list_backups() -> str:
        try:
            backups = backup_mod.list_backups()
            if not backups:
                return "Henüz yedek dosyası yok."
            lines = [f"**{len(backups)} yedek bulundu:**"]
            for b in backups:
                lines.append(f"- {b['filename']} ({b['size_formatted']}, {b['created_str']})")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Hata: {str(e)}"

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
# WEB DASHBOARD — static/template dosyalardan sunulur
# ============================================================

def _base_path() -> pathlib.Path:
    """Frontend dosyalari icin temel yol. EXE'de _MEIPASS, gelistirmede dosya dizini."""
    if getattr(sys, 'frozen', False):
        return pathlib.Path(sys._MEIPASS)
    return pathlib.Path(__file__).parent


async def homepage(request):
    try:
        return HTMLResponse((_base_path() / "templates" / "index.html").read_text(encoding="utf-8"))
    except Exception as e:
        import traceback
        return HTMLResponse(f"<pre>Error rendering dashboard:\n{traceback.format_exc()}</pre>", status_code=500)


async def health_endpoint(request):
    try:
        return JSONResponse({
            "status": "ok",
            "version": "1.0.0",
            "modules": MODULES_AVAILABLE,
            "active_count": sum(1 for v in MODULES_AVAILABLE.values() if v),
            "total_count": len(MODULES_AVAILABLE),
            "skills_count": len(skills_engine.load_skills()) if SKILLS_AVAILABLE else 0,
            "workspace": WORKSPACE_AVAILABLE,
            "memory": MEMORY_AVAILABLE,
            "deadlines": DEADLINES_AVAILABLE,
            "dava": DAVA_AVAILABLE,
            "backup": BACKUP_AVAILABLE,
            "computer_tools": COMPUTER_TOOLS_AVAILABLE,
            "date": date.today().isoformat(),
        })
    except Exception as e:
        import traceback
        return JSONResponse({"status": "degraded", "error": str(e)[:200], "modules": {}, "active_count": 0, "total_count": 0}, status_code=200)


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
    @cached_tool()
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
    @cached_tool()
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
    "ollama_cloud": {
        "name": "Ollama Cloud",
        "url": "https://ollama.com/v1/chat/completions",
        "models": [
            "gpt-oss:120b", "gpt-oss:20b", "deepseek-v3.1:671b",
            "qwen3-coder:480b", "glm-4.6", "kimi-k2:1t", "qwen3:235b",
        ],
        "default_model": "gpt-oss:120b",
        "needs_key": True,
    },
    "ollama": {
        "name": "Ollama (Yerel)",
        "url": "http://localhost:11434/v1/chat/completions",
        "models": ["llama3.2", "llama3.1", "mistral", "qwen2.5", "gemma2", "gpt-oss:20b"],
        "default_model": "llama3.2",
        "needs_key": False,
    },
}

# Merkezi LLM Gateway (failover + metrik) — LLM_PROVIDERS üzerinden çalışır
# Kaydedilmiş gateway config'i uygula (varsa)
if GATEWAY_AVAILABLE:
    try:
        _saved_gw_cfg = gateway_mod.load_config()
        if _saved_gw_cfg:
            gateway_mod.apply_config(LLM_PROVIDERS, _saved_gw_cfg)
    except Exception:
        pass
GATEWAY = LLMGateway(LLM_PROVIDERS) if GATEWAY_AVAILABLE else None


# Reasoning (düşünme) destekleyen model aileleri — reasoning_effort yalnızca bunlara gönderilir
_REASONING_MODEL_HINTS = (
    "gpt-oss", "deepseek-v3", "deepseek-r1", "qwen3", "glm-4.6", "glm-4-6",
    "kimi", "minimax-m2", "magistral", "reasoning", "nemotron", "exaone-deep",
    "smallthinker", "thinking",
)


def _is_reasoning_model(model: str) -> bool:
    """Model adından reasoning/düşünme modeli olup olmadığını tahmin eder."""
    m = (model or "").lower()
    return any(h in m for h in _REASONING_MODEL_HINTS)


# Geriye uyumluluk: OPENROUTER_API_KEY environment variable
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
RATE_LIMIT_PER_IP = 10  # IP başına günlük istek limiti
ip_rate_limits: dict[str, list[float]] = defaultdict(list)

SYSTEM_PROMPT = """Sen Türkiye MCP asistanısın — deneyimli bir Türk avukatı ve mali müşavir gibi davranan bir uzman yapay zekâsın. Türk hukuk, mali, ihale ve piyasa verileri konusunda uzmansın.

Kullanıcıya Türkçe, profesyonel ama anlaşılır bir dille yanıt ver. Eldeki MCP araç sonuçlarını kullanarak doğru, gerekçeli ve kaynaklı cevaplar ver.

TEMEL İLKELER:
1. **Asla uydurma yapma.** Karar/esas numarası, tutar, oran gibi verileri YALNIZCA MCP araç sonuçlarından veya yüklenen belgeden al. Bilgi yoksa "bu veriyi şu an doğrulayamıyorum" de.
2. **Belge varsa önce onu anla:** Yüklenen belgenin türünü, taraflarını ve konusunu kısaca özetle, sonra soruyu yanıtla.
3. **İlgililik kontrolü:** Kullanıcının sorusu yüklenen belgeyle ilgisizse, önce kibarca "Bu soru yüklediğiniz belge ile doğrudan ilgili görünmüyor" diye belirt; ardından yine de elinden geldiğince yardımcı ol.
4. **Çapraz hafıza:** Sağlanan "ilgili geçmiş kayıtlar" varsa, uygun yerde "Çalışma alanınızdaki '…' kaydında benzer bir durum var" şeklinde hatırlat.

YANIT FORMATI:
- Markdown kullan (tablo, liste, kalın yazı). Kararları daire/esas/karar no ve tarihiyle, her birinin ortaya koyduğu ilkeyle aktar.
- Hukuki/mali terimleri kısaca açıkla; ilgili mevzuat (kanun/madde) atıflarını ekle.
- Yanıtı **📋 Kaynak** bölümüyle bitir (kullanılan araç/veri tabanı).
- Kesin tavsiye değil, bilgilendirme niteliğinde yaz; nihai karar için teyide/avukata yönlendir.

SKILL OLUŞTURMA: Kullanıcı "yeni skill ekle" veya "skill oluştur" dediğinde, aşağıdaki formatta bir SKILL.md içeriği üret:
---
name: <Skill Adı>
description: <Tek satır açıklama>
triggers: [anahtar, kelimeler]
doc_types: [belge, türleri]
---
<Markdown body: adım adım uzmanlık yönergesi>

Yanıtında SKILL.md bloğunu ```SKILL.md kod bloğu içinde sun. Triggers, kullanıcının sorusunda geçebilecek tüm Türkçe anahtar kelimeleri içersin.

Kullanıcı "şu skill'i düzenle: <ad>" dediğinde, mevcut skill'in içeriğini güncelleyerek aynı formatta sun."""


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
    # Hukuk — belge tam metni
    "karar metni": "get_bedesten_document", "karar tam metin": "get_bedesten_document",
    "emsal metin": "get_emsal_document", "emsal karar metni": "get_emsal_document",
    "anayasa metin": "get_anayasa_document", "anayasa karar metni": "get_anayasa_document",
    "kik metin": "get_kik_document", "kik karar metni": "get_kik_document",
    "rekabet metin": "get_rekabet_document", "rekabet karar metni": "get_rekabet_document",
    # Mali
    "asgari ücret": "get_asgari_ucret", "asgari": "get_asgari_ucret",
    "prim": "get_prim_matrahi", "sgk prim": "get_prim_matrahi",
    "resmi gazete": "search_resmi_gazete",
    "genelge": "search_resmi_gazete",
    # Mevzuat — arama
    "mevzuat": "search_mevzuat_bedesten",
    "kanun": "search_mevzuat_bedesten",
    "yönetmelik": "search_mevzuat_bedesten",
    "khk": "search_mevzuat_bedesten",
    # Mevzuat — tam metin
    "kanun metni": "get_mevzuat_document",
    "madde": "get_mevzuat_article",
    "içindekiler": "get_mevzuat_article_tree",
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
    "karar": "search_bedesten_unified",
}



# --- BILGISAYAR ARAÇLARI (Kullanici izniyle) ---
if COMPUTER_TOOLS_AVAILABLE:
    @app.tool(description="Yerel dosya okur (kullanici izni gerekli). Salt-okunur.", annotations={"readOnlyHint": True})
    async def computer_read_file(path: str = "", max_lines: int = 500) -> str:
        """Yerel dosya okur.

        Args:
            path: Dosya yolu
            max_lines: Maksimum satir sayisi (varsayilan: 500)
        """
        try:
            result = computer_tools.read_file(path, max_lines)
            return json.dumps(result, ensure_ascii=False, indent=2)
        except PermissionError as e:
            return f"IZIN HATASI: {e}"
        except Exception as e:
            return f"HATA: {e}"

    @app.tool(description="Dizin icerigini listeler (kullanici izni gerekli). Salt-okunur.", annotations={"readOnlyHint": True})
    async def computer_list_directory(path: str = "", pattern: str = "*") -> str:
        """Dizin icerigini listeler.

        Args:
            path: Dizin yolu
            pattern: Glob patterni (varsayilan: *)
        """
        try:
            result = computer_tools.list_directory(path, pattern)
            return json.dumps(result, ensure_ascii=False, indent=2)
        except PermissionError as e:
            return f"IZIN HATASI: {e}"
        except Exception as e:
            return f"HATA: {e}"

    @app.tool(description="Sistem bilgisi verir (isletim sistemi, CPU, RAM, disk).", annotations={"readOnlyHint": True})
    async def computer_get_system_info() -> str:
        """Sistem bilgisi verir."""
        try:
            result = computer_tools.get_system_info()
            return json.dumps(result, ensure_ascii=False, indent=2)
        except PermissionError as e:
            return f"IZIN HATASI: {e}"
        except Exception as e:
            return f"HATA: {e}"

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


# Suç/konu → kanonik hukuki arama terimi eşlemesi (emsal için anlamlı sorgu üretir)
_LEGAL_SUBJECT_MAP = [
    (["kredi kart", "banka kart", "pos ", "kart bilgis"], "banka veya kredi kartlarının kötüye kullanılması"),
    (["dolandırıcılık", "dolandirici"], "dolandırıcılık suçu"),
    (["nitelikli hırsızlık", "hırsızlık", "hirsizlik"], "hırsızlık suçu"),
    (["güveni kötüye", "guveni kotuye", "emniyeti suistimal"], "güveni kötüye kullanma"),
    (["sahtecilik", "sahte belge", "evrakta sahte"], "resmi belgede sahtecilik"),
    (["zimmet"], "zimmet suçu"),
    (["rüşvet", "rusvet"], "rüşvet suçu"),
    (["uyuşturucu", "uyusturucu"], "uyuşturucu madde ticareti"),
    (["kasten öldür", "kasten oldur", "adam öldür"], "kasten öldürme"),
    (["kasten yaralama", "yaralama", "darp"], "kasten yaralama"),
    (["tehdit"], "tehdit suçu"),
    (["hakaret"], "hakaret suçu"),
    (["cinsel saldırı", "cinsel istismar", "cinsel taciz"], "cinsel saldırı"),
    (["bilişim", "bilisim", "sistem girme"], "bilişim sistemine girme suçu"),
    (["kişisel veri", "kvkk", "verilerin hukuka aykırı"], "kişisel verilerin hukuka aykırı ele geçirilmesi"),
    (["boşanma", "bosanma"], "boşanma davası"),
    (["nafaka"], "nafaka"),
    (["kıdem", "ihbar tazminat"], "kıdem ve ihbar tazminatı"),
    (["işe iade", "ise iade"], "işe iade davası"),
    (["kira tespit", "kira bedel"], "kira tespiti davası"),
    (["tahliye"], "kiralananın tahliyesi"),
    (["tapu iptal", "tapu iptali"], "tapu iptali ve tescili"),
    (["trafik kaza", "maddi tazminat", "destekten yoksun"], "trafik kazası tazminatı"),
]


def _legal_search_terms(text: str) -> str:
    """Belge/mesaj metninden emsal araması için anlamlı bir hukuki sorgu üretir.

    Belgenin KENDİ esas/karar numaralarını DEĞİL, konuyu/suç tipini esas alır.
    """
    low = (text or "").lower()
    hits = []
    for needles, canonical in _LEGAL_SUBJECT_MAP:
        if any(n in low for n in needles):
            hits.append(canonical)
    # TCK/CMK madde atıfları
    arts = re.findall(r"\b(?:tck|ceza\s*kanunu)[^0-9]{0,12}(\d{2,3})", low)
    if arts:
        hits.append(f"TCK {arts[0]}")
    # En çok 2 kanonik terim → odaklı sorgu
    if hits:
        # tekrarsız, sırayı koru
        seen = set(); uniq = [h for h in hits if not (h in seen or seen.add(h))]
        return " ".join(uniq[:2])
    return ""


def _is_criminal_context(text: str) -> bool:
    low = (text or "").lower()
    return any(k in low for k in ["iddianame", "savcılık", "savcilik", "şüpheli", "supheli",
                                   "sanık", "sanik", "müşteki", "musteki", "tck", "ceza",
                                   "soruşturma", "sorusturma", "kovuşturma"])


async def _fetch_emsal_with_content(query: str, criminal: bool = False, limit: int = 3) -> str:
    """Bedesten'de emsal arar ve ilk birkaç kararın TAM METNİNİ çeker.

    Sadece karar numarası değil; gerçek içerik döndürür ki model uydurmasın.
    """
    if not query.strip() or not MODULES_AVAILABLE.get("bedesten"):
        return ""
    court_types = ["YARGITAYKARARI", "KYB"] if criminal else \
                  ["YARGITAYKARARI", "ISTINAFHUKUK", "YERELHUKUK"]
    try:
        listing = await _call_tool("search_bedesten_unified", keyword=query,
                                    court_types=court_types, page_number=1)
    except Exception as e:
        return f"### Emsal arama hatası\n{e}"
    if not listing or "❌" in listing:
        return ""
    parts = [f"### EMSAL ARAMA — sorgu: \"{query}\"\n{listing}"]
    ids = re.findall(r"ID:\s*`([^`]+)`", listing)
    fetched = 0
    for did in ids:
        if fetched >= limit:
            break
        try:
            content = await _call_tool("get_bedesten_document", document_id=did)
        except Exception:
            continue
        if content and "❌" not in content and "bulunamad" not in content.lower():
            parts.append(f"#### KARAR TAM METNİ (Bedesten ID: {did})\n{content[:2800]}")
            fetched += 1
    if fetched == 0:
        parts.append("_(Karar metinleri çekilemedi; yalnızca künye listesi mevcut.)_")
    return "\n\n".join(parts)


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


# Belge türü tespiti için anahtar kelime kalıpları (öncelik sırasıyla)
_DOC_TYPE_RULES = [
    ("dava_dilekcesi", "Dava Dilekçesi", ["dava dilekçesi", "davaci", "davacı", "davalı", "talep ederim", "açıklamalar", "nöbetçi", "asliye hukuk mahkemesi̇ne", "mahkemesine"]),
    ("temyiz_dilekcesi", "Temyiz/İstinaf Dilekçesi", ["temyiz", "istinaf", "bölge adliye", "bozulması"]),
    ("mahkeme_karari", "Mahkeme Kararı", ["gerekçeli karar", "hüküm", "hukum", "karar verildi", "esas no", "karar no", "oybirliği", "oybirliğiyle"]),
    ("ihtarname", "İhtarname", ["ihtarname", "ihtar ederim", "ihtaren", "noterliği"]),
    ("icra_takibi", "İcra Takibi", ["icra", "ödeme emri", "odeme emri", "takip talebi", "haciz", "icra müdürlüğü"]),
    ("sozlesme", "Sözleşme", ["sözleşme", "sozlesme", "taraflar", "işbu sözleşme", "madde 1", "akdedilmiştir"]),
    ("fatura", "Fatura", ["fatura", "kdv", "vergi kimlik", "tutar", "toplam", "e-fatura", "e-arşiv"]),
    ("ihale_dokumani", "İhale Dokümanı", ["ihale", "ekap", "idari şartname", "teknik şartname", "yaklaşık maliyet", "yeterlik"]),
    ("resmi_yazi", "Resmi Yazı", ["t.c.", "sayı :", "konu :", "valiliği", "bakanlığı", "müdürlüğü"]),
]


def _classify_document(text: str) -> dict:
    """Belge metnini sezgisel olarak sınıflandırır (LLM gerektirmez).

    Returns: {type, type_label, subject, parties}
    """
    low = (text or "").lower()
    doc_type, label = "belge", "Belge"
    best = 0
    for t, lbl, kws in _DOC_TYPE_RULES:
        score = sum(1 for k in kws if k in low)
        if score > best:
            best, doc_type, label = score, t, lbl

    # Taraflar
    parties = []
    for role_pat, role in [
        (r"davac[ıi]\s*[:\-]\s*([^\n]{3,60})", "Davacı"),
        (r"daval[ıi]\s*[:\-]\s*([^\n]{3,60})", "Davalı"),
        (r"alacakl[ıi]\s*[:\-]\s*([^\n]{3,60})", "Alacaklı"),
        (r"borçlu\s*[:\-]\s*([^\n]{3,60})", "Borçlu"),
    ]:
        m = re.search(role_pat, text or "", re.IGNORECASE)
        if m:
            parties.append({"rol": role, "ad": m.group(1).strip()})

    # Konu
    subject = ""
    m = re.search(r"konu\s*[:\-]\s*([^\n]{5,120})", text or "", re.IGNORECASE)
    if m:
        subject = m.group(1).strip()
    else:
        for line in (text or "").splitlines():
            s = line.strip()
            if len(s) >= 12:
                subject = s[:120]
                break

    return {"type": doc_type, "type_label": label, "subject": subject, "parties": parties}


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
                    metadata["method"] = "rapidocr_ocr"
                    metadata["ocr_used"] = True
            except Exception as e:
                logger.warning(f"OCR fallback basarisiz: {e}")

        return full_text, metadata

    except ImportError:
        logger.warning("pymupdf yuklu degil, OCR deneniyor...")
        try:
            ocr_text = _extract_text_with_ocr(content)
            metadata["method"] = "rapidocr_ocr"
            metadata["ocr_used"] = True
            return ocr_text, metadata
        except Exception as e:
            metadata["error"] = str(e)
            return "", metadata
    except Exception as e:
        metadata["error"] = str(e)
        return "", metadata


def _fix_turkish_ocr_errors(text: str) -> str:
    """RapidOCR latin modelinin bilinen Türkçe karakter hatalarını düzelt.

    Yalnızca yüksek güvenli düzeltmeler uygulanır. Bağlam bağımlı düzeltmeler
    (örn. 'g' → 'ğ') yanlış pozitifler oluşturabileceğinden LLM'e bırakılır.
    """
    if not text:
        return text
    # Satır sonu unicode normalizasyon hataları
    text = text.replace("", "·")  # bullet yerine yanlış kodlanmış
    # Tek tırnak hataları
    text = text.replace("‘", "'").replace("’", "'")
    # Çift tırnak hataları
    text = text.replace("“", '"').replace("”", '"')
    return text


def _extract_text_with_ocr(content: bytes) -> str:
    """PDF'den OCR ile metin çıkar — pymupdf + RapidOCR (pip-only, Tesseract gerektirmez).

    İki katmanlı strateji:
    1. RapidOCR (ONNX tabanlı, hızlı, pip-only) — birincil
    2. pymupdf yerleşik OCR (tessdata gerektirir) — ikincil fallback
    """
    import pymupdf

    # --- Birincil: RapidOCR (ONNX tabanlı, hızlı) ---
    try:
        from rapidocr_onnxruntime import RapidOCR
        import numpy as np

        reader = RapidOCR()
        doc = pymupdf.open(stream=content, filetype="pdf")
        text_parts = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            img_array = img_array.reshape(pix.height, pix.width, pix.n)
            result, _ = reader(img_array)
            if result:
                page_text = "\n".join([line[1] for line in result])
                page_text = _fix_turkish_ocr_errors(page_text)
                text_parts.append(f"--- Sayfa {page_num + 1} (OCR) ---\n{page_text}")
        doc.close()
        if text_parts:
            return "\n\n".join(text_parts)
    except ImportError:
        logger.warning("rapidocr-onnxruntime yuklu degil, pymupdf OCR deneniyor...")
    except Exception as e:
        logger.warning(f"RapidOCR basarisiz: {e}, pymupdf OCR deneniyor...")

    # --- İkincil: pymupdf yerleşik OCR (tessdata dosyaları gerektirir) ---
    try:
        doc = pymupdf.open(stream=content, filetype="pdf")
        text_parts = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            tp = page.get_textpage_ocr(language="tur+eng")
            text = page.get_text(textpage=tp)
            if text.strip():
                text_parts.append(f"--- Sayfa {page_num + 1} (OCR) ---\n{text}")
        doc.close()
        if text_parts:
            return "\n\n".join(text_parts)
    except Exception as e:
        logger.warning(f"pymupdf OCR da basarisiz: {e}")

    raise ImportError("OCR kutuphaneleri kullanilamiyor (rapidocr-onnxruntime veya tessdata)")


async def export_docx_endpoint(request):
    """Yapılandırılmış belge taslağını DOCX olarak dışa aktarır.

    Body: {
        "title": "...",
        "sections": [{"heading": "...", "body": "..."}, ...],
        "metadata": {"parties": [...], "subject": "...", "legal_refs": [...], "date": "..."},
        "doc_type": "dava_dilekcesi"  // optional
    }
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Geçersiz JSON gövdesi."}, status_code=400)

    title = (body.get("title") or "Belge").strip()
    sections = body.get("sections") or []
    metadata = body.get("metadata") or {}
    doc_type = body.get("doc_type") or ""

    if not sections:
        return JSONResponse({"error": "sections alanı boş olamaz."}, status_code=400)

    try:
        from docx import Document
        from docx.shared import Pt, Cm, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT
    except ImportError:
        return JSONResponse({"error": "python-docx yüklü değil."}, status_code=500)

    doc = Document()

    # Sayfa kenar boşlukları (Türk hukuk formatı)
    for section in doc.sections:
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    # Stil ayarları
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Times New Roman'
    font.size = Pt(12)

    # Başlık
    heading_para = doc.add_paragraph()
    heading_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = heading_para.add_run(title.upper())
    run.bold = True
    run.font.size = Pt(14)
    run.font.name = 'Times New Roman'

    # Meta veriler
    if metadata:
        # Taraf tablosu
        parties = metadata.get("parties") or []
        if parties:
            doc.add_paragraph()  # Boş satır
            table = doc.add_table(rows=1, cols=2)
            table.style = 'Table Grid'
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            hdr = table.rows[0].cells
            hdr[0].text = "Sıfat"
            hdr[1].text = "Ad Soyad / Unvan"
            for cell in hdr:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.bold = True
                        run.font.name = 'Times New Roman'
                        run.font.size = Pt(11)
            for party in parties:
                row = table.add_row()
                row.cells[0].text = party.get("role", "")
                row.cells[1].text = party.get("name", "")
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        for run in paragraph.runs:
                            run.font.name = 'Times New Roman'
                            run.font.size = Pt(11)

        # Konu
        subject = metadata.get("subject") or ""
        if subject:
            doc.add_paragraph()
            p = doc.add_paragraph()
            run_label = p.add_run("Konu: ")
            run_label.bold = True
            run_label.font.name = 'Times New Roman'
            run_label.font.size = Pt(12)
            run_text = p.add_run(subject)
            run_text.font.name = 'Times New Roman'
            run_text.font.size = Pt(12)

        # Yasal referanslar
        legal_refs = metadata.get("legal_refs") or []
        if legal_refs:
            p = doc.add_paragraph()
            run_label = p.add_run("Yasal Dayanaklar: ")
            run_label.bold = True
            run_label.font.name = 'Times New Roman'
            run_label.font.size = Pt(11)
            run_text = p.add_run(", ".join(legal_refs))
            run_text.font.name = 'Times New Roman'
            run_text.font.size = Pt(11)

        # Tarih
        date_str = metadata.get("date") or ""
        if date_str:
            doc.add_paragraph()
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            run = p.add_run(f"Tarih: {date_str}")
            run.font.name = 'Times New Roman'
            run.font.size = Pt(11)

    # Bölümler
    doc.add_paragraph()  # Boş satır
    for section in sections:
        heading = section.get("heading") or ""
        body = section.get("body") or ""

        if heading:
            h = doc.add_paragraph()
            run = h.add_run(heading)
            run.bold = True
            run.font.name = 'Times New Roman'
            run.font.size = Pt(12)

        if body:
            # Gövde metni — paragraflara böl
            for para_text in body.split("\n"):
                para_text = para_text.strip()
                if para_text:
                    p = doc.add_paragraph(para_text)
                    for run in p.runs:
                        run.font.name = 'Times New Roman'
                        run.font.size = Pt(12)

        doc.add_paragraph()  # Bölümler arası boşluk

    # İmza alanı (dilekçe ve ihtarname için)
    if doc_type in ("dava_dilekcesi", "temyiz_dilekcesi", "ihtarname"):
        doc.add_paragraph()
        doc.add_paragraph()
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run = p.add_run("İmza")
        run.font.name = 'Times New Roman'
        run.font.size = Pt(12)

    # DOCX'i belleğe yaz
    import io
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    # Dosya adı
    import re
    safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')[:50]
    filename = f"{safe_title}.docx"

    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


# ============================================================
# WORKSPACE — Klasör / Oturum / Dosya kalıcılığı
# ============================================================

def _ws_guard():
    """Workspace yoksa hata yanıtı döndürür, varsa None."""
    if not WORKSPACE_AVAILABLE:
        return JSONResponse({"error": "Workspace modülü yüklü değil."}, status_code=503)
    return None


async def workspace_snapshot_endpoint(request):
    """Tüm klasör + oturum ağacını döndürür."""
    g = _ws_guard()
    if g:
        return g
    try:
        return JSONResponse(workspace.snapshot())
    except Exception as e:
        return JSONResponse({"error": f"Workspace okuma hatası: {e}"}, status_code=500)


async def workspace_folder_endpoint(request):
    """Klasör oluştur / yeniden adlandır / sil.

    Body: {"action": "create|rename|delete", "id": "...", "name": "..."}
    """
    g = _ws_guard()
    if g:
        return g
    try:
        body = await request.json()
    except Exception:
        body = {}
    action = (body.get("action") or "create").lower()
    try:
        if action == "create":
            folder = workspace.create_folder(body.get("name", "Yeni Klasör"))
            return JSONResponse({"status": "ok", "folder": folder})
        elif action == "rename":
            ok = workspace.rename_folder(body.get("id", ""), body.get("name", ""))
            return JSONResponse({"status": "ok" if ok else "notfound"})
        elif action == "delete":
            ok = workspace.delete_folder(body.get("id", ""), bool(body.get("deleteSessions")))
            return JSONResponse({"status": "ok" if ok else "notfound"})
        return JSONResponse({"error": "Geçersiz işlem."}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def workspace_session_get_endpoint(request):
    """Tek bir oturumu (mesajlar dahil) getirir. ?id=..."""
    g = _ws_guard()
    if g:
        return g
    sid = request.query_params.get("id", "")
    if not sid:
        return JSONResponse({"error": "id gerekli."}, status_code=400)
    session = workspace.get_session(sid)
    if session is None:
        return JSONResponse({"error": "Oturum bulunamadı."}, status_code=404)
    return JSONResponse(session)


async def workspace_session_save_endpoint(request):
    """Oturumu kaydeder/günceller (upsert).

    Body: tam oturum nesnesi {id?, title, folderId?, messages[], attachments[]}
    """
    g = _ws_guard()
    if g:
        return g
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Geçersiz istek."}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "Geçersiz oturum verisi."}, status_code=400)
    try:
        session = workspace.save_session(body)
        return JSONResponse({"status": "ok", "id": session["id"], "updated": session["updated"]})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def workspace_session_delete_endpoint(request):
    """Oturum sil veya taşı. Body: {"id": "...", "action": "delete|move", "folderId": ...}"""
    g = _ws_guard()
    if g:
        return g
    try:
        body = await request.json()
    except Exception:
        body = {}
    sid = body.get("id", "")
    action = (body.get("action") or "delete").lower()
    if not sid:
        return JSONResponse({"error": "id gerekli."}, status_code=400)
    if action == "move":
        ok = workspace.move_session(sid, body.get("folderId"))
    else:
        ok = workspace.delete_session(sid)
    return JSONResponse({"status": "ok" if ok else "notfound"})


async def workspace_file_upload_endpoint(request):
    """Bir dosyayı klasöre yerleştirir; PDF/UYAP ise içeriğini de çözümler.

    Multipart form: file, folderId
    Yanıt: dosya meta + (varsa) çıkarılan metin + referanslar.
    """
    g = _ws_guard()
    if g:
        return g
    try:
        form = await request.form()
    except Exception:
        return JSONResponse({"error": "Geçersiz form verisi."}, status_code=400)

    file = form.get("file")
    folder_id = form.get("folderId") or "_root"
    if not file:
        return JSONResponse({"error": "Dosya bulunamadı."}, status_code=400)

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        return JSONResponse({"error": "Dosya boyutu 50MB'dan büyük olamaz."}, status_code=400)

    filename = file.filename or "dosya"
    lower = filename.lower()

    extracted_text = ""
    refs = []
    parse_error = ""

    try:
        if lower.endswith(".pdf"):
            text, _meta = _extract_text_from_pdf(content)
            extracted_text = text or ""
            refs = _extract_document_refs(extracted_text)
        elif lower.endswith(".eyp") or lower.endswith(".udf"):
            if 'uyap_parser' in globals() and uyap_parser is not None:
                belge = uyap_parser.parse_eyp(content)
                extracted_text = uyap_parser.to_markdown(belge)
                refs = _extract_document_refs(extracted_text)
            else:
                parse_error = "UYAP modülü yüklü değil."
        elif lower.endswith(".txt") or lower.endswith(".md"):
            extracted_text = content.decode("utf-8", errors="replace")
            refs = _extract_document_refs(extracted_text)
    except Exception as e:
        parse_error = f"Çözümleme hatası: {e}"

    # Belge zekâsı: türünü, taraflarını, konusunu tespit et
    understanding = _classify_document(extracted_text) if extracted_text.strip() else {
        "type": "belge", "type_label": "Belge", "subject": "", "parties": []
    }

    # Çapraz hafıza: diğer oturumlarda benzer dava/belge var mı?
    related = []
    try:
        kw = [w for w in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü]{5,}", understanding.get("subject", ""))][:6]
        related = workspace.find_related(refs=refs, keywords=kw,
                                         exclude_session_id=form.get("sessionId", ""))
    except Exception:
        related = []

    try:
        info = workspace.store_file(folder_id, filename, content, meta={
            "hasText": bool(extracted_text.strip()),
            "refCount": len(refs),
            "docType": understanding.get("type"),
        })
    except Exception as e:
        return JSONResponse({"error": f"Dosya kaydedilemedi: {e}"}, status_code=500)

    truncated = len(extracted_text) > 12000
    return JSONResponse({
        "status": "ok",
        "file": info,
        "text": extracted_text[:12000] + ("..." if truncated else ""),
        "full_text_length": len(extracted_text),
        "truncated": truncated,
        "references": refs,
        "understanding": understanding,
        "related": related,
        "parse_error": parse_error,
    })


async def workspace_files_list_endpoint(request):
    """Klasördeki dosyaları listeler. ?folder=..."""
    g = _ws_guard()
    if g:
        return g
    folder_id = request.query_params.get("folder", "_root")
    return JSONResponse({"files": workspace.list_files(folder_id)})


async def workspace_file_delete_endpoint(request):
    """Dosya sil. Body: {"folderId": "...", "name": "..."}"""
    g = _ws_guard()
    if g:
        return g
    try:
        body = await request.json()
    except Exception:
        body = {}
    ok = workspace.delete_file(body.get("folderId", "_root"), body.get("name", ""))
    return JSONResponse({"status": "ok" if ok else "notfound"})


# ===== Memory (Bellek) Endpoint'leri =====

async def memory_list_endpoint(request):
    """Tüm bellek kayıtlarını listele."""
    if not MEMORY_AVAILABLE:
        return JSONResponse({"memories": []})
    return JSONResponse({"memories": memory_mod.list_memories()})


async def memory_add_endpoint(request):
    """Yeni bellek kaydı ekle. Body: {"category": "preference|fact|instruction", "content": "..."}"""
    if not MEMORY_AVAILABLE:
        return JSONResponse({"error": "memory module not available"}, status_code=503)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    category = body.get("category", "preference")
    content = body.get("content", "")
    try:
        entry = memory_mod.add_memory(category, content)
        return JSONResponse(entry)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


async def memory_update_endpoint(request):
    """Bellek kaydını güncelle. Body: {"id": "mem_xxx", "category"?: ..., "content"?: ...}"""
    if not MEMORY_AVAILABLE:
        return JSONResponse({"error": "memory module not available"}, status_code=503)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    mem_id = body.get("id", "")
    if not mem_id:
        return JSONResponse({"error": "id required"}, status_code=400)
    result = memory_mod.update_memory(mem_id, category=body.get("category"), content=body.get("content"))
    if result is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(result)


async def memory_delete_endpoint(request):
    """Bellek kaydını sil. Body: {"id": "mem_xxx"}"""
    if not MEMORY_AVAILABLE:
        return JSONResponse({"error": "memory module not available"}, status_code=503)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    mem_id = body.get("id", "")
    ok = memory_mod.delete_memory(mem_id)
    return JSONResponse({"status": "ok" if ok else "notfound"})


async def memory_clear_endpoint(request):
    """Tüm bellek kayıtlarını sil."""
    if not MEMORY_AVAILABLE:
        return JSONResponse({"error": "memory module not available"}, status_code=503)
    n = memory_mod.clear_all()
    return JSONResponse({"status": "ok", "deleted": n})


# ============================================================
# SÜRE TAKİP ENDPOINT'LERİ
# ============================================================
async def deadline_list_endpoint(request):
    """Tüm süreleri listele. Opsiyonel ?status=active filtresi."""
    if not DEADLINES_AVAILABLE:
        return JSONResponse({"deadlines": []})
    status = request.query_params.get("status")
    return JSONResponse({"deadlines": deadlines_mod.list_deadlines(status if status else None)})


async def deadline_add_endpoint(request):
    """Yeni süre ekle. Body: {"category": "...", "title": "...", "start_date": "YYYY-MM-DD", "days_allowed"?: int, "description"?: "..."}"""
    if not DEADLINES_AVAILABLE:
        return JSONResponse({"error": "deadlines module not available"}, status_code=503)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    category = body.get("category", "diger")
    title = body.get("title", "")
    start_date = body.get("start_date", "")
    days_allowed = body.get("days_allowed")  # None means use category default
    description = body.get("description", "")
    try:
        dl = deadlines_mod.add_deadline(category, title, start_date, days_allowed, description)
        return JSONResponse(dl)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


async def deadline_update_endpoint(request):
    """Süreyi güncelle. Body: {"id": "dl_xxx", ...fields}"""
    if not DEADLINES_AVAILABLE:
        return JSONResponse({"error": "deadlines module not available"}, status_code=503)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    dl_id = body.get("id", "")
    if not dl_id:
        return JSONResponse({"error": "id required"}, status_code=400)
    kwargs = {k: v for k, v in body.items() if k != "id" and v is not None}
    try:
        result = deadlines_mod.update_deadline(dl_id, **kwargs)
        if result is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        return JSONResponse(result)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


async def deadline_delete_endpoint(request):
    """Süreyi sil. Body: {"id": "dl_xxx"}"""
    if not DEADLINES_AVAILABLE:
        return JSONResponse({"error": "deadlines module not available"}, status_code=503)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    dl_id = body.get("id", "")
    ok = deadlines_mod.delete_deadline(dl_id)
    return JSONResponse({"status": "ok" if ok else "notfound"})


async def deadline_complete_endpoint(request):
    """Süreyi tamamlandı olarak işaretle. Body: {"id": "dl_xxx"}"""
    if not DEADLINES_AVAILABLE:
        return JSONResponse({"error": "deadlines module not available"}, status_code=503)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    dl_id = body.get("id", "")
    result = deadlines_mod.mark_completed(dl_id)
    if result is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(result)


async def deadline_upcoming_endpoint(request):
    """Yaklaşan süreleri getir. Opsiyonel ?days=30."""
    if not DEADLINES_AVAILABLE:
        return JSONResponse({"deadlines": []})
    days = int(request.query_params.get("days", "30"))
    return JSONResponse({"deadlines": deadlines_mod.get_upcoming(days)})


async def deadline_overdue_endpoint(request):
    """Gecikmiş süreleri getir."""
    if not DEADLINES_AVAILABLE:
        return JSONResponse({"deadlines": []})
    return JSONResponse({"deadlines": deadlines_mod.get_overdue()})


# ============================================================
# DAVA KARTI ENDPOINT'LERİ
# ============================================================
async def dava_list_endpoint(request):
    """Dava kartlarını listele."""
    if not DAVA_AVAILABLE:
        return JSONResponse({"kartlar": []})
    durum = request.query_params.get("durum", "")
    dava_turu = request.query_params.get("dava_turu", "")
    return JSONResponse({"kartlar": dava_mod.list_kartlar(durum=durum if durum else None, dava_turu=dava_turu if dava_turu else None)})


async def dava_add_endpoint(request):
    """Yeni dava kartı ekle."""
    if not DAVA_AVAILABLE:
        return JSONResponse({"error": "Dava modülü kullanılamıyor"}, status_code=503)
    body = await request.json()
    try:
        k = dava_mod.add_kart(
            esas_no=body.get("esas_no", ""),
            dava_turu=body.get("dava_turu", "diger"),
            taraf_muvekkil=body.get("taraf_muvekkil", ""),
            taraf_karsi=body.get("taraf_karsi", ""),
            daire=body.get("daire", ""),
            konu=body.get("konu", ""),
            acilis_tarihi=body.get("acilis_tarihi", ""),
            notlar=body.get("notlar", ""),
        )
        return JSONResponse(k)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


async def dava_update_endpoint(request):
    """Dava kartını güncelle."""
    if not DAVA_AVAILABLE:
        return JSONResponse({"error": "Dava modülü kullanılamıyor"}, status_code=503)
    body = await request.json()
    kart_id = body.get("id", "")
    if not kart_id:
        return JSONResponse({"error": "id zorunlu"}, status_code=400)
    kwargs = {k: v for k, v in body.items() if k != "id" and v is not None}
    k = dava_mod.update_kart(kart_id, **kwargs)
    if k:
        return JSONResponse(k)
    return JSONResponse({"error": "Kart bulunamadı"}, status_code=404)


async def dava_delete_endpoint(request):
    """Dava kartını sil."""
    if not DAVA_AVAILABLE:
        return JSONResponse({"error": "Dava modülü kullanılamıyor"}, status_code=503)
    body = await request.json()
    kart_id = body.get("id", "")
    if dava_mod.delete_kart(kart_id):
        return JSONResponse({"status": "ok"})
    return JSONResponse({"error": "Kart bulunamadı"}, status_code=404)


async def dava_search_endpoint(request):
    """Dava kartlarında arama."""
    if not DAVA_AVAILABLE:
        return JSONResponse({"kartlar": []})
    query = request.query_params.get("q", "")
    return JSONResponse({"kartlar": dava_mod.search_kartlar(query)})


async def dava_link_deadline_endpoint(request):
    """Dava kartına süre bağla."""
    if not DAVA_AVAILABLE:
        return JSONResponse({"error": "Dava modülü kullanılamıyor"}, status_code=503)
    body = await request.json()
    k = dava_mod.link_deadline(body.get("dava_id", ""), body.get("deadline_id", ""))
    if k:
        return JSONResponse(k)
    return JSONResponse({"error": "Kart veya süre bulunamadı"}, status_code=404)


async def dava_unlink_deadline_endpoint(request):
    """Dava kartından süre bağını kaldır."""
    if not DAVA_AVAILABLE:
        return JSONResponse({"error": "Dava modülü kullanılamıyor"}, status_code=503)
    body = await request.json()
    k = dava_mod.unlink_deadline(body.get("dava_id", ""), body.get("deadline_id", ""))
    if k:
        return JSONResponse(k)
    return JSONResponse({"error": "Kart veya süre bulunamadı"}, status_code=404)


# ============================================================
# YEDEKLEME ENDPOINT'LERİ
# ============================================================

async def backup_list_endpoint(request):
    """Mevcut yedekleri listele."""
    if not BACKUP_AVAILABLE:
        return JSONResponse({"backups": []})
    return JSONResponse({"backups": backup_mod.list_backups()})


async def backup_create_endpoint(request):
    """Yeni yedek oluştur."""
    if not BACKUP_AVAILABLE:
        return JSONResponse({"error": "Yedekleme modülü kullanılamıyor"}, status_code=503)
    result = backup_mod.create_backup()
    if result.get("ok"):
        result["size_formatted"] = backup_mod._format_size(result["size"])
    return JSONResponse(result, status_code=200 if result.get("ok") else 500)


async def backup_restore_endpoint(request):
    """Yedekten geri yükle."""
    if not BACKUP_AVAILABLE:
        return JSONResponse({"error": "Yedekleme modülü kullanılamıyor"}, status_code=503)
    body = await request.json()
    filename = body.get("filename", "")
    if not filename:
        return JSONResponse({"error": "filename zorunlu"}, status_code=400)
    result = backup_mod.restore_backup(filename)
    return JSONResponse(result, status_code=200 if result.get("ok") else 400)


async def backup_download_endpoint(request):
    """Yedek dosyasını indir."""
    if not BACKUP_AVAILABLE:
        return JSONResponse({"error": "Yedekleme modülü kullanılamıyor"}, status_code=503)
    filename = request.query_params.get("file", "")
    if not filename:
        return JSONResponse({"error": "file parametresi zorunlu"}, status_code=400)
    path = backup_mod.get_backup_path(filename)
    if not path:
        return JSONResponse({"error": "Yedek dosyası bulunamadı"}, status_code=404)
    from starlette.responses import FileResponse
    return FileResponse(path, filename=filename, media_type="application/zip")


async def backup_delete_endpoint(request):
    """Yedek dosyasını sil."""
    if not BACKUP_AVAILABLE:
        return JSONResponse({"error": "Yedekleme modülü kullanılamıyor"}, status_code=503)
    body = await request.json()
    filename = body.get("filename", "")
    if not filename:
        return JSONResponse({"error": "filename zorunlu"}, status_code=400)
    if backup_mod.delete_backup(filename):
        return JSONResponse({"status": "ok"})
    return JSONResponse({"error": "Yedek dosyası bulunamadı"}, status_code=404)


# ============================================================
# ÖNBELLEK YÖNETİM ENDPOINT'LERİ
# ============================================================
async def cache_stats_endpoint(request):
    """Önbellek istatistiklerini döndür."""
    return JSONResponse(TOOL_CACHE.stats())

async def cache_clear_endpoint(request):
    """Tüm önbelleği temizle."""
    count = TOOL_CACHE.clear()
    return JSONResponse({"cleared": count, "status": "ok"})


# ============================================================
# API ANAHTAR YÖNETİMİ
# ============================================================
API_KEY_DEFS = {
    "tavily": {"env_var": "TAVILY_API_KEY", "label": "Tavily API Anahtarı", "fallback": True},
    "brave": {"env_var": "BRAVE_API_TOKEN", "label": "Brave API Token", "fallback": True},
    "mistral": {"env_var": "MISTRAL_API_KEY", "label": "Mistral API Anahtarı", "fallback": False},
    "evds": {"env_var": "EVDS_API_KEY", "label": "EVDS API Anahtarı", "fallback": False},
}
_KEYRING_SERVICE = "turkiye-mcp"


def _get_user_api_key(key_name: str) -> Optional[str]:
    """Kullanıcının API anahtarını al: keyring > env var > None."""
    env_var = API_KEY_DEFS.get(key_name, {}).get("env_var", key_name)
    # 1. Keyring (desktop modda)
    try:
        import keyring
        key = keyring.get_password(_KEYRING_SERVICE, key_name)
        if key:
            return key
    except Exception:
        pass
    # 2. Environment variable
    return os.environ.get(env_var)


def _set_user_api_key(key_name: str, value: str) -> bool:
    """API anahtarını keyring'e kaydet."""
    try:
        import keyring
        keyring.set_password(_KEYRING_SERVICE, key_name, value)
        return True
    except Exception:
        return False


def _delete_user_api_key(key_name: str) -> bool:
    """API anahtarını keyring'den sil."""
    try:
        import keyring
        keyring.delete_password(_KEYRING_SERVICE, key_name)
        return True
    except Exception:
        return False


async def api_keys_endpoint(request):
    """API anahtar durumlarını getir (GET) veya güncelle (POST)."""
    if request.method == "GET":
        keys = {}
        for name, info in API_KEY_DEFS.items():
            key = _get_user_api_key(name)
            if key:
                keys[name] = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "****"
            else:
                keys[name] = None
            keys[f"{name}_fallback"] = info["fallback"]
        return JSONResponse(keys)
    # POST — anahtarları kaydet/sil
    body = await request.json()
    result = {}
    for name, value in body.items():
        if name not in API_KEY_DEFS:
            continue
        if value and value.strip():
            ok = _set_user_api_key(name, value.strip())
            result[name] = "saved" if ok else "error"
        else:
            ok = _delete_user_api_key(name)
            result[name] = "deleted" if ok else "error"
    # Modül client'larını güncelle
    _refresh_api_keys()
    return JSONResponse(result)


def _refresh_api_keys():
    """Kaydedilen API anahtarlarını ilgili modül client'larına uygula."""
    global bddk_client, kvkk_client, sigorta_tahkim_client
    tavily_key = _get_user_api_key("tavily")
    brave_key = _get_user_api_key("brave")
    # Sadece mevcut client'ları güncelle
    if MODULES_AVAILABLE.get("bddk") and tavily_key:
        try:
            bddk_client.tavily_api_key = tavily_key
        except Exception:
            pass
    if MODULES_AVAILABLE.get("kvkk") and brave_key:
        try:
            kvkk_client.brave_api_token = brave_key
        except Exception:
            pass
    if MODULES_AVAILABLE.get("sigorta_tahkim") and tavily_key:
        try:
            sigorta_tahkim_client.tavily_api_key = tavily_key
        except Exception:
            pass

# Başlangıçta kaydedilen API anahtarlarını uygula
_refresh_api_keys()


_MEMORY_EXTRACT_PROMPT = (
    "Sen bir bellek yöneticisisin. Kullanıcı-asistan görüşmesinden iki şey çıkar:\n\n"
    "1) EKLE — GELECEKTE hatırlanmaya değer KALICI kullanıcı bilgileri:\n"
    "   - preference: kalıcı tercih (ör. 'kısa ve madde madde yanıt sever')\n"
    "   - fact: kullanıcı hakkında kalıcı olgu (ör. 'ceza hukuku avukatı', 'adı Zeynep')\n"
    "   - instruction: asistana kalıcı talimat (ör. 'her yanıtta mevzuat maddesi ver')\n"
    "   SADECE gerçekten kalıcı ve değerli olanları al. Tek seferlik sorular, geçici "
    "konular, sıradan sohbet veya asistanın kendi bilgisi EKLENMEZ. Emin değilsen ekleme.\n\n"
    "2) UNUT — Kullanıcı AÇIKÇA bir bilgiyi unutmanı/silmeni istediyse (ör. 'bunu unut', "
    "'X bilgisini sil', 'beni unutma listesinden çıkar'), MEVCUT BELLEK listesinden silinecek "
    "kayıtların id'lerini ver. Kullanıcı açıkça istemediyse UNUT listesi BOŞ olmalı.\n\n"
    "SADECE şu biçimde geçerli JSON döndür, başka metin yazma:\n"
    '{"add":[{"category":"fact","content":"..."}],"forget":["mem_xxxx"]}'
)


def _parse_json_object(text: str) -> dict:
    import json as _json
    t = (text or "").strip()
    if "```" in t:
        import re as _re
        m = _re.search(r"```(?:json)?\s*(.*?)```", t, _re.S)
        if m:
            t = m.group(1).strip()
    a, b = t.find("{"), t.rfind("}")
    if a == -1 or b == -1 or b < a:
        return {}
    try:
        data = _json.loads(t[a:b + 1])
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


async def memory_learn_endpoint(request):
    """Son görüşmeden kalıcı kullanıcı bilgisi çıkarıp otomatik belleğe ekler.

    Body: {history:[{role,text}], provider, model, api_key}
    Yanıtı yavaşlatmamak için frontend bunu arka planda (fire-and-forget) çağırır.
    """
    if not MEMORY_AVAILABLE or not GATEWAY_AVAILABLE:
        return JSONResponse({"added": []})
    provider_id, api_key, model = _get_llm_config(request)
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
    if provider_id not in LLM_PROVIDERS:
        return JSONResponse({"added": []})
    pc = LLM_PROVIDERS[provider_id]
    if pc["needs_key"] and not api_key:
        return JSONResponse({"added": []})

    raw_history = body.get("history") or []
    convo = []
    for h in raw_history[-8:]:
        role = "Kullanıcı" if h.get("role") == "user" else "Asistan"
        txt = (h.get("text") or h.get("content") or "").strip()
        if txt:
            convo.append(f"{role}: {txt[:1200]}")
    if not convo:
        return JSONResponse({"added": [], "forgotten": []})

    # Mevcut bellek (unut komutu için id'leriyle)
    existing = memory_mod.list_memories()
    existing_ids = {m.get("id") for m in existing}
    mem_lines = [f"{m.get('id')}: {m.get('content')}" for m in existing[:40]]
    mem_block = ("\n\nMEVCUT BELLEK:\n" + "\n".join(mem_lines)) if mem_lines else "\n\nMEVCUT BELLEK: (boş)"

    api_keys_map = {provider_id: api_key}
    for k, v in (body.get("api_keys") or {}).items():
        if v:
            api_keys_map[(k or "").lower()] = v

    try:
        result = await GATEWAY.complete(
            system=_MEMORY_EXTRACT_PROMPT,
            history=[],
            message="GÖRÜŞME:\n" + "\n".join(convo) + mem_block,
            chain=[{"provider": provider_id, "model": model}],
            api_keys=api_keys_map,
            timeout_for=lambda pid: 60,
        )
    except Exception:
        return JSONResponse({"added": [], "forgotten": []})
    if result.get("error"):
        return JSONResponse({"added": [], "forgotten": []})

    obj = _parse_json_object(result.get("reply", ""))
    added = []
    for it in (obj.get("add") or [])[:4]:
        if not isinstance(it, dict):
            continue
        cat = (it.get("category") or "").strip().lower()
        content = (it.get("content") or "").strip()
        if cat not in ("preference", "fact", "instruction") or len(content) < 4:
            continue
        if memory_mod.has_similar(content):
            continue
        try:
            entry = memory_mod.add_memory(cat, content, source="auto")
            added.append({"category": cat, "content": content, "id": entry["id"]})
        except Exception:
            continue

    forgotten = []
    for mid in (obj.get("forget") or [])[:10]:
        mid = str(mid).strip()
        if mid in existing_ids and memory_mod.delete_memory(mid):
            forgotten.append(mid)

    return JSONResponse({"added": added, "forgotten": forgotten})


async def ollama_models_endpoint(request):
    """Yerel Ollama'da yüklü modelleri listeler (cloud proxy modelleri dahil).

    Kullanıcının makinesinde çalışan Ollama'dan canlı model listesi çeker.
    """
    base = request.query_params.get("base", "http://localhost:11434").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(base + "/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
            return JSONResponse({"ok": True, "models": models})
    except Exception as e:
        return JSONResponse({"ok": False, "models": [], "error": str(e)}, status_code=200)


async def skills_endpoint(request):
    """Yüklü uzmanlık yönergelerini (skills) listeler."""
    if not SKILLS_AVAILABLE:
        return JSONResponse({"skills": []})
    try:
        return JSONResponse({"skills": skills_engine.list_skill_meta()})
    except Exception as e:
        return JSONResponse({"skills": [], "error": str(e)})


async def skills_toggle_endpoint(request):
    """Bir skill'i aç/kapat. Body: {"name": "...", "enabled": true|false}"""
    if not SKILLS_AVAILABLE:
        return JSONResponse({"error": "Skills yüklü değil."}, status_code=503)
    try:
        body = await request.json()
    except Exception:
        body = {}
    name = body.get("name", "")
    if not name:
        return JSONResponse({"error": "name gerekli."}, status_code=400)
    skills_engine.set_enabled(name, bool(body.get("enabled", True)))
    return JSONResponse({"status": "ok", "skills": skills_engine.list_skill_meta()})


async def skills_content_endpoint(request):
    """Skill'in tam SKILL.md içeriğini döndür."""
    if not SKILLS_AVAILABLE:
        return JSONResponse({"error": "Skills yüklü değil."}, status_code=503)
    name = request.query_params.get("name", "")
    if not name:
        return JSONResponse({"error": "name parametresi gerekli."}, status_code=400)
    content = skills_engine.get_skill_content(name)
    if content is None:
        return JSONResponse({"error": "Skill bulunamadı.", "name": name}, status_code=404)
    return JSONResponse({"name": name, "content": content})


async def skills_save_endpoint(request):
    """Skill oluştur veya güncelle. Body: {"name": "...", "content": "---\\nname: ...\\n---\\nbody"}"""
    if not SKILLS_AVAILABLE:
        return JSONResponse({"error": "Skills yüklü değil."}, status_code=503)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    name = body.get("name", "")
    content = body.get("content", "")
    if not name or not content:
        return JSONResponse({"error": "name ve content gerekli."}, status_code=400)
    try:
        result = skills_engine.save_skill(name, content)
        return JSONResponse(result)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


async def gateway_status_endpoint(request):
    """LLM Gateway metrikleri (sağlayıcı başına başarı/başarısızlık/gecikme)."""
    if not GATEWAY_AVAILABLE or GATEWAY is None:
        return JSONResponse({"available": False, "providers": {}})
    return JSONResponse({"available": True, "providers": GATEWAY.status()})


async def gateway_config_endpoint(request):
    """Gateway yapılandırması — GET: mevcut config, POST: güncelle."""
    if request.method == "GET":
        snapshot = gateway_mod.get_config_snapshot(LLM_PROVIDERS)
        return JSONResponse(snapshot)
    # POST — yapılandırmayı güncelle
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Geçersiz JSON"}, status_code=400)
    providers_over = body.get("providers", {})
    default_chain = body.get("default_chain", [])
    # Config'i oluştur ve kaydet
    config = {}
    if providers_over:
        config["providers"] = providers_over
    if default_chain:
        config["default_chain"] = default_chain
    gateway_mod.save_config(config)
    # Mevcut LLM_PROVIDERS'a uygula
    gateway_mod.apply_config(LLM_PROVIDERS, config)
    # JS PROVIDERS'ı da güncelle
    return JSONResponse({"status": "ok", "config": gateway_mod.get_config_snapshot(LLM_PROVIDERS)})

async def computer_permissions_endpoint(request):
    """Bilgisayar araclari izinlerini yonet — GET: mevcut izinler, POST: guncelle."""
    if not COMPUTER_TOOLS_AVAILABLE:
        return JSONResponse({"available": False})
    if request.method == "GET":
        perms = computer_tools.load_permissions()
        descs = computer_tools.TOOL_DESCRIPTIONS
        result = {}
        for k, v in perms.items():
            d = descs.get(k, {})
            result[k] = {"allowed": v, "name": d.get("name", k), "desc": d.get("desc", ""), "risk": d.get("risk", "unknown"), "category": d.get("category", "")}
        return JSONResponse({"available": True, "permissions": result})
    # POST
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Gecersiz JSON"}, status_code=400)
    new_perms = body.get("permissions", {})
    current = computer_tools.load_permissions()
    for k, v in new_perms.items():
        if k in current:
            current[k] = bool(v)
    computer_tools.save_permissions(current)
    return JSONResponse({"status": "ok", "permissions": current})




# Araç kataloğu — UI'de araçları kategorize göstermek için
TOOLS_CATALOG = [
    ("Hukuk", "search_bedesten_unified", "Yargıtay/Danıştay/yerel/istinaf birleşik karar arama"),
    ("Hukuk", "get_bedesten_document", "Karar tam metnini getirir"),
    ("Hukuk", "search_anayasa_unified", "Anayasa Mahkemesi kararları"),
    ("Hukuk", "get_anayasa_document", "Anayasa Mahkemesi karar tam metni (sayfalı)"),
    ("Hukuk", "search_emsal", "EMSAL (UYAP) örnek kararlar"),
    ("Hukuk", "get_emsal_document", "EMSAL karar tam metni"),
    ("Hukuk", "search_kik_v2_decisions", "Kamu İhale Kurumu kararları"),
    ("Hukuk", "get_kik_document", "KİK kurul kararı tam metni"),
    ("Hukuk", "search_rekabet_kurumu", "Rekabet Kurumu kararları"),
    ("Hukuk", "get_rekabet_document", "Rekabet Kurumu karar tam metni (sayfalı PDF)"),
    ("Hukuk", "search_sayistay_unified", "Sayıştay kararları"),
    ("Hukuk", "search_kvkk_decisions", "KVKK kararları"),
    ("Hukuk", "search_bddk_decisions", "BDDK kararları"),
    ("Hukuk", "search_sigorta_tahkim", "Sigorta Tahkim kararları"),
    ("Hukuk", "search_uyusmazlik", "Uyuşmazlık Mahkemesi kararları"),
    ("Mevzuat", "search_resmi_gazete", "Resmi Gazete belge arama"),
    ("Mevzuat", "get_daily_bulletin", "Günlük Resmi Gazete bülteni"),
    ("Mevzuat", "get_recent_mali_changes", "Son N günün mali belgeleri"),
    ("Mevzuat", "search_mevzuat_bedesten", "Mevzuat araması (kanun, KHK, yönetmelik)"),
    ("Mevzuat", "get_mevzuat_document", "Mevzuat tam metni"),
    ("Mevzuat", "get_mevzuat_article", "Mevzuat belirli madde metni"),
    ("Mevzuat", "get_mevzuat_article_tree", "Mevzuat madde ağacı (içindekiler)"),
    ("Mevzuat", "search_mevzuat", "Mevzuat.gov.tr araması (alternatif kaynak)"),
    ("Mali", "search_gib_sirkuler", "GİB sirküler arama"),
    ("Mali", "get_tax_calendar", "Vergi takvimi"),
    ("Mali", "check_efatura_taxpayer", "VKN/TCKN e-Fatura mükellef sorgu"),
    ("Mali", "get_asgari_ucret", "Asgari ücret bilgileri"),
    ("Mali", "get_prim_matrahi", "SGK prim matrahı ve oranları"),
    ("Mali", "get_turmob_pratik_bilgiler", "TÜRMOB pratik bilgiler"),
    ("Mali", "get_ismmmo_pratik_bilgiler", "İSMMMO pratik bilgiler"),
    ("İhale", "search_tenders", "Kamu ihaleleri (EKAP v2)"),
    ("İhale", "get_recent_tenders", "Son N günün ihaleleri"),
    ("İhale", "search_ilan_ads", "Resmi ilanlar (ilan.gov.tr)"),
    ("Piyasa", "get_bist_stock", "BIST hisse verileri"),
    ("Piyasa", "get_fx_rates", "Döviz kurları"),
    ("Piyasa", "get_crypto", "Kripto para verileri"),
    ("UYAP", "parse_uyap_document", "UYAP EYP/UDF belge çözümleme"),
    ("UYAP", "get_uyap_parties", "UYAP belgesindeki taraflar"),
    ("UYAP", "get_uyap_references", "UYAP belgesindeki referanslar"),
    ("Sistem", "check_health", "Tüm modüllerin durumu"),
    ("Süreler", "list_deadlines", "Hukuki süreleri listele"),
    ("Süreler", "add_deadline", "Yeni hukuki süre ekle"),
    ("Süreler", "get_upcoming_deadlines", "Yaklaşan süreleri getir"),
    ("Süreler", "get_overdue_deadlines", "Gecikmiş süreleri getir"),
    ("Süreler", "compute_deadline", "Süre bitiş tarihini hesapla"),
    ("Dava", "list_dava_kartlari", "Dava kartlarını listele"),
    ("Dava", "add_dava_karti", "Yeni dava kartı ekle"),
    ("Dava", "search_dava_kartlari", "Dava kartlarında ara"),
    ("Dava", "link_deadline_to_dava", "Dava kartına süre bağla"),
    ("Yedek", "create_backup", "Veri yedeği oluştur"),
    ("Yedek", "list_backups", "Mevcut yedekleri listele"),
]


async def tools_catalog_endpoint(request):
    """Mevcut MCP araçlarını kategori bazında listeler (yalnızca aktif modüller)."""
    routed = set(TOOL_ROUTING.values())
    items = []
    for cat, name, desc in TOOLS_CATALOG:
        available = name in globals() and callable(globals().get(name))
        items.append({
            "category": cat, "name": name, "description": desc,
            "available": available, "auto_routed": name in routed,
        })
    cats = {}
    for it in items:
        cats.setdefault(it["category"], 0)
        if it["available"]:
            cats[it["category"]] += 1
    return JSONResponse({"tools": items, "total": len(items),
                         "available": sum(1 for i in items if i["available"]),
                         "categories": cats})


async def test_llm_endpoint(request):
    """LLM sağlayıcı bağlantısını/anahtarını hızlıca test eder.

    Body/Header: provider, api_key, model. Kısa bir "ping" mesajı gönderir.
    """
    provider_id, api_key, model = _get_llm_config(request)
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

    if provider_id not in LLM_PROVIDERS:
        return JSONResponse({"ok": False, "error": f"Bilinmeyen sağlayıcı: {provider_id}"}, status_code=400)
    pc = LLM_PROVIDERS[provider_id]
    if not model:
        model = pc["default_model"]
    if pc["needs_key"] and not api_key:
        return JSONResponse({"ok": False, "error": "API anahtarı gerekli."}, status_code=200)

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            if pc.get("is_anthropic"):
                resp = await client.post(pc["url"], headers={
                    "x-api-key": api_key, "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                }, json={"model": model, "max_tokens": 8,
                         "messages": [{"role": "user", "content": "ping"}]})
            else:
                headers = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                resp = await client.post(pc["url"], headers=headers, json={
                    "model": model, "max_tokens": 8,
                    "messages": [{"role": "user", "content": "ping"}]})
            if resp.status_code < 300:
                return JSONResponse({"ok": True, "provider": provider_id, "model": model,
                                     "message": "Bağlantı başarılı."})
            return JSONResponse({"ok": False, "status": resp.status_code,
                                 "error": resp.text[:240]}, status_code=200)
    except httpx.ConnectError:
        msg = ("Yerel Ollama'ya bağlanılamadı (localhost:11434)." if provider_id == "ollama"
               else "Sağlayıcıya bağlanılamadı.")
        return JSONResponse({"ok": False, "error": msg}, status_code=200)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=200)


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

    message = (body.get("message", "") or "").strip()[:2000]
    if not message:
        return JSONResponse({"error": "Mesaj bos olamaz."}, status_code=400)

    # Yüklenen belge bağlamı (frontend'den ekli dosyaların metni)
    document_context = (body.get("document_context") or "").strip()
    if len(document_context) > 14000:
        document_context = document_context[:14000] + "\n…(belge kısaltıldı)"

    # Çok turlu süreklilik: önceki mesajlar
    raw_history = body.get("history") or []
    history = []
    if isinstance(raw_history, list):
        for h in raw_history[-12:]:  # son 12 mesaj
            role = h.get("role")
            text = (h.get("text") or h.get("content") or "").strip()
            if role in ("user", "assistant") and text:
                history.append({"role": role, "content": text[:2000]})

    # MCP araçlarını çağır — kullanıcı mesajı üzerinden
    tool_context, called_tools = await _route_and_call(message)

    # Kullanıcı emsal/içtihat isterse veya belge ekliyse: emsal kararların
    # GERÇEK METİNLERİNİ çek (belgenin kendi numaralarını değil, KONUSUNU arar).
    wants_precedent = any(k in message.lower() for k in
                          ["emsal", "içtihat", "ictihat", "benzer karar", "örnek karar",
                           "ornek karar", "karşılaştır", "karsilastir", "benzer"])
    emsal_query = ""
    if wants_precedent or document_context:
        basis_text = (document_context + " " + message) if document_context else message
        emsal_query = _legal_search_terms(basis_text)
        if not emsal_query:
            # konu çıkarılamadıysa belge konusundan/mesajdan kısa bir sorgu
            emsal_query = (message or "")[:70]
        try:
            criminal = _is_criminal_context(basis_text)
            emsal_block = await _fetch_emsal_with_content(emsal_query, criminal=criminal, limit=3)
            if emsal_block:
                tool_context = (tool_context + "\n---\n" if tool_context else "") + emsal_block
                called_tools.add("search_bedesten_unified")
                called_tools.add("get_bedesten_document")
        except Exception:
            pass

    # Belge türü + ilgili geçmiş kayıtlar (frontend'den)
    doc_type = (body.get("doc_type") or "").strip()
    related = body.get("related") or []

    # Bağlama göre uzmanlık yönergelerini (skills) seç
    skills_prompt = ""
    skills_used = []
    if SKILLS_AVAILABLE:
        try:
            selected = skills_engine.select_skills(message, doc_type)
            skills_prompt = skills_engine.build_skills_prompt(selected)
            skills_used = [s["name"] for s in selected]
        except Exception:
            skills_prompt = ""

    # Belge bağlamı varsa sistem yönergesini güçlendir
    doc_system = ""
    if document_context:
        dt_label = (" (" + doc_type + ")") if doc_type else ""
        doc_system = (
            f"\n\nKULLANICI BİR BELGE YÜKLEDİ{dt_label}. Önce belgenin türünü, taraflarını ve "
            "konusunu (suç tipi/uyuşmazlık) kısaca özetle. Soru belgeyle ilgisizse kibarca belirt, "
            "sonra yine de yanıtla.\n\n--- BELGE İÇERİĞİ ---\n"
            + document_context + "\n--- BELGE SONU ---"
        )

    # Emsal kararların GERÇEK metni çekildiyse: katı kullanım + künye + karşılaştırma yönergesi
    emsal_system = ""
    if "EMSAL ARAMA" in (tool_context or ""):
        emsal_system = (
            "\n\nEMSAL KARARLAR — ÖNEMLİ KURALLAR:\n"
            "1. Aşağıdaki MCP araç sonuçlarında 'KARAR TAM METNİ' başlıklı bölümler GERÇEK karar "
            "metinleridir. Karşılaştırma ve sonuç çıkarımını YALNIZCA bu metinlere dayandır.\n"
            "2. ASLA uydurma karar veya genel 'genellikle ... ile ilgilidir' türü tahmini açıklama "
            "yazma. Bir kararın içeriğini ancak metni verildiyse aktar.\n"
            "3. Her emsal için künyeyi tam yaz: **Mahkeme/Daire | Esas No | Karar No | (Bedesten ID)**. "
            "ID, kullanıcının UYAP/Bedesten'de karara ulaşması için referanstır.\n"
            "4. Şu yapıyı kullan: (a) Belgedeki olay ve hukuki nitelendirme, (b) Her emsal kararın "
            "ilgili kısmı ve ortaya koyduğu ilke, (c) **Benzerlik/Farklılık** (olgular, deliller, "
            "hukuki nitelendirme), (d) **Olası sonuç** (lehte/aleyhte, ihtiyatlı dille), (e) öneriler.\n"
            "5. İçerik çekilemediyse bunu açıkça belirt; künye listesini emsal olarak sun ama içerik "
            "uydurma."
        )

    # Çapraz hafıza: kullanıcının çalışma alanındaki benzer kayıtlar
    related_system = ""
    if related:
        lines = []
        for r in related[:5]:
            m = r.get("matched", [{}])
            tag = m[0].get("value", "") if m else ""
            lines.append(f"- '{r.get('title','')}' ({r.get('folder','Genel')}) — eşleşme: {tag}")
        related_system = (
            "\n\nİLGİLİ GEÇMİŞ KAYITLAR (çalışma alanından): Aşağıdaki kayıtlarda benzer "
            "belge/uyuşmazlık tespit edildi. Yanıtında uygun yerde kullanıcıyı bunlara yönlendir "
            "('Çalışma alanınızdaki … kaydında benzer bir durum var' gibi):\n" + "\n".join(lines)
        )

    full_system = SYSTEM_PROMPT
    if skills_prompt:
        full_system += "\n\n" + skills_prompt
    full_system += doc_system + emsal_system + related_system
    # Bellek enjeksiyonu
    if MEMORY_AVAILABLE:
        mems = memory_mod.list_memories()
        if mems:
            cat_labels = {"preference": "tercih", "fact": "olgu", "instruction": "talimat"}
            mem_lines = [f"- [{cat_labels.get(m['category'], m['category'])}] {m['content']}" for m in mems]
            full_system += (
                "\n\nKULLANICI HAFIZASI (öncelikli — bu bilgileri her yanıtta göz önünde bulundur):\n"
                + "\n".join(mem_lines)
            )
    # Süre hatırlatma enjeksiyonu
    if DEADLINES_AVAILABLE:
        try:
            upcoming = deadlines_mod.get_upcoming(days=30)
            overdue = deadlines_mod.get_overdue()
            if upcoming or overdue:
                dl_lines = []
                if overdue:
                    dl_lines.append("GECİKMİŞ SÜRELER (acil harekete geçirilmeli):")
                    for d in overdue:
                        dl_lines.append(f"  - [{d['category']}] {d['title']} — bitiş: {d['deadline_date']} (GECİKMİŞ!)")
                if upcoming:
                    dl_lines.append("YAKLAŞAN SÜRELER:")
                    for d in upcoming:
                        dl_lines.append(f"  - [{d['category']}] {d['title']} — bitiş: {d['deadline_date']}")
                full_system += "\n\nHUKUKİ SÜRE HATIRLATMA (kullanıcıyı uyar):\n" + "\n".join(dl_lines)
        except Exception:
            pass
    if DAVA_AVAILABLE:
        try:
            kartlar = dava_mod.list_kartlar(durum="devam_ediyor")
            if kartlar:
                dava_lines = ["AKTİF DAVA DOSYALARI:"]
                for k in kartlar[:5]:
                    tarafs = f"{k.get('taraf_muvekkil', '')} vs {k.get('taraf_karsi', '')}".strip(' vs')
                    dava_lines.append(f"  - [{dava_mod.DAVA_TURLERI.get(k['dava_turu'], {}).get('label', k['dava_turu'])}] {k['esas_no']} — {tarafs} ({k.get('daire', '')})")
                if len(kartlar) > 5:
                    dava_lines.append(f"  ... ve {len(kartlar)-5} dosya daha")
                full_system += "\n\n" + "\n".join(dava_lines)
        except Exception:
            pass
    if tool_context:
        full_system += f"\n\nMCP araç sonuçları:\n\n{tool_context}"

    # ---- Gateway üzerinden tamamlama (failover zinciri) ----
    # Birincil model + kullanıcının tanımladığı yedek modeller (failover)
    chain = [{"provider": provider_id, "model": model}]
    client_fallbacks = body.get("fallbacks") or []
    # Istemci fallback yoksa, sunucu tarafindaki kayitli default_chain kullan
    if not client_fallbacks and GATEWAY_AVAILABLE:
        try:
            _gw_cfg = gateway_mod.load_config()
            client_fallbacks = _gw_cfg.get("default_chain", [])
        except Exception:
            pass
    for fb in client_fallbacks[:4]:
        p = (fb.get("provider") or "").lower()
        if p in LLM_PROVIDERS:
            chain.append({"provider": p, "model": fb.get("model") or LLM_PROVIDERS[p]["default_model"]})

    # Sağlayıcı başına anahtarlar (birincil header + body'deki api_keys haritası)
    api_keys_map = {provider_id: api_key}
    for k, v in (body.get("api_keys") or {}).items():
        if v:
            api_keys_map[(k or "").lower()] = v
    if OPENROUTER_API_KEY and "openrouter" not in api_keys_map:
        api_keys_map["openrouter"] = OPENROUTER_API_KEY

    try:
        timeout_override = int(body.get("timeout_override") or 0)
    except Exception:
        timeout_override = 0

    def _timeout_for(pid):
        if timeout_override and 10 <= timeout_override <= 600:
            return timeout_override
        # Kaydedilmis saglayici timeout'u (gateway config)
        pc = LLM_PROVIDERS.get(pid, {})
        if "timeout" in pc and isinstance(pc["timeout"], (int, float)) and pc["timeout"] >= 10:
            return int(pc["timeout"])
        return 300 if pid == "ollama" else 120

    result = await GATEWAY.complete(
        system=full_system, history=history, message=message,
        chain=chain, api_keys=api_keys_map, timeout_for=_timeout_for,
    )

    remaining = RATE_LIMIT_PER_IP - len(ip_rate_limits.get(request.client.host if request.client else "unknown", []))
    if result.get("error"):
        return JSONResponse({"error": result["error"], "attempts": result.get("attempts", []),
                             "remaining": remaining}, status_code=502)

    return JSONResponse({
        "response": result["reply"],
        "sources": list(called_tools)[:5],
        "skills_used": skills_used,
        "attempts": result.get("attempts", []),
        "usage": result.get("usage", {}),
        "context": result.get("context", {}),
        "remaining": remaining,
        "provider": result["provider"],
        "model": result["model"],
    })


async def chat_stream_endpoint(request):
    """Chat SSE endpoint — streaming LLM yanıtı üretir.

    /api/chat ile aynı hazırlık kodunu kullanır, ancak yanıt tek JSON yerine
    SSE event'leri (meta, token, done, error) olarak gönderilir.
    Frontend fetch + ReadableStream ile token-token okur.
    """
    # LLM yapılandırmasını al
    provider_id, api_key, model = _get_llm_config(request)

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

    if provider_id not in LLM_PROVIDERS:
        err = json.dumps({"message": f"Bilinmeyen sağlayıcı: {provider_id}"})
        return StreamingResponse(
            iter([f"event: error\ndata: {err}\n\n"]),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    provider_config = LLM_PROVIDERS[provider_id]

    if provider_config["needs_key"] and not api_key:
        err = json.dumps({"message": "API anahtarı gerekli.", "needs_key": True,
                          "provider": provider_id})
        return StreamingResponse(
            iter([f"event: error\ndata: {err}\n\n"]),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # IP rate limiting
    if provider_config["needs_key"]:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        day_ago = now - 86400
        ip_rate_limits[client_ip] = [t for t in ip_rate_limits.get(client_ip, []) if t > day_ago]
        if len(ip_rate_limits[client_ip]) >= RATE_LIMIT_PER_IP:
            err = json.dumps({"message": f"Günlük limit aşıldı ({RATE_LIMIT_PER_IP} istek/IP)."})
            return StreamingResponse(
                iter([f"event: error\ndata: {err}\n\n"]),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        ip_rate_limits.setdefault(client_ip, []).append(now)

    message = (body.get("message", "") or "").strip()[:2000]
    if not message:
        err = json.dumps({"message": "Mesaj boş olamaz."})
        return StreamingResponse(
            iter([f"event: error\ndata: {err}\n\n"]),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Belge bağlamı, geçmiş, MCP araçları, emsal, skills — /api/chat ile aynı
    document_context = (body.get("document_context") or "").strip()
    if len(document_context) > 14000:
        document_context = document_context[:14000] + "\n…(belge kısaltıldı)"

    raw_history = body.get("history") or []
    history = []
    if isinstance(raw_history, list):
        for h in raw_history[-12:]:
            role = h.get("role")
            text = (h.get("text") or h.get("content") or "").strip()
            if role in ("user", "assistant") and text:
                history.append({"role": role, "content": text[:2000]})

    tool_context, called_tools = await _route_and_call(message)

    wants_precedent = any(k in message.lower() for k in
                          ["emsal", "içtihat", "ictihat", "benzer karar", "örnek karar",
                           "ornek karar", "karşılaştır", "karsilastir", "benzer"])
    if wants_precedent or document_context:
        basis_text = (document_context + " " + message) if document_context else message
        emsal_query = _legal_search_terms(basis_text)
        if not emsal_query:
            emsal_query = (message or "")[:70]
        try:
            criminal = _is_criminal_context(basis_text)
            emsal_block = await _fetch_emsal_with_content(emsal_query, criminal=criminal, limit=3)
            if emsal_block:
                tool_context = (tool_context + "\n---\n" if tool_context else "") + emsal_block
                called_tools.add("search_bedesten_unified")
                called_tools.add("get_bedesten_document")
        except Exception:
            pass

    doc_type = (body.get("doc_type") or "").strip()
    related = body.get("related") or []

    skills_prompt = ""
    skills_used = []
    if SKILLS_AVAILABLE:
        try:
            selected = skills_engine.select_skills(message, doc_type)
            skills_prompt = skills_engine.build_skills_prompt(selected)
            skills_used = [s["name"] for s in selected]
        except Exception:
            skills_prompt = ""

    doc_system = ""
    if document_context:
        dt_label = (" (" + doc_type + ")") if doc_type else ""
        doc_system = (
            f"\n\nKULLANICI BİR BELGE YÜKLEDİ{dt_label}. Önce belgenin türünü, taraflarını ve "
            "konusunu (suç tipi/uyuşmazlık) kısaca özetle. Soru belgeyle ilgisizse kibarca belirt, "
            "sonra yine de yanıtla.\n\n--- BELGE İÇERİĞİ ---\n"
            + document_context + "\n--- BELGE SONU ---"
        )

    emsal_system = ""
    if "EMSAL ARAMA" in (tool_context or ""):
        emsal_system = (
            "\n\nEMSAL KARARLAR — ÖNEMLİ KURALLAR:\n"
            "1. Aşağıdaki MCP araç sonuçlarında 'KARAR TAM METNİ' başlıklı bölümler GERÇEK karar "
            "metinleridir. Karşılaştırma ve sonuç çıkarımını YALNIZCA bu metinlere dayandır.\n"
            "2. ASLA uydurma karar veya genel 'genellikle ... ile ilgilidir' türü tahmini açıklama "
            "yazma. Bir kararın içeriğini ancak metni verildiyse aktar.\n"
            "3. Her emsal için künyeyi tam yaz: **Mahkeme/Daire | Esas No | Karar No | (Bedesten ID)**. "
            "ID, kullanıcının UYAP/Bedesten'de karara ulaşması için referanstır.\n"
            "4. Şu yapıyı kullan: (a) Belgedeki olay ve hukuki nitelendirme, (b) Her emsal kararın "
            "ilgili kısmı ve ortaya koyduğu ilke, (c) **Benzerlik/Farklılık** (olgular, deliller, "
            "hukuki nitelendirme), (d) **Olası sonuç** (lehte/aleyhte, ihtiyatlı dille), (e) öneriler.\n"
            "5. İçerik çekilemediyse bunu açıkça belirt; künye listesini emsal olarak sun ama içerik "
            "uydurma."
        )

    related_system = ""
    if related:
        lines = []
        for r in related[:5]:
            m = r.get("matched", [{}])
            tag = m[0].get("value", "") if m else ""
            lines.append(f"- '{r.get('title','')}' ({r.get('folder','Genel')}) — eşleşme: {tag}")
        related_system = (
            "\n\nİLGİLİ GEÇMİŞ KAYITLAR (çalışma alanından): Aşağıdaki kayıtlarda benzer "
            "belge/uyuşmazlık tespit edildi. Yanıtında uygun yerde kullanıcıyı bunlara yönlendir "
            "('Çalışma alanınızdaki … kaydında benzer bir durum var' gibi):\n" + "\n".join(lines)
        )

    full_system = SYSTEM_PROMPT
    if skills_prompt:
        full_system += "\n\n" + skills_prompt
    full_system += doc_system + emsal_system + related_system
    if MEMORY_AVAILABLE:
        mems = memory_mod.list_memories()
        if mems:
            cat_labels = {"preference": "tercih", "fact": "olgu", "instruction": "talimat"}
            mem_lines = [f"- [{cat_labels.get(m['category'], m['category'])}] {m['content']}" for m in mems]
            full_system += (
                "\n\nKULLANICI HAFIZASI (öncelikli — bu bilgileri her yanıtta göz önünde bulundur):\n"
                + "\n".join(mem_lines)
            )
    # Süre hatırlatma enjeksiyonu
    if DEADLINES_AVAILABLE:
        try:
            upcoming = deadlines_mod.get_upcoming(days=30)
            overdue = deadlines_mod.get_overdue()
            if upcoming or overdue:
                dl_lines = []
                if overdue:
                    dl_lines.append("GECİKMİŞ SÜRELER (acil harekete geçirilmeli):")
                    for d in overdue:
                        dl_lines.append(f"  - [{d['category']}] {d['title']} — bitiş: {d['deadline_date']} (GECİKMİŞ!)")
                if upcoming:
                    dl_lines.append("YAKLAŞAN SÜRELER:")
                    for d in upcoming:
                        dl_lines.append(f"  - [{d['category']}] {d['title']} — bitiş: {d['deadline_date']}")
                full_system += "\n\nHUKUKİ SÜRE HATIRLATMA (kullanıcıyı uyar):\n" + "\n".join(dl_lines)
        except Exception:
            pass
    if DAVA_AVAILABLE:
        try:
            kartlar = dava_mod.list_kartlar(durum="devam_ediyor")
            if kartlar:
                dava_lines = ["AKTİF DAVA DOSYALARI:"]
                for k in kartlar[:5]:
                    tarafs = f"{k.get('taraf_muvekkil', '')} vs {k.get('taraf_karsi', '')}".strip(' vs')
                    dava_lines.append(f"  - [{dava_mod.DAVA_TURLERI.get(k['dava_turu'], {}).get('label', k['dava_turu'])}] {k['esas_no']} — {tarafs} ({k.get('daire', '')})")
                if len(kartlar) > 5:
                    dava_lines.append(f"  ... ve {len(kartlar)-5} dosya daha")
                full_system += "\n\n" + "\n".join(dava_lines)
        except Exception:
            pass
    if tool_context:
        full_system += f"\n\nMCP araç sonuçları:\n\n{tool_context}"

    # Failover zinciri
    chain = [{"provider": provider_id, "model": model}]
    client_fallbacks = body.get("fallbacks") or []
    if not client_fallbacks and GATEWAY_AVAILABLE:
        try:
            _gw_cfg = gateway_mod.load_config()
            client_fallbacks = _gw_cfg.get("default_chain", [])
        except Exception:
            pass
    for fb in client_fallbacks[:4]:
        p = (fb.get("provider") or "").lower()
        if p in LLM_PROVIDERS:
            chain.append({"provider": p, "model": fb.get("model") or LLM_PROVIDERS[p]["default_model"]})

    api_keys_map = {provider_id: api_key}
    for k, v in (body.get("api_keys") or {}).items():
        if v:
            api_keys_map[(k or "").lower()] = v
    if OPENROUTER_API_KEY and "openrouter" not in api_keys_map:
        api_keys_map["openrouter"] = OPENROUTER_API_KEY

    try:
        timeout_override = int(body.get("timeout_override") or 0)
    except Exception:
        timeout_override = 0

    def _timeout_for(pid):
        if timeout_override and 10 <= timeout_override <= 600:
            return timeout_override
        pc = LLM_PROVIDERS.get(pid, {})
        if "timeout" in pc and isinstance(pc["timeout"], (int, float)) and pc["timeout"] >= 10:
            return int(pc["timeout"])
        return 300 if pid == "ollama" else 120

    remaining = RATE_LIMIT_PER_IP - len(ip_rate_limits.get(request.client.host if request.client else "unknown", []))

    # SSE generator
    async def _sse_gen():
        try:
            async for event in GATEWAY.stream(
                system=full_system, history=history, message=message,
                chain=chain, api_keys=api_keys_map, timeout_for=_timeout_for,
            ):
                if await request.is_disconnected():
                    break
                if event["type"] == "meta":
                    yield f"event: meta\ndata: {json.dumps({'provider': event['provider'], 'model': event['model']})}\n\n"
                elif event["type"] == "token":
                    yield f"event: token\ndata: {json.dumps({'content': event.get('content', ''), 'reasoning': event.get('reasoning', '')})}\n\n"
                elif event["type"] == "done":
                    payload = {
                        "sources": list(called_tools)[:5],
                        "skills_used": skills_used,
                        "attempts": event.get("attempts", []),
                        "usage": event.get("usage", {}),
                        "context": event.get("context", {}),
                        "remaining": remaining,
                    }
                    yield f"event: done\ndata: {json.dumps(payload)}\n\n"
                elif event["type"] == "error":
                    payload = {"message": event.get("message", ""), "attempts": event.get("attempts", [])}
                    yield f"event: error\ndata: {json.dumps(payload)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(
        _sse_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ============================================================
# ASGI APPLICATION
# ============================================================

# Get FastMCP's ASGI app via http_app(transport="sse")
# http_app() supports transport="http" | "streamable-http" | "sse"
mcp_asgi = app.http_app(transport="sse")

# Build Starlette app with dashboard + MCP mount
# NOTE: Don't pass lifespan from mcp_asgi — it causes 500 errors.
# The FastMCP lifespan is incompatible with Starlette's and crashes on startup.
starlette_app = Starlette(
    middleware=[
        Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]),
    ],
    routes=[
        Route("/", homepage),
        Route("/health", health_endpoint),
        Route("/api/chat", chat_endpoint, methods=["POST"]),
        Route("/api/chat/stream", chat_stream_endpoint, methods=["POST"]),
        Route("/api/chat/providers", providers_endpoint, methods=["GET"]),
        Route("/api/chat/configure", configure_llm_endpoint, methods=["POST"]),
        Route("/api/chat/status", llm_status_endpoint, methods=["GET"]),
        Route("/api/chat/test", test_llm_endpoint, methods=["POST"]),
        Route("/api/ollama/models", ollama_models_endpoint, methods=["GET"]),
        Route("/api/skills", skills_endpoint, methods=["GET"]),
        Route("/api/skills/toggle", skills_toggle_endpoint, methods=["POST"]),
        Route("/api/skills/content", skills_content_endpoint, methods=["GET"]),
        Route("/api/skills/save", skills_save_endpoint, methods=["POST"]),
        Route("/api/gateway/status", gateway_status_endpoint, methods=["GET"]),
        Route("/api/gateway/config", gateway_config_endpoint, methods=["GET", "POST"]),
        Route("/api/computer/permissions", computer_permissions_endpoint, methods=["GET", "POST"]),
        Route("/api/tools", tools_catalog_endpoint, methods=["GET"]),
        Route("/api/upload/pdf", upload_pdf_endpoint, methods=["POST"]),
        Route("/api/export/docx", export_docx_endpoint, methods=["POST"]),
        Route("/api/search/refs", search_document_refs_endpoint, methods=["POST"]),
        Route("/api/upload/uyap", upload_uyap_endpoint, methods=["POST"]),
        Route("/api/workspace", workspace_snapshot_endpoint, methods=["GET"]),
        Route("/api/workspace/folder", workspace_folder_endpoint, methods=["POST"]),
        Route("/api/workspace/session", workspace_session_get_endpoint, methods=["GET"]),
        Route("/api/workspace/session", workspace_session_save_endpoint, methods=["POST"]),
        Route("/api/workspace/session/delete", workspace_session_delete_endpoint, methods=["POST"]),
        Route("/api/workspace/file", workspace_file_upload_endpoint, methods=["POST"]),
        Route("/api/workspace/files", workspace_files_list_endpoint, methods=["GET"]),
        Route("/api/workspace/file/delete", workspace_file_delete_endpoint, methods=["POST"]),
        Route("/api/memory", memory_list_endpoint, methods=["GET"]),
        Route("/api/memory", memory_add_endpoint, methods=["POST"]),
        Route("/api/memory/update", memory_update_endpoint, methods=["POST"]),
        Route("/api/memory/delete", memory_delete_endpoint, methods=["POST"]),
        Route("/api/memory/learn", memory_learn_endpoint, methods=["POST"]),
        Route("/api/memory/clear", memory_clear_endpoint, methods=["POST"]),
        # Süre takip
        Route("/api/deadlines", deadline_list_endpoint, methods=["GET"]),
        Route("/api/deadlines", deadline_add_endpoint, methods=["POST"]),
        Route("/api/deadlines/update", deadline_update_endpoint, methods=["POST"]),
        Route("/api/deadlines/delete", deadline_delete_endpoint, methods=["POST"]),
        Route("/api/deadlines/complete", deadline_complete_endpoint, methods=["POST"]),
        Route("/api/deadlines/upcoming", deadline_upcoming_endpoint, methods=["GET"]),
        Route("/api/deadlines/overdue", deadline_overdue_endpoint, methods=["GET"]),
        # Dava kartları
        Route("/api/dava-kartlari", dava_list_endpoint, methods=["GET"]),
        Route("/api/dava-kartlari", dava_add_endpoint, methods=["POST"]),
        Route("/api/dava-kartlari/update", dava_update_endpoint, methods=["POST"]),
        Route("/api/dava-kartlari/delete", dava_delete_endpoint, methods=["POST"]),
        Route("/api/dava-kartlari/search", dava_search_endpoint, methods=["GET"]),
        Route("/api/dava-kartlari/link-deadline", dava_link_deadline_endpoint, methods=["POST"]),
        Route("/api/dava-kartlari/unlink-deadline", dava_unlink_deadline_endpoint, methods=["POST"]),
        # Yedekleme
        Route("/api/backup", backup_list_endpoint, methods=["GET"]),
        Route("/api/backup/create", backup_create_endpoint, methods=["POST"]),
        Route("/api/backup/restore", backup_restore_endpoint, methods=["POST"]),
        Route("/api/backup/download", backup_download_endpoint, methods=["GET"]),
        Route("/api/backup/delete", backup_delete_endpoint, methods=["POST"]),
        Route("/api/cache/stats", cache_stats_endpoint, methods=["GET"]),
        Route("/api/cache/clear", cache_clear_endpoint, methods=["POST"]),
        Route("/api/settings/api-keys", api_keys_endpoint, methods=["GET", "POST"]),
        Mount("/static", app=StaticFiles(directory=str(_base_path() / "static")), name="static"),
        Mount("/", app=mcp_asgi),
    ],
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