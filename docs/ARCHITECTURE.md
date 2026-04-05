# Architecture Diagram

This is the architecture we actually built and operated for the hackathon.

## ASCII Diagram

```text
+---------------------+
| Users / k6 / Judges |
+---------------------+
           |
           v
+---------------------------+
| DigitalOcean LoadBalancer |
+---------------------------+
           |
           v
+--------------------+
| Kubernetes Service |
+--------------------+
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
```

## Mermaid Diagram

```mermaid
flowchart LR
    U[Users / k6 / Judges] --> LB[DigitalOcean Load Balancer]
    LB --> SVC[Kubernetes Service]
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
```

## Notes

- the app runs as a Kubernetes `Deployment`
- replicas are fronted by a `LoadBalancer` service
- each pod serves traffic through Gunicorn, which hosts the Flask app workers
- Prometheus scrapes the app metrics endpoint
- Grafana is used for dashboards and live alert delivery to Discord
- Redis is only used for short-code caching, not as a primary datastore
