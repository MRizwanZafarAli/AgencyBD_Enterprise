"""
Unified LLM Gateway for AgencyBD_Enterprise.

Model-agnostic completions with token/cost logging per tenant. There is NO canned fallback: if no
model provider is available the call raises ``NotConfiguredError`` rather than
returning text that looks like model output.

Providers, in order: Anthropic API (ANTHROPIC_API_KEY) -> local Ollama (only if OLLAMA_HOST is set).
"""

import json
import os
import re
import time
import urllib.request
from typing import Any, Callable, Dict, Optional

from config.honesty import NotConfiguredError
from database.models import AgentRunRepository

# USD per million tokens. Verify against Anthropic's current pricing page before relying on cost figures.
MODEL_PRICING = {
    "claude-sonnet-5-5": {"in": 3.0, "out": 15.0},
    "claude-haiku-5-5": {"in": 0.25, "out": 1.25},
    "claude-opus-5-5": {"in": 15.0, "out": 75.0},
    "llama3.1:8b": {"in": 0.0, "out": 0.0},
}

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"  # fixed host: not user-controlled


class LLMError(RuntimeError):
    """The model provider failed (network, auth, malformed response)."""


class LLMGateway:
    @staticmethod
    def has_provider() -> bool:
        key = os.getenv("ANTHROPIC_API_KEY", "")
        return bool(key and not key.startswith("your_")) or bool(os.getenv("OLLAMA_HOST"))

    # -- provider calls (separate methods so tests can substitute them) -----------------------------

    @classmethod
    def _call_anthropic(cls, prompt: str, system: Optional[str], model: str, temperature: float, max_tokens: int) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "model": model, "max_tokens": max_tokens, "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
        req = urllib.request.Request(
            ANTHROPIC_URL, data=json.dumps(body).encode("utf-8"),
            headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        usage = data.get("usage", {})
        return {"text": data["content"][0]["text"], "tokens_in": usage.get("input_tokens", 0),
                "tokens_out": usage.get("output_tokens", 0), "model": model, "provider": "anthropic"}

    @classmethod
    def _call_ollama(cls, prompt: str, system: Optional[str]) -> Dict[str, Any]:
        host = os.environ["OLLAMA_HOST"].rstrip("/")  # operator-configured, never request-derived
        payload = {"model": os.getenv("OLLAMA_MODEL", "llama3.1:8b"), "prompt": prompt, "stream": False}
        if system:
            payload["system"] = system
        req = urllib.request.Request(f"{host}/api/generate", data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data.get("response", "")
        return {"text": text, "tokens_in": len(prompt.split()), "tokens_out": len(text.split()),
                "model": payload["model"], "provider": "ollama_local"}

    # -- public API ---------------------------------------------------------------------------------

    @classmethod
    def complete(
        cls,
        prompt: str,
        system: Optional[str] = None,
        model: str = "claude-sonnet-5-5",
        temperature: float = 0.3,
        max_tokens: int = 1500,
        agent_name: str = "GeneralAgent",
        org_id: str = "org_default",
    ) -> Dict[str, Any]:
        started = time.time()
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        errors = []
        result: Optional[Dict[str, Any]] = None

        if api_key and not api_key.startswith("your_"):
            try:
                result = cls._call_anthropic(prompt, system, model, temperature, max_tokens)
            except Exception as exc:  # network/auth/format: record, then try the next provider
                errors.append(f"anthropic: {str(exc)[:120]}")
        if result is None and os.getenv("OLLAMA_HOST"):
            try:
                result = cls._call_ollama(prompt, system)
            except Exception as exc:
                errors.append(f"ollama: {str(exc)[:120]}")

        latency_ms = int((time.time() - started) * 1000)

        if result is None:
            if errors:
                AgentRunRepository.log_run(agent_name=agent_name, model=model, tokens_in=0, tokens_out=0, cost_usd=0.0,
                                           latency_ms=latency_ms, status=f"error: {'; '.join(errors)}"[:200], org_id=org_id)
                raise LLMError("; ".join(errors))
            raise NotConfiguredError("llm", "No language model is configured. Set ANTHROPIC_API_KEY (or OLLAMA_HOST for a local model).")

        pricing = MODEL_PRICING.get(result["model"], {"in": 0.0, "out": 0.0})
        cost = (result["tokens_in"] * pricing["in"] + result["tokens_out"] * pricing["out"]) / 1_000_000.0
        AgentRunRepository.log_run(agent_name=agent_name, model=result["model"], tokens_in=result["tokens_in"],
                                   tokens_out=result["tokens_out"], cost_usd=cost, latency_ms=latency_ms,
                                   status="success", org_id=org_id)
        return {**result, "cost_usd": cost, "latency_ms": latency_ms}

    @staticmethod
    def extract_json(text: str) -> Any:
        """Parses the first JSON object in a model reply (tolerates code fences and leading prose)."""
        cleaned = re.sub(r"```(?:json)?", "", text).strip()
        start = cleaned.find("{")
        if start == -1:
            raise ValueError("No JSON object found in model output.")
        depth, in_str, esc = 0, False, False
        for i in range(start, len(cleaned)):
            ch = cleaned[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(cleaned[start:i + 1])
        raise ValueError("Unterminated JSON object in model output.")

    @classmethod
    def complete_json(cls, prompt: str, system: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Like complete(), but returns the parsed JSON object under 'data'."""
        out = cls.complete(prompt, system=(system or "") + "\nRespond with a single JSON object and nothing else.", **kwargs)
        out["data"] = cls.extract_json(out["text"])
        return out
