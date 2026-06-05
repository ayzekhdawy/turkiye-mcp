"""skills.py — Anthropic skill formatında "oyun kitabı" (playbook) sistemi.

`skills/<skill-adi>/SKILL.md` dosyalarını yükler. Her dosya YAML frontmatter
(name, description, triggers, doc_types) + markdown gövde (yönerge) içerir.
Kullanıcı mesajı ve (varsa) yüklenen belgenin türüne göre ilgili skill'ler
seçilir ve sistem promptuna enjekte edilir. Böylece model — hangi LLM olursa
olsun — alan uzmanı bir avukat/mali müşavir gibi yapılandırılmış davranır.

Referans format: https://github.com/anthropics/skills
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

_SKILLS_CACHE: Optional[List[Dict[str, Any]]] = None


def _skills_dir() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills")


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


def load_skills(force: bool = False) -> List[Dict[str, Any]]:
    """skills/ dizinindeki tüm SKILL.md dosyalarını yükler (cache'li)."""
    global _SKILLS_CACHE
    if _SKILLS_CACHE is not None and not force:
        return _SKILLS_CACHE

    skills: List[Dict[str, Any]] = []
    base = _skills_dir()
    if os.path.isdir(base):
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
                skills.append({
                    "id": meta.get("name") or os.path.splitext(entry)[0],
                    "name": meta.get("name", entry),
                    "description": meta.get("description", ""),
                    "triggers": [t.lower() for t in (meta.get("triggers") or [])],
                    "doc_types": [d.lower() for d in (meta.get("doc_types") or [])],
                    "body": body.strip(),
                })
            except Exception:
                continue
    _SKILLS_CACHE = skills
    return skills


def select_skills(message: str, doc_type: str = "", max_skills: int = 2) -> List[Dict[str, Any]]:
    """Mesaj + belge türüne göre en ilgili skill'leri puanlayarak seçer."""
    skills = load_skills()
    if not skills:
        return []
    msg = (message or "").lower()
    dt = (doc_type or "").lower()
    scored = []
    for sk in skills:
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


def list_skill_meta() -> List[Dict[str, str]]:
    """Arayüz için hafif skill meta listesi."""
    return [{"name": s["name"], "description": s["description"]} for s in load_skills()]
