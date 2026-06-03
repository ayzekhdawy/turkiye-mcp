#!/usr/bin/env python3
"""Türkiye MCP Server — Yerel Masaüstü Uygulaması.

Bu dosya yerel Windows EXE olarak çalıştırılır:
- ASGI sunucusunu 127.0.0.1:8080'de başlatır
- pywebview ile native pencere açar
- pystray ile sistem tepsisi ikonu sağlar
- Pencere kapatıldığında arka planda çalışmaya devam eder
- EXE tekrar açıldığında mevcut server'a bağlanır

Kullanım:
    python local_run.py          # Geliştirme modu
    python local_run.py --no-gui # Sadece sunucu (GUI yok)
    python local_run.py --browser # pywebview yerine tarayıcıda aç

    PyInstaller EXE: build.bat veya pyinstaller turkiye_mcp.spec
"""

import os
import sys

# ── EN ERKEN crash tespiti ──
if getattr(sys, 'frozen', False):
    _early_log = os.path.join(os.path.dirname(sys.executable), "turkiye_mcp_early.txt")
else:
    _early_log = os.path.join(os.getcwd(), "turkiye_mcp_early.txt")

try:
    with open(_early_log, "w", encoding="utf-8") as _f:
        _f.write(f"Python started OK\nfrozen={getattr(sys, 'frozen', False)}\nexe={sys.executable}\n")
except Exception as _e:
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, f"Early crash: {_e}", "TurkiyeMCP", 0x10)
    except Exception:
        pass

import threading
import logging
import time
import traceback
from pathlib import Path


def hide_console():
    """Windows konsol penceresini gizle (GUI uygulaması görünümü için)."""
    if sys.platform == "win32" and getattr(sys, 'frozen', False):
        try:
            import ctypes
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
        except Exception:
            pass


# Windows konsol encoding sorunu çözümü
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        if sys.stdout:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── Dosya yolları ──
if getattr(sys, 'frozen', False):
    _EXE_DIR = Path(sys.executable).parent
else:
    _EXE_DIR = Path.cwd()

_CRASH_LOG = _EXE_DIR / "turkiye_mcp_crash.log"


def _log_crash(msg: str):
    """Kritik hataları crash log dosyasına yaz."""
    try:
        with open(_CRASH_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"CRASH: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*60}\n")
            f.write(msg)
            f.write("\n")
    except Exception:
        pass


# Top-level exception yakalayıcı — EXE sessizce çökmesin
def _global_excepthook(exc_type, exc_value, exc_tb):
    """Yakalanmamış hataları logla ve crash dosyasına yaz."""
    tb = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
    _log_crash(f"UNHANDLED EXCEPTION:\n{tb}")
    try:
        logger.error(f"YAKALANMAMIS HATA: {tb}")
    except Exception:
        pass


sys.excepthook = _global_excepthook

# Yerel mod bayrağı — app.py bunu kontrol eder
os.environ["TURKIYE_MCP_LOCAL"] = "1"

# ── Logging ──
_log_file = _EXE_DIR / "turkiye_mcp.log"


class FileAndConsoleHandler(logging.FileHandler):
    """Dosyaya yazar, konsola da yazabildiğimiz kadar yazar."""
    def emit(self, record):
        try:
            super().emit(record)
        except Exception:
            pass
        try:
            msg = self.format(record) + "\n"
            stream = sys.stderr or sys.stdout
            if stream and hasattr(stream, 'write'):
                stream.write(msg)
                stream.flush()
        except Exception:
            pass


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[FileAndConsoleHandler(str(_log_file), encoding="utf-8")],
)
logger = logging.getLogger("turkiye_mcp.local")

logger.info(f"Türkiye MCP başlatılıyor... EXE dizini: {_EXE_DIR}")
logger.info(f"Crash log: {_CRASH_LOG}")
logger.info(f"Runtime log: {_log_file}")

PORT = 8080
HOST = "127.0.0.1"


def is_server_running(host: str, port: int) -> bool:
    """Sunucunun çalışıp çalışmadığını kontrol et.
    200 (hazır) veya 500 (başlıyor) dönüyorsa sunucu çalışıyor sayılır."""
    import httpx
    try:
        resp = httpx.get(f"http://{host}:{port}/health", timeout=3)
        return resp.status_code in (200, 500)
    except Exception:
        return False


