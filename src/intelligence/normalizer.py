"""
Normalizes raw source data into a consistent format for storage and LLM analysis.
"""
from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from src.settings import Settings, workspace_for_source


def _truncate(text: str | None, max_len: int = 2000) -> str:
    """Truncate text for LLM context efficiency."""
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _clean_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r"<[^>]+>", "", text)


def _extract_email_body(payload: dict[str, Any]) -> str:
    """Extract email body from Gmail payload, preferring plain text."""
    # Check thread_context for most recent message body
    thread_context = payload.get("thread_context", [])
    if thread_context:
        latest = thread_context[-1] if isinstance(thread_context[-1], dict) else {}
        body = latest.get("body", "") or latest.get("snippet", "")
        if body:
            return _clean_html(body)

    # Fallback to snippet
    return payload.get("snippet", "")


def normalize_gmail_event(event: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Normalize a Gmail event for storage."""
    payload = event.get("payload", {})
    source = payload.get("source", "gmail_work")

    # Build recipients list
    recipients = []
    for email in payload.get("to_recipients", []):
        recipients.append({"email": email, "type": "to"})
    for email in payload.get("cc_recipients", []):
        recipients.append({"email": email, "type": "cc"})

    # Extract body content
    body = _extract_email_body(payload)

    # Thread context for summary
    thread_context = payload.get("thread_context", [])
    thread_summary = None
    if len(thread_context) > 1:
        summaries = []
        for msg in thread_context[-3:]:  # Last 3 messages
            if isinstance(msg, dict):
                sender = msg.get("sender", "Unknown")
                snippet = msg.get("snippet", "")[:100]
                summaries.append(f"{sender}: {snippet}")
        thread_summary = " | ".join(summaries)

    return {
        "id": str(uuid4()),
        "source": source,
        "event_type": "email",
        "external_id": payload.get("thread_id") or payload.get("message_id"),
        "title": payload.get("subject", "No subject"),
        "body": _truncate(body),
        "snippet": _truncate(payload.get("snippet", ""), 200),
        "actor": payload.get("sender", ""),
        "actor_email": _extract_email_address(payload.get("sender", "")),
        "recipients": recipients,
        "occurred_at": payload.get("timestamp") or event.get("event_ts"),
        "is_directed_to_user": payload.get("directed_to_user", False),
        "is_mention": False,
        "requires_response": payload.get("is_actionable", False),
        "thread_summary": thread_summary,
        "metadata": {
            "labels": payload.get("labels", []),
            "is_unread": payload.get("is_unread", False),
            "thread_message_count": payload.get("thread_message_count", 1),
            "reply_to": payload.get("reply_to_header", ""),
        },
        "workspace_slug": workspace_for_source(settings, source),
    }


def normalize_github_event(event: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Normalize a GitHub event for storage."""
    payload = event.get("payload", {})
    source = "github"

    event_type = payload.get("type", "notification")
    if "pull_request" in event_type.lower() or "pullrequest" in str(payload.get("subject", {})).lower():
        event_type = "pr"
    elif "issue" in event_type.lower():
        event_type = "issue"
    elif "workflow" in event_type.lower() or "check" in event_type.lower():
        event_type = "workflow"
    elif "review" in event_type.lower():
        event_type = "pr_review"

    subject = payload.get("subject", {})
    title = subject.get("title", "") if isinstance(subject, dict) else str(subject)

    # Check if user is mentioned or assigned
    reason = payload.get("reason", "")
    is_mention = reason in ("mention", "team_mention", "assign")
    is_directed = reason in ("assign", "review_requested", "author")
    requires_response = reason in ("assign", "review_requested", "mention")

    return {
        "id": str(uuid4()),
        "source": source,
        "event_type": event_type,
        "external_id": payload.get("id") or event.get("event_id"),
        "title": title,
        "body": _truncate(payload.get("body", "")),
        "snippet": _truncate(title, 200),
        "actor": payload.get("actor", ""),
        "actor_email": None,
        "recipients": [],
        "occurred_at": payload.get("updated_at") or event.get("event_ts"),
        "is_directed_to_user": is_directed,
        "is_mention": is_mention,
        "requires_response": requires_response,
        "metadata": {
            "repo": payload.get("repo", ""),
            "reason": reason,
            "url": payload.get("url", ""),
            "state": payload.get("state", ""),
        },
        "workspace_slug": workspace_for_source(settings, source),
    }


def normalize_calendar_event(event: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Normalize a Calendar event for storage."""
    payload = event.get("payload", {})
    source = "calendar"

    # Build attendees as recipients
    attendees = payload.get("attendees", [])
    recipients = []
    for att in attendees:
        if isinstance(att, dict):
            recipients.append({
                "email": att.get("email", ""),
                "name": att.get("displayName", ""),
                "type": "attendee",
                "status": att.get("responseStatus", ""),
            })
        elif isinstance(att, str):
            recipients.append({"email": att, "type": "attendee"})

    start = payload.get("start", {})
    start_time = start.get("dateTime") or start.get("date") if isinstance(start, dict) else start

    end = payload.get("end", {})
    end_time = end.get("dateTime") or end.get("date") if isinstance(end, dict) else end

    return {
        "id": str(uuid4()),
        "source": source,
        "event_type": "event",
        "external_id": payload.get("id") or event.get("event_id"),
        "title": payload.get("summary", "Untitled Event"),
        "body": _truncate(payload.get("description", "")),
        "snippet": payload.get("summary", ""),
        "actor": payload.get("organizer", {}).get("email") if isinstance(payload.get("organizer"), dict) else None,
        "actor_email": payload.get("organizer", {}).get("email") if isinstance(payload.get("organizer"), dict) else None,
        "recipients": recipients,
        "occurred_at": start_time or event.get("event_ts"),
        "due_at": end_time,
        "is_directed_to_user": True,  # All calendar events are relevant
        "is_mention": False,
        "requires_response": payload.get("responseStatus") == "needsAction",
        "metadata": {
            "location": payload.get("location", ""),
            "hangout_link": payload.get("hangoutLink", ""),
            "conference_data": payload.get("conferenceData"),
            "recurrence": payload.get("recurrence"),
            "status": payload.get("status", ""),
        },
        "workspace_slug": workspace_for_source(settings, source),
    }


def normalize_hedy_event(event: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Normalize a Hedy transcript event for storage."""
    payload = event.get("payload", {})
    source = "hedy"

    # Extract participants
    participants = payload.get("participants", [])
    recipients = []
    for p in participants:
        if isinstance(p, dict):
            recipients.append({
                "email": p.get("email", ""),
                "name": p.get("name", ""),
                "type": "participant",
            })
        elif isinstance(p, str):
            recipients.append({"name": p, "type": "participant"})

    # Get transcript summary or full text
    summary = payload.get("summary", "")
    transcript = payload.get("transcript", "")
    body = summary or transcript

    # Extract action items if present
    action_items = payload.get("action_items", [])
    extracted_tasks = []
    for item in action_items:
        if isinstance(item, dict):
            extracted_tasks.append({
                "task": item.get("text", item.get("description", "")),
                "assignee": item.get("assignee", ""),
                "due_date": item.get("due_date"),
            })
        elif isinstance(item, str):
            extracted_tasks.append({"task": item})

    return {
        "id": str(uuid4()),
        "source": source,
        "event_type": "transcript",
        "external_id": payload.get("id") or payload.get("meeting_id") or event.get("event_id"),
        "title": payload.get("title", "Meeting"),
        "body": _truncate(body, 3000),  # Allow longer for transcripts
        "snippet": _truncate(summary or body, 300),
        "actor": payload.get("organizer", ""),
        "actor_email": None,
        "recipients": recipients,
        "occurred_at": payload.get("date") or payload.get("started_at") or event.get("event_ts"),
        "due_at": None,
        "is_directed_to_user": True,
        "is_mention": False,
        "requires_response": len(extracted_tasks) > 0,
        "extracted_tasks": extracted_tasks,
        "metadata": {
            "duration_minutes": payload.get("duration_minutes"),
            "recording_url": payload.get("recording_url"),
            "keywords": payload.get("keywords", []),
        },
        "workspace_slug": workspace_for_source(settings, source),
    }


def _extract_email_address(sender: str) -> str | None:
    """Extract email address from sender string like 'Name <email@example.com>'."""
    if not sender:
        return None
    match = re.search(r"<([^>]+)>", sender)
    if match:
        return match.group(1).lower()
    if "@" in sender:
        return sender.strip().lower()
    return None


def normalize_event(source: str, event: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Normalize any event based on its source."""
    if source.startswith("gmail"):
        return normalize_gmail_event(event, settings)
    elif source == "github":
        return normalize_github_event(event, settings)
    elif source == "calendar":
        return normalize_calendar_event(event, settings)
    elif source == "hedy":
        return normalize_hedy_event(event, settings)
    else:
        # Generic fallback
        payload = event.get("payload", {})
        return {
            "id": str(uuid4()),
            "source": source,
            "event_type": "unknown",
            "external_id": event.get("event_id"),
            "title": payload.get("title", payload.get("subject", "Unknown")),
            "body": _truncate(str(payload)),
            "snippet": "",
            "actor": payload.get("sender", payload.get("actor", "")),
            "occurred_at": event.get("event_ts"),
            "workspace_slug": workspace_for_source(settings, source),
        }


def normalize_events(source: str, events: list[dict[str, Any]], settings: Settings) -> list[dict[str, Any]]:
    """Normalize a batch of events from a source."""
    normalized = []
    for event in events:
        try:
            normalized.append(normalize_event(source, event, settings))
        except Exception as e:
            # Log but don't fail the batch
            import logging
            logging.warning("Failed to normalize event from %s: %s", source, e)
    return normalized
