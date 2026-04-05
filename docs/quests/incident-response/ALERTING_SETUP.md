## Alerting Setup

This repo now exposes Prometheus metrics at `/metrics/prometheus` and includes a `ServiceMonitor` plus alert rules in [config/monitoring/url-shortener-monitoring.yml](/c:/Aarav/coding/PE-Hackathon-Template-2026-fifa/config/monitoring/url-shortener-monitoring.yml).

Grafana state that should survive pod replacement now also has repo-backed artifacts:

- dashboard import via [config/monitoring/grafana-dashboard-configmap.yml](/c:/Aarav/coding/PE-Hackathon-Template-2026-fifa/config/monitoring/grafana-dashboard-configmap.yml)
- alert routing policy via [config/monitoring/grafana-alerting-policies-configmap.yml](/c:/Aarav/coding/PE-Hackathon-Template-2026-fifa/config/monitoring/grafana-alerting-policies-configmap.yml)
- contact point template via [config/monitoring/grafana-contact-points-secret.yml](/c:/Aarav/coding/PE-Hackathon-Template-2026-fifa/config/monitoring/grafana-contact-points-secret.yml)
- Grafana persistence and provisioning mounts via [config/monitoring/kube-prometheus-stack-values.yml](/c:/Aarav/coding/PE-Hackathon-Template-2026-fifa/config/monitoring/kube-prometheus-stack-values.yml)

### Why not StatsD

Use Prometheus here, not StatsD.

- Prometheus is a direct fit for Kubernetes scraping, alert rules, and later Grafana dashboards.
- StatsD would require an extra exporter or agent before you can alert on the data.
- Silver and Gold both want alerting plus dashboards, so Prometheus is the shorter path.

### Cluster Setup

1. Install `kube-prometheus-stack` into a `monitoring` namespace.
2. Apply [config/monitoring/url-shortener-monitoring.yml](/c:/Aarav/coding/PE-Hackathon-Template-2026-fifa/config/monitoring/url-shortener-monitoring.yml).
3. Verify Prometheus is scraping `url-shortener-service` on `/metrics/prometheus`.

### Discord Alerts

The repo now keeps the alert expressions themselves in Prometheus rules and the Grafana routing layer in provisioning files.

1. Create a Discord webhook for your alert channel.
2. Store that webhook in the `GRAFANA_DISCORD_WEBHOOK_URL` GitHub Actions secret.
3. Let the workflow render `grafana-contact-points-secret.yml` into a cluster secret.
4. Let the workflow run `helm upgrade --install` for `kube-prometheus-stack` with `config/monitoring/kube-prometheus-stack-values.yml` so Grafana starts with the contact point and notification policy already defined.

Grafana is the cleanest option because Discord webhooks accept Grafana's webhook payload format more naturally than raw Alertmanager notifications.

### Demo Plan

For Silver:

1. Scale the deployment to zero or break the app startup.
2. Wait for the `UrlShortenerServiceDown` alert to fire.
3. Show the Discord notification and the rule YAML.

For high error rate:

1. Deploy a broken build or force repeated `5xx` responses.
2. Wait for the `UrlShortenerHighErrorRate` alert to fire.
3. Show the Discord notification and the rule YAML.
