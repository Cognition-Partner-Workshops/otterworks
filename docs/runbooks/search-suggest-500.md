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

3. Reproduce against the service directly (bypassing the gateway) and confirm the
   handler, not MeiliSearch, is failing:
   ```
   curl -i "http://localhost:8087/api/v1/search/suggest?q=te"
   ```
   A `500` with a `KeyError: '_rankingScore'` or `TypeError: string indices must be
   integers` traceback points at the ranking-score enrichment step in
   `services/search-service/app/api/search.py::suggest`.

## Root Cause

The autocomplete ranking step sorted suggestions with `s["_rankingScore"]`, but
MeiliSearch only returns `_rankingScore` when `showRankingScore: true` is sent
with the query, and `MeiliSearchService.suggest` returns plain strings. The key
lookup raised inside the handler, outside its `try`/`except`, so every
`/suggest` call returned 500 while the path was active.

## Resolution Steps

1. Rank inside `MeiliSearchService.suggest`: request `showRankingScore: True`,
   read the score with `hit.get("_rankingScore", 0.0)`, sort, and return strings.
2. Keep the `/suggest` handler on a single code path wrapped in `try`/`except`
   so a backend failure degrades to `{"suggestions": []}` with HTTP 200 instead
   of a 5xx (autocomplete is best-effort; the search bar must not break).
3. Deploy search-service and confirm `SearchSuggestHighErrorRate` resolves:
   ```
   curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:8087/api/v1/search/suggest?q=te"
   ```
   must return `200` with the flag set or unset.

## Post-Incident

- Add tests for hits with and without `_rankingScore` and for a MeiliSearch
  failure (`tests/test_search_api.py::TestSuggestEndpoint`).
- Any future "enrichment" of MeiliSearch hits must read optional fields with
  `.get()` and stay inside the handler's error boundary.
