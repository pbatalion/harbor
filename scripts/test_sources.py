from __future__ import annotations

from pprint import pprint

from src.settings import load_settings
from src.sources.calendar import fetch_calendar_events
from src.sources.github import fetch_github_events
from src.sources.gmail import fetch_gmail_events
from src.sources.hedy import fetch_hedy_events
from src.state.checkpoints import checkpoint_with_overlap
from src.state.db import init_db


def main() -> None:
    settings = load_settings()
    init_db(settings.database_path)

    since = checkpoint_with_overlap(settings.database_path, "gmail_work", settings.checkpoint_overlap_minutes)

    payloads = {
        "gmail_work": fetch_gmail_events(settings, account="work", since=since),
        "gmail_personal": fetch_gmail_events(settings, account="personal", since=since),
        "github": fetch_github_events(settings, since=since),
        "calendar": fetch_calendar_events(settings, since=since),
        "hedy": fetch_hedy_events(settings, since=since),
    }

    summary = {key: len(value) for key, value in payloads.items()}
    print("Source counts:")
    pprint(summary)

    print("\nExample payloads:")
    for key, values in payloads.items():
        print(f"\n[{key}]")
        pprint(values[:1])


if __name__ == "__main__":
    main()
