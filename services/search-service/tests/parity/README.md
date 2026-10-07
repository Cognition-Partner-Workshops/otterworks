# Search service parity harness

Black-box record/replay of the search service's HTTP behaviour, used to prove
the Flask → FastAPI translation (see `../../TRANSLATION_GUIDE.md`) keeps every
route, status code, header and metric identical. It is not collected by
`pytest tests/` (see `conftest.py`); it drives a running service by URL.

| File | Purpose |
|------|---------|
| `cases.py` | Ordered cases: HTTP requests plus control steps (restart service, set/clear the chaos flag in Redis, stop/start MeiliSearch). |
| `harness.py` | `record` runs `cases.py`; `replay` re-sends the requests stored in the transcript and diffs. |
| `flask_transcript.json` | Recorded against the Flask app: request → status, `Content-Type`, `Allow`, `Vary`, `Location`, `Access-Control-*`, body. |
| `flask_metrics.json` | `/metrics` at the end of the run: the four `search_service_*` families, label names, label values and samples. |
| `compose.parity.yml` | Compose overlay: sets `SEARCH_SERVICE_TOKEN`, `REQUIRE_AUTH=true`, single uvicorn worker. |

## Run

From the repo root (the base `docker-compose.yml` does not define
`redis`/`meilisearch`, so the infra file is needed too):

```bash
C="docker compose -f docker-compose.infra.yml -f docker-compose.yml -f services/search-service/tests/parity/compose.parity.yml"
$C up -d --build redis meilisearch search-service

cd services/search-service
python3 -m tests.parity.harness replay            # exit 0 = zero diffs
python3 -m tests.parity.harness record            # only to re-baseline
```

Python 3.10+ stdlib only. `--base-url`, `--meili-url`, `--compose`,
`--transcript`, `--metrics` (and `PARITY_*` env vars) override the defaults;
`replay --out-dir DIR` also writes the replayed transcript for inspection.

The harness restarts `search-service` first so counters and in-memory search
analytics start from zero, and it briefly stops MeiliSearch for the 503 cases.

## Normalisation

- Only the headers listed above are recorded; `Date`, `Server`,
  `Content-Length` are ignored. Token order in `Allow`, `Vary` and
  `Access-Control-Allow-{Methods,Headers}` is sorted.
- JSON bodies are compared parsed (key order is not significant); non-JSON
  bodies (Flask/Werkzeug HTML error pages) are compared verbatim.
- `/metrics` response bodies are reduced to the list of `search_service_*`
  families present; the full detail lives in `flask_metrics.json`, where
  `*_created`, histogram `_bucket` and `_sum` values are `<volatile>` and
  counter / `_count` values are kept.

## Why one worker

The image runs two worker processes (`gunicorn --workers 2` when the Flask
transcript was recorded, `uvicorn --workers 2` now). Prometheus metrics and
search analytics are per-process in-memory state, so with two workers
`/metrics` and `/analytics` depend on which worker answered and cannot replay.
The overlay pins one worker (`gunicorn --workers 1 --threads 4` for the Flask
recording, `uvicorn --workers 1` for the FastAPI replay).
