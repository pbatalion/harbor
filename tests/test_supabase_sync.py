from src.integrations.supabase import _build_draft_records, _build_item_records
from src.settings import (
    DraftRoutingConfig,
    Settings,
    WorkspaceConfig,
    workspace_for_draft,
    workspace_for_source,
)


def _test_settings() -> Settings:
    """Create a Settings object with test workspace configuration."""
    return Settings(
        workspaces={
            "work": WorkspaceConfig(
                slug="work",
                name="Work",
                description="Test work workspace",
                sources=["gmail_work", "github"],
                sort_order=1,
                draft_routing=DraftRoutingConfig(
                    email_patterns=["@networkcraze.com", "apollo", "supabase"],
                    is_default=False,
                ),
            ),
            "downer": WorkspaceConfig(
                slug="downer",
                name="Downer",
                description="Test downer workspace",
                sources=["gmail_personal", "calendar", "hedy"],
                sort_order=2,
                draft_routing=DraftRoutingConfig(
                    email_patterns=[],
                    is_default=True,
                ),
            ),
        }
    )


def test_workspace_mapping_matches_work_and_downer_split() -> None:
    settings = _test_settings()
    assert workspace_for_source(settings, "gmail_work") == "work"
    assert workspace_for_source(settings, "github") == "work"
    assert workspace_for_source(settings, "gmail_personal") == "downer"
    assert workspace_for_source(settings, "calendar") == "downer"


def test_build_item_records_preserves_actionable_metadata() -> None:
    settings = _test_settings()
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
    rows = _build_item_records(settings, "run-1", grouped)
    assert len(rows) == 1
    assert rows[0]["workspace_slug"] == "work"
    assert rows[0]["item_type"] == "email"
    assert rows[0]["is_actionable"] is True
    assert rows[0]["external_id"] == "gmail_work:m1"


def test_build_draft_records_assigns_workspace_from_recipient() -> None:
    settings = _test_settings()
    rows = _build_draft_records(
        settings,
        "run-1",
        [
            {"type": "email_reply", "to": "Person <person@networkcraze.com>", "context": "c", "draft": "d"},
            {"type": "follow_up", "to": "person@campdowner.com", "context": "c2", "draft": "d2"},
        ],
    )
    assert rows[0]["workspace_slug"] == "work"
    assert rows[1]["workspace_slug"] == "downer"
