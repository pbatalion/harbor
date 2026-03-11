from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.state.db import get_checkpoint, set_checkpoint


def checkpoint_with_overlap(
    db_path: str, source: str, overlap_minutes: int, default_days_back: int = 2
) -> datetime:
    value = get_checkpoint(db_path, source)
    if value is None:
        return datetime.now(UTC) - timedelta(days=default_days_back)
    return value - timedelta(minutes=overlap_minutes)


def advance_checkpoint(db_path: str, source: str, high_watermark: datetime | None) -> None:
    if high_watermark is None:
        high_watermark = datetime.now(UTC)
    set_checkpoint(db_path, source, high_watermark)
