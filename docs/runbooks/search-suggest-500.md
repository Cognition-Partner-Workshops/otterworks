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

3. Reproduce locally against the mocked backend:
   ```
   cd services/search-service && .venv/bin/pytest tests/test_search_api.py -k Ranked
   ```

## Root Cause

With the flag set, `suggest()` in `services/search-service/app/api/search.py` ran a
ranking-score enrichment step outside its `try`/`except`: it sorted the
`MeiliSearchService.suggest()` result with `s["_rankingScore"]`. That result is a
list of strings (`TypeError: string indices must be integers`), and even as hit
dicts MeiliSearch only returns `_rankingScore` when `showRankingScore` is
requested (`KeyError: '_rankingScore'`). Either exception escaped the handler as
an HTTP 500 and fed `SearchSuggestHighErrorRate`.

## Resolution Steps

1. `MeiliSearchService.suggest(prefix, ranked=True)` requests `showRankingScore`,
   reads the score with `hit.get("_rankingScore")` (missing → 0.0) and orders
   titles by score across both indexes.
2. The handler calls that path inside the existing `try`/`except`, so any backend
   failure degrades to `{"suggestions": []}` with HTTP 200 instead of a 5xx.
3. Roll out search-service and watch the search-service panel on the Chaos
   Scenarios dashboard; the alert resolves once the 5xx rate drops below 5%.
4. Clear the flag if it was injected for a lab: `scripts/inject-bug.sh <ID> reset`.

## Post-Incident

- Autocomplete is best-effort: the handler never returns 5xx for backend errors.
- Regression tests: `TestSuggestRankedEndpoint` in
  `services/search-service/tests/test_search_api.py`.
