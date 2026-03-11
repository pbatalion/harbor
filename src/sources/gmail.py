from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from email.utils import getaddresses, parsedate_to_datetime
from typing import Any

import requests

from src.settings import Settings
from src.utils.auth import AuthError, get_google_access_token

logger = logging.getLogger(__name__)
_GMAIL_METADATA_HEADERS = ["From", "Subject", "Date", "To", "Cc", "Reply-To"]


def _header_value(headers: list[dict[str, str]], name: str) -> str:
    lowered = name.lower()
    for header in headers:
        if header.get("name", "").lower() == lowered:
            return header.get("value", "")
    return ""


def _parse_gmail_timestamp(internal_date_ms: str) -> datetime:
    try:
        return datetime.fromtimestamp(int(internal_date_ms) / 1000, tz=UTC)
    except Exception:
        return datetime.now(UTC)


def _to_iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _extract_email_addresses(value: str) -> list[str]:
    if not value:
        return []
    parsed = getaddresses([value])
    emails: list[str] = []
    for _, addr in parsed:
        addr = addr.strip().lower()
        if addr:
            emails.append(addr)
    return emails


def _parse_iso(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except Exception:
        return datetime.now(UTC)


def _parse_message_timestamp(data: dict[str, Any], headers: list[dict[str, str]]) -> datetime:
    ts = _parse_gmail_timestamp(str(data.get("internalDate", "0")))
    date_header = _header_value(headers, "Date")
    if not date_header:
        return ts
    try:
        return parsedate_to_datetime(date_header).astimezone(UTC)
    except Exception:
        return ts


def _thread_message_summary(data: dict[str, Any], account_email: str) -> dict[str, Any]:
    payload = data.get("payload", {})
    headers = payload.get("headers", [])
    ts = _parse_message_timestamp(data, headers)

    sender = _header_value(headers, "From")
    subject = _header_value(headers, "Subject")
    to_header = _header_value(headers, "To")
    cc_header = _header_value(headers, "Cc")
    reply_to_header = _header_value(headers, "Reply-To")
    labels = data.get("labelIds", [])

    to_recipients = _extract_email_addresses(to_header)
    cc_recipients = _extract_email_addresses(cc_header)
    directed_to_user = bool(account_email and account_email in to_recipients)
    cc_only_for_user = bool(account_email and account_email in cc_recipients and not directed_to_user)

    return {
        "message_id": str(data.get("id", "")),
        "sender": sender,
        "subject": subject,
        "snippet": str(data.get("snippet", "")),
        "to_header": to_header,
        "cc_header": cc_header,
        "reply_to_header": reply_to_header,
        "to_recipients": to_recipients,
        "cc_recipients": cc_recipients,
        "labels": labels,
        "is_unread": "UNREAD" in labels,
        "directed_to_user": directed_to_user,
        "cc_only_for_user": cc_only_for_user,
        "is_actionable": directed_to_user,
        "timestamp": _to_iso(ts),
    }


def _mock_events(account: str, since: datetime) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    event_id = f"mock-gmail-{account}-{int(now.timestamp())}"
    return [
        {
            "event_id": event_id,
            "event_ts": _to_iso(now),
            "payload": {
                "source": f"gmail_{account}",
                "message_id": event_id,
                "thread_id": f"mock-thread-{account}",
                "sender": "teammate@example.com",
                "subject": f"[{account}] Mock action needed",
                "snippet": "Need your review on migration plan by end of day.",
                "to_header": "",
                "cc_header": "",
                "reply_to_header": "",
                "to_recipients": [],
                "cc_recipients": [],
                "account_email": "",
                "directed_to_user": False,
                "cc_only_for_user": False,
                "is_actionable": False,
                "labels": ["INBOX", "UNREAD"],
                "is_unread": True,
                "thread_message_count": 1,
                "thread_context": [],
                "timestamp": _to_iso(now),
                "since": _to_iso(since),
            },
        }
    ]


def fetch_gmail_events(settings: Settings, account: str, since: datetime) -> list[dict[str, Any]]:
    refresh_token = (
        settings.google_refresh_token_work
        if account == "work"
        else settings.google_refresh_token_personal
    )
    if not (settings.google_client_id and settings.google_client_secret and refresh_token):
        return _mock_events(account, since) if settings.seed_mock_data_if_empty else []

    try:
        access_token = get_google_access_token(
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            refresh_token=refresh_token,
        )
    except AuthError as exc:
        logger.warning("Gmail auth failed account=%s error=%s", account, exc)
        return []

    headers = {"Authorization": f"Bearer {access_token}"}
    account_email = ""
    profile_resp = requests.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/profile",
        headers=headers,
        timeout=20,
    )
    if profile_resp.status_code == 200:
        account_email = str(profile_resp.json().get("emailAddress", "")).strip().lower()

    lookback_since = datetime.now(UTC) - timedelta(days=settings.lookback_days)
    query_since = min(since, lookback_since)
    query = f"label:inbox after:{int(query_since.timestamp())}"

    thread_ids: list[str] = []
    seen_thread_ids: set[str] = set()
    page_token: str | None = None
    for _ in range(settings.gmail_max_pages):
        params: dict[str, Any] = {"q": query, "maxResults": settings.gmail_page_size}
        if page_token:
            params["pageToken"] = page_token
        list_resp = requests.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/threads",
            headers=headers,
            params=params,
            timeout=20,
        )
        if list_resp.status_code != 200:
            logger.warning(
                "Gmail list request failed account=%s status=%s body=%s",
                account,
                list_resp.status_code,
                list_resp.text[:300],
            )
            return []

        body = list_resp.json()
        for thread in body.get("threads", []):
            thread_id = str(thread.get("id", "")).strip()
            if not thread_id or thread_id in seen_thread_ids:
                continue
            seen_thread_ids.add(thread_id)
            thread_ids.append(thread_id)
        page_token = body.get("nextPageToken")
        if not page_token:
            break

    events: list[dict[str, Any]] = []

    for thread_id in thread_ids:
        detail_resp = requests.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/threads/{thread_id}",
            headers=headers,
            params={
                "format": "metadata",
                "metadataHeaders": _GMAIL_METADATA_HEADERS,
            },
            timeout=20,
        )
        if detail_resp.status_code != 200:
            continue
        data = detail_resp.json()
        raw_messages = [msg for msg in data.get("messages", []) if isinstance(msg, dict)]
        if not raw_messages:
            continue

        thread_messages = [_thread_message_summary(msg, account_email) for msg in raw_messages]
        thread_messages.sort(key=lambda message: _parse_iso(str(message.get("timestamp", ""))))

        context_max = settings.gmail_thread_context_max_messages
        if context_max > 0:
            thread_context = thread_messages[-context_max:]
        else:
            thread_context = thread_messages

        latest = thread_messages[-1]
        message_id = str(latest.get("message_id", "")).strip() or thread_id
        event_ts = str(latest.get("timestamp", _to_iso(datetime.now(UTC))))

        events.append(
            {
                "event_id": f"gmail-thread:{message_id}",
                "event_ts": event_ts,
                "payload": {
                    "source": f"gmail_{account}",
                    "message_id": message_id,
                    "thread_id": thread_id,
                    "sender": str(latest.get("sender", "")),
                    "subject": str(latest.get("subject", "")),
                    "snippet": str(latest.get("snippet", "")),
                    "to_header": str(latest.get("to_header", "")),
                    "cc_header": str(latest.get("cc_header", "")),
                    "reply_to_header": str(latest.get("reply_to_header", "")),
                    "to_recipients": latest.get("to_recipients", []),
                    "cc_recipients": latest.get("cc_recipients", []),
                    "account_email": account_email,
                    "directed_to_user": bool(latest.get("directed_to_user")),
                    "cc_only_for_user": bool(latest.get("cc_only_for_user")),
                    "is_actionable": bool(latest.get("is_actionable")),
                    "labels": latest.get("labels", []),
                    "is_unread": bool(latest.get("is_unread")),
                    "thread_message_count": len(thread_messages),
                    "thread_context": thread_context,
                    "timestamp": event_ts,
                },
            }
        )

    return events
