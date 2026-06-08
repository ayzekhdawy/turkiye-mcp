"""gateway.py — LLM Gateway (merkezi sağlayıcı yönlendirme + failover).

Tüm LLM çağrılarını tek bir kontrol katmanında toplar. Bir model zinciri
(chain) verilir; birincil model başarısız olursa (zaman aşımı, 400, bağlantı
hatası veya BOŞ yanıt) sıradaki modele otomatik geçilir. Sağlayıcı başına
metrik (başarı/başarısızlık/gecikme) tutulur ve /api/gateway/status ile
sunulur.

Tek başına çalışır; sağlayıcı tanımları (providers dict) dışarıdan verilir.
"""

from __future__ import annotations

import time
from collections import defaultdict
import json
import os
import threading
from typing import Any, Dict, List, Optional

import httpx

# Reasoning (düşünme) destekleyen model aileleri — reasoning_effort yalnızca bunlara gider
_REASONING_HINTS = (
    "gpt-oss", "deepseek-v3", "deepseek-r1", "qwen3", "glm-4.6", "glm-4-6",
    "kimi", "minimax-m2", "magistral", "reasoning", "nemotron", "exaone-deep",
    "smallthinker", "thinking", "o1", "o3",
)


def is_reasoning_model(model: str) -> bool:
    m = (model or "").lower()
    return any(h in m for h in _REASONING_HINTS)


# Model adından bağlam penceresi (token) tahmini — kullanım göstergesi için
_CONTEXT_TABLE = [
    (("gpt-4o", "gpt-4.1", "gpt-4-turbo", "o1", "o3", "gpt-oss"), 128000),
    (("gpt-3.5",), 16000),
    (("claude",), 200000),
    (("gemini-1.5", "gemini-2", "gemini-3"), 1000000),
    (("llama3.1", "llama3.2", "llama3.3", "llama-3.1", "llama-3.3"), 128000),
    (("qwen3",), 32000), (("qwen2.5",), 32000),
    (("deepseek",), 64000), (("minimax",), 200000),
    (("glm-4",), 128000), (("kimi",), 128000),
    (("mistral", "mixtral"), 32000),
    (("gemma3", "gemma2", "gemma4"), 8192),
    (("nemotron", "command",), 128000),
]


def estimate_context(model: str) -> int:
    m = (model or "").lower()
    for keys, ctx in _CONTEXT_TABLE:
        if any(k in m for k in keys):
            return ctx
    return 8192


def _extract_usage(data: dict) -> dict:
    """OpenAI/Anthropic yanıtından token kullanımını normalize eder."""
    u = data.get("usage") or {}
    prompt = u.get("prompt_tokens", u.get("input_tokens", 0)) or 0
    completion = u.get("completion_tokens", u.get("output_tokens", 0)) or 0
    total = u.get("total_tokens", (prompt + completion)) or (prompt + completion)
    return {"prompt": int(prompt), "completion": int(completion), "total": int(total)}



# ===== Gateway konfigürasyonu (sunucu tarafında kalıcı) =====

_LOCK = threading.RLock()

def _data_dir() -> str:
    """Gateway config dosyasının dizini (workspace ile aynı kök)."""
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


def _config_path() -> str:
    return os.path.join(_data_dir(), "gateway_config.json")


def load_config() -> dict:
    """Kaydedilmiş gateway yapılandırmasını yükle (boşsa varsayılan döner)."""
    with _LOCK:
        try:
            with open(_config_path(), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}


def save_config(config: dict) -> None:
    """Gateway yapılandırmasını diske kaydet (atomik yazım)."""
    with _LOCK:
        tmp = _config_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _config_path())


