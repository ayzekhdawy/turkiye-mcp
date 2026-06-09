"""
backup.py — Yedekleme ve dışa/içe aktarma.
workspace, memory, deadlines, dava kartları, gateway config, computer permissions
ve skills_state verilerini tek .zip dosyasında paketler.
Stdlib-only, thread-safe.
"""

import json
import os
import zipfile
import time
import threading

_LOCK = threading.RLock()

# Yedek dosya adı öneki
BACKUP_PREFIX = "turkiye_mcp_backup_"
# Yedek dosya boyutu üst sınırı (bayt) — 50 MB
MAX_BACKUP_SIZE = 50 * 1024 * 1024
# Yedek dışı bırakılacak dosya/dizin adları
_EXCLUDE_NAMES = {"server.pid", "__pycache__", ".tmp"}


def _data_dir() -> str:
    """Veri dizini (workspace ile aynı kök)."""
    env = os.environ.get("TURKIYE_MCP_DATA_DIR")
    if env:
        root = env
    else:
        appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if appdata:
            root = os.path.join(appdata, "TurkiyeMCP")
        else:
            root = os.path.join(os.path.expanduser("~"), ".turkiye-mcp")
    return root


def _workspace_dir() -> str:
    ws = os.path.join(_data_dir(), "workspace")
    os.makedirs(ws, exist_ok=True)
    return ws


def _backup_dir() -> str:
    """Yedek dosyalarının saklandığı dizin (workspace altında)."""
    bd = os.path.join(_workspace_dir(), "backups")
    os.makedirs(bd, exist_ok=True)
    return bd


def create_backup() -> dict:
    """Tüm veriyi yedekle. .zip dosyası oluşturur.

    Returns:
        dict: {ok: True, filename: str, path: str, size: int, files: int}
              veya {ok: False, error: str}
    """
    with _LOCK:
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"{BACKUP_PREFIX}{timestamp}.zip"
            backup_path = os.path.join(_backup_dir(), filename)

            ws_dir = _workspace_dir()
            root_dir = _data_dir()
            file_count = 0
            total_size = 0

            with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # workspace/ dizinindeki tüm dosyaları ekle
                for dirpath, dirnames, filenames in os.walk(ws_dir):
                    # backups dizinini atla (kendi yedeklerini yedekleme)
                    if "backups" in dirnames:
                        dirnames.remove("backups")
                    for fn in filenames:
                        # Geçici ve PID dosyalarını atla
                        if fn.endswith(".tmp") or fn == "server.pid":
                            continue
                        full_path = os.path.join(dirpath, fn)
                        rel_path = os.path.relpath(full_path, root_dir)
                        # Yol doğrulama: üst dizine çıkmayı engelle
                        if rel_path.startswith(".."):
                            continue
                        file_size = os.path.getsize(full_path)
                        total_size += file_size
                        file_count += 1
                        zf.write(full_path, rel_path)

                # skills_state.json (workspace dışında, kök dizinde)
                skills_path = os.path.join(root_dir, "skills_state.json")
                if os.path.exists(skills_path):
                    zf.write(skills_path, "skills_state.json")
                    file_count += 1
                    total_size += os.path.getsize(skills_path)

            # Boyut sınırı kontrolü
            final_size = os.path.getsize(backup_path)
            if final_size > MAX_BACKUP_SIZE:
                os.remove(backup_path)
                return {
                    "ok": False,
                    "error": f"Yedek boyutu sınırı aştı ({final_size / 1024 / 1024:.1f} MB / {MAX_BACKUP_SIZE // 1024 // 1024} MB)",
                }

            return {
                "ok": True,
                "filename": filename,
                "path": backup_path,
                "size": final_size,
                "files": file_count,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}


