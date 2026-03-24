"""
Storage layer for normalized source events in Supabase.
Provides read/write access for the LLM triage system.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from src.settings import Settings

logger = logging.getLogger(__name__)


def _get_supabase_client(settings: Settings):
    """Get Supabase client if configured."""
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return None

    try:
        from supabase import create_client
        return create_client(settings.supabase_url, settings.supabase_service_role_key)
    except Exception as e:
        logger.warning("Failed to create Supabase client: %s", e)
        return None


def store_source_events(
    settings: Settings,
    run_id: str,
    events: list[dict[str, Any]],
) -> int:
    """
    Store normalized source events in Supabase.
    Returns the number of events stored.
    """
    client = _get_supabase_client(settings)
    if not client:
        logger.warning("Supabase not configured, skipping event storage")
        return 0

    if not events:
        return 0

    # Prepare records for insert
    records = []
    for event in events:
        record = {
            "id": event.get("id"),
            "source": event.get("source"),
            "event_type": event.get("event_type"),
            "external_id": event.get("external_id"),
            "title": event.get("title", ""),
            "body": event.get("body"),
            "snippet": event.get("snippet"),
            "actor": event.get("actor"),
            "actor_email": event.get("actor_email"),
            "recipients": event.get("recipients", []),
            "occurred_at": event.get("occurred_at"),
            "due_at": event.get("due_at"),
            "is_directed_to_user": event.get("is_directed_to_user", False),
            "is_mention": event.get("is_mention", False),
            "requires_response": event.get("requires_response", False),
            "extracted_tasks": event.get("extracted_tasks", []),
            "extracted_entities": event.get("extracted_entities", {}),
            "thread_summary": event.get("thread_summary"),
            "metadata": event.get("metadata", {}),
            "workspace_slug": event.get("workspace_slug"),
            "run_id": run_id,
        }
        records.append(record)

    try:
        # Upsert to handle duplicates
        result = client.table("assistant_source_events").upsert(
            records,
            on_conflict="run_id,source,external_id",
        ).execute()

        stored = len(result.data) if result.data else 0
        logger.info("Stored %d source events for run %s", stored, run_id[:8])
        return stored

    except Exception as e:
        logger.error("Failed to store source events: %s", e)
        return 0


def load_source_events_for_triage(
    settings: Settings,
    run_id: str,
    workspace_slug: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Load source events for LLM triage.
    Returns normalized events optimized for LLM context.
    """
    client = _get_supabase_client(settings)
    if not client:
        return []

    try:
        query = client.table("assistant_source_events").select(
            "id, source, event_type, title, body, snippet, actor, "
            "recipients, occurred_at, due_at, is_directed_to_user, is_mention, "
            "requires_response, extracted_tasks, thread_summary, metadata, workspace_slug"
        ).eq("run_id", run_id).order("occurred_at", desc=True).limit(limit)

        if workspace_slug:
            query = query.eq("workspace_slug", workspace_slug)

        result = query.execute()
        return result.data or []

    except Exception as e:
        logger.error("Failed to load source events: %s", e)
        return []


def load_recent_events_for_context(
    settings: Settings,
    workspace_slug: str | None = None,
    hours: int = 48,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    Load recent events across runs for broader context.
    Useful for understanding patterns and ongoing threads.
    """
    client = _get_supabase_client(settings)
    if not client:
        return []

    since = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()

    try:
        query = client.table("assistant_source_events").select(
            "source, event_type, title, snippet, actor, occurred_at, "
            "requires_response, workspace_slug"
        ).gte("occurred_at", since).order("occurred_at", desc=True).limit(limit)

        if workspace_slug:
            query = query.eq("workspace_slug", workspace_slug)

        result = query.execute()
        return result.data or []

    except Exception as e:
        logger.error("Failed to load recent events: %s", e)
        return []


def get_events_requiring_response(
    settings: Settings,
    run_id: str,
    workspace_slug: str | None = None,
) -> list[dict[str, Any]]:
    """
    Get events that likely require a response.
    These are prioritized for draft generation.
    """
    client = _get_supabase_client(settings)
    if not client:
        return []

    try:
        query = client.table("assistant_source_events").select(
            "id, source, event_type, title, body, snippet, actor, actor_email, "
            "recipients, occurred_at, thread_summary, metadata, workspace_slug"
        ).eq("run_id", run_id).eq("requires_response", True).order("occurred_at", desc=True)

        if workspace_slug:
            query = query.eq("workspace_slug", workspace_slug)

        result = query.execute()
        return result.data or []

    except Exception as e:
        logger.error("Failed to load events requiring response: %s", e)
        return []


def get_extracted_tasks(
    settings: Settings,
    run_id: str,
    workspace_slug: str | None = None,
) -> list[dict[str, Any]]:
    """
    Get all extracted tasks from source events.
    """
    client = _get_supabase_client(settings)
    if not client:
        return []

    try:
        query = client.table("assistant_source_events").select(
            "id, source, title, extracted_tasks, occurred_at, workspace_slug"
        ).eq("run_id", run_id).neq("extracted_tasks", [])

        if workspace_slug:
            query = query.eq("workspace_slug", workspace_slug)

        result = query.execute()

        # Flatten tasks with source context
        tasks = []
        for event in result.data or []:
            for task in event.get("extracted_tasks", []):
                tasks.append({
                    "source_event_id": event["id"],
                    "source": event["source"],
                    "source_title": event["title"],
                    "task": task.get("task", ""),
                    "assignee": task.get("assignee"),
                    "due_date": task.get("due_date"),
                    "priority": task.get("priority"),
                })

        return tasks

    except Exception as e:
        logger.error("Failed to load extracted tasks: %s", e)
        return []
