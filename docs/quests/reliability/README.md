# Reliability Quest

This folder is the reliability write-up for the hackathon submission. It is meant to be readable by judges first and engineers second.

## Bronze: The Shield

What we shipped:

- `pytest` test suite covering models, routes, validation, and core helper behavior
- GitHub Actions test gate in `.github/workflows/k8s-deploy.yml`
- `GET /health` endpoint in `app/__init__.py`

Why it matters:

- every push to the deployment branches runs the test job first
- the app exposes a simple health probe for local checks, Kubernetes probes, and load balancer checks

Where to look:

- Tests: `tests/`
- CI gate: `.github/workflows/k8s-deploy.yml`
- Health endpoint: `app/__init__.py`

## Silver: The Fortress

What we added:

- coverage enforcement with `pytest-cov` in `pyproject.toml`
- integration tests that create users, create URLs, update URLs, redirect, and verify database state
- failure documentation for 404, 405, 500, and 503 behavior

What blocks bad code from shipping:

- the `deploy` job depends on the `test` job, so a failing test run stops the rollout
- rollout health is checked with `kubectl rollout status`, so a broken deploy still fails even after image push

Where to look:

- Coverage config: `pyproject.toml`
- Integration tests: `tests/test_api_integration.py`
- Failure behavior: `docs/failure_modes.md`

## Gold: The Immortal

What moved this from "tested" to "resilient":

- coverage raised past the Gold target
- strict JSON validation so the API returns clean JSON errors instead of stack traces
- Kubernetes probes and deployment settings so unhealthy pods are replaced automatically
- a failure manual that explains what breaks, how it fails, and how to demonstrate recovery

Current result:

- full test suite passes
- coverage is above the 70% Gold target
- malformed payloads, missing resources, and database failures return JSON responses

Notes on hidden reliability checks:

- the project now handles strict JSON object validation, boolean-vs-integer edge cases, duplicate user creation idempotently, inactive short links as `404`, and a long list of URL/event edge cases
- those behaviors were all driven by tests and failure analysis, not just by happy-path implementation

## Bonus Documentation Links

- API docs: [api-docs.md](../../api-docs.md)
- Failure manual: [failure_modes.md](../../failure_modes.md)
- Deploy and rollback guide: [deploy_guide.md](../../deploy_guide.md)
- Troubleshooting notes: [troubleshooting.md](../../troubleshooting.md)
