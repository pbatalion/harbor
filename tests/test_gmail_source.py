from datetime import UTC, datetime, timedelta

from src.settings import Settings
from src.sources.gmail import fetch_gmail_events


class DummyResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def _settings(thread_context_max: int) -> Settings:
    return Settings(
        google_client_id="client-id",
        google_client_secret="client-secret",
        google_refresh_token_work="refresh-token",
        seed_mock_data_if_empty=False,
        gmail_thread_context_max_messages=thread_context_max,
    )


def _fake_gmail_get(url, *args, **kwargs):
    if url.endswith("/users/me/profile"):
        return DummyResponse(200, payload={"emailAddress": "pbatalion@networkcraze.com"})
    if url.endswith("/users/me/threads"):
        return DummyResponse(200, payload={"threads": [{"id": "thread-1"}]})
    if url.endswith("/users/me/threads/thread-1"):
        return DummyResponse(
            200,
            payload={
                "id": "thread-1",
                "messages": [
                    {
                        "id": "m1",
                        "threadId": "thread-1",
                        "internalDate": "1700000000000",
                        "snippet": "Can you review this?",
                        "labelIds": ["INBOX"],
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "Alice <alice@example.com>"},
                                {"name": "Subject", "value": "Initial ask"},
                                {"name": "To", "value": "pbatalion@networkcraze.com"},
                                {"name": "Date", "value": "Mon, 01 Jan 2024 10:00:00 +0000"},
                            ]
                        },
                    },
                    {
                        "id": "m2",
                        "threadId": "thread-1",
                        "internalDate": "1700003600000",
                        "snippet": "Following up to team",
                        "labelIds": ["INBOX", "UNREAD"],
                        "payload": {
                            "headers": [
                                {"name": "From", "value": "Alice <alice@example.com>"},
                                {"name": "Subject", "value": "Team follow-up"},
                                {"name": "To", "value": "director@campdowner.com"},
                                {"name": "Cc", "value": "pbatalion@networkcraze.com"},
                                {"name": "Date", "value": "Mon, 01 Jan 2024 11:00:00 +0000"},
                            ]
                        },
                    },
                ],
            },
        )
    return DummyResponse(404, text="not found")


def test_gmail_thread_latest_cc_only_is_not_actionable(monkeypatch) -> None:
    settings = _settings(thread_context_max=0)
    monkeypatch.setattr("src.sources.gmail.get_google_access_token", lambda **kwargs: "token")
    monkeypatch.setattr("src.sources.gmail.requests.get", _fake_gmail_get)

    events = fetch_gmail_events(settings, account="work", since=datetime.now(UTC) - timedelta(days=1))

    assert len(events) == 1
    payload = events[0]["payload"]
    assert payload["thread_id"] == "thread-1"
    assert payload["message_id"] == "m2"
    assert payload["directed_to_user"] is False
    assert payload["cc_only_for_user"] is True
    assert payload["is_actionable"] is False
    assert payload["thread_message_count"] == 2
    assert len(payload["thread_context"]) == 2
    assert payload["thread_context"][0]["message_id"] == "m1"
    assert payload["thread_context"][1]["message_id"] == "m2"


def test_gmail_thread_context_respects_max_messages(monkeypatch) -> None:
    settings = _settings(thread_context_max=1)
    monkeypatch.setattr("src.sources.gmail.get_google_access_token", lambda **kwargs: "token")
    monkeypatch.setattr("src.sources.gmail.requests.get", _fake_gmail_get)

    events = fetch_gmail_events(settings, account="work", since=datetime.now(UTC) - timedelta(days=1))

    assert len(events) == 1
    payload = events[0]["payload"]
    assert payload["thread_message_count"] == 2
    assert len(payload["thread_context"]) == 1
    assert payload["thread_context"][0]["message_id"] == "m2"
