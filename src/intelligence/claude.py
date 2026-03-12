from __future__ import annotations

import json
from typing import Any

import requests

from src.settings import Settings
from src.utils.http import post, TransientHTTPError


class ClaudeError(RuntimeError):
    pass


def _extract_json_text(text: str) -> str:
    cleaned = text.strip()

    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 3:
            cleaned = "\n".join(lines[1:-1]).strip()

    if cleaned.startswith("json\n"):
        cleaned = cleaned[5:].strip()

    return cleaned


def _parse_json_payload(text: str) -> dict[str, Any]:
    cleaned = _extract_json_text(text)

    for candidate in [cleaned]:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    # Best-effort extraction of the first JSON object.
    first_obj = cleaned.find("{")
    last_obj = cleaned.rfind("}")
    if first_obj >= 0 and last_obj > first_obj:
        try:
            parsed = json.loads(cleaned[first_obj : last_obj + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    raise ClaudeError(f"Claude returned non-JSON object payload: {cleaned[:700]}")


def call_claude(
    *, settings: Settings, system_prompt: str, data: dict[str, Any], max_tokens: int = 1400
) -> dict[str, Any]:
    if not settings.anthropic_api_key:
        raise ClaudeError("Missing ANTHROPIC_API_KEY")

    payload = {
        "model": settings.anthropic_model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [
            {
                "role": "user",
                "content": json.dumps(data, ensure_ascii=True),
            }
        ],
    }

    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    try:
        response = post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
            timeout=60,
        )
    except (requests.RequestException, TransientHTTPError) as exc:
        raise ClaudeError(f"Claude request failed: {exc}") from exc

    if response.status_code != 200:
        raise ClaudeError(f"Claude API error: {response.status_code} {response.text[:600]}")

    body = response.json()
    blocks = body.get("content", [])
    text = "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
    if not text:
        raise ClaudeError("Empty Claude response text")

    return _parse_json_payload(text)
