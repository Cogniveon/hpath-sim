"""Defines a redis worker for the histopathology simulator."""
import redis
from rq import Queue, Worker

from conf import REDIS_HOST, REDIS_PORT


REDIS_CONN = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT  # default
)
"""Provides an connection to the redis server at ``redis://<REDIS_HOST>:<REDIS_PORT>``."""

HPATH_SIM_QUEUE = Queue(name='hpath', connection=REDIS_CONN, default_timeout=3600)
"""Redis queue for histopathology model simulation."""


def start() -> None:
    """Start an RQ worker on the default queue."""
    worker = Worker(queues=[HPATH_SIM_QUEUE], connection=REDIS_CONN)
    worker.work(
        date_format="%d %b %Y %H:%M:%S",
        log_format="%(process)5d   %(asctime)s.%(msecs)03d %(message)s"
    )


if __name__ == '__main__':
    start()
