"""computer_tools.py - Kullanici izniyle yerel bilgisayar araclari.

GUVENLIK: Bu aracllar kullanici izni olmadan CALISTIRILAMAZ.
Her arac, dashboard'dan acikca etkinlestirilmeli (permissions).
Izin durumlari workspace/computer_permissions.json dosyasinda saklanir.

Mevcut aracllar:
- read_file: Yerel dosya okuma (salt-okunur)
- list_directory: Dizin listeleme (salt-okunur)
- get_system_info: Sistem bilgisi (salt-okunur)

NOT: Komut calistirma (execute_command) guvenlik riski tasir.
Kullanici isterse eklenebilir ama varsayilan kapalidir.
"""

from __future__ import annotations

import json
import os
import platform
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

_LOCK = threading.RLock()

# Varsayilan arac izinleri (hepsi kapali)
DEFAULT_PERMISSIONS = {
    "read_file": False,
    "list_directory": False,
    "get_system_info": False,
    "execute_command": False,  # Yuksek risk - her zaman kapali baslar
}

# Arac aciklamalari (UI'de gosterilir)
TOOL_DESCRIPTIONS = {
    "read_file": {
        "name": "Dosya Okuma",
        "desc": "Yerel dosyalari okur (salt-okunur, yazma yok)",
        "risk": "medium",
        "category": "dosya",
    },
    "list_directory": {
        "name": "Dizin Listeleme",
        "desc": "Klasor icerigini listeler (salt-okunur)",
        "risk": "low",
        "category": "dosya",
    },
    "get_system_info": {
        "name": "Sistem Bilgisi",
        "desc": "Isletim sistemi, CPU, RAM, disk bilgisi verir",
        "risk": "low",
        "category": "sistem",
    },
    "execute_command": {
        "name": "Komut Calistirma",
        "desc": "Yerel komut/shell calistirir - YUKSEK RISK",
        "risk": "high",
        "category": "sistem",
    },
}


def _data_dir() -> str:
    """Veri dizini (workspace ile ayni kok)."""
    env = os.environ.get("TURKIYE_MCP_DATA_DIR")
    if env:
        root = env
    else:
        appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if appdata:
            root = os.path.join(appdata, "TurkiyeMCP")
        else:
            root = os.path.join(os.path.expanduser("~"), ".turkiye-mcp")
    ws = os.path.join(root, "workspace")
    os.makedirs(ws, exist_ok=True)
    return ws


def _permissions_path() -> str:
    return os.path.join(_data_dir(), "computer_permissions.json")


def load_permissions() -> Dict[str, bool]:
    """Arac izin durumlarian yukle."""
    with _LOCK:
        try:
            with open(_permissions_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
                return {**DEFAULT_PERMISSIONS, **data}
        except Exception:
            return dict(DEFAULT_PERMISSIONS)


def save_permissions(perms: Dict[str, bool]) -> None:
    """Arac izin durumlarian kaydet."""
    with _LOCK:
        tmp = _permissions_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(perms, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _permissions_path())


def is_allowed(tool_name: str) -> bool:
    """Bir aracin kullanima izinli olup olmadigini kontrol et."""
    perms = load_permissions()
    return perms.get(tool_name, False)


def require_permission(tool_name: str) -> None:
    """Izin yoksa hata firlat."""
    if not is_allowed(tool_name):
        raise PermissionError(
            f"'{tool_name}' araci etkinlestirilmemis. "
            "Dashboard -> Sistem -> Bilgisayar Araclarindan etkinlestirin."
        )


# ===== Yol Guvenligi =====

_BLOCKED_PATHS = [
    "/etc/shadow", "/etc/passwd", "/etc/sudoers",
    "C:\\Windows\\System32\\config\\",
    "C:\\Windows\\SAM",
]


def _check_path_safety(path: str) -> None:
    """Hassas sistem dosyalarina erisimi engelle."""
    abs_path = os.path.abspath(path).lower()
    for blocked in _BLOCKED_PATHS:
        if abs_path.startswith(blocked.lower()):
            raise PermissionError(f"Erisim reddedildi: hassas sistem dosyasi ({path})")


# ===== Arac Uygulamalari =====

def read_file(path: str, max_lines: int = 500) -> Dict[str, Any]:
    """Yerel dosya oku (salt-okunur)."""
    require_permission("read_file")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Dosya bulunamadi: {path}")
    _check_path_safety(path)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[:max_lines]
        return {
            "path": path,
            "lines": len(lines),
            "truncated": len(lines) >= max_lines,
            "content": "".join(lines),
        }
    except Exception as e:
        raise RuntimeError(f"Dosya okunamadi: {e}")


def list_directory(path: str, pattern: str = "*") -> Dict[str, Any]:
    """Dizin icerigini listele."""
    require_permission("list_directory")
    if not os.path.isdir(path):
        raise NotADirectoryError(f"Dizin bulunamadi: {path}")
    _check_path_safety(path)
    import glob as glob_mod
    entries = glob_mod.glob(os.path.join(path, pattern))
    result = []
    for entry in sorted(entries)[:200]:
        try:
            st = os.stat(entry)
            result.append({
                "name": os.path.basename(entry),
                "type": "d" if os.path.isdir(entry) else "f",
                "size": st.st_size if not os.path.isdir(entry) else 0,
                "modified": datetime.fromtimestamp(st.st_mtime).isoformat(),
            })
        except Exception:
            pass
    return {"path": path, "entries": result, "count": len(result)}


def get_system_info() -> Dict[str, Any]:
    """Sistem bilgisi dondur."""
    require_permission("get_system_info")
    info = {
        "platform": platform.system(),
        "platform_release": platform.release(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "hostname": platform.node(),
        "cpu_count": os.cpu_count(),
    }
    try:
        import shutil
        disk = shutil.disk_usage(os.path.expanduser("~"))
        info["disk_total_gb"] = round(disk.total / (1024**3), 1)
        info["disk_used_gb"] = round(disk.used / (1024**3), 1)
        info["disk_free_gb"] = round(disk.free / (1024**3), 1)
    except Exception:
        pass
    return info


def execute_command(command: str, timeout: int = 30) -> Dict[str, Any]:
    """Yerel komut calistir - YUKSEK RISK, varsayilan kapali."""
    require_permission("execute_command")
    blocked = ["rm -rf", "del /", "format", "mkfs", "dd if=", ":(){:|:&};:",
               "shutdown", "reboot", "halt", "poweroff"]
    cmd_lower = command.lower().strip()
    for b in blocked:
        if b in cmd_lower:
            raise PermissionError(f"Engellenmis komut: '{b}' iceriyor")
    import subprocess
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=os.path.expanduser("~"),
        )
        return {
            "command": command,
            "exit_code": result.returncode,
            "stdout": result.stdout[:5000],
            "stderr": result.stderr[:2000],
        }
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Komut {timeout}s icinde tamamlanmadi")
    except Exception as e:
        raise RuntimeError(f"Komut calistirilamadi: {e}")