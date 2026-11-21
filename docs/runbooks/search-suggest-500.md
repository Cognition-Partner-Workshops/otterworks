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

3. Reproduce locally against the unit tests (`cd services/search-service && .venv/bin/pytest tests/test_search_api.py -k suggest`).

## Root Cause

`suggest()` in `app/api/search.py` had a ranking-score enrichment path that sorted
suggestions with `s["_rankingScore"]`. `MeiliSearchService.suggest()` returns plain
strings, so the lookup raised `TypeError` (`KeyError` on an empty index), and the path
sat outside the handler's `try`/`except`, so Flask answered 500.

## Resolution Steps

1. Ranking now lives in `MeiliSearchService.suggest()`: the query sets
   `showRankingScore: true`, reads `_rankingScore` with a `0.0` fallback, and sorts.
2. The whole handler body is inside `try`/`except`; any backend failure degrades to an
   empty suggestion list with a `suggest_failed` log line, never a 5xx.
3. Clear the chaos flag if it was set (`redis-cli DEL chaos:search-service:suggest_500`);
   with the fix deployed the flag no longer changes behaviour.
4. Confirm `SearchSuggestHighErrorRate` resolves and `/api/v1/search/suggest?q=te`
   returns 200 in the affected environment.

## Post-Incident

<!-- TODO -->
