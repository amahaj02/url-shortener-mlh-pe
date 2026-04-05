# MLH PE Hackathon — Flask + Peewee + PostgreSQL Template

A minimal hackathon starter template. You get the scaffolding and database wiring — you build the models, routes, and CSV loading logic.

**Stack:** Flask · Peewee ORM · PostgreSQL · uv

## Important

Use the seed files from the [MLH PE Hackathon](https://mlh-pe-hackathon.com) platform. They give you the schema/data needed for testing and submission. If anything is unclear, ask in Discord or the platform Q&A.

## Prerequisites

- **uv** — a fast Python package manager that handles Python versions, virtual environments, and dependencies automatically.
  Install it with:

    ```bash
    # macOS / Linux
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # Windows (PowerShell)
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

    For other methods see the [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/).

- PostgreSQL running locally (you can use Docker or a local instance)

## uv Basics

`uv` manages your Python version, virtual environment, and dependencies automatically — no manual `python -m venv` needed.

| Command               | What it does                                             |
| --------------------- | -------------------------------------------------------- |
| `uv sync`             | Install all dependencies (creates `.venv` automatically) |
| `uv run <script>`     | Run a script using the project's virtual environment     |
| `uv add <package>`    | Add a new dependency                                     |
| `uv remove <package>` | Remove a dependency                                      |

## Quick Start

```bash
# 1. Clone the repo
git clone <repo-url> && cd mlh-pe-hackathon

# 2. Install dependencies
uv sync

# 3. Create the database
createdb hackathon_db

# 4. Configure environment
cp .env.example .env   # edit if your DB credentials differ

# 5. Run the server (same env as `uv sync`)
uv run run.py

# 6. Verify
curl http://localhost:3000/health
# → {"status":"ok"}
```

## Production Runtime (DigitalOcean)

`uv run run.py` starts **Gunicorn** with `deployment/gunicorn.conf.py` (same idea as the Docker `CMD`). You can also invoke Gunicorn directly:

```bash
uv run gunicorn -c deployment/gunicorn.conf.py run:app
```

- Bind address: set `GUNICORN_BIND` (e.g. `0.0.0.0:3000` locally), or rely on `HOST` + `PORT` when `GUNICORN_BIND` is unset.
- **Docker / Kubernetes** listen on **8000** (`Dockerfile` and `config/deployment.yml` set `PORT` and `GUNICORN_BIND` accordingly).
- `workers * threads` is auto-capped to stay within your DB pool budget.
- Keep `DATABASE_MAX_CONNECTIONS` below your managed Postgres limit across all app instances.
- Tune `WEB_CONCURRENCY` and `GUNICORN_THREADS` in `.env`.

## Project Structure

```
mlh-pe-hackathon/
├── app/
│   ├── __init__.py          # App factory (create_app)
│   ├── database.py          # DatabaseProxy, BaseModel, connection hooks
│   ├── models/
│   │   └── __init__.py      # Import your models here
│   └── routes/
│       └── __init__.py      # register_routes() — add blueprints here
├── .env.example             # DB connection template
├── .gitignore               # Python + uv gitignore
├── .python-version          # Pin Python version for uv
├── pyproject.toml           # Project metadata + dependencies
├── run.py                   # Entry point: uv run run.py
└── README.md
```

## How to Add a Model

1. Create a file in `app/models/`, e.g. `app/models/product.py`:

```python
from peewee import CharField, DecimalField, IntegerField

from app.database import BaseModel


class Product(BaseModel):
    name = CharField()
    category = CharField()
    price = DecimalField(decimal_places=2)
    stock = IntegerField()
```

2. Import it in `app/models/__init__.py`:

```python
from app.models.product import Product
```

3. Create the table (run once in a Python shell or a setup script):

```python
from app.database import db
from app.models.product import Product

db.create_tables([Product])
```

## How to Add Routes

1. Create a blueprint in `app/routes/`, e.g. `app/routes/products.py`:

```python
from flask import Blueprint, jsonify
from playhouse.shortcuts import model_to_dict

from app.models.product import Product

products_bp = Blueprint("products", __name__)


@products_bp.route("/products")
def list_products():
    products = Product.select()
    return jsonify([model_to_dict(p) for p in products])
```

2. Register it in `app/routes/__init__.py`:

```python
def register_routes(app):
    from app.routes.products import products_bp
    app.register_blueprint(products_bp)
```

## How to Load CSV Data

```python
import csv
from peewee import chunked
from app.database import db
from app.models.product import Product

def load_csv(filepath):
    with open(filepath, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    with db.atomic():
        for batch in chunked(rows, 100):
            Product.insert_many(batch).execute()
```

## Useful Peewee Patterns

```python
from peewee import fn
from playhouse.shortcuts import model_to_dict

# Select all
products = Product.select()

# Filter
cheap = Product.select().where(Product.price < 10)

# Get by ID
p = Product.get_by_id(1)

# Create
Product.create(name="Widget", category="Tools", price=9.99, stock=50)

# Convert to dict (great for JSON responses)
model_to_dict(p)

# Aggregations
avg_price = Product.select(fn.AVG(Product.price)).scalar()
total = Product.select(fn.SUM(Product.stock)).scalar()

# Group by
from peewee import fn
query = (Product
         .select(Product.category, fn.COUNT(Product.id).alias("count"))
         .group_by(Product.category))
```

## Tips

- Use `model_to_dict` from `playhouse.shortcuts` to convert model instances to dictionaries for JSON responses.
- Wrap bulk inserts in `db.atomic()` for transactional safety and performance.
- In non-testing mode, the template opens/closes DB connections per request to keep pooled connections healthy.
- Check `.env.example` for all available configuration options.

## Load Testing with k6 (50 Concurrent Users)

> For load tests, set `TESTING=false` in `.env` so requests hit PostgreSQL. SQLite test mode can lock under concurrency.

1. Start the API:

```bash
uv run run.py
```

2. In a separate terminal, run the k6 script:

```bash
k6 run -e BASE_URL=http://localhost:3000 -e DURATION=60s tests/perf/k6_50_vus.js
```

- The script uses `constant-vus` with `vus: 50` for the full duration.
- Update `BASE_URL` if your API is not running on `localhost:3000`.

## Observability Bronze

### Structured JSON Logs

- Application logs are emitted as JSON with:
  - `timestamp`
  - `level`
  - `logger`
  - `message`
- HTTP request logs also include fields such as:
  - `component`
  - `client_ip`
  - `method`
  - `path`
  - `status_code`
  - `duration_ms`

### Metrics

- `GET /metrics` returns JSON with CPU and memory usage for the running process.

Example:

```bash
curl http://localhost:3000/metrics
```

### Viewing Logs Without SSH

- Kubernetes:

```bash
kubectl logs deployment/url-shortener --namespace=default -f
```

- k9s:
  - open the pod or deployment
  - press `l` to stream logs

This gives you live structured logs without shelling into the container.

## Incident Response Gold

### Command Center Dashboard

- Grafana dashboard JSON: [config/monitoring/grafana-dashboard-url-shortener.json](/c:/Aarav/coding/PE-Hackathon-Template-2026-fifa/config/monitoring/grafana-dashboard-url-shortener.json)
- Tracks the four golden signals:
  - latency
  - traffic
  - errors
  - saturation

Import the dashboard JSON into Grafana, select your Prometheus data source, and use it for screenshots and live diagnosis.

### Runbook

- Incident runbook: [docs/RUNBOOK.md](/c:/Aarav/coding/PE-Hackathon-Template-2026-fifa/docs/RUNBOOK.md)

### Sherlock Mode

Typical diagnosis flow:

1. Look at latency first.
2. Check whether traffic changed materially.
3. Compare error rate and saturation to see whether the issue is load, application failure, or DB pressure.
4. Confirm the suspected cause using structured app logs and SQL timing logs.
