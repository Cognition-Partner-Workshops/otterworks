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

3. Reproduce against the pod (or `localhost:8087` locally):
   ```
   curl -s -o /dev/null -w '%{http_code}\n' 'http://localhost:8087/api/v1/search/suggest?q=te'
   ```
   A `500` with `KeyError: '_rankingScore'` (or `TypeError: string indices
   must be integers`) in the log confirms the ranking-score enrichment path.

## Root Cause

The `/suggest` handler sorted suggestions with `s["_rankingScore"]`, but
`MeiliSearchService.suggest()` returns plain title strings and MeiliSearch only
adds `_rankingScore` to a hit when `showRankingScore: true` is requested. The
lookup raised on every call, and the enrichment branch sat outside the
handler's `try/except`, so the exception surfaced as a 500.

## Resolution Steps

1. Deploy a search-service build in which ranking happens inside
   `MeiliSearchService.suggest()`: it requests `showRankingScore`, reads the
   score with a default, and the handler's `try/except` turns any backend
   failure into an empty suggestion list (HTTP 200).
2. Confirm recovery: the `curl` above returns `200` with a JSON body and the
   search-service 5xx rate on the Chaos Scenarios dashboard drops below 5%.
3. If the chaos flag is set, clear it so the alert resolves on the old build
   too: `redis-cli DEL chaos:search-service:suggest_500`.

## Post-Incident

- `/suggest` is a degrade-gracefully endpoint: any change to it must keep the
  response a `200` with `suggestions: []` on backend errors.
- The regression tests in `services/search-service/tests/test_search_api.py`
  (`TestSuggestEndpoint`) cover ranking order, missing `_rankingScore` and a
  MeiliSearch outage.
