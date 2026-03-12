from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from rq import Retry

from src.delivery.email_digest import send_email_digest
from src.integrations.supabase import sync_run_snapshot
from src.delivery.sms import send_sms_alert
from src.intelligence.schema import deterministic_fallback_digest, validate_json_schema
from src.intelligence.triage import aggregate_triage, summarize_each_source
from src.privacy.redaction import redact_sensitive_payload
from src.queue.connection import get_queue
from src.settings import load_settings
from src.sources.calendar import fetch_calendar_events
from src.sources.github import fetch_github_events
from src.sources.gmail import fetch_gmail_events
from src.sources.hedy import fetch_hedy_events
from src.state.checkpoints import advance_checkpoint, checkpoint_with_overlap
from src.state.db import (
    complete_run,
    create_run,
    fail_run,
    init_db,
    load_recent_source_events,
    load_run_events,
    persist_source_events,
)
from src.state.drafts import store_drafts
from src.utils.filters import filter_noise_emails
from src.utils.timestamps import parse_iso

logger = logging.getLogger(__name__)


def _high_watermark(events: list[dict[str, Any]]) -> datetime | None:
    if not events:
        return None
    return max(parse_iso(str(event.get("event_ts", ""))) for event in events)


def _event_timestamp(event: dict[str, Any]) -> datetime:
    ts = str(event.get("timestamp") or event.get("event_ts") or "")
    if ts:
        return parse_iso(ts)
    return datetime.now(UTC)


