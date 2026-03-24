"""
Enhanced triage system that reads from stored source events.
Provides smarter analysis with cross-source intelligence.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from src.intelligence.claude import call_claude
from src.intelligence.storage import (
    get_events_requiring_response,
    load_source_events_for_triage,
)
from src.settings import Settings

logger = logging.getLogger(__name__)


ENHANCED_TRIAGE_PROMPT = """
You are Harbor, Phil's intelligent operations assistant. You have access to normalized events from Gmail, GitHub, Calendar, and meeting transcripts (Hedy).

Your job is to:
1. Identify what genuinely needs Phil's attention TODAY
2. Extract concrete tasks and deadlines from all sources
3. Spot patterns and connections across sources
4. Prioritize ruthlessly - Phil is busy

Analyze the provided events and return a JSON response with this exact structure:

{
  "urgent_items": [
    {
      "title": "Brief description",
      "source": "gmail_work|github|calendar|hedy",
      "reason": "Why this is urgent",
      "action": "What Phil should do"
    }
  ],
  "tasks_extracted": [
    {
      "task": "Specific actionable task",
      "source": "Where this came from",
      "due_date": "YYYY-MM-DD or null",
      "priority": "high|medium|low",
      "context": "Brief context"
    }
  ],
  "needs_response": [
    {
      "event_id": "ID of the event",
      "title": "Subject/title",
      "from": "Who it's from",
      "suggested_response": "Brief draft response",
      "tone": "formal|casual|urgent"
    }
  ],
  "day_plan": "One paragraph: What Phil should focus on today based on this data",
  "cross_source_insights": [
    "Pattern or connection noticed across multiple sources"
  ]
}

Rules:
- Be specific and actionable, not vague
- Tasks from meeting transcripts are often buried - extract them carefully
- Look for deadlines mentioned in emails AND calendar
- GitHub review requests from colleagues are usually high priority
- If an email thread has been going >3 messages, it probably needs attention
- Calendar events starting within 2 hours should be flagged
- Connect the dots: "This email mentions the same project as this GitHub PR"
""".strip()


DRAFT_GENERATION_PROMPT = """
You are writing email/message drafts on behalf of Phil. You have the full context of each conversation.

For each item requiring a response, generate a professional, concise reply.

Guidelines:
- Match the tone of the original message
- Be helpful and clear
- Keep responses focused and not overly long
- If declining or deferring, be polite but firm
- Include specific details from the original when relevant
- Never make commitments Phil hasn't authorized

Return JSON:
{
  "drafts": [
    {
      "event_id": "ID of source event",
      "draft_type": "email_reply|github_comment|follow_up",
      "recipient": "Email or username",
      "subject": "Re: Original subject",
      "draft": "The actual draft text",
      "context": "Why you drafted this response"
    }
  ]
}
""".strip()


def build_triage_context(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a structured context object for the LLM."""
    # Group events by source
    by_source: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        source = event.get("source", "unknown")
        if source not in by_source:
            by_source[source] = []
        by_source[source].append({
            "id": event.get("id"),
            "type": event.get("event_type"),
            "title": event.get("title"),
            "snippet": event.get("snippet") or event.get("body", "")[:300],
            "from": event.get("actor"),
            "occurred_at": event.get("occurred_at"),
            "requires_response": event.get("requires_response"),
            "is_directed_to_user": event.get("is_directed_to_user"),
            "thread_summary": event.get("thread_summary"),
        })

    # Calculate stats
    total = len(events)
    needs_response = sum(1 for e in events if e.get("requires_response"))
    directed = sum(1 for e in events if e.get("is_directed_to_user"))

    return {
        "current_time": datetime.now(UTC).isoformat(),
        "summary": {
            "total_events": total,
            "needs_response": needs_response,
            "directed_to_user": directed,
            "sources": list(by_source.keys()),
        },
        "events_by_source": by_source,
    }


