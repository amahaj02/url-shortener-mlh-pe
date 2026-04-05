# Deploy Guide

This is the practical deploy path for the current repo.

## Normal Deploy

1. Push to a branch watched by the GitHub Actions workflow.
2. The workflow runs tests first.
3. If tests pass, it builds the image, pushes to DigitalOcean Container Registry, renders `config/deployment.yml`, and applies it to the cluster.
4. The workflow waits for `kubectl rollout status` before calling the deploy successful.
5. Monitoring manifests are applied after the app rollout.

Key files:

- Workflow: `.github/workflows/k8s-deploy.yml`
- App workload: `config/deployment.yml`
- Monitoring rules: `config/monitoring/url-shortener-monitoring.yml`

## Rollback

If the new rollout is unhealthy:

```bash
kubectl rollout undo deployment/url-shortener --namespace=default
```

Then verify:

```bash
kubectl rollout status deployment/url-shortener --namespace=default
kubectl get pods -n default -l app=url-shortener
```

## Post-Deploy Checks

- `GET /health` returns `200`
- service has endpoints
- Prometheus target is up
- no fresh error spike in logs

Useful commands:

```bash
kubectl get service url-shortener-service --namespace=default
kubectl get endpoints url-shortener-service --namespace=default
kubectl logs deployment/url-shortener --namespace=default --since=10m
```