def restore_backup(filename: str) -> dict:
    """Bir .zip yedek dosyasından veriyi geri yükle.

    Geri yükleme öncesi mevcut verilerin otomatik yedeğini alır.

    Args:
        filename: Yedek dosya adı (turkiye_mcp_backup_YYYYMMDD_HHMMSS.zip)

    Returns:
        dict: {ok: True, restored_files: int, pre_backup: str}
              veya {ok: False, error: str}
    """
    with _LOCK:
        try:
            backup_path = os.path.join(_backup_dir(), filename)
            if not os.path.exists(backup_path):
                return {"ok": False, "error": f"Yedek dosyası bulunamadı: {filename}"}

            # Güvenlik: dosya adında path traversal engelle
            if ".." in filename or os.path.isabs(filename):
                return {"ok": False, "error": "Geçersiz dosya adı"}

            # Geri yükleme öncesi otomatik yedek
            pre_backup = create_backup()
            pre_backup_name = pre_backup.get("filename", "pre_restore_backup")

            root_dir = _data_dir()
            restored_count = 0

            with zipfile.ZipFile(backup_path, "r") as zf:
                for info in zf.infolist():
                    # Path traversal koruması
                    if info.filename.startswith("/") or ".." in info.filename:
                        continue
                    # Hedef yol
                    target_path = os.path.normpath(os.path.join(root_dir, info.filename))
                    # Hedef root dizini içinde mi kontrol et
                    if not target_path.startswith(os.path.normpath(root_dir)):
                        continue

                    if info.is_dir():
                        os.makedirs(target_path, exist_ok=True)
                    else:
                        parent_dir = os.path.dirname(target_path)
                        os.makedirs(parent_dir, exist_ok=True)
                        with zf.open(info) as src, open(target_path, "wb") as dst:
                            dst.write(src.read())
                        restored_count += 1

            return {
                "ok": True,
                "restored_files": restored_count,
                "pre_backup": pre_backup_name,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}


def list_backups() -> list[dict]:
    """Mevcut yedek dosyalarını listele.

    Returns:
        list[dict]: Her yedek için filename, size, created_epoch, created_str
    """
    bd = _backup_dir()
    backups = []
    for fn in sorted(os.listdir(bd), reverse=True):
        if not fn.startswith(BACKUP_PREFIX) or not fn.endswith(".zip"):
            continue
        full_path = os.path.join(bd, fn)
        stat = os.stat(full_path)
        # Dosya adından tarihi çıkar: turkiye_mcp_backup_20260609_143000.zip
        date_str = fn.replace(BACKUP_PREFIX, "").replace(".zip", "")
        try:
            created = time.strptime(date_str, "%Y%m%d_%H%M%S")
            created_epoch = time.mktime(created)
            created_formatted = time.strftime("%Y-%m-%d %H:%M:%S", created)
        except ValueError:
            created_epoch = stat.st_mtime
            created_formatted = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))

        backups.append({
            "filename": fn,
            "size": stat.st_size,
            "size_formatted": _format_size(stat.st_size),
            "created_epoch": created_epoch,
            "created_str": created_formatted,
        })
    return backups


def delete_backup(filename: str) -> bool:
    """Bir yedek dosyasını sil.

    Args:
        filename: Yedek dosya adı

    Returns:
        bool: Silindi ise True
    """
    with _LOCK:
        # Güvenlik: path traversal engelle
        if ".." in filename or os.path.isabs(filename) or "/" in filename or "\\" in filename:
            return False
        if not filename.startswith(BACKUP_PREFIX):
            return False
        backup_path = os.path.join(_backup_dir(), filename)
        if os.path.exists(backup_path):
            os.remove(backup_path)
            return True
        return False


def get_backup_path(filename: str) -> str | None:
    """Bir yedek dosyasının tam yolunu döndür.

    Args:
        filename: Yedek dosya adı

    Returns:
        Tam yol veya None
    """
    # Güvenlik: path traversal engelle
    if ".." in filename or os.path.isabs(filename) or "/" in filename or "\\" in filename:
        return None
    if not filename.startswith(BACKUP_PREFIX) or not filename.endswith(".zip"):
        return None
    backup_path = os.path.join(_backup_dir(), filename)
    if os.path.exists(backup_path):
        return backup_path
    return None


def _format_size(size_bytes: int) -> str:
    """Bayt cinsinden boyutu okunabilir formata çevir."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / 1024 / 1024:.1f} MB"