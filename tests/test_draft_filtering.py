from src.queue.jobs import _filter_non_actionable_email_drafts


def test_drops_email_reply_not_in_allowed_targets() -> None:
    drafts = [
        {"type": "email_reply", "to": "Person A <a@example.com>", "draft": "x", "context": "c"},
        {"type": "follow_up", "to": "", "draft": "y", "context": "d"},
    ]
    filtered = _filter_non_actionable_email_drafts(drafts, {"b@example.com"})
    assert len(filtered) == 1
    assert filtered[0]["type"] == "follow_up"


def test_keeps_email_reply_in_allowed_targets() -> None:
    drafts = [{"type": "email_reply", "to": "Person B <b@example.com>", "draft": "x", "context": "c"}]
    filtered = _filter_non_actionable_email_drafts(drafts, {"b@example.com"})
    assert len(filtered) == 1
    assert filtered[0]["type"] == "email_reply"
