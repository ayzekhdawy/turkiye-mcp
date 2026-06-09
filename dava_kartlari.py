"""
dava_kartlari.py — Dava/müvekkil kartı takibi (esas no, taraf, mahkeme, durum).
deadlines.py pattern'ini takip eder.
Veri dizini: %LOCALAPPDATA%/TurkiyeMCP/workspace/dava_kartlari.json
Stdlib-only, thread-safe.
"""

import json
import os
import threading
import time
import uuid

_LOCK = threading.RLock()

# Dava türü kategorileri
DAVA_TURLERI = {
    "tazminat":          {"label": "Tazminat",            "badge": "dk-badge-tazminat"},
    "istirdat":          {"label": "İstirdat",            "badge": "dk-badge-istirdat"},
    "menfi_tespit":      {"label": "Menfi Tespit",        "badge": "dk-badge-tespit"},
    "icra_itiraz":       {"label": "İcra İtiraz",         "badge": "dk-badge-icra"},
    "aile_hukuku":       {"label": "Aile Hukuku",         "badge": "dk-badge-aile"},
    "miras":             {"label": "Miras",               "badge": "dk-badge-miras"},
    "ticari_uyumazlik":  {"label": "Ticari Uyuşmazlık",   "badge": "dk-badge-ticari"},
    "idari_dava":        {"label": "İdari Dava",           "badge": "dk-badge-idari"},
    "ceza":              {"label": "Ceza",                 "badge": "dk-badge-ceza"},
    "is_hukuku":         {"label": "İş Hukuku",            "badge": "dk-badge-is"},
    "kira":              {"label": "Kira",                 "badge": "dk-badge-kira"},
    "gayrimenkul":       {"label": "Gayrimenkul",          "badge": "dk-badge-gmulk"},
    "sozlesme":          {"label": "Sözleşme",             "badge": "dk-badge-sozlesme"},
    "diger":             {"label": "Diğer",                "badge": "dk-badge-diger"},
}

# Dava durumları
DURUMLAR = {
    "devam_ediyor": {"label": "Devam Ediyor", "color": "#3b82f6"},
    "kazanildi":    {"label": "Kazanıldı",    "color": "#22c55e"},
    "kaybedildi":   {"label": "Kaybedildi",   "color": "#ef4444"},
    "feragat":      {"label": "Feragat",      "color": "#f59e0b"},
    "kabul":        {"label": "Kabul",         "color": "#8b5cf6"},
}

VALID_DURUMLAR = tuple(DURUMLAR.keys())
VALID_TURLER = tuple(DAVA_TURLERI.keys())


def _data_dir() -> str:
    """Dava kartı dosyasının dizini (workspace ile aynı kök)."""
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
    return os.path.join(_data_dir(), "dava_kartlari.json")


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


def list_kartlar(durum: str | None = None, dava_turu: str | None = None) -> list[dict]:
    """Tüm dava kartlarını listele. Opsiyonel durum ve tür filtresi."""
    with _LOCK:
        data = _read_json(_data_path(), {"kartlar": []})
    entries = data.get("kartlar", [])
    if durum:
        entries = [e for e in entries if e.get("durum") == durum]
    if dava_turu:
        entries = [e for e in entries if e.get("dava_turu") == dava_turu]
    return entries


def get_kart(kart_id: str) -> dict | None:
    """ID ile tek bir dava kartı getir."""
    with _LOCK:
        data = _read_json(_data_path(), {"kartlar": []})
    for entry in data.get("kartlar", []):
        if entry.get("id") == kart_id:
            return entry
    return None


def add_kart(
    esas_no: str,
    dava_turu: str,
    taraf_muvekkil: str = "",
    taraf_karsi: str = "",
    daire: str = "",
    konu: str = "",
    acilis_tarihi: str = "",
    notlar: str = "",
    source: str = "manual",
) -> dict:
    """Yeni dava kartı ekle.

    Args:
        esas_no: Esas numarası (zorunlu)
        dava_turu: DAVA_TURLERI anahtarlarından biri (zorunlu)
        taraf_muvekkil: Müvekkil/tarafımız adı
        taraf_karsi: Karşı taraf adı
        daire: Mahkeme/daire adı
        konu: Kısa konu açıklaması
        acilis_tarihi: Dava açılış tarihi YYYY-MM-DD
        notlar: Serbest not
        source: "manual" veya "auto"

    Returns:
        Oluşturulan dava kartı
    """
    if dava_turu not in DAVA_TURLERI:
        raise ValueError(f"Geçersiz dava türü: {dava_turu}. Geçerli: {', '.join(DAVA_TURLERI.keys())}")
    if not esas_no or not esas_no.strip():
        raise ValueError("Esas numarası boş olamaz")
    now = time.time()
    entry = {
        "id": "dk_" + uuid.uuid4().hex[:8],
        "esas_no": esas_no.strip(),
        "daire": daire.strip() if daire else "",
        "dava_turu": dava_turu,
        "taraf_muvekkil": taraf_muvekkil.strip() if taraf_muvekkil else "",
        "taraf_karsi": taraf_karsi.strip() if taraf_karsi else "",
        "konu": konu.strip() if konu else "",
        "durum": "devam_ediyor",
        "acilis_tarihi": acilis_tarihi.strip() if acilis_tarihi else "",
        "sonuc_tarihi": "",
        "notlar": notlar.strip() if notlar else "",
        "deadline_ids": [],
        "source": source if source in ("manual", "auto") else "manual",
        "created": now,
        "updated": now,
    }
    with _LOCK:
        data = _read_json(_data_path(), {"kartlar": []})
        data.setdefault("kartlar", []).append(entry)
        _write_json(_data_path(), data)
    return entry


