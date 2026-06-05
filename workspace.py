"""workspace.py — Sunucu taraflı kalıcı çalışma alanı.

Klasörler (projeler), oturumlar (sohbetler) ve yüklenen dosyaları
diskte JSON + ham dosya olarak saklar. Böylece kullanıcı uygulamayı
kapatıp açtığında kaldığı yerden devam edebilir, sohbetlerini
klasörlere düzenleyebilir ve dosyalarını bir projeye yerleştirebilir.

Veri düzeni (TURKIYE_MCP_DATA_DIR veya %LOCALAPPDATA%/TurkiyeMCP):

    workspace/
      index.json                       # klasör + oturum meta listesi
      sessions/<session_id>.json       # tam sohbet (mesajlar, ekler)
      files/<folder_id>/<dosya_adi>    # yüklenen ham dosyalar

Eşzamanlılık için basit bir kilit (threading.Lock) kullanılır; tek
kullanıcılı yerel masaüstü senaryosu için yeterlidir.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

_LOCK = threading.RLock()


# ----------------------------------------------------------------------
# Yol yönetimi
# ----------------------------------------------------------------------

def _base_dir() -> str:
    """Veri kök dizinini döndürür (yoksa oluşturur)."""
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
    os.makedirs(os.path.join(ws, "sessions"), exist_ok=True)
    os.makedirs(os.path.join(ws, "files"), exist_ok=True)
    return ws


def _index_path() -> str:
    return os.path.join(_base_dir(), "index.json")


def _session_path(session_id: str) -> str:
    sid = _safe_id(session_id)
    return os.path.join(_base_dir(), "sessions", f"{sid}.json")


def _files_dir(folder_id: str) -> str:
    fid = _safe_id(folder_id)
    d = os.path.join(_base_dir(), "files", fid)
    os.makedirs(d, exist_ok=True)
    return d


def _safe_id(value: str) -> str:
    """ID/dosya adını dizin geçişine karşı temizler."""
    value = (value or "").strip()
    value = os.path.basename(value)
    value = re.sub(r"[^A-Za-z0-9._\-]", "_", value)
    return value or "unknown"


def _new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def _now() -> float:
    return time.time()


# ----------------------------------------------------------------------
# Düşük seviye JSON okuma/yazma
# ----------------------------------------------------------------------

def _read_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception:
        return default


def _write_json(path: str, data: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _load_index() -> Dict[str, Any]:
    idx = _read_json(_index_path(), {"folders": [], "sessions": []})
    idx.setdefault("folders", [])
    idx.setdefault("sessions", [])
    return idx


def _save_index(idx: Dict[str, Any]) -> None:
    _write_json(_index_path(), idx)


# ----------------------------------------------------------------------
# Klasör (proje) işlemleri
# ----------------------------------------------------------------------

def list_folders() -> List[Dict[str, Any]]:
    return _load_index()["folders"]


def create_folder(name: str) -> Dict[str, Any]:
    name = (name or "Yeni Klasör").strip()[:80]
    with _LOCK:
        idx = _load_index()
        folder = {"id": _new_id("f_"), "name": name, "created": _now()}
        idx["folders"].append(folder)
        _save_index(idx)
    return folder


def rename_folder(folder_id: str, name: str) -> bool:
    name = (name or "").strip()[:80]
    if not name:
        return False
    with _LOCK:
        idx = _load_index()
        for f in idx["folders"]:
            if f["id"] == folder_id:
                f["name"] = name
                _save_index(idx)
                return True
    return False


def delete_folder(folder_id: str, delete_sessions: bool = False) -> bool:
    """Klasörü siler. delete_sessions=False ise içindeki oturumlar
    köke (folderId=None) taşınır."""
    with _LOCK:
        idx = _load_index()
        before = len(idx["folders"])
        idx["folders"] = [f for f in idx["folders"] if f["id"] != folder_id]
        if len(idx["folders"]) == before:
            return False
        remaining = []
        for s in idx["sessions"]:
            if s.get("folderId") == folder_id:
                if delete_sessions:
                    try:
                        os.remove(_session_path(s["id"]))
                    except OSError:
                        pass
                    continue
                s["folderId"] = None
            remaining.append(s)
        idx["sessions"] = remaining
        _save_index(idx)
        # Klasör dosyalarını sil
        try:
            d = os.path.join(_base_dir(), "files", _safe_id(folder_id))
            if os.path.isdir(d):
                for fn in os.listdir(d):
                    try:
                        os.remove(os.path.join(d, fn))
                    except OSError:
                        pass
                os.rmdir(d)
        except OSError:
            pass
    return True


# ----------------------------------------------------------------------
# Oturum (sohbet) işlemleri
# ----------------------------------------------------------------------

def list_sessions() -> List[Dict[str, Any]]:
    """Hafif oturum meta listesi (mesaj içeriği olmadan)."""
    return _load_index()["sessions"]


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    data = _read_json(_session_path(session_id), None)
    return data


def save_session(session: Dict[str, Any]) -> Dict[str, Any]:
    """Oturumu kaydeder/günceller (upsert). Tam mesaj gövdesini diske,
    hafif meta veriyi index'e yazar."""
    sid = session.get("id") or _new_id("s_")
    session["id"] = sid
    session["updated"] = _now()
    if "created" not in session:
        session["created"] = _now()
    title = (session.get("title") or "Yeni Sohbet")[:120]
    session["title"] = title
    folder_id = session.get("folderId")

    with _LOCK:
        _write_json(_session_path(sid), session)
        idx = _load_index()
        meta = {
            "id": sid,
            "title": title,
            "folderId": folder_id,
            "created": session["created"],
            "updated": session["updated"],
            "messageCount": len(session.get("messages", [])),
            "attachmentCount": len(session.get("attachments", [])),
        }
        found = False
        for i, s in enumerate(idx["sessions"]):
            if s["id"] == sid:
                idx["sessions"][i] = meta
                found = True
                break
        if not found:
            idx["sessions"].append(meta)
        _save_index(idx)
    return session


