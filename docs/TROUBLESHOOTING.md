# Troubleshooting

These are the issues that actually came up during the hackathon work and how we handled them.

## Hidden URL reliability test kept failing

Symptom:

- one advanced hidden challenge around URLs kept returning "incorrect output"

Fix:

- inactive short links were changed to return `404` instead of `410`
- that matched the evaluator's expected behavior

## Intermittent load-test timeouts

Symptom:

- k6 runs showed a small number of request timeouts even when p95 latency looked fine

Fix:

- added structured request IDs
- added SQL timing logs
- used cache and metrics to separate "few stuck requests" from "whole service is slow"

## Grafana alert didn't notify Discord at first

Symptom:

- alert logic existed, but no Discord notification arrived

Fix:

- used Grafana-managed alerting with a Discord webhook contact point
- made sure the rule labels matched the notification policy
- waited through the pending period so the alert could move from pending to firing

## Grafana UI stopped behaving correctly

Symptom:

- Grafana logs showed SQLite locking errors

Fix:

- restart the Grafana pod first
- if that is not enough, inspect the persistence layer because the issue is inside Grafana's own SQLite store, not the app

## Coverage run blocked on Windows

Symptom:

- `.coverage` file in the repo root was locked and coverage plugins failed to write over it

Fix:

- run the test suite separately from coverage when needed
- write coverage data to a temporary path outside the locked file

## Public malformed HTTP requests in logs

Symptom:

- Gunicorn logged invalid request lines, headers, and methods from random IPs

Fix:

- treated them as normal internet scan noise
- relied on Gunicorn rejecting them before Flask handled them
- kept the focus on app-layer 4xx/5xx metrics instead
