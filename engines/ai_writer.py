"""
Multi-Provider AI Email Writer Engine.
Supports Local AI (Ollama, LM Studio, vLLM / OpenAI-compatible) and Paid APIs
(OpenAI, Anthropic Claude, Google Gemini, OpenRouter/Groq), plus honest
structured fallback when no live model is configured.
"""

import json
import os
import re
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import requests


def _parse_subject_body(text: str, fallback_subject: str) -> Tuple[str, str]:
    raw = (text or "").strip()
    lines = raw.splitlines()
    subject = fallback_subject
    body_lines = lines
    for i, line in enumerate(lines[:5]):
        m = re.match(r"^\s*(?:Subject|SUBJ)\s*:\s*(.+)$", line, re.IGNORECASE)
        if m:
            subject = m.group(1).strip().strip('"')
            body_lines = lines[i + 1 :]
            break
    body = "\n".join(body_lines).strip()
    return subject or fallback_subject, body or raw


def _validate_base_url(url: str, allow_local: bool = True) -> str:
    clean = (url or "").strip().rstrip("/")
    parsed = urlparse(clean)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Base URL must start with http:// or https:// and include a hostname.")
    if not allow_local and parsed.hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        raise ValueError("Localhost base URL is only allowed for local AI providers.")
    return clean


def generate_email_draft(
    *,
    provider: str = "auto",
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    recipient_name: str = "",
    company_name: str = "",
    goal: str = "",
    tone: str = "consultative",
    context: str = "",
    reply_to_subject: str = "",
    reply_to_body: str = "",
) -> Dict[str, Any]:
    """Generates a tailored B2B email subject + body using the chosen local or paid AI provider."""
    first_name = (recipient_name or "").strip().split()[0] if recipient_name and recipient_name.strip() else "there"
    company = (company_name or "").strip() or "your team"
    default_subject = (
        f"Re: {reply_to_subject}" if reply_to_subject else f"Quick idea for {company}"
    )

    system_prompt = (
        "You are a senior B2B business development writer. Write concise, human, non-spammy emails "
        "(under 130 words) with zero hype or fabricated metrics. Return ONLY:\n"
        "Subject: <one crisp subject line>\n\n<email body>"
    )
    user_parts = [
        f"Recipient first name: {first_name}",
        f"Company: {company}",
        f"Tone: {tone}",
    ]
    if goal:
        user_parts.append(f"Goal / Offer: {goal}")
    if context:
        user_parts.append(f"Prospect / Account Context: {context}")
    if reply_to_body:
        user_parts.append(f"Replying to inbound message:\n{reply_to_body[:1200]}")
    user_prompt = "\n".join(user_parts)

    chosen = (provider or "auto").strip().lower()
    if chosen == "auto":
        if os.getenv("OLLAMA_HOST"):
            chosen = "ollama"
        elif os.getenv("OPENAI_API_KEY"):
            chosen = "openai"
        elif os.getenv("ANTHROPIC_API_KEY"):
            chosen = "anthropic"
        elif os.getenv("GEMINI_API_KEY"):
            chosen = "gemini"
        else:
            chosen = "template_fallback"

    if chosen == "ollama":
        host = _validate_base_url(base_url or os.getenv("OLLAMA_HOST") or "http://localhost:11434", allow_local=True)
        mdl = (model or "llama3.1").strip()
        resp = requests.post(
            f"{host}/api/chat",
            json={
                "model": mdl,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=45,
        )
        resp.raise_for_status()
        text = resp.json().get("message", {}).get("content", "")
        subj, bdy = _parse_subject_body(text, default_subject)
        return {"subject": subj, "body": bdy, "provider_used": "ollama", "model_used": mdl}

    if chosen in ("openai", "openai_compatible"):
        key = (api_key or os.getenv("OPENAI_API_KEY") or "").strip()
        url = _validate_base_url(base_url or "https://api.openai.com/v1", allow_local=True)
        mdl = (model or ("gpt-4o-mini" if chosen == "openai" else "local-model")).strip()
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        elif chosen == "openai":
            raise ValueError("OpenAI API key is required (enter it in the AI Assistant or Settings).")
        resp = requests.post(
            f"{url}/chat/completions",
            headers=headers,
            json={
                "model": mdl,
                "temperature": 0.6,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=45,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        subj, bdy = _parse_subject_body(text, default_subject)
        return {"subject": subj, "body": bdy, "provider_used": chosen, "model_used": mdl}

    if chosen == "anthropic":
        key = (api_key or os.getenv("ANTHROPIC_API_KEY") or "").strip()
        if not key:
            raise ValueError("Anthropic API key is required (enter it in the AI Assistant or Settings).")
        mdl = (model or "claude-3-5-sonnet-latest").strip()
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": mdl,
                "max_tokens": 500,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=45,
        )
        resp.raise_for_status()
        blocks = resp.json().get("content", [])
        text = "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        subj, bdy = _parse_subject_body(text, default_subject)
        return {"subject": subj, "body": bdy, "provider_used": "anthropic", "model_used": mdl}

    if chosen == "gemini":
        key = (api_key or os.getenv("GEMINI_API_KEY") or "").strip()
        if not key:
            raise ValueError("Gemini API key is required (enter it in the AI Assistant or Settings).")
        mdl = (model or "gemini-2.0-flash").strip()
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent?key={key}",
            json={
                "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
            },
            timeout=45,
        )
        resp.raise_for_status()
        cands = resp.json().get("candidates", [])
        text = cands[0]["content"]["parts"][0]["text"] if cands else ""
        subj, bdy = _parse_subject_body(text, default_subject)
        return {"subject": subj, "body": bdy, "provider_used": "gemini", "model_used": mdl}

    # Structured offline/manual fallback when no live LLM key or local Ollama is active
    hook = goal.strip() or f"helping {company} improve conversion speed and technical reliability"
    ctx_line = f"\n\nI noticed: {context.strip()}" if context.strip() else ""
    if reply_to_body:
        body = (
            f"Hi {first_name},\n\n"
            f"Thanks for getting back to me.{ctx_line}\n\n"
            f"Happy to share a brief walkthrough tailored to {company} — would Tuesday or Thursday work for a 15-minute call?\n\n"
            f"Best,"
        )
    else:
        body = (
            f"Hi {first_name},\n\n"
            f"I was looking at {company} and wanted to reach out regarding {hook}.{ctx_line}\n\n"
            f"If it's relevant this quarter, I'd be glad to send over a 3-point teardown specific to {company}. Open to a quick look?\n\n"
            f"Best,"
        )
    return {
        "subject": default_subject,
        "body": body,
        "provider_used": "structured_fallback",
        "model_used": "offline-template",
    }