def update_kart(kart_id: str, **kwargs) -> dict | None:
    """Dava kartını güncelle. Durum değişirse sonuc_tarihi otomatik set edilir."""
    with _LOCK:
        data = _read_json(_data_path(), {"kartlar": []})
        for entry in data.get("kartlar", []):
            if entry.get("id") == kart_id:
                # Alanları güncelle
                if "esas_no" in kwargs:
                    if not kwargs["esas_no"] or not kwargs["esas_no"].strip():
                        raise ValueError("Esas numarası boş olamaz")
                    entry["esas_no"] = kwargs["esas_no"].strip()
                if "dava_turu" in kwargs:
                    if kwargs["dava_turu"] not in DAVA_TURLERI:
                        raise ValueError(f"Geçersiz dava türü: {kwargs['dava_turu']}")
                    entry["dava_turu"] = kwargs["dava_turu"]
                if "taraf_muvekkil" in kwargs:
                    entry["taraf_muvekkil"] = kwargs["taraf_muvekkil"].strip() if kwargs["taraf_muvekkil"] else ""
                if "taraf_karsi" in kwargs:
                    entry["taraf_karsi"] = kwargs["taraf_karsi"].strip() if kwargs["taraf_karsi"] else ""
                if "daire" in kwargs:
                    entry["daire"] = kwargs["daire"].strip() if kwargs["daire"] else ""
                if "konu" in kwargs:
                    entry["konu"] = kwargs["konu"].strip() if kwargs["konu"] else ""
                if "durum" in kwargs:
                    if kwargs["durum"] not in VALID_DURUMLAR:
                        raise ValueError(f"Geçersiz durum: {kwargs['durum']}")
                    entry["durum"] = kwargs["durum"]
                    # Durum devam_ediyor'dan çıkıyorsa sonuc_tarihi otomatik set et
                    if kwargs["durum"] != "devam_ediyor" and not entry.get("sonuc_tarihi"):
                        entry["sonuc_tarihi"] = time.strftime("%Y-%m-%d")
                if "acilis_tarihi" in kwargs:
                    entry["acilis_tarihi"] = kwargs["acilis_tarihi"].strip() if kwargs["acilis_tarihi"] else ""
                if "sonuc_tarihi" in kwargs:
                    entry["sonuc_tarihi"] = kwargs["sonuc_tarihi"].strip() if kwargs["sonuc_tarihi"] else ""
                if "notlar" in kwargs:
                    entry["notlar"] = kwargs["notlar"].strip() if kwargs["notlar"] else ""
                entry["updated"] = time.time()
                _write_json(_data_path(), data)
                return entry
    return None


def delete_kart(kart_id: str) -> bool:
    """Dava kartını sil."""
    with _LOCK:
        data = _read_json(_data_path(), {"kartlar": []})
        before = len(data.get("kartlar", []))
        data["kartlar"] = [k for k in data.get("kartlar", []) if k.get("id") != kart_id]
        if len(data["kartlar"]) < before:
            _write_json(_data_path(), data)
            return True
    return False


def link_deadline(kart_id: str, deadline_id: str) -> dict | None:
    """Dava kartına süre bağla."""
    with _LOCK:
        data = _read_json(_data_path(), {"kartlar": []})
        for entry in data.get("kartlar", []):
            if entry.get("id") == kart_id:
                ids = entry.get("deadline_ids", [])
                if deadline_id not in ids:
                    ids.append(deadline_id)
                    entry["deadline_ids"] = ids
                    entry["updated"] = time.time()
                    _write_json(_data_path(), data)
                return entry
    return None


def unlink_deadline(kart_id: str, deadline_id: str) -> dict | None:
    """Dava kartından süre bağını kaldır."""
    with _LOCK:
        data = _read_json(_data_path(), {"kartlar": []})
        for entry in data.get("kartlar", []):
            if entry.get("id") == kart_id:
                ids = entry.get("deadline_ids", [])
                if deadline_id in ids:
                    ids.remove(deadline_id)
                    entry["deadline_ids"] = ids
                    entry["updated"] = time.time()
                    _write_json(_data_path(), data)
                return entry
    return None


def search_kartlar(query: str) -> list[dict]:
    """Dava kartlarında arama. Esas no, daire, taraf, konu'da arar."""
    if not query or not query.strip():
        return list_kartlar()
    q = query.strip().lower()
    entries = list_kartlar()
    results = []
    for e in entries:
        searchable = " ".join([
            e.get("esas_no", ""),
            e.get("daire", ""),
            e.get("taraf_muvekkil", ""),
            e.get("taraf_karsi", ""),
            e.get("konu", ""),
            e.get("notlar", ""),
            DAVA_TURLERI.get(e.get("dava_turu", ""), {}).get("label", ""),
        ]).lower()
        if q in searchable:
            results.append(e)
    return results


def clear_all() -> int:
    """Tüm dava kartlarını sil. Silinen adedi döndürür."""
    with _LOCK:
        data = _read_json(_data_path(), {"kartlar": []})
        n = len(data.get("kartlar", []))
        _write_json(_data_path(), {"kartlar": []})
    return n