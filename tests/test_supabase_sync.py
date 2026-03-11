from src.integrations.supabase import _build_draft_records, _build_item_records, _workspace_for_source


def test_workspace_mapping_matches_work_and_downer_split() -> None:
    assert _workspace_for_source("gmail_work") == "work"
    assert _workspace_for_source("github") == "work"
    assert _workspace_for_source("gmail_personal") == "downer"
    assert _workspace_for_source("calendar") == "downer"


def test_build_item_records_preserves_actionable_metadata() -> None:
    grouped = {
        "gmail_work": [
            {
                "message_id": "m1",
                "thread_id": "t1",
                "subject": "Action needed",
                "sender": "Alice <alice@example.com>",
                "timestamp": "2026-03-10T12:00:00+00:00",
                "is_actionable": True,
                "is_unread": True,
            }
        ]
    }
    rows = _build_item_records("run-1", grouped)
    assert len(rows) == 1
    assert rows[0]["workspace_slug"] == "work"
    assert rows[0]["item_type"] == "email"
    assert rows[0]["is_actionable"] is True
    assert rows[0]["external_id"] == "gmail_work:m1"


def test_build_draft_records_assigns_workspace_from_recipient() -> None:
    rows = _build_draft_records(
        "run-1",
        [
            {"type": "email_reply", "to": "Person <person@networkcraze.com>", "context": "c", "draft": "d"},
            {"type": "follow_up", "to": "person@campdowner.com", "context": "c2", "draft": "d2"},
        ],
    )
    assert rows[0]["workspace_slug"] == "work"
    assert rows[1]["workspace_slug"] == "downer"
