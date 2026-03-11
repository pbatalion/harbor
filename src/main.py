from __future__ import annotations

import argparse

from src.queue.jobs import enqueue_assistant_run
from src.queue.scheduler import bootstrap_schedule
from src.reporting.follow_through import build_follow_through_snapshot, render_follow_through_report
from src.settings import load_settings
from src.state.db import init_db
from src.utils.logging import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="AI assistant control CLI")
    parser.add_argument(
        "command",
        choices=["init-db", "enqueue-once", "bootstrap-schedule", "report-follow-through"],
        help="Command to run",
    )
    parser.add_argument("--run-id", default="", help="Optional run_id for report-follow-through")
    parser.add_argument(
        "--actionable-limit",
        type=int,
        default=20,
        help="Max actionable email threads to show in report-follow-through",
    )
    args = parser.parse_args()

    settings = load_settings()
    configure_logging(settings.app.log_level)

    if args.command == "init-db":
        init_db(settings.database_path)
        return

    if args.command == "bootstrap-schedule":
        bootstrap_schedule()
        return

    if args.command == "enqueue-once":
        init_db(settings.database_path)
        enqueue_assistant_run()
        return

    if args.command == "report-follow-through":
        snapshot = build_follow_through_snapshot(
            settings.database_path,
            run_id=args.run_id,
            lookback_days=settings.lookback_days,
            actionable_limit=max(1, args.actionable_limit),
            noise_senders=settings.filters.email_noise_senders,
            noise_subject_keywords=settings.filters.email_noise_subject_keywords,
            pending_thread_limit=settings.gmail_pending_thread_limit,
        )
        print(render_follow_through_report(snapshot))
        return


if __name__ == "__main__":
    main()
