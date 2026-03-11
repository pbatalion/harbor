from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from src.state.db import load_recent_source_events, load_run_events
from src.utils.filters import filter_noise_emails


def _parse_iso(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except Exception:
        return datetime.min.replace(tzinfo=UTC)


def _latest_completed_run_id(db_path: str) -> str:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT run_id
            FROM runs
            WHERE status = 'completed'
            ORDER BY completed_at DESC
            LIMIT 1
            """
        ).fetchone()
    finally:
        conn.close()
    return str(row[0]) if row else ""


def _load_run_drafts(db_path: str, run_id: str) -> list[dict[str, str]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT draft_type, recipient, context, draft, status
            FROM drafts
            WHERE run_id = ?
            ORDER BY id ASC
            """,
            (run_id,),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "type": str(row["draft_type"]),
            "to": str(row["recipient"] or ""),
            "context": str(row["context"]),
            "draft": str(row["draft"]),
            "status": str(row["status"]),
        }
        for row in rows
    ]


def _actionable_threads(
    grouped: dict[str, list[dict[str, Any]]], limit: int
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in ("gmail_work", "gmail_personal"):
        for item in grouped.get(source, []):
            if not bool(item.get("is_actionable")):
                continue
            rows.append(
                {
                    "source": source,
                    "timestamp": str(item.get("timestamp", "")),
                    "sender": str(item.get("sender", "")),
                    "subject": str(item.get("subject", "")),
                    "thread_id": str(item.get("thread_id", "")),
                    "is_unread": bool(item.get("is_unread")),
                    "thread_message_count": int(item.get("thread_message_count", 0) or 0),
                }
            )
    rows.sort(key=lambda row: _parse_iso(row["timestamp"]), reverse=True)
    return rows[:limit]


def _event_timestamp(event: dict[str, Any]) -> datetime:
    return _parse_iso(str(event.get("timestamp", "")))


def _pending_threads(emails: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    ordered = sorted(emails, key=_event_timestamp, reverse=True)
    selected: list[dict[str, Any]] = []
    seen_threads: set[str] = set()
    for email in ordered:
        thread_id = str(email.get("thread_id") or email.get("message_id") or "")
        if not thread_id or thread_id in seen_threads:
            continue
        seen_threads.add(thread_id)
        selected.append(email)
        if len(selected) >= limit:
            break
    return selected


def build_follow_through_snapshot(
    db_path: str,
    *,
    run_id: str = "",
    lookback_days: int = 30,
    actionable_limit: int = 20,
    noise_senders: list[str] | None = None,
    noise_subject_keywords: list[str] | None = None,
    pending_thread_limit: int = 200,
) -> dict[str, Any]:
    selected_run_id = run_id or _latest_completed_run_id(db_path)
    if not selected_run_id:
        return {
            "run_id": "",
            "source_counts": {},
            "actionable_threads": [],
            "drafts": [],
        }

    grouped = load_run_events(db_path, selected_run_id)
    lookback_since = datetime.now(UTC) - timedelta(days=lookback_days)
    grouped["gmail_work"] = load_recent_source_events(db_path, "gmail_work", since=lookback_since)
    grouped["gmail_personal"] = load_recent_source_events(db_path, "gmail_personal", since=lookback_since)
    source_counts = {source: len(items) for source, items in grouped.items()}
    sender_rules = noise_senders or []
    subject_rules = noise_subject_keywords or []

    grouped["gmail_work"] = _pending_threads(
        filter_noise_emails(grouped.get("gmail_work", []), sender_rules, subject_rules),
        pending_thread_limit,
    )
    grouped["gmail_personal"] = _pending_threads(
        filter_noise_emails(grouped.get("gmail_personal", []), sender_rules, subject_rules),
        pending_thread_limit,
    )

    return {
        "run_id": selected_run_id,
        "source_counts": source_counts,
        "actionable_threads": _actionable_threads(grouped, actionable_limit),
        "drafts": _load_run_drafts(db_path, selected_run_id),
    }


def render_follow_through_report(snapshot: dict[str, Any]) -> str:
    run_id = str(snapshot.get("run_id", ""))
    if not run_id:
        return "No completed runs found."

    lines = [f"Run: {run_id}", ""]

    lines.append("Source Counts:")
    source_counts = snapshot.get("source_counts", {})
    if source_counts:
        for source in sorted(source_counts.keys()):
            lines.append(f"- {source}: {source_counts[source]}")
    else:
        lines.append("- none")
    lines.append("")

    lines.append("Actionable Email Threads:")
    actionable = snapshot.get("actionable_threads", [])
    if actionable:
        for row in actionable:
            unread = "unread" if row["is_unread"] else "read"
            lines.append(
                f"- [{row['source']}] {row['subject']} | from {row['sender']} | "
                f"{unread} | msgs={row['thread_message_count']} | {row['timestamp']}"
            )
    else:
        lines.append("- none")
    lines.append("")

    lines.append("Draft Actions:")
    drafts = snapshot.get("drafts", [])
    if drafts:
        for draft in drafts:
            lines.append(f"- [{draft['type']}] to={draft['to']} | {draft['context']}")
    else:
        lines.append("- none")

    return "\n".join(lines)
