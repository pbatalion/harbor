from datetime import UTC, datetime, timedelta

from src.settings import Settings
from src.sources.hedy import fetch_hedy_events


class DummyResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def test_hedy_returns_empty_on_api_error_with_credentials(monkeypatch) -> None:
    settings = Settings(
        hedy_api_base_url="https://api.hedy.bot",
        hedy_api_key="secret",
        seed_mock_data_if_empty=True,
    )

    def fake_get(*args, **kwargs):
        return DummyResponse(404, text="not found")

    monkeypatch.setattr("src.sources.hedy.requests.get", fake_get)

    events = fetch_hedy_events(settings, datetime.now(UTC) - timedelta(days=1))
    assert events == []


def test_hedy_builds_event_from_sessions_and_details(monkeypatch) -> None:
    settings = Settings(
        hedy_api_base_url="https://api.hedy.bot",
        hedy_api_key="secret",
        seed_mock_data_if_empty=False,
    )

    session_id = "abc123"

    def fake_get(url, *args, **kwargs):
        if url.endswith("/sessions"):
            return DummyResponse(
                200,
                payload={
                    "data": [
                        {
                            "sessionId": session_id,
                            "title": "Board meeting",
                            "startTime": datetime.now(UTC).isoformat(),
                        }
                    ]
                },
            )
        if url.endswith(f"/sessions/{session_id}"):
            return DummyResponse(
                200,
                payload={
                    "sessionId": session_id,
                    "cleaned_transcript": "Discussed migration timeline",
                },
            )
        return DummyResponse(404, text="nope")

    monkeypatch.setattr("src.sources.hedy.requests.get", fake_get)

    events = fetch_hedy_events(settings, datetime.now(UTC) - timedelta(days=1))
    assert len(events) == 1
    assert events[0]["event_id"] == session_id
    assert "migration timeline" in events[0]["payload"]["text"]
