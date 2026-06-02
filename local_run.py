#!/usr/bin/env python3
"""Türkiye MCP Server — Yerel Masaüstü Uygulaması.

Bu dosya yerel Windows EXE olarak çalıştırılır:
- ASGI sunucusunu 127.0.0.1:8080'de başlatır
- pywebview ile native pencere açar
- pystray ile sistem tepsisi ikonu sağlar
- Pencere kapatıldığında arka planda çalışmaya devam eder

Kullanım:
    python local_run.py          # Geliştirme modu
    python local_run.py --no-gui # Sadece sunucu (GUI yok)
    python local_run.py --browser # pywebview yerine tarayıcıda aç

    PyInstaller EXE: build.bat veya pyinstaller turkiye_mcp.spec
"""

import os
import sys
import threading
import logging
import time

# Windows konsol encoding sorunu çözümü
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Yerel mod bayrağı — app.py bunu kontrol eder
os.environ["TURKIYE_MCP_LOCAL"] = "1"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("turkiye_mcp.local")

PORT = 8080
HOST = "127.0.0.1"


def wait_for_server(host: str, port: int, timeout: float = 30.0) -> bool:
    """Sunucunun hazır olmasını bekle."""
    import httpx
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = httpx.get(f"http://{host}:{port}/health", timeout=2)
            if resp.status_code == 200:
                logger.info("[OK] Sunucu hazir!")
                return True
        except Exception:
            time.sleep(0.5)
    logger.error("[FAIL] Sunucu baslatilamadi (timeout).")
    return False


def start_server(host: str, port: int):
    """ASGI sunucusunu baslat (ayri thread'de)."""
    import uvicorn
    from app import starlette_app
    logger.info(f"Sunucu baslatiliyor: {host}:{port}")
    uvicorn.run(starlette_app, host=host, port=port, log_level="warning")


def create_tray_icon(on_quit):
    """Sistem tepsisi ikonu olustur.

    Returns:
        pystray.Icon or None (pystray yoksa)
    """
    try:
        from PIL import Image, ImageDraw
        import pystray
    except ImportError:
        logger.warning("pystray veya Pillow yuklu degil -- sistem tepsisi ikonu devre disi.")
        return None

    # Turkiye bayragi ikonu olustur (64x64)
    img = Image.new("RGB", (64, 64), "#E30A17")
    draw = ImageDraw.Draw(img)

    # Hilal (yarim ay) -- beyaz daire + kirmizi daire
    draw.ellipse([4, 4, 52, 60], fill="#FFFFFF")
    draw.ellipse([12, 4, 56, 56], fill="#E30A17")

    # Yildiz
    star_points = [
        (36, 16), (39, 26), (50, 26), (41, 33),
        (44, 44), (36, 37), (28, 44), (31, 33),
        (22, 26), (33, 26),
    ]
    draw.polygon(star_points, fill="#FFFFFF")

    menu = pystray.Menu(
        pystray.MenuItem("Goster", on_show, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Tarayicida Ac", lambda icon, item: _open_browser(f"http://{HOST}:{PORT}")),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Kapat", on_quit),
    )

    icon = pystray.Icon("turkiye_mcp", img, "Turkiye MCP Server", menu)
    return icon


def on_show(icon, item):
    """Pencereyi tekrar goster."""
    global _webview_window
    if _webview_window:
        try:
            _webview_window.restore()
        except Exception:
            pass


def _open_browser(url: str):
    """URL'i tarayicida ac."""
    import webbrowser
    webbrowser.open(url)


_webview_window = None


def run_webview(host: str, port: int):
    """pywebview penceresi ac ve calistir."""
    import webview

    url = f"http://{host}:{port}"
    logger.info(f"Pencere aciliyor: {url}")

    global _webview_window
    _webview_window = webview.create_window(
        title="Turkiye MCP Server",
        url=url,
        width=1280,
        height=900,
        min_size=(800, 600),
    )

    def on_closed():
        logger.info("Pencere kapatildi -- sunucu arka planda calismaya devam ediyor.")

    webview.start(on_closed=on_closed)


def run_browser(host: str, port: int, tray_icon=None):
    """Dashboard'u tarayicida ac."""
    url = f"http://{host}:{port}"
    _open_browser(url)
    logger.info(f"Dashboard tarayicida acildi: {url}")

    if tray_icon:
        tray_icon.run()
    else:
        # Tray yoksa sunucu thread'ini bekle
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Sunucu kapatiliyor (Ctrl+C)...")


def main():
    """Ana giris noktasi."""
    import argparse
    parser = argparse.ArgumentParser(
        description="Turkiye MCP Server -- Yerel Masaustu Uygulamasi",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ornekler:
  python local_run.py              # GUI ile baslat
  python local_run.py --no-gui    # Sadece sunucu
  python local_run.py --browser    # Tarayicida ac
  python local_run.py --port 9090  # Farkli port
        """,
    )
    parser.add_argument("--no-gui", action="store_true", help="GUI penceresini acma, sadece sunucuyu baslat")
    parser.add_argument("--port", type=int, default=PORT, help=f"Sunucu portu (varsayilan: {PORT})")
    parser.add_argument("--browser", action="store_true", help="pywebview yerine tarayicida ac")
    parser.add_argument("--no-tray", action="store_true", help="Sistem tepsisi ikonunu devre disi birak")
    args = parser.parse_args()

    port = args.port

    # -- 1. Sunucuyu arka planda baslat --
    server_thread = threading.Thread(
        target=start_server, args=(HOST, port), daemon=True
    )
    server_thread.start()
    logger.info("Sunucu thread'i baslatildi, hazir olmasi bekleniyor...")

    # -- 2. Sunucunun hazir olmasini bekle --
    if not wait_for_server(HOST, port):
        logger.error("Sunucu baslatilamadi. Cikiliyor...")
        sys.exit(1)

    # -- 3. --no-gui modu --
    if args.no_gui:
        logger.info(f"--no-gui modu: Sunucu calisiyor -> http://{HOST}:{port}")
        logger.info("Durdurmak icin Ctrl+C basin.")
        try:
            server_thread.join()
        except KeyboardInterrupt:
            logger.info("Sunucu kapatiliyor...")
        return

    # -- 4. Sistem tepsisi ikonu --
    tray_icon = None
    if not args.no_tray:
        tray_icon = create_tray_icon(on_quit=lambda icon, item: os._exit(0))

    # -- 5. GUI veya tarayici --
    if args.browser or tray_icon is None:
        # Tarayicida ac
        run_browser(HOST, port, tray_icon)
    else:
        # pywebview penceresi + sistem tepsisi
        # Once tray ikonunu arka planda baslat
        tray_thread = threading.Thread(target=tray_icon.run, daemon=True)
        tray_thread.start()
        logger.info("Sistem tepsisi ikonu olusturuldu.")

        # pywebview penceresini ac (bloke eder)
        run_webview(HOST, port)

        # Pencere kapatildiktan sonra sunucu devam eder
        logger.info("Pencere kapatildi. Sunucu arka planda calismaya devam ediyor.")
        logger.info("Sistem tepsisi ikonundan 'Kapat' secenegini kullanarak cikabilirsiniz.")
        try:
            server_thread.join()
        except KeyboardInterrupt:
            logger.info("Sunucu kapatiliyor...")


if __name__ == "__main__":
    main()