def delete_session(session_id: str) -> bool:
    with _LOCK:
        idx = _load_index()
        before = len(idx["sessions"])
        idx["sessions"] = [s for s in idx["sessions"] if s["id"] != session_id]
        _save_index(idx)
        try:
            os.remove(_session_path(session_id))
        except OSError:
            pass
        return len(idx["sessions"]) != before


def move_session(session_id: str, folder_id: Optional[str]) -> bool:
    with _LOCK:
        idx = _load_index()
        hit = False
        for s in idx["sessions"]:
            if s["id"] == session_id:
                s["folderId"] = folder_id
                hit = True
                break
        if not hit:
            return False
        _save_index(idx)
    full = get_session(session_id)
    if full is not None:
        full["folderId"] = folder_id
        _write_json(_session_path(session_id), full)
    return True


# ----------------------------------------------------------------------
# Dosya işlemleri
# ----------------------------------------------------------------------

def store_file(folder_id: str, filename: str, content: bytes,
               meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Yüklenen ham dosyayı klasöre yerleştirir ve meta döndürür."""
    folder_id = folder_id or "_root"
    d = _files_dir(folder_id)
    safe_name = _safe_id(filename) or "dosya"
    # Çakışma varsa sıra ekle
    target = os.path.join(d, safe_name)
    if os.path.exists(target):
        stem, ext = os.path.splitext(safe_name)
        safe_name = f"{stem}_{int(_now())}{ext}"
        target = os.path.join(d, safe_name)
    with open(target, "wb") as f:
        f.write(content)
    info = {
        "id": _new_id("file_"),
        "folderId": folder_id,
        "name": safe_name,
        "originalName": filename,
        "size": len(content),
        "uploaded": _now(),
    }
    if meta:
        info.update(meta)
    # Dosya meta listesini klasörde tut
    meta_path = os.path.join(d, "_files.json")
    files = _read_json(meta_path, [])
    files.append(info)
    _write_json(meta_path, files)
    return info


def list_files(folder_id: str) -> List[Dict[str, Any]]:
    folder_id = folder_id or "_root"
    meta_path = os.path.join(_files_dir(folder_id), "_files.json")
    return _read_json(meta_path, [])


def read_file(folder_id: str, name: str) -> Optional[bytes]:
    path = os.path.join(_files_dir(folder_id or "_root"), _safe_id(name))
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def delete_file(folder_id: str, name: str) -> bool:
    folder_id = folder_id or "_root"
    d = _files_dir(folder_id)
    safe_name = _safe_id(name)
    ok = False
    try:
        os.remove(os.path.join(d, safe_name))
        ok = True
    except OSError:
        pass
    meta_path = os.path.join(d, "_files.json")
    files = _read_json(meta_path, [])
    new_files = [f for f in files if f.get("name") != safe_name]
    if len(new_files) != len(files):
        _write_json(meta_path, new_files)
        ok = True
    return ok


# ----------------------------------------------------------------------
# Birleşik anlık görüntü
# ----------------------------------------------------------------------

def _folder_name(folder_id: Optional[str]) -> str:
    if not folder_id:
        return "Genel"
    for f in _load_index().get("folders", []):
        if f["id"] == folder_id:
            return f["name"]
    return "Genel"


def find_related(refs: Optional[List[Dict[str, Any]]] = None,
                 keywords: Optional[List[str]] = None,
                 exclude_session_id: str = "",
                 limit: int = 5) -> List[Dict[str, Any]]:
    """Tüm oturumlarda benzer belge/dava arar (çapraz hafıza).

    Eşleşme: aynı referans değeri (esas/karar/dosya no) veya anahtar kelime
    örtüşmesi. Bir avukatın "bu davandaki dosyanda benzeri durum var" demesini
    sağlamak için kullanılır.
    """
    ref_values = set()
    for r in (refs or []):
        v = str(r.get("value", "")).strip()
        if v:
            ref_values.add(v)
    kw = set(k.lower() for k in (keywords or []) if len(k) >= 4)

    results = []
    for meta in _load_index().get("sessions", []):
        sid = meta.get("id")
        if sid == exclude_session_id:
            continue
        if not meta.get("attachmentCount") and not ref_values:
            # Eki olmayan oturumlarda yalnızca başlık kelime eşleşmesine bak
            pass
        session = get_session(sid)
        if not session:
            continue
        matched = []
        # Ek belgelerin referansları
        for att in session.get("attachments", []):
            for r in att.get("refs", []):
                v = str(r.get("value", "")).strip()
                if v and v in ref_values:
                    matched.append({"kind": "ref", "value": v, "doc": att.get("name", "")})
        # Başlık / mesaj anahtar kelime örtüşmesi
        hay = (meta.get("title", "") + " " + " ".join(
            m.get("text", "") for m in session.get("messages", [])[:4])).lower()
        kw_hits = [k for k in kw if k in hay]
        if kw_hits and not matched:
            matched.append({"kind": "keyword", "value": ", ".join(kw_hits[:3])})
        if matched:
            results.append({
                "sessionId": sid,
                "title": meta.get("title", "Sohbet"),
                "folder": _folder_name(meta.get("folderId")),
                "matched": matched[:3],
            })
        if len(results) >= limit:
            break
    return results


def snapshot() -> Dict[str, Any]:
    """Tüm workspace ağacını döndürür (klasörler + oturum metaları)."""
    idx = _load_index()
    # En son güncellenen üstte
    sessions = sorted(idx["sessions"], key=lambda s: s.get("updated", 0), reverse=True)
    return {
        "folders": idx["folders"],
        "sessions": sessions,
        "dataDir": _base_dir(),
    }
