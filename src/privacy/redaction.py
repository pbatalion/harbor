from __future__ import annotations

import copy
import re
from typing import Any


SECRET_PATTERNS = [
    (re.compile(r"\b(?:sk|rk|ghp|xoxb|xoxp)-[A-Za-z0-9_-]{10,}\b"), "[REDACTED_SECRET]"),
    (re.compile(r"\b\d{12,19}\b"), "[REDACTED_ACCOUNT_NUMBER]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_PERSONAL_ID]"),
    (re.compile(r"(?i)(password|passcode|otp)\s*[:=]\s*\S+"), "[REDACTED_CREDENTIAL]"),
]


def _redact_text(value: str, custom_terms: list[str]) -> str:
    redacted = value
    for pattern, token in SECRET_PATTERNS:
        redacted = pattern.sub(token, redacted)
    for term in custom_terms:
        term = term.strip()
        if not term:
            continue
        redacted = re.sub(re.escape(term), "[REDACTED_CUSTOM_TERM]", redacted, flags=re.IGNORECASE)
    return redacted


def redact_sensitive_payload(payload: dict[str, Any], custom_terms: list[str]) -> dict[str, Any]:
    result = copy.deepcopy(payload)

    def walk(node: Any) -> Any:
        if isinstance(node, str):
            return _redact_text(node, custom_terms)
        if isinstance(node, list):
            return [walk(item) for item in node]
        if isinstance(node, dict):
            return {key: walk(value) for key, value in node.items()}
        return node

    return walk(result)
