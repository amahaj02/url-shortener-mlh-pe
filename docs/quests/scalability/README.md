# Scalability Quest

This folder covers what was done to move the app from basic load testing to a monitored, cached service that can survive heavier bursts.

## Bronze: The Baseline

What we implemented:

- k6 load testing scripts under `tests/perf/`
- a repeatable 50-user concurrent spike script as the baseline
- documented latency/error-rate output from k6 runs during testing

Current perf entrypoints:

- `tests/perf/k6_50_concurrent_spike.js`
- `tests/perf/k6_200_concurrent_spike.js`
- `tests/perf/k6_500_concurrent_spike.js`
- `tests/perf/k6_1000_concurrent_spike.js`
- `tests/perf/k6_redis_redirect_cache.js`

## Silver: The Scale-Out

The quest log suggests Docker Compose plus Nginx. We met the same goal with the deployment setup we actually used:

- Kubernetes `Deployment` with 3 replicas
- DigitalOcean `LoadBalancer` service in front of the pods
- HPA configured to scale between 3 and 7 replicas based on CPU

Why we used this instead:

- it matched the production environment we were already using
- it gave us real horizontal scaling and real traffic distribution without maintaining a separate local Nginx stack just for the quest

Where to look:

- workload + service + HPA: `config/deployment.yml`
- deploy workflow: `.github/workflows/k8s-deploy.yml`

## Gold: The Speed Of Light

What changed for the Gold tier:

- Redis-backed short-code cache in `app/cache.py`
- redirect path updated to read from cache and repopulate it when needed
- Prometheus metrics and structured logging added so we could spot bottlenecks during load
- additional k6 scripts for 200, 500, and 1000 concurrent users

What was slow before:

- every redirect depended on a database lookup
- under sustained concurrent load, write-heavy endpoints and repeated redirect reads created avoidable pressure on the database and worker pool

What we changed:

- cache hot redirect data in Redis
- keep replicas distributed and autoscaled in Kubernetes
- add enough metrics and logging to tell whether the slowdown was CPU, request backlog, or database-related

Supporting docs:

- Bottleneck report: [bottleneck-report.md](./bottleneck-report.md)
- Capacity plan: [capacity-plan.md](../../capacity-plan.md)
- Architecture diagram: [incident-response/architecture.md](../../architecture.md)
- Decision log: [decision-log.md](../../decision-log.md)
