# Decision Log

## Why Redis

We picked Redis because the redirect path is the hottest read path in the whole app. A short-code lookup is small, stable, and ideal for caching, so Redis gives a fast win without changing the user-facing API.

## Why Kubernetes Service + HPA instead of Docker Compose + Nginx

The quest log uses Docker Compose and Nginx as the example scale-out path. We were already deploying to DigitalOcean Kubernetes, so using a `LoadBalancer` service plus HPA gave us the same operational benefit in the actual environment we were demoing.

## Why Prometheus + Grafana

Prometheus fit the Kubernetes setup directly, and Grafana let us cover both the alerting demo and the dashboard requirement. It was the shortest path from “we need metrics” to “we can explain what is failing and why.”

## Why Structured App Logs

Once the load tests started surfacing intermittent timeouts, text logs were not enough. Structured logs with request IDs and SQL timing gave us a way to correlate slow requests with the likely bottleneck instead of guessing.
