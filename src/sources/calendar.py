from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import requests

from src.settings import Settings
from src.utils.auth import AuthError, get_google_access_token


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
    start = now + timedelta(hours=2)
    end = start + timedelta(hours=1)
    event_id = f"mock-calendar-{int(now.timestamp())}"
    return [
        {
            "event_id": event_id,
            "event_ts": _to_iso(start),
            "payload": {
                "source": "calendar",
                "calendar_id": "mock",
                "event_id": event_id,
                "summary": "Mock planning meeting",
                "start": _to_iso(start),
                "end": _to_iso(end),
                "since": _to_iso(since),
            },
        }
    ]


def fetch_calendar_events(settings: Settings, since: datetime) -> list[dict[str, Any]]:
    refresh_token = settings.google_refresh_token_work or settings.google_refresh_token_personal
    if not (settings.google_client_id and settings.google_client_secret and refresh_token):
        return _mock_events(since) if settings.seed_mock_data_if_empty else []

    try:
        access_token = get_google_access_token(
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            refresh_token=refresh_token,
        )
    except AuthError:
        return _mock_events(since) if settings.seed_mock_data_if_empty else []

    headers = {"Authorization": f"Bearer {access_token}"}

    calendars = settings.google_calendar_ids or ["primary"]
    time_min = since.astimezone(UTC).isoformat()
    time_max = (datetime.now(UTC) + timedelta(days=2)).isoformat()

    events: list[dict[str, Any]] = []
    for calendar_id in calendars:
        resp = requests.get(
            f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events",
            headers=headers,
            params={
                "singleEvents": "true",
                "orderBy": "startTime",
                "timeMin": time_min,
                "timeMax": time_max,
                "maxResults": 100,
            },
            timeout=20,
        )
        if resp.status_code != 200:
            continue

        for item in resp.json().get("items", []):
            event_id = str(item.get("id", ""))
            start_raw = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date")
            end_raw = item.get("end", {}).get("dateTime") or item.get("end", {}).get("date")
            start_dt = _parse_iso(start_raw)
            end_dt = _parse_iso(end_raw)
            events.append(
                {
                    "event_id": f"{calendar_id}:{event_id}",
                    "event_ts": _to_iso(start_dt),
                    "payload": {
                        "source": "calendar",
                        "calendar_id": calendar_id,
                        "event_id": event_id,
                        "summary": item.get("summary", ""),
                        "start": _to_iso(start_dt),
                        "end": _to_iso(end_dt),
                    },
                }
            )

    if not events and settings.seed_mock_data_if_empty:
        return _mock_events(since)
    return events
