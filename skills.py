"""skills.py — Uzmanlık yönergeleri ("oyun kitabı" / playbook) sistemi.

`skills/<skill-adi>/SKILL.md` dosyalarını yükler. Her dosya YAML frontmatter
(name, description, triggers, doc_types) + markdown gövde (yönerge) içerir.
Kullanıcı mesajı ve (varsa) yüklenen belgenin türüne göre ilgili skill'ler
seçilir ve sistem promptuna enjekte edilir. Böylece model — hangi LLM olursa
olsun — alan uzmanı bir avukat/mali müşavir gibi yapılandırılmış davranır.

Yeni bir uzmanlık eklemek için skills/ altına bir SKILL.md dosyası eklemek
yeterlidir. Ayrıca sohbet içinden de yeni skill oluşturulabilir (save_skill).
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

_SKILLS_CACHE: Optional[List[Dict[str, Any]]] = None


def _skills_dir() -> str:
    """Skills dizini. EXE modunda veya yazılamazsa veri dizinine yazar."""
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills")
    if os.path.isdir(base) and os.access(base, os.W_OK):
        return base
    # EXE modunda veya yazılamaz — veri dizinine yaz
    env = os.environ.get("TURKIYE_MCP_DATA_DIR")
    if env:
        data_base = os.path.join(env, "skills")
    else:
        appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if appdata:
            data_base = os.path.join(appdata, "TurkiyeMCP", "skills")
        else:
            data_base = base
    os.makedirs(data_base, exist_ok=True)
    return data_base


def _source_skills_dir() -> str:
    """Paketlenmiş (read-only) skills dizini — EXE'de _MEIPASS altında."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills")


def _state_path() -> str:
    """skills_state.json — devre dışı bırakılan skill'leri saklar (veri dizininde)."""
    env = os.environ.get("TURKIYE_MCP_DATA_DIR")
    if env:
        root = env
    else:
        appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        root = os.path.join(appdata, "TurkiyeMCP") if appdata else os.path.join(os.path.expanduser("~"), ".turkiye-mcp")
    try:
        os.makedirs(root, exist_ok=True)
    except Exception:
        pass
    return os.path.join(root, "skills_state.json")


def _load_disabled() -> set:
    try:
        with open(_state_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("disabled", []))
    except Exception:
        return set()


