"""
deadlines.py — Hukuki süre takibi (dava açma, temyiz, itiraz süreleri).
memory.py pattern'ini takip eder.
Veri dizini: %LOCALAPPDATA%/TurkiyeMCP/workspace/deadlines.json
Stdlib-only, thread-safe.
"""

import json
import os
import threading
import time
import uuid
from datetime import date, timedelta

_LOCK = threading.RLock()

# Türk hukuki süre kategorileri ve varsayılan gün sayıları
CATEGORY_DEFAULTS = {
    "ihtar_itiraz":       {"days": 7,   "label": "İhtar İtirazı"},
    "odeme_emri_itiraz":  {"days": 7,   "label": "Ödeme Emri İtirazı"},
    "icra_itiraz":        {"days": 7,   "label": "İcra İtirazı"},
    "temyiz":             {"days": 15,  "label": "Temyiz"},
    "istinaf":            {"days": 15,  "label": "İstinaf"},
    "yargitay_itiraz":    {"days": 15,  "label": "Yargıtay İtirazı"},
    "idari_basvuru":      {"days": 30,  "label": "İdari Başvuru"},
    "diger":              {"days": 0,   "label": "Diğer (manuel)"},
}

VALID_STATUSES = ("active", "completed", "expired")


def _data_dir() -> str:
    """Süre dosyasının dizini (workspace ile aynı kök)."""
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
    return os.path.join(_data_dir(), "deadlines.json")


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


def compute_deadline(start_date_str: str, days: int) -> str:
    """TBK m.149 kuralına göre süre bitiş tarihi hesapla.

    - İlk gün hariç, son gün dahil (TBK m.149/1)
    - Son gün hafta sonu veya resmi tatilse ilk iş gününe kaydır (basitleştirilmiş: sadece hafta sonu)
    - Resmi tatil verisi olmadığından sadece Cumartesi/Pazar kaydırması yapılır

    Args:
        start_date_str: YYYY-MM-DD formatında başlangıç tarihi
        days: süre gün sayısı

    Returns:
        YYYY-MM-DD formatında bitiş tarihi
    """
    start = date.fromisoformat(start_date_str)
    # İlk gün hariç: start + days
    deadline = start + timedelta(days=days)
    # Hafta sonu kaydırması
    while deadline.weekday() >= 5:  # 5=Cumartesi, 6=Pazar
        deadline += timedelta(days=1)
    return deadline.isoformat()


def list_deadlines(status: str | None = None) -> list[dict]:
    """Tüm süreleri listele. Opsiyonel status filtresi."""
    with _LOCK:
        data = _read_json(_data_path(), {"deadlines": []})
    entries = data.get("deadlines", [])
    if status:
        entries = [e for e in entries if e.get("status") == status]
    return entries


def get_deadline(deadline_id: str) -> dict | None:
    """ID ile tek bir süre getir."""
    with _LOCK:
        data = _read_json(_data_path(), {"deadlines": []})
    for entry in data.get("deadlines", []):
        if entry.get("id") == deadline_id:
            return entry
    return None


def add_deadline(
    category: str,
    title: str,
    start_date: str,
    days_allowed: int | None = None,
    description: str = "",
    source: str = "manual",
) -> dict:
    """Yeni süre ekle.

    Args:
        category: CATEGORY_DEFAULTS anahtarlarından biri
        title: Süre başlığı (zorunlu)
        start_date: Başlangıç tarihi YYYY-MM-DD (zorunlu)
        days_allowed: Süre gün sayısı. None ise kategori varsayılanı kullanılır
        description: Açıklama (opsiyonel)
        source: "manual" veya "auto"

    Returns:
        Oluşturulan süre kaydı
    """
    if category not in CATEGORY_DEFAULTS:
        raise ValueError(f"Geçersiz kategori: {category}. Geçerli: {', '.join(CATEGORY_DEFAULTS.keys())}")
    if not title or not title.strip():
        raise ValueError("Başlık boş olamaz")
    # Tarih doğrulama
    try:
        date.fromisoformat(start_date)
    except (ValueError, TypeError):
        raise ValueError(f"Geçersiz tarih formatı: {start_date} (YYYY-MM-DD bekleniyor)")
    # Gün sayısı: kategori varsayılanı veya manuel
    if days_allowed is None:
        days_allowed = CATEGORY_DEFAULTS[category]["days"]
    if days_allowed <= 0:
        raise ValueError("Gün sayısı 0 veya negatif olamaz (diger kategorisi için manuel değer girin)")
    now = time.time()
    deadline_date = compute_deadline(start_date, days_allowed)
    entry = {
        "id": "dl_" + uuid.uuid4().hex[:8],
        "category": category,
        "title": title.strip(),
        "description": description.strip() if description else "",
        "start_date": start_date,
        "deadline_date": deadline_date,
        "days_allowed": days_allowed,
        "status": "active",
        "source": source if source in ("manual", "auto") else "manual",
        "created": now,
        "updated": now,
    }
    with _LOCK:
        data = _read_json(_data_path(), {"deadlines": []})
        data.setdefault("deadlines", []).append(entry)
        _write_json(_data_path(), data)
    return entry


