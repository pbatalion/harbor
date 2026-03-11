from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class DraftAction(BaseModel):
    type: str
    context: str
    draft: str
    to: str


class EmailDigest(BaseModel):
    summary: str
    work_emails: list[dict[str, Any]]
    personal_emails: list[dict[str, Any]]
    github: list[dict[str, Any]]
    transcript_summaries: list[dict[str, Any]]
    draft_actions: list[DraftAction]


class TriageOutput(BaseModel):
    urgent_items: list[str]
    day_plan: str
    email_digest: EmailDigest


@dataclass
class ValidationResult:
    valid: bool
    data: dict[str, Any]
    error: str = ""


def validate_json_schema(payload: dict[str, Any]) -> ValidationResult:
    try:
        parsed = TriageOutput.model_validate(payload)
        return ValidationResult(valid=True, data=parsed.model_dump())
    except ValidationError as exc:
        return ValidationResult(valid=False, data={}, error=str(exc))


def deterministic_fallback_digest(source_payloads: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    work_emails = source_payloads.get("gmail_work", [])
    personal_emails = source_payloads.get("gmail_personal", [])
    github_items = source_payloads.get("github", [])
    transcript_items = source_payloads.get("hedy", [])

    urgent = []
    for email in work_emails[:10]:
        subject = str(email.get("subject", "")).lower()
        if "urgent" in subject or "asap" in subject:
            urgent.append(f"Work email: {email.get('subject', 'No subject')}")

    return {
        "urgent_items": urgent,
        "day_plan": "1) Handle urgent items first. 2) Clear high-priority inbox and PR reviews. 3) Follow up on transcript action items.",
        "email_digest": {
            "summary": f"Fallback digest generated with {len(work_emails)} work emails, {len(personal_emails)} personal emails, {len(github_items)} GitHub items, and {len(transcript_items)} transcripts.",
            "work_emails": work_emails[:20],
            "personal_emails": personal_emails[:20],
            "github": github_items[:20],
            "transcript_summaries": transcript_items[:20],
            "draft_actions": [],
        },
    }