def apply_config(providers: dict, config: dict) -> dict:
    """Kaydedilmiş config'i providers dict'ine uygula ve güncel halini döndür.

    Config yapısı:
    {
      "providers": {
        "openrouter": {"url": "https://...", "timeout": 120, "default_model": "gpt-4o-mini", "models": [...]},
        ...
      },
      "default_chain": [{"provider": "openrouter", "model": "gpt-4o-mini"}, ...]
    }
    Sadece belirtilen alanları override eder; eksik alanlar varsayından kalır.
    """
    overrides = config.get("providers", {})
    for pid, over in overrides.items():
        if pid not in providers:
            continue
        pc = providers[pid]
        if "url" in over and over["url"]:
            pc["url"] = over["url"]
        if "timeout" in over:
            pc["timeout"] = int(over["timeout"])
        if "default_model" in over and over["default_model"]:
            pc["default_model"] = over["default_model"]
        if "models" in over and isinstance(over["models"], list):
            # Kullanıcının eklediği modeller + varsayılanlar (tekrarsız)
            merged = list(over["models"])
            for m in pc.get("models", []):
                if m not in merged:
                    merged.append(m)
            pc["models"] = merged
    return providers


def get_config_snapshot(providers: dict) -> dict:
    """Mevcut providers dict'inden okunabilir bir config snapshot'u oluştur."""
    result = {}
    for pid, pc in providers.items():
        entry = {"name": pc.get("name", pid)}
        if "url" in pc:
            entry["url"] = pc["url"]
        if "timeout" in pc:
            entry["timeout"] = pc["timeout"]
        if "default_model" in pc:
            entry["default_model"] = pc["default_model"]
        if "models" in pc:
            entry["models"] = list(pc["models"])
        result[pid] = entry
    saved = load_config()
    return {"providers": result, "default_chain": saved.get("default_chain", [])}