def wait_for_server(host: str, port: int, timeout: float = 120.0) -> bool:
    """Sunucunun hazır olmasını bekle.
    Modüller yüklenirken /health 500 dönebilir — bu durumda beklenecek.
    Sadece 200 dönerse hazır sayılır."""
    import httpx
    start = time.time()
    logger.info(f"Sunucu bekleniyor (timeout: {timeout}s)...")
    while time.time() - start < timeout:
        try:
            resp = httpx.get(f"http://{host}:{port}/health", timeout=2)
            if resp.status_code == 200:
                elapsed = time.time() - start
                logger.info(f"[OK] Sunucu hazır! ({elapsed:.1f}s)")
                return True
            # 500 = sunucu çalışıyor ama modüller yükleniyor, bekle
            if resp.status_code == 500:
                time.sleep(1)
                continue
        except Exception:
            time.sleep(0.5)
        elapsed = time.time() - start
        if int(elapsed) % 10 == 0 and elapsed > 1:
            logger.info(f"Sunucu hala bekleniyor... ({elapsed:.0f}s)")
    logger.error(f"[FAIL] Sunucu başlatılamadı (timeout: {timeout}s).")
    _log_crash(f"Server failed to start within {timeout}s\nCheck turkiye_mcp.log for details")
    return False


def start_server(host: str, port: int):
    """ASGI sunucusunu başlat (ayrı thread'de)."""
    try:
        import uvicorn
        from app import starlette_app
        logger.info(f"Sunucu başlatılıyor: {host}:{port}")
        logger.info(f"starlette_app type: {type(starlette_app)}")
        uvicorn.run(starlette_app, host=host, port=port, log_level="info")
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Sunucu başlatma hatası: {tb}")
        _log_crash(f"Server start error:\n{tb}")


def create_tray_icon(on_quit, on_show_window):
    """Sistem tepsisi ikonu oluştur.

    Args:
        on_quit: Tamamen kapatma fonksiyonu
        on_show_window: Pencereyi gösterme fonksiyonu
    """
    try:
        from PIL import Image, ImageDraw
        import pystray
    except ImportError:
        logger.warning("pystray veya Pillow yüklü değil -- sistem tepsisi ikonu devre dışı.")
        return None
    except Exception as e:
        logger.warning(f"Sistem tepsisi ikonu oluşturulamadı: {e}")
        return None

    # Türkiye bayrağı ikonu oluştur (64x64)
    img = Image.new("RGB", (64, 64), "#E30A17")
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 52, 60], fill="#FFFFFF")
    draw.ellipse([12, 4, 56, 56], fill="#E30A17")
    star_points = [
        (36, 16), (39, 26), (50, 26), (41, 33),
        (44, 44), (36, 37), (28, 44), (31, 33),
        (22, 26), (33, 26),
    ]
    draw.polygon(star_points, fill="#FFFFFF")

    menu = pystray.Menu(
        pystray.MenuItem("🇹🇷 Göster", on_show_window, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("🌐 Tarayıcıda Aç", lambda icon, item: _open_browser(f"http://{HOST}:{PORT}")),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("❌ Tamamen Kapat", on_quit),
    )

    icon = pystray.Icon("turkiye_mcp", img, f"Turkiye MCP Server (:{{PORT}})", menu)
    return icon


def _open_browser(url: str):
    """URL'i tarayıcıda aç."""
    import webbrowser
    webbrowser.open(url)


_webview_window = None


def run_webview(host: str, port: int):
    """pywebview penceresi aç ve çalıştır."""
    try:
        import webview
    except ImportError:
        logger.warning("pywebview yüklü değil — tarayıcıda açılıyor...")
        _open_browser(f"http://{host}:{port}")
        return
    except Exception as e:
        logger.error(f"pywebview hatası: {e}")
        _log_crash(f"pywebview import error: {e}\nFalling back to browser mode")
        _open_browser(f"http://{host}:{port}")
        return

    url = f"http://{host}:{port}"
    logger.info(f"Pencere açılıyor: {url}")

    global _webview_window
    _webview_window = webview.create_window(
        title="🇹🇷 Türkiye MCP Server",
        url=url,
        width=1280,
        height=900,
        min_size=(800, 600),
    )

    try:
        # pywebview 6.x uyumluluğu
        try:
            webview.start(on_closed=lambda: logger.info("Pencere kapatıldı."))
        except TypeError:
            webview.start()
    except Exception as e:
        logger.error(f"pywebview çalışma hatası: {e}")
        _log_crash(f"pywebview runtime error: {e}")
        _open_browser(url)


def run_browser(host: str, port: int, tray_icon=None):
    """Dashboard'u tarayıcıda aç."""
    url = f"http://{host}:{port}"
    _open_browser(url)
    logger.info(f"Dashboard tarayıcıda açıldı: {url}")

    if tray_icon:
        tray_icon.run()
    else:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Sunucu kapatılıyor (Ctrl+C)...")


def main():
    """Ana giriş noktası."""
    try:
        _main_inner()
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"KRİTİK HATA: {tb}")
        _log_crash(f"CRITICAL ERROR in main():\n{tb}")
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                f"Türkiye MCP Server başlatılamadı.\n\nHata detayları: {_CRASH_LOG}\n\n{str(e)[:200]}",
                "Türkiye MCP — Hata",
                0x10,
            )
        except Exception:
            pass
        sys.exit(1)


