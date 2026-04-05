# Deploy Guide

This is the practical deploy path for the current repo.

## Normal Deploy

1. Push to a branch watched by the GitHub Actions workflow.
2. The workflow runs tests first.
3. If tests pass, it builds the image, pushes to DigitalOcean Container Registry, renders `config/deployment.yml`, and applies it to the cluster.
4. The workflow waits for `kubectl rollout status` before calling the deploy successful.
5. Monitoring manifests are applied, the Grafana contact point secret is rendered from GitHub Actions secrets, and the workflow runs a Helm upgrade for `kube-prometheus-stack` using the repo values file.
6. TLS issuer and ingress manifests are applied after the app rollout.

Key files:

- Workflow: `.github/workflows/k8s-deploy.yml`
- App workload: `config/deployment.yml`
- Monitoring rules: `config/monitoring/url-shortener-monitoring.yml`
- Grafana dashboard import: `config/monitoring/grafana-dashboard-configmap.yml`
- Grafana alerting policy template: `config/monitoring/grafana-alerting-policies-configmap.yml`
- Grafana contact point template: `config/monitoring/grafana-contact-points-secret.yml`
- Monitoring Helm values: `config/monitoring/kube-prometheus-stack-values.yml`
- App ingress: `config/app-ingress.yml`
- Monitoring ingress: `config/monitoring/monitoring-ingress.yml`
- TLS issuer: `config/letsencrypt-issuer.yml`

## Platform Prerequisites

These are not installed by this repo's workflow and must already exist in the cluster:

- `ingress-nginx`
- `cert-manager`
- the `prometheus-basic-auth` secret in the `monitoring` namespace

The workflow assumes those platform pieces are already available and then applies the repo-managed manifests on top.

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
- `https://fifaurlshortener.duckdns.org/health` returns `200`
- service has endpoints
- ingress resolves and serves the app over TLS
- Prometheus target is up
- no fresh error spike in logs

Useful commands:

```bash
kubectl get service url-shortener-service --namespace=default
kubectl get endpoints url-shortener-service --namespace=default
kubectl get ingress --all-namespaces
kubectl get certificate -n default
kubectl logs deployment/url-shortener --namespace=default --since=10m
```
