from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import requests

from src.settings import Settings

logger = logging.getLogger(__name__)


def _to_iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _parse_iso(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except Exception:
        return datetime.now(UTC)


def _mock_events(since: datetime) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    transcript_id = f"mock-hedy-{int(now.timestamp())}"
    return [
        {
            "event_id": transcript_id,
            "event_ts": _to_iso(now),
            "payload": {
                "source": "hedy",
                "transcript_id": transcript_id,
                "title": "Mock client sync",
                "participants": ["Phil", "Client A"],
                "timestamp": _to_iso(now),
                "text": "Action item: send migration timeline by tomorrow.",
                "since": _to_iso(since),
            },
        }
    ]


def _extract_sessions(response_json: Any) -> list[dict[str, Any]]:
    if isinstance(response_json, list):
        return [x for x in response_json if isinstance(x, dict)]
    if isinstance(response_json, dict):
        data = response_json.get("data")
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
    return []


def fetch_hedy_events(settings: Settings, since: datetime) -> list[dict[str, Any]]:
    if not settings.hedy_api_base_url or not settings.hedy_api_key:
        return _mock_events(since) if settings.seed_mock_data_if_empty else []

    base = settings.hedy_api_base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {settings.hedy_api_key}"}

    # Hedy list endpoint from OpenAPI: GET /sessions
    list_resp = requests.get(
        f"{base}/sessions",
        headers=headers,
        params={"limit": 50},
        timeout=20,
    )
    if list_resp.status_code != 200:
        logger.warning(
            "Hedy list request failed status=%s body=%s",
            list_resp.status_code,
            list_resp.text[:300],
        )
        return []

    sessions = _extract_sessions(list_resp.json())
    events: list[dict[str, Any]] = []

    for item in sessions:
        session_id = str(item.get("sessionId") or item.get("id") or "")
        if not session_id:
            continue

        start_time = _parse_iso(item.get("startTime") or item.get("timestamp"))
        if start_time < since:
            continue

        detail_resp = requests.get(
            f"{base}/sessions/{session_id}",
            headers=headers,
            timeout=20,
        )
        detail: dict[str, Any] = {}
        if detail_resp.status_code == 200:
            raw = detail_resp.json()
            detail = raw if isinstance(raw, dict) else {}
        else:
            logger.warning(
                "Hedy detail request failed session_id=%s status=%s body=%s",
                session_id,
                detail_resp.status_code,
                detail_resp.text[:200],
            )

        transcript_text = str(
            detail.get("cleaned_transcript")
            or detail.get("transcript")
            or item.get("transcript")
            or ""
        )
        recap = detail.get("recap")

        events.append(
            {
                "event_id": session_id,
                "event_ts": _to_iso(start_time),
                "payload": {
                    "source": "hedy",
                    "transcript_id": session_id,
                    "title": item.get("title", ""),
                    "participants": detail.get("participants", []),
                    "timestamp": _to_iso(start_time),
                    "text": transcript_text,
                    "recap": recap if isinstance(recap, dict) else {},
                    "topic": item.get("topic", {}),
                },
            }
        )

    return events
