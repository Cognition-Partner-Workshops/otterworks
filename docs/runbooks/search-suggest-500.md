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

3. Confirm the failing code path: `suggest()` in `app/api/search.py` sorted
   suggestions with `s["_rankingScore"]`. `MeiliSearchService.suggest` returned
   plain strings and never asked MeiliSearch for `showRankingScore`, so the
   lookup raised `TypeError` (hits present) or `KeyError` (empty index) outside
   the handler's `try/except` and surfaced as a 500.

## Resolution Steps

1. Ranking now lives in `MeiliSearchService.suggest`: the query sets
   `showRankingScore: true`, reads `_rankingScore` with a `0.0` default, and
   returns the deduplicated titles ordered by score. The handler has a single
   code path wrapped in `try/except`, so a backend failure degrades to
   `{"suggestions": []}` with HTTP 200 instead of a 5xx.
2. Deploy search-service and watch
   `sum(rate(search_service_requests_total{job="search-service",status=~"5.."}[1m]))`
   fall to zero; `SearchSuggestHighErrorRate` resolves on its own.
3. Clear the chaos flag if it was set: `redis-cli DEL chaos:search-service:suggest_500`.

## Post-Incident

- Regression tests in `services/search-service/tests/test_search_api.py`
  (`TestSuggestEndpoint`) pin: ordering by `_rankingScore`, hits without a
  score, an empty index, and a MeiliSearch outage all return 200.
- Autocomplete is best-effort: any future enrichment of `/suggest` must stay
  inside the handler's `try/except` and never change the `suggestions: string[]`
  contract consumed by `frontend/client-app/src/lib/api.ts`.
