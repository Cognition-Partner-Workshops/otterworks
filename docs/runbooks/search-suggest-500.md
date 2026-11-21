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

3. Reproduce against the pod directly (bypasses the gateway):
   ```
   kubectl -n otterworks port-forward svc/search-service 8087:8087 &
   curl -s -o /dev/null -w '%{http_code}\n' 'http://localhost:8087/api/v1/search/suggest?q=te'
   ```
   `500` with `KeyError: '_rankingScore'` or `TypeError: string indices must be
   integers` in the log confirms the ranking-score enrichment path is the cause.

## Root Cause

The "ranking-score enrichment" in `suggest()` (`services/search-service/app/api/search.py`)
sorted the output of `MeiliSearchService.suggest()` by `s["_rankingScore"]`. That method
returns plain title strings, and MeiliSearch only emits `_rankingScore` when the search
request sets `showRankingScore: true`, so the lookup raised on every call. The branch ran
outside the handler's `try/except`, so the exception escaped as a 500 instead of degrading
to an empty suggestion list.

## Resolution Steps

1. Deploy a search-service build where relevance ordering lives in
   `MeiliSearchService.suggest()` (requests `showRankingScore`, sorts by `_rankingScore`
   with missing scores last) and the handler has a single path inside `try/except`.
2. If the flag is set, clear it so no stale toggle remains: `redis-cli DEL chaos:search-service:suggest_500`.
3. Confirm recovery: the curl above returns `200`, and the alert's expression
   (`search_service_requests_total{status=~"5.."}` / total) drops back under 5% within
   the 1-minute window.

## Post-Incident

- `/suggest` must never return 5xx for a ranking or backend failure; the contract is
  `200 {"suggestions": [], "query": q}` on degradation (covered by
  `tests/test_search_api.py::TestSuggestEndpoint`).
- Any enrichment that depends on an optional MeiliSearch field must request it
  explicitly and read it with a default.
