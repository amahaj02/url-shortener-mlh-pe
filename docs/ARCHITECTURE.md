# Architecture Diagram

This is the architecture we actually built and operated for the hackathon.

## ASCII Diagram

```text
+---------------------+
| Users / k6 / Judges |
+---------------------+
           |
           v
+----------------------------------+
| ingress-nginx LoadBalancer       |
| 134.199.241.177                  |
+----------------------------------+
           |
           v
+--------------------------------------+
| Ingress Rules                        |
| fifaurlshortener.duckdns.org         |
| grafana.*.nip.io / prometheus.*.nip.io |
+--------------------------------------+
      |                     |
      v                     v
+--------------------+   +-----------------------------+
| App Service        |   | Monitoring Services         |
| url-shortener      |   | Grafana / Prometheus        |
+--------------------+   +-----------------------------+
           |
           v
+-----------------------------------------------+
| url-shortener Deployment (3+ app pods)        |
|                                               |
|  +------------------+    +------------------+ |
|  | App Pod          |    | App Pod          | |
|  | Gunicorn         |    | Gunicorn         | |
|  | Flask App        |    | Flask App        | |
|  +------------------+    +------------------+ |
|                                               |
|  +------------------+                         |
|  | App Pod          |                         |
|  | Gunicorn         |                         |
|  | Flask App        |                         |
|  +------------------+                         |
+-----------------------------------------------+
        |                       |           |
        v                       v           v
+---------------+      +---------------+   +----------------+
| PostgreSQL    |      | Redis Cache   |   | /metrics/prom. |
+---------------+      +---------------+   +----------------+
                                                |
                                                v
                                         +-------------+
                                         | Prometheus  |
                                         +-------------+
                                                |
                                                v
                                         +-------------+
                                         | Grafana     |
                                         +-------------+
                                                |
                                                v
                                         +-------------+
                                         | Discord     |
                                         | Webhook     |
                                         +-------------+

+------------------+         +----------------+
| cert-manager     | ------> | Let's Encrypt  |
+------------------+         +----------------+
          \___________________________/
                      |
                      v
             issues TLS for ingress
```

## Mermaid Diagram

```mermaid
flowchart LR
    U[Users / k6 / Judges] --> NGINX[ingress-nginx Load Balancer]
    NGINX --> ING[Ingress Rules]
    ING --> SVC[Kubernetes Service]
    SVC --> POD1[App Pod 1]
    SVC --> POD2[App Pod 2]
    SVC --> POD3[App Pod 3+]

    POD1 --> G1[Gunicorn]
    POD2 --> G2[Gunicorn]
    POD3 --> G3[Gunicorn]

    G1 --> F1[Flask App]
    G2 --> F2[Flask App]
    G3 --> F3[Flask App]

    F1 --> PG[(PostgreSQL)]
    F2 --> PG
    F3 --> PG

    F1 --> R[(Redis)]
    F2 --> R
    F3 --> R

    P[Prometheus] -->|scrapes /metrics/prometheus| SVC
    G[Grafana] --> P
    G --> D[Discord Webhook]
    CM[cert-manager] --> LE[Let's Encrypt]
    LE --> ING
```

## Notes

- the app runs as a Kubernetes `Deployment`
- public traffic enters through `ingress-nginx`, not directly through the app service
- the main app is exposed at `https://fifaurlshortener.duckdns.org`
- TLS is issued by Let's Encrypt through `cert-manager` using `config/letsencrypt-issuer.yml`
- application routing is defined in `config/app-ingress.yml`
- Grafana and Prometheus are exposed separately through `config/monitoring/monitoring-ingress.yml`
- each pod serves traffic through Gunicorn, which hosts the Flask app workers
- Prometheus scrapes the app metrics endpoint
- Grafana is used for dashboards and live alert delivery to Discord
- Redis is only used for short-code caching, not as a primary datastore
