# Bottleneck Report

## Rubric summary (2–3 sentences for submission)

The worst steady-state waste was on **`GET /<short_code>`**: every redirect used to resolve the short code in Postgres on every request. We moved to **Redis-first** resolution (`app/cache.py`, `app/routes/urls.py`) with **`cache_hit`** in logs so we can prove hits under load. We still had to align **database pool size**, **Gunicorn threads**, **Kubernetes requests**, and **k6 pass/fail bars** with reality: a small cluster cannot absorb unlimited concurrent clients, so we tuned pools and load tests instead of treating every timeout as a cache bug.

---

## 1. What we were trying to prove

- **Baseline:** mixed read/write traffic (`tests/perf/k6_concurrent_spike.js`) at **50 concurrent users** (ramp mode: `VU_RAMP=1`, `VUS=50`).
- **Scale checkpoints:** same script at **200** and **500** VUs to see latency and **http_req_failed** stay healthy.
- **Gold / tsunami:** **500+ VUs**, redirect-heavy tests (`tests/perf/k6_redis_redirect_cache.js`), and **error rate under 5%** with evidence of caching.

Recorded numbers for the ramped runs live in [LOAD_TEST_BASELINE.md](../../LOAD_TEST_BASELINE.md).

---

## 2. Hot path: redirects and the database

**Symptom:** Under concurrency, Postgres and connection pools became the obvious limiter. Redirects are the highest-frequency read in a URL shortener; doing a DB lookup on every click duplicates work for popular links.

**Change:** **Redis-first** lookup for short codes: try cache, fall back to DB, then repopulate cache. Cache keys are normalized (e.g. lowercased) so behavior stays consistent.

**Observation:** Redirects are **not** “read-only” in the sense of zero writes. Each redirect still participates in **click analytics**: events are **batched** (`app/event_pipeline.py`) rather than one synchronous `INSERT` per request. If redirect volume spikes, tune **`EVENT_BATCH_SIZE`** and **`EVENT_FLUSH_INTERVAL_SEC`**—batching shifts pressure from per-request latency to flush throughput and DB write bursts.

---

## 3. Database connections vs app threads

Postgres exposes a hard **`max_connections`** budget (e.g. on the order of **~197** in our environment). The app uses a **Peewee pool per worker** sized by **`DATABASE_MAX_CONNECTIONS`** (see `config/deployment.yml`).

Rough ceiling for app traffic:

**`replicas × WEB_CONCURRENCY × DATABASE_MAX_CONNECTIONS`**

With **HPA max 3** replicas, **`WEB_CONCURRENCY=1`**, and **`DATABASE_MAX_CONNECTIONS=48`**, that is about **144** concurrent DB connections from the app—intentionally **below** `max_connections` so admin tools, migrations, and other clients still fit.

If you add replicas or workers without revisiting **`max_connections`** or a **PgBouncer / managed pool** in front of Postgres, you risk **`too many connections`** or connection churn. The bottleneck report is not “raise threads forever”; it is **match pool + replicas to the database’s contract**.

---

## 4. Gunicorn: threads and the pool

We run **`WEB_CONCURRENCY=1`** with **`GUNICORN_THREADS`** in the **60s** so one worker process can handle many concurrent requests.

**`GUNICORN_THREADS_CAP_TO_POOL`** (in `deployment/gunicorn.conf.py`) controls whether thread count is capped to the DB pool size. **Capping** avoids over-committing threads relative to connections; **disabling the cap** lets more threads **share** the same pool—threads block on the pool when busy, which can be acceptable when **Redis-first redirects** reduce how often requests need a DB slot. We documented this tradeoff in [capacity-plan.md](../../capacity-plan.md) and [CONFIG_REFERENCE.md](../../CONFIG_REFERENCE.md).

Misinterpreting this shows up as **queueing**: p95 looks fine while some requests **stall** or hit **dial / i/o timeouts** because the offered concurrency from k6 exceeds what the pod can drain.

---

## 5. Kubernetes: HPA and scheduling the third replica

We use **HPA** (e.g. min **2**, max **3** replicas) so the service can scale under CPU/memory pressure.

**What we hit:** A **third** pod can stay **`Pending`** with **Insufficient cpu** or **Insufficient memory** on small nodes if **resource requests** are too high relative to what the node has left after system workloads.

**Mitigation we aligned with:** **Lower CPU/memory requests** (e.g. **750m** CPU, **1280Mi** memory requests in `config/deployment.yml`) so a third replica can **schedule** on typical small nodes, while **limits** still allow burst headroom. This is a scheduling bottleneck, not an application bug—if the pod cannot land, HPA cannot help.

---

## 6. Load testing: k6 thresholds and “false failures”

We share scenarios in **`tests/perf/k6_write_spike_shared.js`**.

**Failure rate:** **`MAX_HTTP_FAILED_RATE`** defaults to **5%** (`0.05`) so the k6 threshold matches the rubric’s **under 5% errors** language.

**Latency:** A single global **p(95) under 500ms** threshold **fails** honest runs at **200** or **500** VUs even when the system is healthy—queueing and tail latency rise with offered load. We implemented **tiered p(95) bars** by target **`VUS`** (ramp) and **`HTTP_REQ_PER_SEC`** (arrival), with optional overrides **`K6_HTTP_P95_MS`**, **`K6_HTTP_P95_MS_RAMP`**, **`K6_HTTP_P95_MS_ARRIVAL`** (documented in that file and `.env.example`). The goal is to **fail** on real regressions, not on “strict bar at every scale.”

**Timeouts under extreme VUs:** Seeing **`dial: i/o timeout`** alongside **memory pressure** often means the **load generator opened more parallel work than the service could accept**—requests pile up at the LB/OS, not necessarily that Redis is broken. **500 VUs** is a **stress probe** after smaller runs pass; see [capacity-plan.md](../../capacity-plan.md).

---

## 7. Symptoms vs root causes (quick map)

| What we saw | Plausible cause | What we checked / changed |
|-------------|-------------------|---------------------------|
| High redirect latency, repeated DB work for same short code | No cache on hot reads | Redis-first path, `cache_hit` logs |
| `too many connections` / pool exhaustion | Pool × replicas × workers vs `max_connections` | `DATABASE_MAX_CONNECTIONS`, replica count, PgBouncer docs |
| Good p95 but scattered timeouts | Queueing, thread/pool mismatch | `GUNICORN_THREADS`, `GUNICORN_THREADS_CAP_TO_POOL`, offered load vs capacity |
| Third replica Pending | Node cannot fit requests | Lower **requests** or larger nodes |
| k6 fails only on p(95) at high VUs | Threshold too strict for scale | Tiered **`K6_HTTP_P95_MS_*`** in shared k6 |

---

## 8. Bottom line

The **first architectural win** was stopping Postgres from answering the same redirect question on every click. The **ongoing work** was **capacity hygiene**: pool and replica math against **`max_connections`**, honest **Gunicorn** threading vs the pool, **Kubernetes** requests that let HPA add pods, and **load tests** whose thresholds reflect scale—not a single latency number copied from a laptop baseline.

For deeper deployment and env tuning, use [capacity-plan.md](../../capacity-plan.md) and [CONFIG_REFERENCE.md](../../CONFIG_REFERENCE.md).