def update_deadline(deadline_id: str, **kwargs) -> dict | None:
    """Süre kaydını güncelle. start_date veya days_allowed değişirse deadline_date yeniden hesaplanır."""
    with _LOCK:
        data = _read_json(_data_path(), {"deadlines": []})
        for entry in data.get("deadlines", []):
            if entry.get("id") == deadline_id:
                # Alanları güncelle
                if "category" in kwargs:
                    if kwargs["category"] not in CATEGORY_DEFAULTS:
                        raise ValueError(f"Geçersiz kategori: {kwargs['category']}")
                    entry["category"] = kwargs["category"]
                if "title" in kwargs:
                    if not kwargs["title"] or not kwargs["title"].strip():
                        raise ValueError("Başlık boş olamaz")
                    entry["title"] = kwargs["title"].strip()
                if "description" in kwargs:
                    entry["description"] = kwargs["description"].strip() if kwargs["description"] else ""
                if "start_date" in kwargs:
                    try:
                        date.fromisoformat(kwargs["start_date"])
                    except (ValueError, TypeError):
                        raise ValueError(f"Geçersiz tarih formatı: {kwargs['start_date']}")
                    entry["start_date"] = kwargs["start_date"]
                if "days_allowed" in kwargs:
                    if kwargs["days_allowed"] <= 0:
                        raise ValueError("Gün sayısı 0 veya negatif olamaz")
                    entry["days_allowed"] = kwargs["days_allowed"]
                if "status" in kwargs:
                    if kwargs["status"] not in VALID_STATUSES:
                        raise ValueError(f"Geçersiz durum: {kwargs['status']}")
                    entry["status"] = kwargs["status"]
                # deadline_date yeniden hesapla
                entry["deadline_date"] = compute_deadline(entry["start_date"], entry["days_allowed"])
                entry["updated"] = time.time()
                _write_json(_data_path(), data)
                return entry
    return None


def delete_deadline(deadline_id: str) -> bool:
    """Süre kaydını sil."""
    with _LOCK:
        data = _read_json(_data_path(), {"deadlines": []})
        before = len(data.get("deadlines", []))
        data["deadlines"] = [d for d in data.get("deadlines", []) if d.get("id") != deadline_id]
        if len(data["deadlines"]) < before:
            _write_json(_data_path(), data)
            return True
    return False


def mark_completed(deadline_id: str) -> dict | None:
    """Süre kaydını tamamlandı olarak işaretle."""
    return update_deadline(deadline_id, status="completed")


def get_upcoming(days: int = 30) -> list[dict]:
    """Yaklaşan aktif süreleri getir (bitiş tarihi bugünden N gün sonrasına kadar)."""
    today = date.today().isoformat()
    future = (date.today() + timedelta(days=days)).isoformat()
    entries = list_deadlines(status="active")
    return [e for e in entries if today <= e.get("deadline_date", "") <= future]


def get_overdue() -> list[dict]:
    """Gecikmiş aktif süreleri getir (bitiş tarihi bugünden önce)."""
    today = date.today().isoformat()
    entries = list_deadlines(status="active")
    return [e for e in entries if e.get("deadline_date", "") < today]


def clear_all() -> int:
    """Tüm süreleri sil. Silinen adedi döndürür."""
    with _LOCK:
        data = _read_json(_data_path(), {"deadlines": []})
        n = len(data.get("deadlines", []))
        _write_json(_data_path(), {"deadlines": []})
    return n