class LLMGateway:
    """Çok sağlayıcılı LLM yönlendirme + failover + metrik."""

    def __init__(self, providers: Dict[str, Any]):
        self.providers = providers
        self.metrics: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"calls": 0, "ok": 0, "fail": 0, "empty": 0, "latency_ms": 0.0, "last": ""}
        )

    # ---- tek bir sağlayıcıya çağrı ----
    async def _call_one(self, provider_id: str, model: str, system: str,
                        history: List[Dict[str, str]], message: str,
                        api_key: str, timeout: float) -> str:
        pc = self.providers[provider_id]
        reasoning = is_reasoning_model(model)
        # Reasoning modelleri gizli düşünceye token harcar → nihai yanıt için
        # daha geniş bütçe ver (yoksa content boş dönebilir).
        max_tokens = 4096 if reasoning else 2048
        async with httpx.AsyncClient(timeout=timeout) as client:
            if pc.get("is_anthropic"):
                resp = await client.post(pc["url"], headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                }, json={
                    "model": model, "max_tokens": max_tokens, "system": system,
                    "messages": history + [{"role": "user", "content": message}],
                })
                resp.raise_for_status()
                data = resp.json()
                text = (data.get("content", [{}])[0].get("text", "") or "").strip()
                return {"text": text, "usage": _extract_usage(data)}

            # OpenAI uyumlu (OpenRouter/OpenAI/Gemini/Ollama/Ollama Cloud)
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            if provider_id == "openrouter":
                headers["HTTP-Referer"] = "https://turkiye-mcp.up.railway.app"

            messages = [{"role": "system", "content": system}] + history + [
                {"role": "user", "content": message}]
            payload = {"model": model, "messages": messages, "max_tokens": max_tokens}
            # reasoning modelleri için reasoning_effort; desteklemeyen modelde 400 → çıkar, tekrar dene
            if provider_id in ("ollama", "ollama_cloud") and reasoning:
                payload["reasoning_effort"] = "low"
            resp = await client.post(pc["url"], headers=headers, json=payload)
            if resp.status_code == 400 and "reasoning_effort" in payload:
                payload.pop("reasoning_effort", None)
                resp = await client.post(pc["url"], headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            msg = data.get("choices", [{}])[0].get("message", {}) or {}
            text = (msg.get("content") or msg.get("reasoning")
                    or msg.get("reasoning_content") or "").strip()
            usage = _extract_usage(data)
            # Bazı sağlayıcılar prompt_tokens döndürmez → girdiden kabaca tahmin et (~4 char/token)
            if not usage["prompt"]:
                approx = len(system) + sum(len(h.get("content", "")) for h in history) + len(message)
                usage["prompt"] = approx // 4
                usage["total"] = usage["prompt"] + usage["completion"]
            return {"text": text, "usage": usage}

    # ---- zincir üzerinden tamamlama (failover) ----
    async def complete(self, *, system: str, history: List[Dict[str, str]], message: str,
                       chain: List[Dict[str, str]], api_keys: Dict[str, str],
                       timeout_for=None) -> Dict[str, Any]:
        attempts: List[Dict[str, Any]] = []
        last_error = ""

        for step in chain:
            pid = (step.get("provider") or "").lower()
            pc = self.providers.get(pid)
            if not pc:
                continue
            model = step.get("model") or pc["default_model"]
            api_key = api_keys.get(pid, "") or ""
            if pc["needs_key"] and not api_key:
                attempts.append({"provider": pid, "model": model, "status": "no_key"})
                last_error = f"{pc['name']} için API anahtarı yok"
                continue

            timeout = timeout_for(pid) if timeout_for else (300 if pid == "ollama" else 120)
            m = self.metrics[pid]
            m["calls"] += 1
            t0 = time.time()
            try:
                out = await self._call_one(pid, model, system, history, message, api_key, timeout)
                reply = out.get("text", "")
                usage = out.get("usage", {"prompt": 0, "completion": 0, "total": 0})
                dt = (time.time() - t0) * 1000
                m["latency_ms"] += dt
                if reply:
                    m["ok"] += 1
                    m["last"] = "ok"
                    m["tokens"] = m.get("tokens", 0) + usage.get("total", 0)
                    ctx = estimate_context(model)
                    used = usage.get("total", 0)
                    attempts.append({"provider": pid, "model": model, "status": "ok",
                                     "ms": int(dt), "tokens": usage.get("total", 0)})
                    return {"reply": reply, "provider": pid, "model": model, "attempts": attempts,
                            "usage": usage,
                            "context": {"window": ctx, "used": used,
                                        "ratio": round(used / ctx, 4) if ctx else 0}}
                m["empty"] += 1
                m["last"] = "empty"
                attempts.append({"provider": pid, "model": model, "status": "empty"})
                last_error = "model boş yanıt döndürdü"
            except httpx.TimeoutException:
                m["fail"] += 1; m["last"] = "timeout"
                attempts.append({"provider": pid, "model": model, "status": "timeout"})
                last_error = "zaman aşımı"
            except httpx.ConnectError:
                m["fail"] += 1; m["last"] = "connect"
                attempts.append({"provider": pid, "model": model, "status": "connect"})
                last_error = ("yerel Ollama'ya bağlanılamadı" if pid == "ollama"
                              else "sağlayıcıya bağlanılamadı")
            except httpx.HTTPStatusError as e:
                m["fail"] += 1; m["last"] = f"http{e.response.status_code}"
                detail = ""
                try:
                    detail = e.response.text[:160]
                except Exception:
                    pass
                attempts.append({"provider": pid, "model": model,
                                 "status": f"http {e.response.status_code}", "detail": detail})
                last_error = f"HTTP {e.response.status_code}"
            except Exception as e:
                m["fail"] += 1; m["last"] = "error"
                attempts.append({"provider": pid, "model": model, "status": "error",
                                 "detail": str(e)[:160]})
                last_error = str(e) or type(e).__name__

        return {"error": f"Tüm modeller başarısız oldu ({last_error}).", "attempts": attempts}

    def status(self) -> Dict[str, Any]:
        out = {}
        for pid, m in self.metrics.items():
            ok = m["ok"]
            out[pid] = {
                "name": self.providers.get(pid, {}).get("name", pid),
                "calls": int(m["calls"]), "ok": int(ok), "fail": int(m["fail"]),
                "empty": int(m["empty"]), "last": m["last"],
                "avg_latency_ms": int(m["latency_ms"] / ok) if ok else 0,
                "tokens": int(m.get("tokens", 0)),
            }
        return out
