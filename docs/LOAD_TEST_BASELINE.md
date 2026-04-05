# Load test baseline (50 concurrent users)

Use this for hackathon **verification**: k6 installed, **50 concurrent users**, **latency + error rate** recorded, **screenshot**, **documented p95**.

## Requirements mapping

| Ask | How you satisfy it |
|-----|-------------------|
| Install k6 or Locust | This repo uses **k6** (`tests/perf/`). Install k6 (see below). |
| 50 concurrent users | **`VU_RAMP=1`** uses **50 VUs** by default (override **`VUS`**). Without it, the script targets **~100 HTTP req/s** via **`constant-arrival-rate`** (override **`HTTP_REQ_PER_SEC`**). |
| Not “total hits” | Arrival mode schedules iterations at a steady rate; **`VU_RAMP=1`** ramps **0 → VUS** over **`DURATION`**. |
| Response time (latency) | k6 prints **p95** (and avg, max) under `http_req_duration`. |
| Error rate | k6 prints **`http_req_failed`** (rate and count). |
| Screenshot | Capture the terminal after a run: must show **50 max VUs** and summary stats (see [What to screenshot](#what-to-screenshot)). |
| Baseline p95 | Copy the **p(95)** line(s) into the [Baseline record](#baseline-record-fill-in-after-your-run) table below (and/or your report). |

## Install k6

- **macOS (Homebrew):** `brew install k6`
- **Other:** [https://grafana.com/docs/k6/latest/set-up/install-k6/](https://grafana.com/docs/k6/latest/set-up/install-k6/)

Verify: `k6 version`

## Run the 50-user load test

From the **repository root**:

```bash
BASE_URL=https://your-service-url.example.com \
DURATION=2m \
k6 run tests/perf/k6_concurrent_spike.js
```

- **`BASE_URL`**: your deployed API (load balancer or ingress URL), **no trailing slash**. For local: `BASE_URL=http://localhost:3000`
- **`DURATION`**: how long the scenario runs (default **`2m`**).
- **Default mode (~100 req/s):** **`HTTP_REQ_PER_SEC`** defaults to **100** (integer HTTP requests per second). Raise **`PRE_ALLOCATED_VUS`** / **`MAX_VUS`** if k6 warns it can’t sustain the rate.
- **Why only ~4 VUs in the summary?** Arrival mode does **not** mean “500 users.” k6 uses **as many VUs as needed** to hit the target rate. If each iteration finishes in a few hundred ms, **only a handful of VUs** run at once — that is correct. For **many concurrent VUs** (e.g. tsunami), use **`VU_RAMP=1`** and set **`VUS`**.
- **Ramp mode (VUs):** set **`VU_RAMP=1`**, then **`VUS`** (default **50**) and **`DURATION`** as the ramp length to **VUS**.

Each iteration does: **POST /users** → **POST /urls** → **GET /urls?user_id=** → **GET /users/:id** → **GET /urls/:id** → **GET /events?user_id=** → **POST /events** (mixed read/write coverage on the main resources).

## What to screenshot

Include visible proof of:

1. **Command** (e.g. `k6 run tests/perf/k6_concurrent_spike.js`) and **`BASE_URL`** / **`VUS`** if set.
2. **Concurrency:** e.g. `50 max VUs`, or `vus_max...........: 50`, or scenarios line showing **50** VUs.
3. **Thresholds** (pass/fail) and/or summary **HTTP** block.
4. **`http_req_failed`** (should be `0.00%` for a healthy baseline).
5. **`p(95)`** under `http_req_duration` (overall and/or tagged steps such as `create_user`, `create_url`, `list_urls_by_user`, `get_user`, `get_url`, `list_events`, `create_event`).

## Baseline record (fill in after your run)

| Field | Your value |
|-------|------------|
| Date / time (timezone) | |
| `BASE_URL` | |
| `DURATION` | |
| k6 version | |
| **Error rate** (`http_req_failed`) | |
| **p95 all requests** (`http_req_duration` → `p(95)=…`) | |
| **p95** `create_user` (if shown) | |
| **p95** `create_url` (if shown) | |
| **p95** `list_urls_by_user` (if shown) | |
| Notes (region, replicas, DB tier, etc.) | |

**Baseline p95 for the rubric:** use the overall **`http_req_duration`** **p(95)** unless instructions ask for a specific endpoint.

## Gold tier

Use this when the rubric asks for **optimization/caching**, a **“tsunami”** (e.g. **500+ concurrent users** or high sustained throughput), and **error rate under 5%**.

| Loot | What to capture |
|------|-----------------|
| **Tsunami** | Run **`VU_RAMP=1 VUS=500`** (or higher) against the deployed API. Example: `BASE_URL=… VU_RAMP=1 VUS=500 DURATION=3m k6 run tests/perf/k6_concurrent_spike.js`. Screenshot k6 summary: **max VUs**, **`http_req_failed`**, **p(95)**. |
| **Under 5% errors** | Set **`MAX_HTTP_FAILED_RATE=0.05`** so the k6 pass/fail bar matches **5%** (default threshold is stricter: **2%**). |
| **~100 req/s** | k6 prints **http_reqs** and duration; **RPS ≈ http_reqs / wall time** in the summary (or use Grafana request rate if you export metrics). |
| **Caching evidence** | **Logs:** structured `short_url_redirect` includes **`cache_hit`** ([`app/routes/urls.py`](../../app/routes/urls.py)). **Redirect load:** `k6 run tests/perf/k6_redis_redirect_cache.js` — set **`VUS`** (e.g. 200, 500) and **`DURATION`**; use **`VU_RAMP=1`** to ramp **0 → VUS** over **`DURATION`**. Compare **p95** / errors with Redis enabled vs disabled if you need a before/after story. |
| **Bottleneck report** | Short write-up: [bottleneck-report.md](../quests/scalability/bottleneck-report.md) (start from the **Rubric summary** at the top). |

## Related files

- Main ramped load: `tests/perf/k6_concurrent_spike.js`
- Shared scenario: `tests/perf/k6_write_spike_shared.js`
- Redirect/cache load: `tests/perf/k6_redis_redirect_cache.js`
- Capacity notes: [capacity-plan.md](./capacity-plan.md)
