# Capacity Plan

This is a practical capacity note for the current hackathon build, not a promise of infinite scale.

## Current Shape

- Baseline deployment: 2 replicas (see `config/deployment.yml`)
- Autoscaling range: 2 to 3 replicas (HPA)
- Per-pod request/limit (`config/deployment.yml`):
  - CPU request: `1000m`
  - CPU limit: `1800m`
  - memory request: `768Mi`
  - memory limit: `1536Mi`
- Postgres: **25** `max_connections` cluster-wide, **3** reserved (maintenance) → **22** usable for the app (see `deployment.yml` env).
- Gunicorn per pod:
  - `WEB_CONCURRENCY=1` (one process per pod so pool size can be **7** and stay at or under 22 total: `3×1×7=21`)
  - `GUNICORN_THREADS=7` (capped to Peewee pool in `deployment/gunicorn.conf.py`)
  - `DATABASE_MAX_CONNECTIONS=7` per worker — **21** connections at HPA max; **1** left unused (22 is not divisible evenly across six pools from 3×2 workers, so we use 1×7 per pod instead of 2×3)

## Load-Test Entry Points

- `tests/perf/k6_write_spike_shared.js` — shared write scenario (POST /users → /urls → GET /urls)
- `tests/perf/k6_50_concurrent_spike.js` … `k6_1000_concurrent_spike.js` — same scenario; default VUS matches filename (override with `VUS`, `DURATION`, `BASE_URL`)
- `tests/perf/k6_smoke_write.js` — 1 VU, 30s, loose thresholds (quick wiring check)
- `tests/perf/k6_redis_redirect_cache.js` — GET /:short_code (redirect cache path)

## Expected Limiters

The likely limits for this app are:

1. database connection budget
2. CPU saturation on write-heavy bursts
3. request queueing in Gunicorn workers
4. Redis/cache miss rate on redirect-heavy traffic

## Practical Read Of The Current System

- 50 concurrent users is the baseline test
- 200 concurrent users is the “scale-out” checkpoint
- 500+ concurrent users is where cache effectiveness and autoscaling start to matter
- 1000 concurrent users is useful as a stress run, but it should be treated as a probe for headroom, not a guaranteed steady-state operating point

## What To Watch

- p95 request latency
- error rate
- CPU utilization vs limit
- memory utilization vs limit
- in-flight requests
- high-error-rate and high-CPU alerts

If the app starts missing targets, the first things to inspect are the redirect cache hit behavior, DB pressure, and whether the HPA is scaling quickly enough.