def _pending_threads(emails: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    # Keep latest message per thread so digests focus on actionable threads, not every message.
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


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _extract_email(text: str) -> str:
    match = EMAIL_RE.search(text or "")
    return match.group(0).lower() if match else ""


def _allowed_email_reply_targets(grouped: dict[str, list[dict[str, Any]]]) -> set[str]:
    allowed: set[str] = set()
    for source in ("gmail_work", "gmail_personal"):
        for item in grouped.get(source, []):
            if not bool(item.get("is_actionable")):
                continue
            sender = str(item.get("sender", ""))
            sender_email = _extract_email(sender)
            if sender_email:
                allowed.add(sender_email)
    return allowed


def _filter_non_actionable_email_drafts(
    draft_actions: list[dict[str, Any]], allowed_reply_targets: set[str]
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for draft in draft_actions:
        draft_type = str(draft.get("type", "")).strip().lower()
        if draft_type != "email_reply":
            filtered.append(draft)
            continue
        target = _extract_email(str(draft.get("to", "")))
        if target and target in allowed_reply_targets:
            filtered.append(draft)
            continue
        logger.info("Dropping email draft not directed to user target=%s", target or "<none>")
    return filtered


def enqueue_assistant_run() -> str:
    settings = load_settings()
    init_db(settings.database_path)

    run_id = str(uuid.uuid4())
    create_run(settings.database_path, run_id)

    queue = get_queue(settings)
    retry = Retry(max=2, interval=[15, 45])

    deps = [
        queue.enqueue(fetch_gmail_work_job, run_id, retry=retry),
        queue.enqueue(fetch_gmail_personal_job, run_id, retry=retry),
        queue.enqueue(fetch_github_job, run_id, retry=retry),
        queue.enqueue(fetch_calendar_job, run_id, retry=retry),
        queue.enqueue(fetch_hedy_job, run_id, retry=retry),
    ]
    queue.enqueue(aggregate_and_deliver_job, run_id, depends_on=deps, retry=retry)

    logger.info("Enqueued assistant run_id=%s", run_id)
    return run_id


def fetch_gmail_work_job(run_id: str) -> dict[str, Any]:
    return _fetch_source_job(run_id, "gmail_work")


def fetch_gmail_personal_job(run_id: str) -> dict[str, Any]:
    return _fetch_source_job(run_id, "gmail_personal")


def fetch_github_job(run_id: str) -> dict[str, Any]:
    return _fetch_source_job(run_id, "github")


def fetch_calendar_job(run_id: str) -> dict[str, Any]:
    return _fetch_source_job(run_id, "calendar")


def fetch_hedy_job(run_id: str) -> dict[str, Any]:
    return _fetch_source_job(run_id, "hedy")


def _fetch_source_job(run_id: str, source: str) -> dict[str, Any]:
    settings = load_settings()

    source_enabled = {
        "gmail_work": settings.sources.gmail.enabled,
        "gmail_personal": settings.sources.gmail.enabled,
        "github": settings.sources.github.enabled,
        "calendar": settings.sources.calendar.enabled,
        "hedy": settings.sources.hedy.enabled,
    }.get(source, True)

    if not source_enabled:
        logger.info("Skipping disabled source=%s run_id=%s", source, run_id)
        return {"source": source, "events": 0, "written": 0, "error": "disabled"}

    since = checkpoint_with_overlap(
        settings.database_path,
        source,
        overlap_minutes=settings.checkpoint_overlap_minutes,
        settings=settings,
    )

    try:
        if source == "gmail_work":
            events = fetch_gmail_events(settings, account="work", since=since)
        elif source == "gmail_personal":
            events = fetch_gmail_events(settings, account="personal", since=since)
        elif source == "github":
            events = fetch_github_events(settings, since=since)
        elif source == "calendar":
            events = fetch_calendar_events(settings, since=since)
        elif source == "hedy":
            events = fetch_hedy_events(settings, since=since)
        else:
            events = []

        written = persist_source_events(settings.database_path, run_id, source, events)
        advance_checkpoint(settings.database_path, source, _high_watermark(events), settings=settings)
        logger.info("Fetched source=%s run_id=%s events=%s written=%s", source, run_id, len(events), written)
        return {"source": source, "events": len(events), "written": written, "error": ""}
    except Exception as exc:
        logger.exception("Source fetch failed source=%s run_id=%s", source, run_id)
        # Keep run moving for partial-success delivery.
        advance_checkpoint(settings.database_path, source, None, settings=settings)
        return {"source": source, "events": 0, "written": 0, "error": str(exc)}


def aggregate_and_deliver_job(run_id: str) -> dict[str, Any]:
    settings = load_settings()

    try:
        grouped = load_run_events(settings.database_path, run_id)
        lookback_since = datetime.now(UTC) - timedelta(days=settings.lookback_days)

        # Use 30-day lookback for actionable email threads, not just newly persisted messages.
        grouped["gmail_work"] = load_recent_source_events(
            settings.database_path, "gmail_work", since=lookback_since
        )
        grouped["gmail_personal"] = load_recent_source_events(
            settings.database_path, "gmail_personal", since=lookback_since
        )

        grouped["gmail_work"] = filter_noise_emails(
            grouped.get("gmail_work", []),
            settings.filters.email_noise_senders,
            settings.filters.email_noise_subject_keywords,
        )
        grouped["gmail_personal"] = filter_noise_emails(
            grouped.get("gmail_personal", []),
            settings.filters.email_noise_senders,
            settings.filters.email_noise_subject_keywords,
        )

        grouped["gmail_work"] = _pending_threads(
            grouped.get("gmail_work", []), settings.gmail_pending_thread_limit
        )
        grouped["gmail_personal"] = _pending_threads(
            grouped.get("gmail_personal", []), settings.gmail_pending_thread_limit
        )

        if settings.redaction.enabled:
            redacted = redact_sensitive_payload(
                grouped,
                custom_terms=settings.redaction.custom_sensitive_terms,
            )
        else:
            redacted = grouped

        try:
            source_summaries = summarize_each_source(settings, redacted)
            raw_analysis = aggregate_triage(settings, source_summaries, grouped)
        except Exception:
            logger.exception("LLM pipeline failed; falling back to deterministic digest run_id=%s", run_id)
            raw_analysis = deterministic_fallback_digest(grouped)

        digest = raw_analysis.get("email_digest", {})
        digest.setdefault("work_emails", grouped.get("gmail_work", [])[:25])
        digest.setdefault("personal_emails", grouped.get("gmail_personal", [])[:25])
        digest.setdefault("github", grouped.get("github", [])[:25])
        digest.setdefault("transcript_summaries", grouped.get("hedy", [])[:25])
        raw_analysis["email_digest"] = digest

        validation = validate_json_schema(raw_analysis)
        analysis = validation.data if validation.valid else deterministic_fallback_digest(grouped)

        allowed_reply_targets = _allowed_email_reply_targets(grouped)
        draft_actions = analysis.get("email_digest", {}).get("draft_actions", [])
        analysis["email_digest"]["draft_actions"] = _filter_non_actionable_email_drafts(
            draft_actions, allowed_reply_targets
        )

        sms_sent = send_sms_alert(settings, analysis.get("urgent_items", []))
        digest_location = send_email_digest(settings, analysis, run_id)
        store_drafts(settings.database_path, run_id, analysis.get("email_digest", {}).get("draft_actions", []))
        try:
            sync_run_snapshot(
                settings,
                run_id=run_id,
                grouped=grouped,
                analysis=analysis,
                digest_location=digest_location,
            )
        except Exception:
            logger.exception("Supabase sync failed run_id=%s", run_id)

        complete_run(settings.database_path, run_id)
        logger.info(
            "Run complete run_id=%s sms_sent=%s digest=%s",
            run_id,
            sms_sent,
            digest_location,
        )
        return {
            "run_id": run_id,
            "sms_sent": sms_sent,
            "digest_location": digest_location,
            "schema_valid": validation.valid,
        }
    except Exception as exc:
        fail_run(settings.database_path, run_id, str(exc))
        logger.exception("Run failed run_id=%s", run_id)
        raise
