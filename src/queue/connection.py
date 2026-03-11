from __future__ import annotations

from redis import Redis
from rq import Queue

from src.settings import Settings


def get_redis(settings: Settings) -> Redis:
    return Redis.from_url(settings.redis_url)


def get_queue(settings: Settings) -> Queue:
    return Queue(name=settings.app.queue_name, connection=get_redis(settings), default_timeout=600)
