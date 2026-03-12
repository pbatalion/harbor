from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from src.utils.timestamps import utcnow_iso


@contextmanager
def get_conn(db_path: str):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str) -> None:
    with get_conn(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                error TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS checkpoints (
                source TEXT PRIMARY KEY,
                high_watermark TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS source_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                source TEXT NOT NULL,
                event_id TEXT NOT NULL,
                event_ts TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(source, event_id)
            );

            CREATE TABLE IF NOT EXISTS drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                draft_type TEXT NOT NULL,
                context TEXT NOT NULL,
                draft TEXT NOT NULL,
                recipient TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS email_threads (
                thread_id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                last_subject TEXT,
                last_sender TEXT,
                last_updated_at TEXT NOT NULL
            );
            """
        )


def create_run(db_path: str, run_id: str) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO runs (run_id, status, created_at) VALUES (?, ?, ?)",
            (run_id, "running", utcnow_iso()),
        )


def complete_run(db_path: str, run_id: str) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            "UPDATE runs SET status = ?, completed_at = ? WHERE run_id = ?",
            ("completed", utcnow_iso(), run_id),
        )


def fail_run(db_path: str, run_id: str, error: str) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            "UPDATE runs SET status = ?, completed_at = ?, error = ? WHERE run_id = ?",
            ("failed", utcnow_iso(), error[:2000], run_id),
        )


def get_checkpoint(db_path: str, source: str) -> datetime | None:
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT high_watermark FROM checkpoints WHERE source = ?", (source,)
        ).fetchone()
    if not row:
        return None
    return datetime.fromisoformat(row["high_watermark"])


def set_checkpoint(db_path: str, source: str, high_watermark: datetime) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO checkpoints (source, high_watermark, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(source) DO UPDATE SET
                high_watermark = excluded.high_watermark,
                updated_at = excluded.updated_at
            """,
            (source, high_watermark.isoformat(), utcnow_iso()),
        )


def persist_source_events(db_path: str, run_id: str, source: str, events: list[dict[str, Any]]) -> int:
    written = 0
    with get_conn(db_path) as conn:
        for event in events:
            event_id = str(event["event_id"])
            event_ts = str(event["event_ts"])
            payload_json = json.dumps(event["payload"], separators=(",", ":"), ensure_ascii=True)
            try:
                conn.execute(
                    """
                    INSERT INTO source_events (run_id, source, event_id, event_ts, payload_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (run_id, source, event_id, event_ts, payload_json, utcnow_iso()),
                )
                written += 1
            except sqlite3.IntegrityError:
                continue
    return written


def load_run_events(db_path: str, run_id: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT source, payload_json FROM source_events WHERE run_id = ?", (run_id,)
        ).fetchall()

    for row in rows:
        grouped.setdefault(row["source"], []).append(json.loads(row["payload_json"]))
    return grouped


def load_recent_source_events(
    db_path: str, source: str, since: datetime, limit: int = 5000
) -> list[dict[str, Any]]:
    with get_conn(db_path) as conn:
        rows = conn.execute(
            """
            SELECT payload_json
            FROM source_events
            WHERE source = ? AND event_ts >= ?
            ORDER BY event_ts DESC, id DESC
            LIMIT ?
            """,
            (source, since.isoformat(), limit),
        ).fetchall()
    return [json.loads(row["payload_json"]) for row in rows]


def save_drafts(db_path: str, run_id: str, drafts: list[dict[str, Any]]) -> None:
    with get_conn(db_path) as conn:
        for draft in drafts:
            conn.execute(
                """
                INSERT INTO drafts (run_id, draft_type, context, draft, recipient, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    str(draft.get("type", "follow_up")),
                    str(draft.get("context", "")),
                    str(draft.get("draft", "")),
                    str(draft.get("to", "")),
                    "pending_review",
                    utcnow_iso(),
                ),
            )


def upsert_thread_state(
    db_path: str, thread_id: str, state: str, last_subject: str = "", last_sender: str = ""
) -> None:
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO email_threads (thread_id, state, last_subject, last_sender, last_updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(thread_id) DO UPDATE SET
                state = excluded.state,
                last_subject = excluded.last_subject,
                last_sender = excluded.last_sender,
                last_updated_at = excluded.last_updated_at
            """,
            (thread_id, state, last_subject, last_sender, utcnow_iso()),
        )
