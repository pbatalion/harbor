from datetime import UTC, datetime

from src.reporting.follow_through import build_follow_through_snapshot, render_follow_through_report
from src.state.db import complete_run, create_run, init_db, persist_source_events


def test_follow_through_snapshot_filters_actionable_and_includes_drafts(tmp_path) -> None:
    db_path = str(tmp_path / "assistant.db")
    init_db(db_path)

    run_id = "run-123"
    create_run(db_path, run_id)
    complete_run(db_path, run_id)

    now = datetime.now(UTC).isoformat()
    events = [
        {
            "event_id": "a1",
            "event_ts": now,
            "payload": {
                "source": "gmail_work",
                "subject": "Action needed",
                "sender": "Alice <alice@example.com>",
                "thread_id": "t1",
                "timestamp": now,
                "is_actionable": True,
                "is_unread": True,
                "thread_message_count": 3,
            },
        },
        {
            "event_id": "a2",
            "event_ts": now,
            "payload": {
                "source": "gmail_work",
                "subject": "CC only",
                "sender": "Bob <bob@example.com>",
                "thread_id": "t2",
                "timestamp": now,
                "is_actionable": False,
                "is_unread": True,
                "thread_message_count": 2,
            },
        },
    ]
    persist_source_events(db_path, run_id, "gmail_work", events)

    # Insert one draft row directly to validate report loading.
    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO drafts (run_id, draft_type, context, draft, recipient, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                "email_reply",
                "reply context",
                "draft text",
                "alice@example.com",
                "pending_review",
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    snapshot = build_follow_through_snapshot(db_path, run_id=run_id, actionable_limit=10)
    assert snapshot["run_id"] == run_id
    assert snapshot["source_counts"]["gmail_work"] == 2
    assert len(snapshot["actionable_threads"]) == 1
    assert snapshot["actionable_threads"][0]["thread_id"] == "t1"
    assert len(snapshot["drafts"]) == 1
    assert snapshot["drafts"][0]["type"] == "email_reply"

    rendered = render_follow_through_report(snapshot)
    assert "Actionable Email Threads" in rendered
    assert "Action needed" in rendered
    assert "CC only" not in rendered


def test_follow_through_snapshot_uses_recent_gmail_events_across_runs(tmp_path) -> None:
    db_path = str(tmp_path / "assistant.db")
    init_db(db_path)

    old_run = "run-old"
    new_run = "run-new"
    create_run(db_path, old_run)
    complete_run(db_path, old_run)
    create_run(db_path, new_run)
    complete_run(db_path, new_run)

    now = datetime.now(UTC).isoformat()
    old_events = [
        {
            "event_id": "recent-thread",
            "event_ts": now,
            "payload": {
                "source": "gmail_work",
                "subject": "Older actionable thread",
                "sender": "Alice <alice@example.com>",
                "thread_id": "t-old",
                "timestamp": now,
                "is_actionable": True,
                "is_unread": False,
                "thread_message_count": 4,
            },
        }
    ]
    persist_source_events(db_path, old_run, "gmail_work", old_events)

    snapshot = build_follow_through_snapshot(db_path, run_id=new_run, actionable_limit=10, lookback_days=30)
    assert snapshot["run_id"] == new_run
    assert snapshot["source_counts"]["gmail_work"] == 1
    assert len(snapshot["actionable_threads"]) == 1
    assert snapshot["actionable_threads"][0]["subject"] == "Older actionable thread"
