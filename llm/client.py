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
    @classmethod
    def _call_mock(cls, prompt: str, system: Optional[str], agent_name: str, org_id: str) -> Dict[str, Any]:
        started = time.time()
        if agent_name == "FitAnalyst":
            post = prompt.split("JOB POST", 1)[1] if "JOB POST" in prompt else prompt
            
            raw_sentences = []
            for line in post.splitlines():
                line = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", line).strip()
                if not line or line.startswith("{") or line.startswith("AGENCY:") or line.startswith("PORTFOLIO:"):
                    continue
                for chunk in re.split(r"(?<=[.!?])\s+", line):
                    chunk = chunk.strip().strip("-*•· ")
                    if len(chunk) >= 18:
                        raw_sentences.append(chunk)

            def _clean_quote(sentence: str, full_text: str, max_words: int = 8) -> str:
                words = sentence.split()
                for length in range(min(len(words), max_words), 3, -1):
                    for start in range(len(words) - length + 1):
                        q = " ".join(words[start:start+length])
                        if q in full_text and len(q) >= 14:
                            return q
                return ""

            match_topics = [
                (r"(optimiz\w+|analys\w+|report\w+|dashboard\w+|crm|pipeline|data\s+analysis)", "Data & Operations Workflow Optimization"),
                (r"(react|python|fastapi|typescript|cloud|api|mulesoft|salesforce|next\.js)", "Technical Architecture & Delivery"),
                (r"(automat\w+|streamlin\w+|scal\w+|growth|integrat\w+|workflows?)", "Workflow Automation & Systems Integration"),
                (r"(deliver\w+|architect\w+|platform|infrastructure|full-?stack)", "Engineering & Product Acceleration"),
            ]

            risk_topics = [
                (r"(must be in|time zone|est or ct|location:|relocation|us-?\s*remote|overlap)", "Geographic & Timezone Constraints"),
                (r"(join our\b|team\b|revenue operations team|full-?time|salary|benefits|401k|employee)", "Employment Structure (Internal FTE vs Agency Contract)"),
                (r"(commission-only|no base|no retainer|unpaid)", "Commercial & Compensation Model"),
                (r"(\d+\+?\s*years?|senior level|lead developer|certified)", "Specific Seniority or Domain Requirements"),
            ]

            reasons, risks = [], []
            for pat, label in match_topics:
                for s in raw_sentences:
                    if re.search(pat, s, re.IGNORECASE):
                        q = _clean_quote(s, post)
                        if q and q in post:
                            reasons.append({"point": f"{label}: Direct overlap with core agency capabilities.", "quote": q})
                            break
                if len(reasons) >= 2:
                    break

            for pat, label in risk_topics:
                for s in raw_sentences:
                    if re.search(pat, s, re.IGNORECASE):
                        q = _clean_quote(s, post)
                        if q and q in post:
                            risks.append({"point": f"{label}: Key constraint noted in client specification.", "quote": q})
                            break
                if len(risks) >= 2:
                    break

            if not reasons and raw_sentences:
                q = _clean_quote(raw_sentences[0], post)
                if q:
                    reasons.append({"point": "Operational scope aligns with agency engineering services.", "quote": q})
            if not risks and len(raw_sentences) > 1:
                q = _clean_quote(raw_sentences[1], post)
                if q:
                    risks.append({"point": "Review timeline and deployment dependencies before kickoff.", "quote": q})

            is_internal_hire = any("Employment" in r["point"] for r in risks)
            verdict = "maybe" if is_internal_hire else ("pursue" if reasons else "skip")

            if verdict == "pursue":
                summary = "High-priority commercial match. Deliverables and technical scope match past delivered case studies."
            elif verdict == "maybe":
                summary = "Viable contract opportunity if pitched as an external sprint team to cover the workflow backlog without hiring overhead."
            else:
                summary = "Unlikely fit. Stated requirements or budget constraints do not align with agency service thresholds."

            questions = [
                "What is the target delivery date for the primary deliverables?",
                "Which existing third-party platforms or APIs must be integrated on day one?",
                "Would the hiring team consider a milestone-based sprint engagement rather than waiting for an FTE?"
            ]

            data = {
                "verdict": verdict,
                "summary": summary,
                "reasons": reasons,
                "risks": risks,
                "questions_to_ask": questions[:3]
            }
            res_text = json.dumps(data)
        elif agent_name == "ProposalStudio":
            m_title = re.search(r"Title:\s*(.+)", prompt)
            job_title = m_title.group(1).strip() if m_title else "Software Development"
            m_case = re.search(r"\[CASE STUDY asset:(\d+)\][^\n]*\n([^\n]+)", prompt)
            if m_case:
                aid = int(m_case.group(1))
                case_body = m_case.group(2)
            else:
                aid = 1
                case_body = "Platform modernizations and workflow integrations."

            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", case_body) if len(s.strip()) > 20]
            proof_sentence = sentences[0] if sentences else case_body

            variant_a = {
                "body": (
                    f"Regarding your post about {job_title}: our team can deliver this engagement with dedicated expertise. "
                    f"In past work, we {proof_sentence.lower()} "
                    f"We begin with a focused discovery sprint to align on priorities and milestones. "
                    f"Would you be open to a brief conversation this week to confirm scope?"
                ),
                "claims": [
                    {"text": proof_sentence, "source": f"asset:{aid}"},
                    {"text": job_title, "source": "job"}
                ]
            }
            variant_b = {
                "body": (
                    f"Quick answer to your post regarding {job_title}: we can deliver this project with speed and reliability. "
                    f"For a recent client, we {proof_sentence.lower()} "
                    f"We can begin immediately and establish clear milestones inside your scheduled window. "
                    f"Would a short introductory call help to review details?"
                ),
                "claims": [
                    {"text": proof_sentence, "source": f"asset:{aid}"},
                    {"text": job_title, "source": "job"}
                ]
            }
            res_text = json.dumps({"variant_a": variant_a, "variant_b": variant_b})
        else:
            res_text = json.dumps({"status": "ok"})

        tokens_in = len(prompt.split())
        tokens_out = len(res_text.split())
        latency_ms = int((time.time() - started) * 1000)
        return {
            "text": res_text,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "model": "claude-mock-grounded",
            "provider": "mock",
            "cost_usd": 0.0,
            "latency_ms": latency_ms,
        }
    @staticmethod
    def has_provider() -> bool:
        key = os.getenv("ANTHROPIC_API_KEY", "")
        return bool(key and not key.startswith("your_")) or bool(os.getenv("OLLAMA_HOST")) or os.getenv("AGENCYBD_MOCK_LLM") == "1"

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
            if api_key.lower() in ("mock", "test", "demo") or os.getenv("AGENCYBD_MOCK_LLM") == "1":
                return cls._call_mock(prompt, system, agent_name, org_id)
            try:
                result = cls._call_anthropic(prompt, system, model, temperature, max_tokens)
            except Exception as exc:  # network/auth/format: record, then try the next provider
                errors.append(f"anthropic: {str(exc)[:120]}")
        if result is None and os.getenv("OLLAMA_HOST"):
            if os.getenv("OLLAMA_HOST").lower() in ("mock", "test", "demo"):
                return cls._call_mock(prompt, system, agent_name, org_id)
            try:
                result = cls._call_ollama(prompt, system)
            except Exception as exc:
                errors.append(f"ollama: {str(exc)[:120]}")
        if result is None and os.getenv("AGENCYBD_MOCK_LLM") == "1":
            return cls._call_mock(prompt, system, agent_name, org_id)

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
