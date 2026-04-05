# Capacity Plan

This is a practical capacity note for the current hackathon build, not a promise of infinite scale.

## Current Shape

- Baseline deployment: 2 replicas (see `config/deployment.yml`)
- Autoscaling range: 2 to 3 replicas (HPA)
- Per-pod request/limit (`config/deployment.yml`):
  - CPU request: `1000m`
  - CPU limit: `1800m`
  - memory request: `1536Mi`
  - memory limit: `3072Mi`
- Postgres: sized for a larger cluster (e.g. **`max_connections` ≈ 197**). App pool per worker **`DATABASE_MAX_CONNECTIONS=48`** → at HPA **max 3** replicas, **`3×1×48 ≈ 144`** app connections, leaving headroom for reserved roles and other clients.
- Gunicorn per pod:
  - `WEB_CONCURRENCY=1`
  - `GUNICORN_THREADS=64` with `GUNICORN_THREADS_CAP_TO_POOL=false` (threads share the Peewee pool; Redis-first redirects reduce DB waits)
  - `DATABASE_MAX_CONNECTIONS=48` per worker (see `deployment/gunicorn.conf.py` for thread/pool interaction)

## Load-Test Entry Points

- `tests/perf/k6_write_spike_shared.js` — shared scenario (POST /users → /urls → GET /urls?user_id= → GET /users/:id → GET /urls/:id → GET /events?user_id= → POST /events)
- `tests/perf/k6_concurrent_spike.js` — same scenario; **default ~100 HTTP req/s** (`constant-arrival-rate`); or **`VU_RAMP=1`** with **`VUS`** / **`DURATION`** for ramped load
- `tests/perf/k6_redis_redirect_cache.js` — GET /:short_code (redirect cache path); **`VUS`** + **`DURATION`**; optional **`VU_RAMP=1`** for 0→VUS ramp; **`MAX_HTTP_FAILED_RATE`**
- Gold-tier checklist (500+ users, caching evidence, under 5% errors): [LOAD_TEST_BASELINE.md — Gold tier](./LOAD_TEST_BASELINE.md#gold-tier)

## Expected Limiters

The likely limits for this app are:

1. database connection budget
2. CPU saturation on write-heavy bursts
3. request queueing in Gunicorn workers
4. Redis/cache miss rate on redirect-heavy traffic

### If k6 shows `dial: i/o timeout` and pods look memory-heavy (k9s)

That usually means the **load generator opened far more concurrent connections than the service can accept quickly**. With **`WEB_CONCURRENCY=1`**, **`GUNICORN_THREADS` in the 60s**, and a **Peewee pool** per pod (`DATABASE_MAX_CONNECTIONS`), each pod still has a **finite** number of worker threads and DB slots; **`VU_RAMP=1` + `VUS=500`** can offer **far more parallel clients** than that — many requests sit in OS/LB queues, connections stall, and you see **timeouts** and **high RSS** (buffers, queued work), not necessarily a “Redis bug.”

**Redirects are not cache-only:** every `GET /<short_code>` still does a DB lookup for `Url`, Redis get/set, and **enqueues a click event** (`Event.create_event` → **`app/event_pipeline.py`** batched `insert_many`). Clicks are **not** one synchronous insert per request in production; tune **`EVENT_BATCH_SIZE`** / **`EVENT_FLUSH_INTERVAL_SEC`** if needed. Heavy redirect tests are still **write-amplified** (many events, batched flushes).

**What to do:** run a **lower `VUS`** first (e.g. 50–100), reduce **`HITS_PER_ITER`**, or **scale replicas / thread budget** so offered load matches capacity. Treat **500 VUs** as a stress probe after smaller runs pass, not the first test against two small pods.

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
