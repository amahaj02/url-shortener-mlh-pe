# Capacity Plan

This is a practical capacity note for the current hackathon build, not a promise of infinite scale.

## Current Shape

- Baseline deployment: 2 replicas (smaller per-pod CPU/memory; see `config/deployment.yml`)
- Autoscaling range: 2 to 6 replicas
- Per-pod request/limit (tune for your nodes; `config/deployment.yml`):
  - CPU request: `500m`
  - CPU limit: `900m`
  - memory request: `384Mi`
  - memory limit: `768Mi`
- Gunicorn per pod:
  - `WEB_CONCURRENCY=2`
  - `GUNICORN_THREADS=10` (capped per worker by `DATABASE_MAX_CONNECTIONS` in `deployment/gunicorn.conf.py`)
  - `DATABASE_MAX_CONNECTIONS=20` per worker (≈ `workers × DATABASE_MAX_CONNECTIONS` DB conns per pod under load)

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
