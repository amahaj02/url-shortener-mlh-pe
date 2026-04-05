# Failure Modes

This service is designed to fail cleanly under common error scenarios and to recover automatically when run under Kubernetes.

## User-Facing Failure Behavior

### Invalid JSON body
- A malformed body returns `400`.
- Response shape:

```json
{"errors":{"payload":"Invalid JSON"}}
```

### JSON body is not an object
- Empty body, arrays, strings, numbers, booleans, and `null` return `400`.
- Response shape:

```json
{"errors":{"payload":"JSON object required"}}
```

### Unknown route
- Returns `404`.
- Response shape:

```json
{"error":"Not found"}
```

### Wrong HTTP method
- Returns `405`.
- Response shape:

```json
{"error":"Method not allowed"}
```

### Unknown short code
- Returns `404`.
- Response shape:

```json
{"error":"Short URL not found"}
```

### Inactive short code
- Returns `404` (treated like a missing short code).
- Response shape:

```json
{"error":"URL not found"}
```

### Database unavailable during request handling
- The app catches Peewee `OperationalError` and `InterfaceError`.
- Returns `503`.
- Response shape:

```json
{"error":"Service unavailable"}
```

### Unexpected application exception
- Returns `500`.
- Response shape:

```json
{"error":"Internal server error"}
```

## Internal Resilience Behavior

### Event logging pressure
- Event writes are queued and flushed asynchronously in batches.
- If the event queue fills, events may be dropped to protect request latency.
- The API request still succeeds when the primary business operation succeeds.

### App process crash in Kubernetes
- The app runs in a Kubernetes `Deployment`.
- Pods are recreated automatically by the Deployment controller.
- `readinessProbe`, `startupProbe`, and `livenessProbe` help the cluster detect unhealthy pods and stop routing traffic to them.

### Deployment startup failures
- If the app cannot start, the rollout stays incomplete.
- The GitHub Actions deployment workflow waits on:

```bash
kubectl rollout status deployment/url-shortener --namespace=default --timeout=180s
```

- This causes the deploy job to fail instead of reporting a false positive.

## Chaos Demo

### Kubernetes self-healing demo
1. Confirm pods are running:

```bash
kubectl get pods -l app=url-shortener --namespace=default
```

2. Delete one live pod on purpose:

```bash
kubectl delete pod -l app=url-shortener --namespace=default --wait=false
```

3. Watch Kubernetes replace it:

```bash
kubectl get pods -l app=url-shortener --namespace=default -w
```

Expected result:
- one pod enters `Terminating`
- a new pod is scheduled automatically
- readiness probe passes
- service remains available through the load balancer

### Bad-input demo
Send malformed JSON:

```bash
curl -i -X POST http://<service-url>/urls \
  -H "Content-Type: application/json" \
  -d "{not-json"
```

Expected result:
- HTTP `400`
- JSON response: `{"errors":{"payload":"Invalid JSON"}}`
