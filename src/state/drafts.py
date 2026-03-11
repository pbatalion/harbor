from __future__ import annotations

from typing import Any

from src.state.db import save_drafts


def store_drafts(db_path: str, run_id: str, drafts: list[dict[str, Any]]) -> None:
    save_drafts(db_path, run_id, drafts)
