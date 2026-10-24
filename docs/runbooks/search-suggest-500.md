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

3. Reproduce against the pod directly and confirm the handler (not MeiliSearch) is failing:
   ```
   kubectl -n otterworks port-forward svc/search-service 8087:8087 &
   curl -s -o /dev/null -w '%{http_code}\n' 'http://localhost:8087/api/v1/search/suggest?q=te'
   ```
   A `500` here with `KeyError: '_rankingScore'` or `TypeError: string indices must be integers`
   in the logs means the ranking-score enrichment in `suggest()` is indexing `_rankingScore`
   on hits that never carried it.

## Root Cause

`GET /api/v1/search/suggest` sorted suggestions with `s["_rankingScore"]`, but
`MeiliSearchService.suggest()` returned plain title strings and never asked MeiliSearch for the
score (`showRankingScore` was not set, so the field is absent from hits). Every request on that
path raised and surfaced as a 500.

## Resolution Steps

1. Mitigate: clear the chaos flag so traffic falls back to the unranked path while the fix rolls out:
   ```
   redis-cli DEL chaos:search-service:suggest_500
   ```
2. Fix (`services/search-service`): request `showRankingScore: true` in `MeiliSearchService.suggest()`,
   sort with `hit.get("_rankingScore", 0.0)` so a missing score ranks last instead of raising, and
   keep the whole handler inside the existing `try`/`except` that returns `200` with an empty list
   on backend failure. Tests: `tests/test_search_api.py::TestSuggestEndpoint`.
3. Deploy search-service and confirm `SearchSuggestHighErrorRate` resolves; the 5xx rate on the
   search-service panel should return to 0 within one evaluation window.

## Post-Incident

- Autocomplete is best-effort: any exception in `suggest()` must degrade to `200` with
  `{"suggestions": []}`, never a 5xx.
- MeiliSearch only returns `_rankingScore` when `showRankingScore` is requested; never index into
  it unconditionally.
