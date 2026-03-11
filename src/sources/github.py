from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import requests

from src.settings import Settings


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
    event_id = f"mock-github-{int(now.timestamp())}"
    return [
        {
            "event_id": event_id,
            "event_ts": _to_iso(now),
            "payload": {
                "source": "github",
                "type": "notification",
                "id": event_id,
                "repo": "Network-Craze/platform",
                "subject": "Review requested: API worker queue refactor",
                "url": "https://github.com/Network-Craze/platform/pull/123",
                "updated_at": _to_iso(now),
                "since": _to_iso(since),
            },
        }
    ]


def fetch_github_events(settings: Settings, since: datetime) -> list[dict[str, Any]]:
    if not settings.github_token:
        return _mock_events(since) if settings.seed_mock_data_if_empty else []

    headers = {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    params = {"since": since.astimezone(UTC).isoformat().replace("+00:00", "Z"), "all": "true"}

    resp = requests.get(
        "https://api.github.com/notifications", headers=headers, params=params, timeout=20
    )
    if resp.status_code != 200:
        return _mock_events(since) if settings.seed_mock_data_if_empty else []

    events: list[dict[str, Any]] = []
    for item in resp.json():
        notif_id = str(item.get("id", ""))
        updated = _parse_iso(item.get("updated_at"))
        subject = item.get("subject", {})
        repository = item.get("repository", {})
        events.append(
            {
                "event_id": notif_id,
                "event_ts": _to_iso(updated),
                "payload": {
                    "source": "github",
                    "type": "notification",
                    "id": notif_id,
                    "repo": repository.get("full_name", ""),
                    "subject": subject.get("title", ""),
                    "subject_type": subject.get("type", ""),
                    "url": subject.get("url", ""),
                    "updated_at": _to_iso(updated),
                },
            }
        )

    return events
