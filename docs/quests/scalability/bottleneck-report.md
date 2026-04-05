# Bottleneck Report

This report is the short version of what we learned while pushing the app from "works locally" to "can survive real traffic without immediately falling over."

## Rubric summary (2–3 sentences for submission)

The hottest path was **`GET /<short_code>`**: every redirect used to hit Postgres for the same short codes repeatedly. We added **Redis-backed caching** for redirect resolution (`app/cache.py`) so repeat lookups avoid the database, and we kept **observability** (logs with `cache_hit`, metrics) to prove cache hits and find the next bottleneck. Under load tests (**500+ VUs** with **`http_req_failed` &lt; 5%**), the system stayed stable because the DB was no longer doing redundant read work on every click.

## What We Tested

Our baseline load test was the mixed k6 workflow in `tests/perf/k6_concurrent_spike.js` (default **50 VUs**; higher tiers use the same script with **`VUS=200`**, **`500`**, or **`1000`**). It exercises the main write/read paths that matter most for this app:

- creating users
- creating short URLs
- listing URLs by user

Later runs increased concurrency with the 200, 500, and 1000 VU variants. We also paid special attention to the redirect path because that is the highest-frequency read in a URL shortener and the most obvious place to burn database capacity unnecessarily.

## What We Saw First

The first useful signal was that average latency and even p95 latency could look fine while a small number of requests still timed out. That was an important clue.

This told us the problem was probably not "the whole system is slow all the time." It looked more like a queueing or hotspot issue:

- most requests were still moving through quickly
- a few requests were getting stuck long enough to hit client timeouts
- the failures showed up more often on write-heavy paths and on repeated redirect/read traffic

That pushed us away from guessing and toward instrumenting the app properly.

## Where The Pressure Was Coming From

The biggest avoidable bottleneck was the redirect path.

Originally, every `GET /<short_code>` required a database lookup. That is fine at low traffic, but it is wasteful for a service where popular links get hit over and over again. The app was asking Postgres the same question repeatedly even when the answer was small, stable, and easy to cache.

That meant the database was doing repetitive read work for hot links while also serving write-heavy endpoints such as:

- `POST /users`
- `POST /urls`
- `GET /urls?user_id=...`

So the database was not just the system of record. It was also being treated like a low-latency cache, which is exactly the kind of design that starts to hurt once concurrency increases.

## How We Confirmed It

We added observability before trying to "optimize" blindly.

The changes that helped us reason about the issue were:

- structured request logs
- request IDs for correlation
- Prometheus request metrics
- SQL timing logs
- Grafana dashboards and alerts

That gave us a much clearer picture:

- if latency rose while traffic stayed steady, we were likely saturating part of the stack rather than seeing a simple external spike
- if CPU climbed and a few requests timed out, worker queueing became more plausible
- if redirect traffic stayed hot and the same short codes were being resolved repeatedly, cache absence was an obvious inefficiency

The result was not one dramatic smoking gun log line. It was a pattern: repeated read traffic was needlessly hitting Postgres, and under concurrent load that increased pressure on the same backend that also needed to handle writes.

## What We Changed

We made the redirect path cheaper and gave the service more room to breathe.

The main changes were:

- Redis-backed caching for short-code redirects in `app/cache.py`
- redirect logic updated to read from cache and repopulate it on misses
- Kubernetes deployment with multiple replicas behind a `LoadBalancer`
- HPA-based scaling so the app could add pods under CPU pressure
- structured metrics and logs so we could tell whether a slowdown was caused by CPU, request backlog, or database pressure

This was the right tradeoff for the app we built. We did not need a complicated redesign. We needed to stop doing unnecessary repeated reads against the primary datastore.

## What Improved

After adding the cache and keeping the service scaled behind Kubernetes, the architecture made a lot more sense for the workload:

- hot redirect reads no longer had to go to Postgres every time
- the database could spend more of its budget on writes and uncached lookups
- the service had better headroom as concurrency increased
- we had enough telemetry to explain performance problems instead of just describing symptoms

This is also why Redis was a good fit here. The cached object is small, the lookup key is stable, and the read pattern is exactly the sort of thing caches are meant to absorb.

## What Still Limits The System

The cache helps a lot, but it does not make the app infinitely scalable.

The likely limits are still:

1. database connection budget
2. CPU saturation during write-heavy bursts
3. worker queueing when a few requests become slow
4. cache miss rate on cold or uneven traffic

So the main lesson was not "Redis solved everything." The lesson was that the first real bottleneck was unnecessary database work on the hottest read path, and fixing that gave us a cleaner foundation for higher-concurrency testing.

## Bottom Line

The bottleneck we chose to address first was the redirect path hitting Postgres on every request.

That was the highest-leverage fix because:

- it removed repetitive read pressure from the database
- it helped the app behave more predictably under concurrency
- it made the system easier to reason about during load tests

For this project, that was the difference between a basic API that works and a service that starts to look operationally credible under sustained traffic.
