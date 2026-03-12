from __future__ import annotations

from datetime import UTC, datetime


def parse_iso(value: str) -> datetime:
    """Parse an ISO 8601 timestamp string to a timezone-aware datetime.

    Handles both 'Z' suffix and '+00:00' formats. Returns current UTC time
    if parsing fails.
    """
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except Exception:
        return datetime.now(UTC)


def utcnow_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).isoformat()
