# Incident Response Quest

This folder is the operations-facing write-up for observability, alerting, and response.

## Bronze: The Watchtower

What we implemented:

- JSON logs with timestamps, levels, logger names, and structured fields
- `GET /metrics` for JSON CPU and memory data
- `GET /metrics/prometheus` for Prometheus scraping
- log access through `kubectl logs` and k9s, so no SSH is needed
- public Grafana and Prometheus ingress paths for judge/demo access, with Grafana login and Prometheus basic auth

Where to look:

- logging setup: `app/logging_config.py`
- app metrics endpoints: `app/__init__.py`
- Prometheus metrics instrumentation: `app/prometheus_metrics.py`
- monitoring ingress: `config/monitoring/monitoring-ingress.yml`

## Silver: The Alarm

What we implemented:

- alert logic in `config/monitoring/url-shortener-monitoring.yml`
- Grafana + Discord notification flow for live alerts
- service-down, high-error-rate, and high-CPU rules
- monitoring ingress protected with Grafana login and Prometheus basic auth

What actually woke the on-call engineer in the demo:

- Grafana-managed alert routed to a Discord webhook
- firing notification shown on Discord once the pending period completed

Notes for judges:

- the rule definitions live in repo YAML
- the Discord contact point itself was configured in Grafana UI against the webhook, so that part is operational config rather than repo code

## Gold: The Command Center

What we implemented:

- Grafana dashboard JSON covering latency, traffic, errors, and saturation
- a runbook for the alert scenarios
- a repeatable "Sherlock mode" narrative for diagnosing issues from dashboard plus logs
- public app ingress with DuckDNS + Let's Encrypt TLS for the main service

Supporting docs:

- Architecture diagram: [../../architecture.md](../../architecture.md)
- Deploy guide: [../../deploy_guide.md](../../deploy_guide.md)
- Troubleshooting guide: [../../troubleshooting.md](../../troubleshooting.md)
- Config reference: [../../config_reference.md](../../config_reference.md)
- Runbook: [../../runbook.md](../../runbook.md)
- Alerting setup: [../../alerting_setup.md](../../alerting_setup.md)
