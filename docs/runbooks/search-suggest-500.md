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

3. Reproduce locally: `GET /api/v1/search/suggest?q=te` against search-service returns 500 while the flag is set
   (`TypeError: string indices must be integers` or `KeyError: '_rankingScore'` in the `suggest()` handler).

## Root Cause

`suggest()` in `services/search-service/app/api/search.py` had a ranking-score enrichment branch that sorted
`MeiliSearchService.suggest()` results by `s["_rankingScore"]`. That method returns plain title strings, and
MeiliSearch only includes `_rankingScore` when `showRankingScore: true` is sent, so the sort always raised.
The branch sat outside the handler's `try/except`, so the exception surfaced as a 500.

## Resolution Steps

1. Clear the chaos flag to stop the bleeding: `redis-cli DEL chaos:search-service:suggest_500`.
2. Deploy the fix: `MeiliSearchService.suggest()` requests `showRankingScore` and orders hits by `_rankingScore`
   (hits without a score keep their order); the handler has a single code path inside `try/except`, so a
   backend failure returns `200` with empty suggestions instead of a 5xx.
3. Confirm `SearchSuggestHighErrorRate` resolves and the search bar shows suggestions again.

## Post-Incident

- Keep `/suggest` degrade-to-empty: autocomplete is best-effort and must never fail the search bar.
- Any ranking enrichment belongs in `MeiliSearchService.suggest()` with a test, not in the handler.
