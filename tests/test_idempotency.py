from datetime import UTC, datetime

from src.state.db import init_db, persist_source_events


def test_persist_source_events_is_idempotent(tmp_path) -> None:
    db_path = str(tmp_path / "assistant.db")
    init_db(db_path)

    now = datetime.now(UTC).isoformat()
    events = [
        {
            "event_id": "same-id",
            "event_ts": now,
            "payload": {"source": "gmail_work", "subject": "A"},
        }
    ]

    first = persist_source_events(db_path, "run-1", "gmail_work", events)
    second = persist_source_events(db_path, "run-1", "gmail_work", events)

    assert first == 1
    assert second == 0
