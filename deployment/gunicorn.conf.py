import os
from pathlib import Path


def _int_env(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


cpu_count = os.cpu_count() or 2
db_pool_size = max(1, _int_env("DATABASE_MAX_CONNECTIONS", 20))
db_reserved = max(1, _int_env("DATABASE_POOL_RESERVED_CONNECTIONS", 4))
db_request_budget = max(1, db_pool_size - db_reserved)

workers = max(1, _int_env("WEB_CONCURRENCY", min(4, cpu_count)))
threads = max(1, _int_env("GUNICORN_THREADS", 4))

# Keep request concurrency under DB pool budget to reduce queueing at the DB.
if workers * threads > db_request_budget:
    threads = max(1, db_request_budget // workers)
    if workers * threads > db_request_budget:
        workers = max(1, db_request_budget // threads)

bind = os.getenv("GUNICORN_BIND", "0.0.0.0:5000")
worker_class = "gthread"
worker_tmp_dir = "/dev/shm" if Path("/dev/shm").exists() else "/tmp"
timeout = _int_env("GUNICORN_TIMEOUT", 30)
keepalive = _int_env("GUNICORN_KEEPALIVE", 2)
max_requests = _int_env("GUNICORN_MAX_REQUESTS", 1000)
max_requests_jitter = _int_env("GUNICORN_MAX_REQUESTS_JITTER", 100)
graceful_timeout = _int_env("GUNICORN_GRACEFUL_TIMEOUT", 30)
