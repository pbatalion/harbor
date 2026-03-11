from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from src.intelligence.claude import ClaudeError, call_claude
from src.intelligence.prompts import SOURCE_SUMMARY_PROMPT, TRIAGE_PROMPT
from src.settings import Settings

logger = logging.getLogger(__name__)


def _heuristic_source_summary(source: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    summary = f"{source}: {len(items)} item(s)"
    urgent_items: list[str] = []

    for item in items[:20]:
        subject = str(item.get("subject") or item.get("summary") or item.get("title") or "")
        lowered = subject.lower()
        if "urgent" in lowered or "asap" in lowered or "blocker" in lowered:
            urgent_items.append(f"{source}: {subject}")

    draft_candidates = []
    draftable_items = items
    if source in {"gmail_work", "gmail_personal"}:
        draftable_items = [item for item in items if bool(item.get("is_actionable"))]

    for item in draftable_items[:3]:
        subject = str(item.get("subject") or item.get("summary") or item.get("title") or "No subject")
        recipient = str(item.get("sender") or item.get("repo") or "")
        draft_candidates.append(
            {
                "type": "follow_up",
                "context": f"Follow-up for {source} item: {subject}",
                "draft": f"Hi, quick follow-up on '{subject}'. I will review and respond shortly.",
                "to": recipient,
            }
        )

    return {
        "source": source,
        "summary": summary,
        "urgent_items": urgent_items,
        "important_items": [],
        "draft_candidates": draft_candidates,
    }


def _coerce_source_summary(source: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": str(payload.get("source", source)),
        "summary": str(payload.get("summary", "")),
        "urgent_items": [str(x) for x in payload.get("urgent_items", []) if isinstance(x, (str, int, float))],
        "important_items": [str(x) for x in payload.get("important_items", []) if isinstance(x, (str, int, float))],
        "draft_candidates": [
            {
                "type": str(item.get("type", "follow_up")),
                "context": str(item.get("context", "")),
                "draft": str(item.get("draft", "")),
                "to": str(item.get("to", "")),
            }
            for item in payload.get("draft_candidates", [])
            if isinstance(item, dict)
        ],
    }


def _coerce_aggregate_output(
    model_output: dict[str, Any], source_payloads: dict[str, list[dict[str, Any]]], source_summaries: list[dict[str, Any]]
) -> dict[str, Any]:
    urgent_items = model_output.get("urgent_items")
    if not isinstance(urgent_items, list):
        triage = model_output.get("triage", {})
        if isinstance(triage, dict):
            urgent_items = triage.get("urgent", [])
    if not isinstance(urgent_items, list):
        urgent_items = []

    day_plan = model_output.get("day_plan", "")
    if isinstance(day_plan, dict):
        blocks = day_plan.get("blocks", [])
        if isinstance(blocks, list) and blocks:
            lines = []
            for block in blocks:
                if isinstance(block, dict):
                    t = str(block.get("time", "")).strip()
                    a = str(block.get("action", "")).strip()
                    if t or a:
                        lines.append(f"{t} {a}".strip())
            day_plan = " | ".join(lines)
        else:
            day_plan = str(day_plan)
    elif not isinstance(day_plan, str):
        day_plan = str(day_plan)

    digest = model_output.get("email_digest", {})
    if not isinstance(digest, dict):
        digest = {}

    if not digest.get("summary"):
        digest["summary"] = "LLM-generated digest."
    digest.setdefault("work_emails", source_payloads.get("gmail_work", [])[:25])
    digest.setdefault("personal_emails", source_payloads.get("gmail_personal", [])[:25])
    digest.setdefault("github", source_payloads.get("github", [])[:25])
    digest.setdefault("transcript_summaries", source_payloads.get("hedy", [])[:25])
    if not isinstance(digest.get("draft_actions"), list):
        draft_actions: list[dict[str, Any]] = []
        for summary in source_summaries:
            draft_actions.extend(summary.get("draft_candidates", []))
        digest["draft_actions"] = draft_actions[:10]

    return {
        "urgent_items": [str(x) for x in urgent_items[:10]],
        "day_plan": day_plan,
        "email_digest": digest,
    }


def _truncate_for_llm(value: Any, max_len: int = 1200) -> Any:
    if isinstance(value, str):
        return value if len(value) <= max_len else f"{value[:max_len]}...[truncated]"
    if isinstance(value, list):
        return [_truncate_for_llm(item, max_len=max_len) for item in value]
    if isinstance(value, dict):
        return {key: _truncate_for_llm(item, max_len=max_len) for key, item in value.items()}
    return value


def summarize_each_source(settings: Settings, source_payloads: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []

    for source, items in source_payloads.items():
        max_items = 8 if source == "hedy" else 40
        compact_items = _truncate_for_llm(items[:max_items], max_len=1200)
        data = {"source": source, "items": compact_items, "generated_at": datetime.now(UTC).isoformat()}

        if settings.anthropic_api_key:
            try:
                summary = call_claude(
                    settings=settings,
                    system_prompt=SOURCE_SUMMARY_PROMPT,
                    data=data,
                    max_tokens=900,
                )
                summaries.append(_coerce_source_summary(source, summary))
                continue
            except Exception as exc:
                logger.warning("Source summarization fallback for %s: %s", source, exc)

        summaries.append(_heuristic_source_summary(source, items))

    return summaries


def aggregate_triage(
    settings: Settings,
    source_summaries: list[dict[str, Any]],
    source_payloads: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    payloads = source_payloads or {}
    payload = {
        "source_summaries": source_summaries,
        "current_time": datetime.now(UTC).isoformat(),
    }

    if settings.anthropic_api_key:
        try:
            model_output = call_claude(
                settings=settings,
                system_prompt=TRIAGE_PROMPT,
                data=payload,
                max_tokens=2600,
            )
            return _coerce_aggregate_output(model_output, payloads, source_summaries)
        except Exception as exc:
            logger.warning("Aggregate triage fallback due to Claude failure: %s", exc)

    urgent_items: list[str] = []
    draft_actions: list[dict[str, Any]] = []
    for summary in source_summaries:
        urgent_items.extend(summary.get("urgent_items", []))
        draft_actions.extend(summary.get("draft_candidates", []))

    return {
        "urgent_items": urgent_items[:10],
        "day_plan": "1) Resolve urgent items. 2) Process inbox and GitHub notifications. 3) Handle transcript follow-ups.",
        "email_digest": {
            "summary": "Heuristic aggregate summary (no LLM credentials configured).",
            "work_emails": [],
            "personal_emails": [],
            "github": [],
            "transcript_summaries": [],
            "draft_actions": draft_actions[:10],
        },
    }
