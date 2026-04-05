# Capacity Plan

This is a practical capacity note for the current hackathon build, not a promise of infinite scale.

## Current Shape

- Baseline deployment: 3 replicas
- Autoscaling range: 3 to 7 replicas
- Per-pod request/limit:
  - CPU request: `350m`
  - CPU limit: `600m`
  - memory request: `600Mi`
  - memory limit: `1200Mi`
- Gunicorn per pod:
  - `WEB_CONCURRENCY=2`
  - `GUNICORN_THREADS=10` (capped per worker by `DATABASE_MAX_CONNECTIONS` in `deployment/gunicorn.conf.py`)
  - `DATABASE_MAX_CONNECTIONS=20` per worker (≈ `workers × DATABASE_MAX_CONNECTIONS` DB conns per pod under load)

## Load-Test Entry Points

- `tests/perf/k6_50_concurrent_spike.js`
- `tests/perf/k6_200_concurrent_spike.js`
- `tests/perf/k6_500_concurrent_spike.js`
- `tests/perf/k6_1000_concurrent_spike.js`
- `tests/perf/k6_redis_redirect_cache.js`

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
