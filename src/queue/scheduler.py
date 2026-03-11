from __future__ import annotations

from rq_scheduler import Scheduler

from src.queue.connection import get_redis
from src.queue.jobs import enqueue_assistant_run
from src.settings import load_settings
from src.utils.logging import configure_logging


def bootstrap_schedule() -> None:
    settings = load_settings()
    configure_logging(settings.app.log_level)

    redis_conn = get_redis(settings)
    scheduler = Scheduler(queue_name=settings.app.queue_name, connection=redis_conn)

    existing = scheduler.get_jobs()
    for job in existing:
        if job.func_name.endswith("enqueue_assistant_run"):
            scheduler.cancel(job)

    for hour in settings.app.schedule_hours_local:
        cron = f"0 {hour} * * *"
        scheduler.cron(
            cron,
            func=enqueue_assistant_run,
            use_local_timezone=True,
            repeat=None,
        )


if __name__ == "__main__":
    bootstrap_schedule()
