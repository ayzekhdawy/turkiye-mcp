"""
memory.py — Kullanıcı başına kalıcı bellek (tercih, olgu, talimat).
workspace.py ve skills.py pattern'ini takip eder.
Veri dizini: %LOCALAPPDATA%/TurkiyeMCP/workspace/memory.json
Stdlib-only, thread-safe.
"""

import json
import os
import threading
import time
import uuid

_LOCK = threading.RLock()


def _data_dir() -> str:
    """Bellek dosyasının dizini (workspace ile aynı kök)."""
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


def _data_path() -> str:
    return os.path.join(_data_dir(), "memory.json")


def _read_json(path: str, default: dict) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path: str, data: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def list_memories() -> list[dict]:
    """Tüm bellek kayıtlarını listele."""
    with _LOCK:
        data = _read_json(_data_path(), {"memories": []})
    return data.get("memories", [])


def clear_all() -> int:
    """Tüm bellek kayıtlarını sil. Silinen adedi döndürür."""
    with _LOCK:
        data = _read_json(_data_path(), {"memories": []})
        n = len(data.get("memories", []))
        _write_json(_data_path(), {"memories": []})
    return n


def _normalize(s: str) -> str:
    return " ".join((s or "").lower().split())


def has_similar(content: str) -> bool:
    """Aynı/çok benzer bir kayıt zaten var mı? (tekrar engelleme)"""
    nc = _normalize(content)
    if not nc:
        return True
    for m in list_memories():
        ec = _normalize(m.get("content", ""))
        if ec == nc or (len(nc) > 12 and (nc in ec or ec in nc)):
            return True
    return False


def add_memory(category: str, content: str, source: str = "manual") -> dict:
    """Yeni bellek kaydı ekle. category: preference|fact|instruction.

    source: 'manual' (kullanıcı ekledi) veya 'auto' (sohbetten öğrenildi).
    """
    if category not in ("preference", "fact", "instruction"):
        raise ValueError("category must be preference, fact, or instruction")
    if not content or not content.strip():
        raise ValueError("content must not be empty")
    now = time.time()
    entry = {
        "id": "mem_" + uuid.uuid4().hex[:8],
        "category": category,
        "content": content.strip(),
        "source": source if source in ("manual", "auto") else "manual",
        "created": now,
        "updated": now,
    }
    with _LOCK:
        data = _read_json(_data_path(), {"memories": []})
        data.setdefault("memories", []).append(entry)
        _write_json(_data_path(), data)
    return entry


def update_memory(memory_id: str, category: str | None = None, content: str | None = None) -> dict | None:
    """Var olan bellek kaydını güncelle."""
    if category is not None and category not in ("preference", "fact", "instruction"):
        raise ValueError("category must be preference, fact, or instruction")
    with _LOCK:
        data = _read_json(_data_path(), {"memories": []})
        for entry in data.get("memories", []):
            if entry.get("id") == memory_id:
                if category is not None:
                    entry["category"] = category
                if content is not None:
                    if not content.strip():
                        raise ValueError("content must not be empty")
                    entry["content"] = content.strip()
                entry["updated"] = time.time()
                _write_json(_data_path(), data)
                return entry
    return None


def delete_memory(memory_id: str) -> bool:
    """Bellek kaydını sil."""
    with _LOCK:
        data = _read_json(_data_path(), {"memories": []})
        before = len(data.get("memories", []))
        data["memories"] = [m for m in data.get("memories", []) if m.get("id") != memory_id]
        if len(data["memories"]) < before:
            _write_json(_data_path(), data)
            return True
    return False