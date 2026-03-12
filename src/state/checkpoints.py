from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from src.integrations.supabase import get_supabase_checkpoint, set_supabase_checkpoint
from src.settings import Settings
from src.state.db import get_checkpoint as get_sqlite_checkpoint
from src.state.db import set_checkpoint as set_sqlite_checkpoint

logger = logging.getLogger(__name__)


def checkpoint_with_overlap(
    db_path: str,
    source: str,
    overlap_minutes: int,
    default_days_back: int = 2,
    settings: Settings | None = None,
) -> datetime:
    """Get checkpoint with overlap for source ingestion.

    Tries Supabase first if settings provided, falls back to SQLite.
    """
    value = None

    # Try Supabase first
    if settings:
        value = get_supabase_checkpoint(settings, source)
        if value:
            logger.debug("Got checkpoint from Supabase for source=%s", source)

    # Fall back to SQLite
    if value is None:
        value = get_sqlite_checkpoint(db_path, source)
        if value:
            logger.debug("Got checkpoint from SQLite for source=%s", source)

    if value is None:
        return datetime.now(UTC) - timedelta(days=default_days_back)

    return value - timedelta(minutes=overlap_minutes)


def advance_checkpoint(
    db_path: str,
    source: str,
    high_watermark: datetime | None,
    settings: Settings | None = None,
) -> None:
    """Advance checkpoint for a source.

    Writes to both Supabase (if configured) and SQLite for redundancy.
    """
    if high_watermark is None:
        high_watermark = datetime.now(UTC)

    # Try Supabase first
    if settings:
        if set_supabase_checkpoint(settings, source, high_watermark):
            logger.debug("Set checkpoint in Supabase for source=%s", source)

    # Always write to SQLite as backup
    set_sqlite_checkpoint(db_path, source, high_watermark)
