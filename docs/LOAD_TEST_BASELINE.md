# Load test baseline (50 concurrent users)

Use this for hackathon **verification**: k6 installed, **50 concurrent users**, **latency + error rate** recorded, **screenshot**, **documented p95**.

## Requirements mapping

| Ask | How you satisfy it |
|-----|-------------------|
| Install k6 or Locust | This repo uses **k6** (`tests/perf/`). Install k6 (see below). |
| 50 concurrent users | `tests/perf/k6_50_concurrent_spike.js` defaults to **50 VUs** (virtual users). |
| Not “total hits” | k6’s `constant-vus` executor keeps **50 workers** looping for the whole run — sustained concurrency, not a single burst count. |
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
DURATION=5m \
k6 run tests/perf/k6_50_concurrent_spike.js
```

- **`BASE_URL`**: your deployed API (load balancer or ingress URL), **no trailing slash**. For local: `BASE_URL=http://localhost:3000`
- **`DURATION`**: `5m` gives steadier **p95** than a very short run; `1m` is OK for a quick pass.
- **VUs**: the script already uses **50** by default (`buildWriteSpikeOptions(50, "5m")`). Override only if needed: `VUS=50`.

Each iteration does: **POST /users** → **POST /urls** → **GET /urls?user_id=** (same as your write-path baseline).

## What to screenshot

Include visible proof of:

1. **Command** (e.g. `k6 run tests/perf/k6_50_concurrent_spike.js`) and **`BASE_URL`** if set.
2. **Concurrency:** e.g. `50 max VUs`, or `vus_max...........: 50`, or scenarios line showing **50** VUs.
3. **Thresholds** (pass/fail) and/or summary **HTTP** block.
4. **`http_req_failed`** (should be `0.00%` for a healthy baseline).
5. **`p(95)`** under `http_req_duration` (overall and/or tagged `create_user`, `create_url`, `list_urls_by_user`).

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

## Related files

- Shared scenario: `tests/perf/k6_write_spike_shared.js`
- Quick smoke (not the 50-user baseline): `tests/perf/k6_smoke_write.js`
- Redirect/cache load: `tests/perf/k6_redis_redirect_cache.js`
- Capacity notes: [capacity-plan.md](./capacity-plan.md)
