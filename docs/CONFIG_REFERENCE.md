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
| `DATABASE_POOL_RESERVED_CONNECTIONS` | Per worker: subtracted from pool before capping `GUNICORN_THREADS` |
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

## CI/CD Secrets

These values are supplied through GitHub Actions secrets rather than committed in the repo:

| Secret | Purpose |
| --- | --- |
| `DIGITALOCEAN_ACCESS_TOKEN` | Auth for `doctl` and registry/cluster access |
| `REGISTRY_NAME` | DigitalOcean registry path used for image push |
| `CLUSTER_NAME` | Target Kubernetes cluster name |
| `K8S_ENV_FILE` | App environment file rendered into the `url-shortener-env` secret |
| `LETSENCRYPT_EMAIL` | Contact email rendered into `config/letsencrypt-issuer.yml` at deploy time |
| `GRAFANA_DISCORD_WEBHOOK_URL` | Discord webhook rendered into `config/monitoring/grafana-contact-points-secret.yml` |

## Ingress And TLS

The current public app entrypoint is defined by:

- `config/app-ingress.yml`
- `config/letsencrypt-issuer.yml`

Current public hostname:

- `fifaurlshortener.duckdns.org`

Monitoring ingress is defined separately in:

- `config/monitoring/monitoring-ingress.yml`

The Prometheus ingress also expects this cluster secret to exist:

- `prometheus-basic-auth` in namespace `monitoring`

## Kubernetes Deployment Defaults

The cluster deployment currently overrides some values directly in `config/deployment.yml`, including:

- `TESTING=false`
- `AUTO_CREATE_TABLES=false`
- `PORT=8000`
- `GUNICORN_BIND=0.0.0.0:8000`
- `WEB_CONCURRENCY=1`
- `GUNICORN_THREADS=7`
- `DATABASE_MAX_CONNECTIONS=7` (Postgres 25 total / 3 reserved → 22 app budget; `3×1×7=21` at max replicas; see [capacity-plan.md](./capacity-plan.md))
- HPA `minReplicas=2`, `maxReplicas=3`; targets **CPU** average **50%** and **memory** average **70%** of request (per-pod resources in `config/deployment.yml`; see [capacity-plan.md](./capacity-plan.md))

## Repo-Managed Kubernetes Manifests

The workflow currently applies these repo-managed manifests:

- `config/deployment.yml`
- `config/monitoring/url-shortener-monitoring.yml`
- `config/monitoring/grafana-dashboard-configmap.yml`
- `config/monitoring/grafana-alerting-policies-configmap.yml`
- `config/letsencrypt-issuer.yml`
- `config/app-ingress.yml`
- `config/monitoring/monitoring-ingress.yml`

The monitoring stack values we now treat as source-of-truth in the repo live in:

- `config/monitoring/kube-prometheus-stack-values.yml`

That values file records the live Grafana persistence settings and the file mounts used for Grafana alerting provisioning.

The deployment workflow now also runs a Helm upgrade for `kube-prometheus-stack` using that values file, so Grafana persistence and provisioning mounts are no longer a manual-only cluster tweak.
