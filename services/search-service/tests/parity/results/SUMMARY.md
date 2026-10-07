# Parity replay on FastAPI (final run, UNT3-9)

Run on `devin/search-service-fastapi` @ `cfee9ee6`, 2026-10-07. Flask baseline image built from `main` @ `af476560`.

Stack: `docker compose -f docker-compose.infra.yml -f docker-compose.yml -f services/search-service/tests/parity/compose.parity.yml up -d --build redis meilisearch search-service`
(uvicorn, 1 worker, `REQUIRE_AUTH=true`, `SEARCH_SERVICE_TOKEN=parity-service-token`, `SQS_ENABLED=true` as in Compose).
Images `redis:7-alpine`, `getmeili/meilisearch:v1.6`, `python:3.12-slim` pulled from `mirror.gcr.io` and retagged.

| Check | Command | Result |
|-------|---------|--------|
| Transcript replay | `python3 -m tests.parity.harness replay --out-dir tests/parity/results` (cwd `services/search-service`) | 130/130 HTTP cases, 0 differing, exit 0 — [replay.log](replay.log) |
| Transcript diff | replayed transcript vs `flask_transcript.json` | byte-identical — [transcript_diff.txt](transcript_diff.txt) |
| Metrics diff | replayed `/metrics` dump vs `flask_metrics.json` | byte-identical — [metrics_diff.txt](metrics_diff.txt) |
| Contract tests (FastAPI) | `SEARCH_SERVICE_URL=http://localhost:8087 pytest tests/contract/test_search_contract.py -v` (repo root) | 16 passed, 2 failed — [contract_fastapi.log](contract_fastapi.log) |
| Contract tests (Flask `main`) | same, against the Flask image on :8097 with the same env | 16 passed, 2 failed — [contract_flask_main.log](contract_flask_main.log) |

The chaos-flag cases (`chaos.suggest.*`, `chaos:search-service:suggest_500`) are part of the 130 and replay identically.

## Pre-existing contract failures (kept on purpose)

`test_index_document_missing_body` and `test_index_file_missing_body` fail identically on Flask `main` and FastAPI:
`POST /api/v1/search/index/{document,file}` with `Content-Type: application/json` and no body returns
`400`, `text/html; charset=utf-8`, the Werkzeug "400 Bad Request" HTML page (167 bytes), so `resp.json()` raises
`JSONDecodeError`. Raw responses from both side by side: [missing_body_responses.txt](missing_body_responses.txt).
The two contract logs are identical apart from timings/addresses. Kept failing for strict HTML 400 parity (human decision).

## Accepted differences (outside what the harness records; for human approval)

1. HTTP status-line reason phrase: Flask/gunicorn sends `400 BAD REQUEST`, uvicorn sends `400 Bad Request`. Clients ignore the reason phrase (RFC 9112 §4); status codes are identical.
2. `Connection: keep-alive` is sent by gunicorn and not by uvicorn on these responses; header-name casing also differs (`Content-Type` vs `content-type`; HTTP header names are case-insensitive). Not part of the recorded header set.

No difference was found in routes, methods, status codes, `{"error": ...}` bodies, HTML error bodies, CORS headers, `Content-Type` or metric names/labels/values.

Note: with `SQS_ENABLED=true` and no LocalStack in this stack, both Flask and FastAPI log `EndpointConnectionError` from the SQS consumer and keep serving HTTP; it does not affect any case.
