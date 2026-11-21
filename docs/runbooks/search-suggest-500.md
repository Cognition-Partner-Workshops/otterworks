# Runbook: Search Autocomplete 500 Errors

**Severity:** Critical

## Alert

`SearchSuggestHighErrorRate` -- fires when search-service 5xx rate exceeds 5% over a 1-minute window.

## Symptoms

- Autocomplete suggestions stop appearing in the web app search bar.
- The Chaos Scenarios dashboard shows elevated error rates on the search-service panel.
- Application logs contain `KeyError: '_rankingScore'` in the suggest endpoint handler.

## Investigation Steps

1. Confirm the error in search-service logs:
   ```
   kubectl logs -l app=search-service --tail=100 -n otterworks | grep -i "KeyError\|rankingScore\|500"
   ```
2. Check whether the chaos flag `chaos:search-service:suggest_500` is set in Redis:
   ```
   redis-cli EXISTS chaos:search-service:suggest_500
   ```

3. Confirm the failing requests are `GET /api/v1/search/suggest` and that the
   stack trace ends in the ranking-score sort (`sorted(..., key=lambda s: s["_rankingScore"])`)
   in `services/search-service/app/api/search.py`.

## Root Cause

The autocomplete ranking pipeline sorted MeiliSearch hits by `_rankingScore`
with a direct key lookup. MeiliSearch only returns `_rankingScore` when the
query sets `showRankingScore: true`; the enrichment path never requested it, so
every hit (and the empty-index placeholder) raised `KeyError` and the handler
returned 500. The ranking path also ran outside the handler's `try/except`, so
the usual "degrade to an empty suggestion list" fallback never applied.

## Resolution Steps

1. Immediate mitigation: clear the flag so the legacy path serves traffic:
   `redis-cli DEL chaos:search-service:suggest_500` (or `scripts/inject-bug.sh <tenant> reset`).
2. Code fix (`services/search-service`): `MeiliSearchService.suggest` requests
   `showRankingScore`, reads the score with a default of `0.0`, orders the
   merged document/file hits by score and returns plain strings; the endpoint
   has a single code path wrapped in `try/except` so a backend error yields a
   `200` with an empty list rather than a 5xx.
3. Verify: `cd services/search-service && .venv/bin/pytest tests/test_search_api.py -k suggest`,
   then `curl -s "$API/api/v1/search/suggest?q=te"` returns `200` with the flag
   set or unset. Watch `SearchSuggestHighErrorRate` resolve on the Chaos
   Scenarios dashboard.

## Post-Incident

- Keep the 5xx-rate alert; add a contract test whenever a MeiliSearch response
  field is read with `[]` rather than `.get()`.
- Any future enrichment step in a user-facing read path must run inside the
  handler's degrade-gracefully guard.
