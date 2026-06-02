# -*- mode: python ; coding: utf-8 -*-
"""Türkiye MCP Server — PyInstaller spec dosyası.

Kullanım:
    pyinstaller turkiye_mcp.spec

veya:
    build.bat

Not: İlk çalıştırmada PyInstaller dependency'leri otomatik bulur.
Sonraki çalıştırmalarda sadece değişen dosyalar yeniden analiz edilir.
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

# Proje kök dizini
PROJECT_ROOT = os.path.dirname(os.path.abspath(SPECPATH))

# ── Hidden imports ──
# PyInstaller'ın otomatik bulamayacağı modüller
hidden_imports = [
    # Core
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    # FastMCP
    "fastmcp",
    "fastmcp.server",
    "fastmcp.server.http_app",
    # Starlette
    "starlette",
    "starlette.routing",
    "starlette.middleware",
    "starlette.middleware.cors",
    "starlette.responses",
    # HTTP
    "httpx",
    "h2",
    "hpack",
    # HTML/XML
    "bs4",
    "lxml",
    "lxml._elementpath",
    "html.parser",
    # Pydantic
    "pydantic",
    "pydantic.deprecated",
    "pydantic.deprecated.decorator",
    # PDF
    "pypdf",
    "markitdown",
    # Feeds
    "feedparser",
    # Crypto
    "cryptography",
    "cryptography.hazmat",
    "cryptography.hazmat.primitives",
    # Date
    "python_dateutil",
    "dateutil",
    # Financial
    "yfinance",
    "pandas",
    "borsapy",
    "yfscreen",
    "tradingview_screener",
    # Local modules
    "resmi_gazete_module",
    "resmi_gazete_module.client",
    "resmi_gazete_module.models",
    "mevzuat_module",
    "mevzuat_module.client",
    "mevzuat_module.models",
    "gib_module",
    "gib_module.client",
    "gib_module.models",
    "ivd_module",
    "ivd_module.client",
    "ivd_module.models",
    "sgk_module",
    "sgk_module.client",
    "sgk_module.models",
    "iskur_module",
    "iskur_module.client",
    "iskur_module.models",
    "turmob_module",
    "turmob_module.client",
    "turmob_module.models",
    "ismmmo_module",
    "ismmmo_module.client",
    "ismmmo_module.models",
    "bedesten_mcp_module",
    "bedesten_mcp_module.client",
    "bedesten_mcp_module.models",
    "anayasa_mcp_module",
    "anayasa_mcp_module.unified_client",
    "anayasa_mcp_module.models",
    "kik_mcp_module",
    "kik_mcp_module.client_v2",
    "kik_mcp_module.models_v2",
    "rekabet_mcp_module",
    "rekabet_mcp_module.client",
    "rekabet_mcp_module.models",
    "sayistay_mcp_module",
    "sayistay_mcp_module.unified_client",
    "sayistay_mcp_module.models",
    "bddk_mcp_module",
    "bddk_mcp_module.client",
    "bddk_mcp_module.models",
    "kvkk_mcp_module",
    "kvkk_mcp_module.client",
    "kvkk_mcp_module.models",
    "sigorta_tahkim_mcp_module",
    "sigorta_tahkim_mcp_module.client",
    "sigorta_tahkim_mcp_module.models",
    "uyusmazlik_mcp_module",
    "uyusmazlik_mcp_module.client",
    "uyusmazlik_mcp_module.models",
    "emsal_mcp_module",
    "emsal_mcp_module.client",
    "emsal_mcp_module.models",
    "ihale_module",
    "ihale_module.ihale_client",
    "ihale_module.ilan_client",
    "ihale_module.ihale_models",
    "borsa_module",
    "borsa_module.borsa_client",
    "borsa_models",
    "borsa_models.yfinance_models",
    "borsa_models.tcmb_models",
    "borsa_models.crypto_models",
    # GUI (optional)
    "webview",
    "pystray",
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
]

# ── Data files ──
# Pydantic, cryptography vb. metadata dosyaları
datas = []
for pkg in ["pydantic", "cryptography", "httpx", "h2", "hpack", "fastmcp", "uvicorn", "starlette"]:
    try:
        datas += copy_metadata(pkg)
    except Exception:
        pass

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
        # Gereksiz büyük paketler
        "tkinter",
        "unittest",
        "test",
        "tests",
        "setuptools",
        "pip",
        "wheel",
        "numpy.testing",
        "pandas.tests",
        "matplotlib",
        "scipy",
    ],
    noarchive=False,
)

# ── PYZ ──
pyz = PYZ(a.pure)

# ── EXE ──
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
    console=False,  # GUI uygulaması (konsol penceresi yok)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # TODO: Türkiye bayrağı .ico dosyası eklenecek
)