def _main_inner():
    """Ana mantık — main() tarafından sarılır."""
    import argparse
    parser = argparse.ArgumentParser(
        description="Türkiye MCP Server — Yerel Masaüstü Uygulaması",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python local_run.py              # GUI ile başlat
  python local_run.py --no-gui    # Sadece sunucu
  python local_run.py --browser    # Tarayıcıda aç
  python local_run.py --port 9090  # Farklı port
        """,
    )
    parser.add_argument("--no-gui", action="store_true", help="GUI penceresini açma, sadece sunucuyu başlat")
    parser.add_argument("--port", type=int, default=PORT, help=f"Sunucu portu (varsayılan: {PORT})")
    parser.add_argument("--browser", action="store_true", help="pywebview yerine tarayıcıda aç")
    parser.add_argument("--no-tray", action="store_true", help="Sistem tepsisi ikonunu devre dışı bırak")
    parser.add_argument("--debug", action="store_true", help="Konsol penceresini göster (hata ayıklama)")
    args = parser.parse_args()

    port = args.port

    # -- 0. Konsol penceresini gizle (debug değilse ve GUI modundaysa) --
    if not args.debug and not args.no_gui:
        hide_console()

    logger.info(f"Başlatma parametreleri: port={port}, no_gui={args.no_gui}, browser={args.browser}, no_tray={args.no_tray}")

    # -- 1. Server zaten çalışıyor mu kontrol et --
    if is_server_running(HOST, port):
        logger.info(f"Sunucu zaten çalışıyor: http://{HOST}:{port} — doğrudan bağlanılıyor...")
        # Server zaten çalışıyor, direkt GUI'yi aç
    else:
        # Server çalışmıyor, başlat
        logger.info("Sunucu çalışmıyor, başlatılıyor...")
        server_thread = threading.Thread(
            target=start_server, args=(HOST, port), daemon=True
        )
        server_thread.start()
        logger.info("Sunucu thread'i başlatıldı, hazır olması bekleniyor...")

        if not wait_for_server(HOST, port, timeout=120.0):
            logger.error("Sunucu başlatılamadı. Çıkılıyor...")
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"Sunucu başlatılamadı (timeout).\n\nDetaylar için: {_CRASH_LOG}",
                    "Türkiye MCP — Hata",
                    0x10,
                )
            except Exception:
                pass
            sys.exit(1)

    # -- 2. --no-gui modu --
    if args.no_gui:
        logger.info(f"--no-gui modu: Sunucu çalışıyor -> http://{HOST}:{port}")
        logger.info("Durdurmak için Ctrl+C basın.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Sunucu kapatılıyor...")
        return

    # -- 3. Sistem tepsisi ikonu --
    tray_icon = None
    if not args.no_tray:
        def on_show_window(icon, item):
            """Tray'den 'Göster' seçilince pencereyi aç."""
            _open_browser(f"http://{HOST}:{port}")

        tray_icon = create_tray_icon(
            on_quit=lambda icon, item: os._exit(0),
            on_show_window=on_show_window,
        )

    # -- 4. GUI veya tarayıcı --
    if args.browser or tray_icon is None:
        run_browser(HOST, port, tray_icon)
    else:
        # Tray ikonunu arka planda başlat
        tray_thread = threading.Thread(target=tray_icon.run, daemon=True)
        tray_thread.start()
        logger.info("Sistem tepsisi ikonu oluşturuldu.")

        # pywebview penceresini aç (bloke eder)
        run_webview(HOST, port)

        # Pencere kapatıldıktan sonra sunucu devam eder
        logger.info("Pencere kapatıldı. Sunucu arka planda çalışmaya devam ediyor.")
        logger.info("Sistem tepsisi ikonundan 'Tamamen Kapat' seçeneğini kullanarak çıkabilirsiniz.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Sunucu kapatılıyor...")


if __name__ == "__main__":
    main()