def _save_disabled(disabled: set) -> None:
    try:
        with open(_state_path(), "w", encoding="utf-8") as f:
            json.dump({"disabled": sorted(disabled)}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def set_enabled(name: str, enabled: bool) -> bool:
    disabled = _load_disabled()
    if enabled:
        disabled.discard(name)
    else:
        disabled.add(name)
    _save_disabled(disabled)
    return True


def _parse_frontmatter(text: str) -> tuple[Dict[str, Any], str]:
    """Basit YAML frontmatter ayrıştırıcı (name, description, triggers, doc_types)."""
    meta: Dict[str, Any] = {}
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            fm = text[3:end].strip()
            body = text[end + 4:].lstrip("\n")
            for line in fm.splitlines():
                if ":" not in line:
                    continue
                key, _, val = line.partition(":")
                key = key.strip()
                val = val.strip()
                if val.startswith("[") and val.endswith("]"):
                    items = [v.strip().strip("'\"") for v in val[1:-1].split(",")]
                    meta[key] = [i for i in items if i]
                else:
                    meta[key] = val.strip("'\"")
    return meta, body


def _scan_skills_dir(base: str, skills: List[Dict[str, Any]]) -> None:
    """Bir skills dizinini tara ve skill'leri listeye ekle."""
    if not os.path.isdir(base):
        return
    seen = {s["name"] for s in skills}
    for entry in sorted(os.listdir(base)):
        path = os.path.join(base, entry)
        md = None
        if os.path.isdir(path):
            cand = os.path.join(path, "SKILL.md")
            if os.path.isfile(cand):
                md = cand
        elif entry.lower().endswith(".md"):
            md = path
        if not md:
            continue
        try:
            with open(md, "r", encoding="utf-8") as f:
                meta, body = _parse_frontmatter(f.read())
            name = meta.get("name", entry)
            if name in seen:
                continue  # kullanıcı dizini kaynak dizine göre öncelikli
            skills.append({
                "id": meta.get("name") or os.path.splitext(entry)[0],
                "name": name,
                "description": meta.get("description", ""),
                "triggers": [t.lower() for t in (meta.get("triggers") or [])],
                "doc_types": [d.lower() for d in (meta.get("doc_types") or [])],
                "body": body.strip(),
            })
        except Exception:
            continue


def load_skills(force: bool = False) -> List[Dict[str, Any]]:
    """skills/ dizinindeki tüm SKILL.md dosyalarını yükler (cache'li).
    Önce kullanıcı veri dizini, sonra kaynak dizini tarar."""
    global _SKILLS_CACHE
    if _SKILLS_CACHE is not None and not force:
        return _SKILLS_CACHE

    skills: List[Dict[str, Any]] = []
    # Kullanıcı dizini öncelikli
    user_dir = _skills_dir()
    _scan_skills_dir(user_dir, skills)
    # Kaynak dizini (farklıysa ekle)
    src_dir = _source_skills_dir()
    if os.path.abspath(src_dir) != os.path.abspath(user_dir):
        _scan_skills_dir(src_dir, skills)

    _SKILLS_CACHE = skills
    return skills


def select_skills(message: str, doc_type: str = "", max_skills: int = 2) -> List[Dict[str, Any]]:
    """Mesaj + belge türüne göre en ilgili skill'leri puanlayarak seçer."""
    skills = load_skills()
    if not skills:
        return []
    msg = (message or "").lower()
    dt = (doc_type or "").lower()
    disabled = _load_disabled()
    scored = []
    for sk in skills:
        if sk["name"] in disabled:
            continue
        score = 0
        for trig in sk["triggers"]:
            if trig and trig in msg:
                score += 2
        if dt and dt in sk["doc_types"]:
            score += 5
        if score > 0:
            scored.append((score, sk))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [sk for _, sk in scored[:max_skills]]


def build_skills_prompt(selected: List[Dict[str, Any]]) -> str:
    """Seçili skill yönergelerini sistem promptuna eklenecek metne dönüştürür."""
    if not selected:
        return ""
    parts = ["# UYGULANACAK UZMANLIK YÖNERGELERİ (SKILLS)"]
    for sk in selected:
        parts.append(f"\n## {sk['name']}\n{sk['body']}")
    return "\n".join(parts)


def list_skill_meta() -> List[Dict[str, Any]]:
    """Arayüz için hafif skill meta listesi (enabled durumuyla)."""
    disabled = _load_disabled()
    return [{"name": s["name"], "description": s["description"],
             "triggers": s["triggers"][:8], "doc_types": s["doc_types"],
             "enabled": s["name"] not in disabled}
            for s in load_skills()]


def _slugify(name: str) -> str:
    """Skill adından dosya adı üret (Türkçe → ASCII, boşluk → tire)."""
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosucgiosu")
    s = name.translate(tr_map)
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:60] or "skill"


def get_skill_content(name: str) -> Optional[str]:
    """Skill'in tam SKILL.md içeriğini döndür (frontmatter + body)."""
    for base in [_skills_dir(), _source_skills_dir()]:
        if not os.path.isdir(base):
            continue
        for entry in os.listdir(base):
            path = os.path.join(base, entry)
            md = None
            if os.path.isdir(path):
                cand = os.path.join(path, "SKILL.md")
                if os.path.isfile(cand):
                    md = cand
            elif entry.lower().endswith(".md"):
                md = path
            if not md:
                continue
            try:
                with open(md, "r", encoding="utf-8") as f:
                    content = f.read()
                meta, _ = _parse_frontmatter(content)
                if meta.get("name") == name:
                    return content
            except Exception:
                continue
    return None


def save_skill(name: str, content: str) -> dict:
    """Yeni skill oluştur veya var olanı güncelle. SKILL.md dosyasına yazar."""
    if not content or not content.strip():
        raise ValueError("content must not be empty")
    if not content.strip().startswith("---"):
        raise ValueError("content must start with YAML frontmatter (---)")

    slug = _slugify(name)
    skill_dir = os.path.join(_skills_dir(), slug)
    os.makedirs(skill_dir, exist_ok=True)
    md_path = os.path.join(skill_dir, "SKILL.md")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)

    # Cache invalidate
    global _SKILLS_CACHE
    _SKILLS_CACHE = None
    load_skills(force=True)

    return {"status": "ok", "name": name, "path": md_path}