"""gateway.py — LLM Gateway (merkezi sağlayıcı yönlendirme + failover).

OpenClaw'ın "gateway" kavramından esinlenir: tüm LLM çağrılarını tek bir
kontrol katmanında toplar. Bir model zinciri (chain) verilir; birincil model
başarısız olursa (zaman aşımı, 400, bağlantı hatası veya BOŞ yanıt) sıradaki
modele otomatik geçilir. Sağlayıcı başına metrik (başarı/başarısızlık/gecikme)
tutulur ve /api/gateway/status ile sunulur.

Tek başına çalışır; sağlayıcı tanımları (providers dict) dışarıdan verilir.
"""

from __future__ import annotations

import time
from collections import defaultdict
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
                return (data.get("content", [{}])[0].get("text", "") or "").strip()

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
            return (msg.get("content") or msg.get("reasoning")
                    or msg.get("reasoning_content") or "").strip()

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
                reply = await self._call_one(pid, model, system, history, message, api_key, timeout)
                dt = (time.time() - t0) * 1000
                m["latency_ms"] += dt
                if reply:
                    m["ok"] += 1
                    m["last"] = "ok"
                    attempts.append({"provider": pid, "model": model, "status": "ok", "ms": int(dt)})
                    return {"reply": reply, "provider": pid, "model": model, "attempts": attempts}
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
            }
        return out
