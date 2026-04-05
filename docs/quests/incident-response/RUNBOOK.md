## URL Shortener Runbook

This runbook is for the `url-shortener` service running on DigitalOcean Kubernetes.

### Scope

Use this when any of the following alerts fire:

- `UrlShortenerServiceDown`
- `UrlShortenerHighErrorRate`
- `UrlShortenerHighCpuUsage`

### Command Center

- Dashboard JSON: [config/monitoring/grafana-dashboard-url-shortener.json](/c:/Aarav/coding/PE-Hackathon-Template-2026-fifa/config/monitoring/grafana-dashboard-url-shortener.json)
- Alert rules: [config/monitoring/url-shortener-monitoring.yml](/c:/Aarav/coding/PE-Hackathon-Template-2026-fifa/config/monitoring/url-shortener-monitoring.yml)
- Failure modes: [docs/failure_modes.md](/c:/Aarav/coding/PE-Hackathon-Template-2026-fifa/docs/failure_modes.md)

### First 5 Minutes

1. Check which alert fired and whether it is still firing.
2. Open the Grafana dashboard and inspect the four golden signals:
   - latency
   - traffic
   - errors
   - saturation
3. Check recent app logs:

```bash
kubectl logs deployment/url-shortener --namespace=default --since=10m
```

4. Check pod health:

```bash
kubectl get pods -n default -l app=url-shortener
kubectl describe pods -n default -l app=url-shortener
```

5. Check rollout status:

```bash
kubectl rollout status deployment/url-shortener --namespace=default
```

### If Service Down Fires

Symptoms:

- `/health` fails
- dashboard traffic drops to zero
- Prometheus `up` for the service goes to `0`

Checks:

```bash
kubectl get deploy url-shortener -n default
kubectl get svc url-shortener-service -n default
kubectl get endpoints url-shortener-service -n default
kubectl logs deployment/url-shortener --namespace=default --tail=200
```

Likely causes:

- bad deploy
- pods crashlooping
- readiness/liveness probe failures
- DB unavailable on startup

Immediate mitigation:

```bash
kubectl rollout undo deployment/url-shortener --namespace=default
kubectl scale deployment/url-shortener --replicas=3 --namespace=default
```

### If High Error Rate Fires

Symptoms:

- 5xx error ratio climbs above threshold
- traffic may stay normal while success rate drops
- logs show `sql_query_failed`, `Database unavailable`, or request warnings

Checks:

```bash
kubectl logs deployment/url-shortener --namespace=default --since=10m | Select-String "ERROR|sql_query_failed|Database unavailable|request_completed"
```

Look for:

- repeated `503` or `500`
- DB failures
- malformed inputs causing unexpected code paths
- cache misses combined with slow DB behavior

Immediate mitigation:

- if tied to a fresh deploy, roll back
- if tied to DB connectivity, verify DB credentials, network access, and connection limits
- if tied to a single endpoint, temporarily stop load generation and isolate the route

### If High CPU Usage Fires

Symptoms:

- CPU saturation panel spikes
- latency usually rises first, then error rate may follow
- k9s shows pods near CPU limit

Checks:

```bash
kubectl top pods -n default -l app=url-shortener
kubectl describe hpa url-shortener-hpa -n default
kubectl logs deployment/url-shortener --namespace=default --since=10m
```

Look for:

- sudden traffic surge
- repeated expensive DB queries
- excessive write pressure on `/users` or `/urls`
- hot pods with low readiness

Immediate mitigation:

- let HPA scale up if it is already reacting
- increase replicas temporarily if the alert is user-impacting
- reduce synthetic load if this is a test
- inspect SQL timing logs for slow queries

### Sherlock Mode Example

Example root-cause workflow:

1. Dashboard shows latency rising first.
2. Traffic remains steady, so the issue is not an external spike alone.
3. Saturation panel shows CPU climbing toward limit.
4. Error rate starts increasing after saturation rises.
5. Logs show slow requests and slow SQL on write-heavy endpoints.

Conclusion:

- the likely bottleneck is application or database saturation, not network loss
- the immediate fix is scaling and reducing expensive synchronous work
- the follow-up fix is query/write-path optimization

### After the Incident

1. Capture screenshots of the dashboard and the alert.
2. Record the exact time window.
3. Save the triggering query or logs.
4. Write a brief summary:
   - what failed
   - how it was detected
   - how it was mitigated
   - what should be improved next
