# Config Reference

This is the short list of environment variables and deploy-time settings that matter for running the app.

## Core App

| Variable | Purpose |
| --- | --- |
| `FLASK_DEBUG` | Local debug mode |
| `TESTING` | Switches the app into test behavior |
| `AUTO_CREATE_TABLES` | Auto-create tables at startup |
| `HOST` / `PORT` | Local bind settings |
| `GUNICORN_BIND` | Explicit bind address for Gunicorn |

## Database

| Variable | Purpose |
| --- | --- |
| `DATABASE_NAME` | Database name |
| `DATABASE_HOST` | Database host |
| `DATABASE_PORT` | Database port |
| `DATABASE_USER` | Database user |
| `DATABASE_PASSWORD` | Database password |
| `DATABASE_SSLMODE` | Managed Postgres TLS mode |
| `DATABASE_CONNECT_TIMEOUT` | Connection timeout |
| `DATABASE_MAX_CONNECTIONS` | Peewee pool size per worker |
| `DATABASE_POOL_RESERVED_CONNECTIONS` | Reserved connection budget |
| `DATABASE_STALE_TIMEOUT_SECONDS` | Pool stale timeout |
| `DATABASE_POOL_WAIT_TIMEOUT_SECONDS` | Pool wait timeout |

## Gunicorn

| Variable | Purpose |
| --- | --- |
| `WEB_CONCURRENCY` | Worker count |
| `GUNICORN_THREADS` | Threads per worker |
| `GUNICORN_TIMEOUT` | Hard request timeout |
| `GUNICORN_KEEPALIVE` | Keepalive |
| `GUNICORN_GRACEFUL_TIMEOUT` | Graceful shutdown timeout |
| `GUNICORN_MAX_REQUESTS` | Worker recycle count |
| `GUNICORN_MAX_REQUESTS_JITTER` | Worker recycle jitter |
| `GUNICORN_ERROR_LOG` | Error log target |
| `GUNICORN_LOG_LEVEL` | Gunicorn log level |

## Event Pipeline

| Variable | Purpose |
| --- | --- |
| `EVENT_QUEUE_MAX` | Maximum queued events |
| `EVENT_BATCH_SIZE` | Batch insert size |
| `EVENT_FLUSH_INTERVAL_SEC` | Background flush interval |

## Logging And Debugging

| Variable | Purpose |
| --- | --- |
| `LOG_LEVEL` | Root app log level |
| `PE_DEBUG_LIST_URLS` | Emit URL-list query args in logs |
| `HTTP_LOG_SUCCESS` | Log successful requests too |
| `HTTP_LOG_SLOW_MS` | Slow-request threshold |
| `HTTP_LOG_LEVEL` | HTTP logger level |
| `SQL_LOG_ALL` | Log all SQL statements |
| `SQL_LOG_SLOW_MS` | Slow SQL threshold |
| `SQL_LOG_LEVEL` | SQL logger level |

## Redis Cache

| Variable | Purpose |
| --- | --- |
| `REDIS_URL` | Full Redis connection URL |
| `REDIS_HOST` | Host-based Redis config |
| `REDIS_PORT` | Redis port |
| `REDIS_PASSWORD` | Redis password |
| `REDIS_DB` | Redis DB index |
| `REDIS_CACHE_TTL_SECONDS` | Cache TTL for short-link entries |

## Prometheus Metrics

| Variable | Purpose |
| --- | --- |
| `PROMETHEUS_NAMESPACE` | Prefix for Prometheus metric names |

## Kubernetes Deployment Defaults

The cluster deployment currently overrides some values directly in `config/deployment.yml`, including:

- `TESTING=false`
- `AUTO_CREATE_TABLES=false`
- `PORT=8000`
- `GUNICORN_BIND=0.0.0.0:8000`
- `WEB_CONCURRENCY=2`
- `GUNICORN_THREADS=2`
- `DATABASE_MAX_CONNECTIONS=3`
