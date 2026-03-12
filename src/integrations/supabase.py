from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import requests

from src.settings import Settings, workspace_for_draft, workspace_for_source
from src.utils.timestamps import parse_iso, utcnow_iso

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Checkpoint storage (Supabase-first)
# ---------------------------------------------------------------------------


def get_supabase_checkpoint(settings: Settings, source: str) -> datetime | None:
    """Get checkpoint from Supabase. Returns None if not found or not configured."""
    if not (settings.supabase_url and settings.supabase_service_role_key):
        return None

    try:
        response = requests.get(
            f"{settings.supabase_url.rstrip('/')}/rest/v1/assistant_checkpoints",
            headers=_request_headers(settings),
            params={"source": f"eq.{source}", "select": "high_watermark"},
            timeout=10,
        )
        if response.status_code != 200:
            logger.warning("Supabase checkpoint read failed: %s", response.text[:200])
            return None

        rows = response.json()
        if not rows:
            return None

        return parse_iso(rows[0]["high_watermark"])
    except Exception as exc:
        logger.warning("Supabase checkpoint read error: %s", exc)
        return None


def set_supabase_checkpoint(settings: Settings, source: str, high_watermark: datetime) -> bool:
    """Set checkpoint in Supabase. Returns True on success."""
    if not (settings.supabase_url and settings.supabase_service_role_key):
        return False

    try:
        row = {
            "source": source,
            "high_watermark": high_watermark.isoformat(),
            "updated_at": utcnow_iso(),
        }
        response = requests.post(
            f"{settings.supabase_url.rstrip('/')}/rest/v1/assistant_checkpoints",
            headers=_request_headers(settings),
            data=json.dumps([row], separators=(",", ":"), ensure_ascii=True),
            timeout=10,
        )
        if response.status_code >= 300:
            logger.warning("Supabase checkpoint write failed: %s", response.text[:200])
            return False
        return True
    except Exception as exc:
        logger.warning("Supabase checkpoint write error: %s", exc)
        return False


def load_recent_items_from_supabase(
    settings: Settings, source: str, since: datetime, limit: int = 500
) -> list[dict[str, Any]] | None:
    """Load recent items from Supabase. Returns None if not configured or on error."""
    if not (settings.supabase_url and settings.supabase_service_role_key):
        return None

    try:
        response = requests.get(
            f"{settings.supabase_url.rstrip('/')}/rest/v1/assistant_items",
            headers=_request_headers(settings),
            params={
                "source": f"eq.{source}",
                "occurred_at": f"gte.{since.isoformat()}",
                "select": "payload",
                "order": "occurred_at.desc",
                "limit": limit,
            },
            timeout=30,
        )
        if response.status_code != 200:
            logger.warning("Supabase items read failed: %s", response.text[:200])
            return None

        rows = response.json()
        return [row["payload"] for row in rows if row.get("payload")]
    except Exception as exc:
        logger.warning("Supabase items read error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Workspace and source mapping
# ---------------------------------------------------------------------------


def _item_type_for_source(source: str) -> str:
    if source.startswith("gmail_"):
        return "email"
    if source == "github":
        return "github"
    if source == "calendar":
        return "calendar"
    if source == "hedy":
        return "transcript"
    return "event"


def _item_external_id(source: str, item: dict[str, Any]) -> str:
    for key in ("message_id", "thread_id", "session_id", "id", "event_id"):
        value = str(item.get(key, "")).strip()
        if value:
            return f"{source}:{value}"
    title = str(item.get("subject") or item.get("title") or item.get("summary") or "item")
    timestamp = str(item.get("timestamp") or item.get("start") or item.get("start_time") or "")
    return f"{source}:{title}:{timestamp}"


def _item_title(item: dict[str, Any]) -> str:
    return str(item.get("subject") or item.get("title") or item.get("summary") or "Untitled item")


def _item_actor(item: dict[str, Any]) -> str:
    return str(item.get("sender") or item.get("repo") or item.get("speaker") or item.get("owner") or "")


def _item_occurred_at(item: dict[str, Any]) -> str:
    for key in ("timestamp", "start", "start_time", "event_ts"):
        value = str(item.get(key, "")).strip()
        if value:
            return parse_iso(value).isoformat()
    return utcnow_iso()


def _source_counts(grouped: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    return {source: len(items) for source, items in grouped.items()}


def _build_item_records(
    settings: Settings, run_id: str, grouped: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source, items in grouped.items():
        workspace_slug = workspace_for_source(settings, source)
        item_type = _item_type_for_source(source)
        for item in items:
            rows.append(
                {
                    "id": f"{run_id}:{_item_external_id(source, item)}",
                    "run_id": run_id,
                    "workspace_slug": workspace_slug,
                    "source": source,
                    "item_type": item_type,
                    "external_id": _item_external_id(source, item),
                    "title": _item_title(item),
                    "actor": _item_actor(item),
                    "occurred_at": _item_occurred_at(item),
                    "is_actionable": bool(item.get("is_actionable", False)),
                    "is_unread": bool(item.get("is_unread", False)),
                    "payload": item,
                    "created_at": utcnow_iso(),
                }
            )
    return rows


def _build_draft_records(
    settings: Settings, run_id: str, draft_actions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, draft in enumerate(draft_actions):
        recipient = str(draft.get("to", ""))
        rows.append(
            {
                "id": f"{run_id}:draft:{index}",
                "run_id": run_id,
                "workspace_slug": workspace_for_draft(settings, recipient),
                "draft_type": str(draft.get("type", "follow_up")),
                "recipient": str(draft.get("to", "")),
                "context": str(draft.get("context", "")),
                "draft": str(draft.get("draft", "")),
                "status": "pending_review",
                "created_at": utcnow_iso(),
            }
        )
    return rows


def _request_headers(settings: Settings) -> dict[str, str]:
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }


def _post_rows(settings: Settings, table: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    response = requests.post(
        f"{settings.supabase_url.rstrip('/')}/rest/v1/{table}",
        headers=_request_headers(settings),
        data=json.dumps(rows, separators=(",", ":"), ensure_ascii=True),
        timeout=30,
    )
    if response.status_code >= 300:
        raise RuntimeError(f"Supabase sync failed table={table} status={response.status_code} body={response.text[:400]}")


def sync_run_snapshot(
    settings: Settings,
    *,
    run_id: str,
    grouped: dict[str, list[dict[str, Any]]],
    analysis: dict[str, Any],
    digest_location: str,
) -> None:
    if not (settings.supabase_url and settings.supabase_service_role_key):
        return

    # Sync workspace configuration from settings
    workspaces = [
        {
            "slug": ws.slug,
            "name": ws.name,
            "description": ws.description,
            "sort_order": ws.sort_order,
        }
        for ws in settings.workspaces.values()
    ]
    _post_rows(settings, "assistant_workspaces", workspaces)

    run_row = [
        {
            "id": run_id,
            "status": "completed",
            "digest_location": digest_location,
            "day_plan": str(analysis.get("day_plan", "")),
            "urgent_items": analysis.get("urgent_items", []),
            "source_counts": _source_counts(grouped),
            "created_at": utcnow_iso(),
            "synced_at": utcnow_iso(),
        }
    ]
    _post_rows(settings, "assistant_runs", run_row)
    _post_rows(settings, "assistant_items", _build_item_records(settings, run_id, grouped))
    _post_rows(
        settings,
        "assistant_drafts",
        _build_draft_records(settings, run_id, analysis.get("email_digest", {}).get("draft_actions", [])),
    )
    logger.info("Synced run snapshot to Supabase run_id=%s", run_id)
