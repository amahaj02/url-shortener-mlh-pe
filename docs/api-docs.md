# API Docs

This is the current public API surface in the repo.

## Health And Metrics

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness/readiness check |
| `GET` | `/metrics` | JSON process metrics for Bronze observability |
| `GET` | `/metrics/prometheus` | Prometheus-format metrics for alerting and dashboards |

## Users

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/users` | List users, optional pagination |
| `POST` | `/users` | Create a user |
| `GET` | `/users/<id>` | Fetch one user |
| `PUT` | `/users/<id>` | Update username/email |
| `DELETE` | `/users/<id>` | Delete a user |
| `POST` | `/users/bulk` | Bulk import users from uploaded CSV |

### `POST /users`

Example body:

```json
{
  "username": "alice",
  "email": "alice@example.com"
}
```

Behavior notes:

- exact duplicate create is treated idempotently and returns `201`
- conflicting username/email for a different record returns `409`

## URLs

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/<short_code>` | Redirect a short code to the original URL |
| `GET` | `/urls` | List URLs, with filters and pagination |
| `POST` | `/urls` | Create a shortened URL |
| `GET` | `/urls/<id>` | Fetch one shortened URL |
| `PUT` | `/urls/<id>` | Update title, active state, or destination |
| `DELETE` | `/urls/<id>` | Delete a shortened URL |

### `POST /urls`

Example body:

```json
{
  "user_id": 1,
  "original_url": "https://example.com/docs",
  "title": "Docs"
}
```

Behavior notes:

- input must be a JSON object
- `user_id` must be a real JSON integer, not a string or boolean
- only `http` and `https` URLs are accepted
- if the same user submits the same destination again, the current app returns the existing URL record
- inactive short links resolve as `404`, not `410`

## Events

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/events` | List events, with filters |
| `POST` | `/events` | Create an event manually |

### `POST /events`

Example body:

```json
{
  "url_id": 10,
  "user_id": 1,
  "event_type": "click",
  "details": {
    "referrer": "https://google.com"
  }
}
```

Behavior notes:

- `details` must be a JSON object or `null`
- missing `url_id` or `user_id` references return `404`

## Maintenance

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/admin/clear-db` | Describe the maintenance endpoint |
| `POST` | `/admin/clear-db` | Delete all rows from known tables and clear cache |

This route is intentionally still public in this repo because the project chose not to harden or remove it during the hackathon sweep.
