## Alerting Setup

This repo now exposes Prometheus metrics at `/metrics/prometheus` and includes a `ServiceMonitor` plus alert rules in [config/monitoring/url-shortener-monitoring.yml](/c:/Aarav/coding/PE-Hackathon-Template-2026-fifa/config/monitoring/url-shortener-monitoring.yml).

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

The simplest Discord path is Grafana Alerting with a Discord webhook contact point.

1. Create a Discord webhook for your alert channel.
2. In Grafana, create a contact point of type `Webhook`.
3. Paste the Discord webhook URL.
4. Route the `UrlShortenerServiceDown` and `UrlShortenerHighErrorRate` alerts to that contact point.

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
