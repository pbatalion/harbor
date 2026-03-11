from __future__ import annotations

import os
import platform

from rq import Worker

from src.queue.connection import get_queue, get_redis
from src.settings import load_settings
from src.utils.logging import configure_logging


def main() -> None:
    if platform.system() == "Darwin":
        # Avoid macOS fork/ObjC crashes in child work-horse processes.
        os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")

    settings = load_settings()
    configure_logging(settings.app.log_level)

    redis_conn = get_redis(settings)
    queue = get_queue(settings)

    worker = Worker([queue], connection=redis_conn)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