def build_draft_context(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Build context for draft generation."""
    items = []
    for event in events:
        items.append({
            "id": event.get("id"),
            "source": event.get("source"),
            "type": event.get("event_type"),
            "title": event.get("title"),
            "body": event.get("body"),
            "from": event.get("actor"),
            "from_email": event.get("actor_email"),
            "recipients": event.get("recipients", []),
            "thread_summary": event.get("thread_summary"),
            "metadata": event.get("metadata", {}),
        })

    return {
        "current_time": datetime.now(UTC).isoformat(),
        "items_requiring_response": items,
    }


def run_enhanced_triage(
    settings: Settings,
    run_id: str,
) -> dict[str, Any]:
    """
    Run enhanced triage on stored source events.
    Returns structured triage results.
    """
    # Load events from storage
    events = load_source_events_for_triage(settings, run_id, limit=80)

    if not events:
        logger.warning("No events found for triage in run %s", run_id[:8])
        return _empty_triage_result()

    # Build context for LLM
    context = build_triage_context(events)

    # Run triage
    if settings.anthropic_api_key:
        try:
            result = call_claude(
                settings=settings,
                system_prompt=ENHANCED_TRIAGE_PROMPT,
                data=context,
                max_tokens=2000,
            )
            return _coerce_triage_result(result)
        except Exception as e:
            logger.error("Enhanced triage failed: %s", e)

    # Fallback to heuristic triage
    return _heuristic_triage(events)


def generate_drafts(
    settings: Settings,
    run_id: str,
) -> list[dict[str, Any]]:
    """
    Generate response drafts for events requiring replies.
    """
    events = get_events_requiring_response(settings, run_id)

    if not events:
        return []

    # Limit to most important
    events = events[:10]

    context = build_draft_context(events)

    if settings.anthropic_api_key:
        try:
            result = call_claude(
                settings=settings,
                system_prompt=DRAFT_GENERATION_PROMPT,
                data=context,
                max_tokens=2500,
            )
            drafts = result.get("drafts", [])
            return [_coerce_draft(d) for d in drafts if isinstance(d, dict)]
        except Exception as e:
            logger.error("Draft generation failed: %s", e)

    # Fallback to simple drafts
    return _heuristic_drafts(events)


def _empty_triage_result() -> dict[str, Any]:
    return {
        "urgent_items": [],
        "tasks_extracted": [],
        "needs_response": [],
        "day_plan": "No events to analyze.",
        "cross_source_insights": [],
    }


def _coerce_triage_result(result: dict[str, Any]) -> dict[str, Any]:
    """Ensure triage result has expected structure."""
    return {
        "urgent_items": [
            {
                "title": str(item.get("title", "")),
                "source": str(item.get("source", "")),
                "reason": str(item.get("reason", "")),
                "action": str(item.get("action", "")),
            }
            for item in result.get("urgent_items", [])
            if isinstance(item, dict)
        ],
        "tasks_extracted": [
            {
                "task": str(task.get("task", "")),
                "source": str(task.get("source", "")),
                "due_date": task.get("due_date"),
                "priority": str(task.get("priority", "medium")),
                "context": str(task.get("context", "")),
            }
            for task in result.get("tasks_extracted", [])
            if isinstance(task, dict)
        ],
        "needs_response": result.get("needs_response", []),
        "day_plan": str(result.get("day_plan", "")),
        "cross_source_insights": [
            str(i) for i in result.get("cross_source_insights", [])
            if isinstance(i, str)
        ],
    }


def _coerce_draft(draft: dict[str, Any]) -> dict[str, Any]:
    """Ensure draft has expected structure."""
    return {
        "event_id": str(draft.get("event_id", "")),
        "draft_type": str(draft.get("draft_type", "follow_up")),
        "recipient": str(draft.get("recipient", "")),
        "subject": str(draft.get("subject", "")),
        "draft": str(draft.get("draft", "")),
        "context": str(draft.get("context", "")),
    }


def _heuristic_triage(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Fallback triage without LLM."""
    urgent = []
    tasks = []

    for event in events:
        title = event.get("title", "").lower()
        if any(word in title for word in ["urgent", "asap", "blocker", "critical"]):
            urgent.append({
                "title": event.get("title"),
                "source": event.get("source"),
                "reason": "Contains urgency keywords",
                "action": "Review and respond",
            })

        # Extract tasks from transcripts
        for task in event.get("extracted_tasks", []):
            tasks.append({
                "task": task.get("task", ""),
                "source": event.get("source"),
                "due_date": task.get("due_date"),
                "priority": task.get("priority", "medium"),
                "context": f"From: {event.get('title')}",
            })

    needs_response = sum(1 for e in events if e.get("requires_response"))

    return {
        "urgent_items": urgent[:5],
        "tasks_extracted": tasks[:10],
        "needs_response": [],
        "day_plan": f"Review {needs_response} items requiring response. Check {len(urgent)} urgent items first.",
        "cross_source_insights": [],
    }


def _heuristic_drafts(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate simple draft templates without LLM."""
    drafts = []

    for event in events[:5]:
        source = event.get("source", "")
        title = event.get("title", "No subject")

        if source.startswith("gmail"):
            drafts.append({
                "event_id": event.get("id", ""),
                "draft_type": "email_reply",
                "recipient": event.get("actor_email") or event.get("actor", ""),
                "subject": f"Re: {title}",
                "draft": f"Hi,\n\nThank you for your message regarding \"{title}\". I'll review this and get back to you shortly.\n\nBest regards",
                "context": f"Auto-generated reply template for: {title}",
            })
        elif source == "github":
            drafts.append({
                "event_id": event.get("id", ""),
                "draft_type": "github_comment",
                "recipient": event.get("actor", ""),
                "subject": title,
                "draft": "Thanks for flagging this. I'll take a look and follow up.",
                "context": f"Auto-generated GitHub response for: {title}",
            })

    return drafts
