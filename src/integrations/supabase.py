from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import requests

from src.settings import Settings

logger = logging.getLogger(__name__)


def _workspace_for_source(source: str) -> str:
    return "work" if source in {"gmail_work", "github"} else "downer"


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


def _parse_iso(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except Exception:
        return datetime.now(UTC)


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


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
            return _parse_iso(value).isoformat()
    return _iso_now()


def _source_counts(grouped: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    return {source: len(items) for source, items in grouped.items()}


def _build_item_records(run_id: str, grouped: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source, items in grouped.items():
        workspace_slug = _workspace_for_source(source)
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
                    "created_at": _iso_now(),
                }
            )
    return rows


def _draft_workspace_slug(draft: dict[str, Any]) -> str:
    recipient = str(draft.get("to", "")).lower()
    if "@networkcraze.com" in recipient or "apollo" in recipient or "supabase" in recipient:
        return "work"
    return "downer"


def _build_draft_records(run_id: str, draft_actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, draft in enumerate(draft_actions):
        rows.append(
            {
                "id": f"{run_id}:draft:{index}",
                "run_id": run_id,
                "workspace_slug": _draft_workspace_slug(draft),
                "draft_type": str(draft.get("type", "follow_up")),
                "recipient": str(draft.get("to", "")),
                "context": str(draft.get("context", "")),
                "draft": str(draft.get("draft", "")),
                "status": "pending_review",
                "created_at": _iso_now(),
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

    workspaces = [
        {
            "slug": "work",
            "name": "Work",
            "description": "Network Craze email, GitHub, and operations queue.",
            "sort_order": 1,
        },
        {
            "slug": "downer",
            "name": "Downer",
            "description": "Camp Downer email, calendar, and meeting follow-through.",
            "sort_order": 2,
        },
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
            "created_at": _iso_now(),
            "synced_at": _iso_now(),
        }
    ]
    _post_rows(settings, "assistant_runs", run_row)
    _post_rows(settings, "assistant_items", _build_item_records(run_id, grouped))
    _post_rows(
        settings,
        "assistant_drafts",
        _build_draft_records(run_id, analysis.get("email_digest", {}).get("draft_actions", [])),
    )
    logger.info("Synced run snapshot to Supabase run_id=%s", run_id)
