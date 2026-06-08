# -*- mode: python ; coding: utf-8 -*-
"""Turkiye MCP Server — macOS PyInstaller spec dosyası.

Kullanım:
    pyinstaller turkiye_mcp_mac.spec

macOS'te .app veya Unix executable uretir.
pywebview ve pystray macOS'te farkli calisir — rumps kullanilir.
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

PROJECT_ROOT = os.getcwd()

# Hidden imports — Windows spec ile ayni + macOS ozel
hidden_imports = [
    # Core
    "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
    "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan", "uvicorn.lifespan.on",
    # FastMCP
    "fastmcp", "fastmcp.server", "fastmcp.server.http_app",
    # Starlette
    "starlette", "starlette.routing", "starlette.middleware",
    "starlette.middleware.cors", "starlette.responses",
    # HTTP
    "httpx", "h2", "hpack",
    # HTML/XML
    "bs4", "lxml", "lxml._elementpath", "html.parser",
    # Pydantic
    "pydantic", "pydantic.deprecated", "pydantic.deprecated.decorator",
    # PDF & OCR
    "pymupdf", "fitz", "pymupdf._fitz", "pypdf", "markitdown",
    # Feeds
    "feedparser",
    # Crypto
    "cryptography", "cryptography.hazmat", "cryptography.hazmat.primitives",
    # Date
    "python_dateutil", "dateutil",
    # Financial
    "yfinance", "pandas", "borsapy", "yfscreen", "tradingview_screener",
    # Local modules
    "resmi_gazete_module", "resmi_gazete_module.client", "resmi_gazete_module.models",
    "mevzuat_module", "mevzuat_module.client", "mevzuat_module.models",
    "gib_module", "gib_module.client", "gib_module.models",
    "ivd_module", "ivd_module.client", "ivd_module.models",
    "sgk_module", "sgk_module.client", "sgk_module.models",
    "iskur_module", "iskur_module.client", "iskur_module.models",
    "turmob_module", "turmob_module.client", "turmob_module.models",
    "ismmmo_module", "ismmmo_module.client", "ismmmo_module.models",
    "bedesten_mcp_module", "bedesten_mcp_module.client", "bedesten_mcp_module.models",
    "anayasa_mcp_module", "anayasa_mcp_module.unified_client", "anayasa_mcp_module.models",
    "kik_mcp_module", "kik_mcp_module.client_v2", "kik_mcp_module.models_v2",
    "rekabet_mcp_module", "rekabet_mcp_module.client", "rekabet_mcp_module.models",
    "sayistay_mcp_module", "sayistay_mcp_module.unified_client", "sayistay_mcp_module.models",
    "bddk_mcp_module", "bddk_mcp_module.client", "bddk_mcp_module.models",
    "kvkk_mcp_module", "kvkk_mcp_module.client", "kvkk_mcp_module.models",
    "sigorta_tahkim_mcp_module", "sigorta_tahkim_mcp_module.client", "sigorta_tahkim_mcp_module.models",
    "uyusmazlik_mcp_module", "uyusmazlik_mcp_module.client", "uyusmazlik_mcp_module.models",
    "emsal_mcp_module", "emsal_mcp_module.client", "emsal_mcp_module.models",
    "ihale_module", "ihale_module.ihale_client", "ihale_module.ilan_client", "ihale_module.ihale_models",
    "borsa_module", "borsa_module.borsa_client",
    "borsa_models", "borsa_models.yfinance_models", "borsa_models.tcmb_models", "borsa_models.crypto_models",
    "uyap_module", "uyap_module.parser",
    "workspace", "skills", "gateway",
    # Keyring (macOS)
    "keyring", "keyring.backends", "keyring.backends.macOS",
    # macOS tray (rumps alternative)
    "rumps",
    # GUI (optional)
    "webview",
    "PIL", "PIL.Image", "PIL.ImageDraw",
]

# Data files
datas = []
for pkg in ["pydantic", "cryptography", "httpx", "h2", "hpack", "fastmcp", "uvicorn", "starlette"]:
    try:
        datas += copy_metadata(pkg)
    except Exception:
        pass

# Skill playbook'lari
_skills_dir = os.path.join(PROJECT_ROOT, "skills")
if os.path.isdir(_skills_dir):
    datas.append((_skills_dir, "skills"))

# magika model dosyalari
try:
    import magika
    magika_dir = os.path.dirname(magika.__file__)
    magika_models = os.path.join(magika_dir, "models", "standard_v3_3")
    if os.path.isdir(magika_models):
        datas.append((magika_models, "magika/models/standard_v3_3"))
    ct_kb = os.path.join(magika_dir, "config", "content_types_kb.min.json")
    if os.path.isfile(ct_kb):
        datas.append((os.path.dirname(ct_kb), "magika/config"))
except ImportError:
    pass

# Icon (macOS .icns formati — mevcut degilse atla)
icon_path = None
if os.path.isfile(os.path.join(PROJECT_ROOT, "T_MCP.icns")):
    icon_path = "T_MCP.icns"
elif os.path.isfile(os.path.join(PROJECT_ROOT, "T_MCP.ico")):
    icon_path = "T_MCP.ico"  # PyInstaller .ico'yu da kabul eder

# ── Analysis ──
a = Analysis(
    [os.path.join(PROJECT_ROOT, "local_run.py")],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "unittest", "test", "tests",
        "setuptools", "pip", "wheel",
        "numpy.testing", "pandas.tests",
        "matplotlib", "scipy",
    ],
    noarchive=False,
)

# ── PYZ ──
pyz = PYZ(a.pure)

# ── EXE (macOS Unix executable) ──
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="TurkiyeMCP",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # macOS'te konsol penceresi acmaz
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)

# ── .app bundle (opsiyonel — macOS uygulama paketi) ──
# macOS'te .app olarak paketlemek icin:
# coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, name="TurkiyeMCP")
# app = BUNDLE(coll, name="TurkiyeMCP.app", icon=icon_path)