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

3. Confirm the error rate on the `search-service` panel of the Chaos Scenarios dashboard,
   or directly in Prometheus:
   ```
   sum(rate(http_requests_total{job="search-service",status=~"5.."}[1m]))
     / sum(rate(http_requests_total{job="search-service"}[1m]))
   ```
4. Reproduce locally: `curl -i 'http://localhost:8087/api/v1/search/suggest?q=te'` with the
   flag set returns `500`; with the flag cleared it returns `200`.

## Root Cause

The ranking-score enrichment in `suggest()` (`services/search-service/app/api/search.py`)
sorted hits with `hit["_rankingScore"]`. MeiliSearch only includes `_rankingScore` when the
query sets `showRankingScore: true`, so every hit raised `KeyError`. The enrichment ran
outside the handler's `try/except`, so the exception became a 500 instead of the empty
suggestion list the fallback path returns.

## Resolution Steps

1. Clear the chaos flag to stop the bleeding: `redis-cli DEL chaos:search-service:suggest_500`.
2. Deploy the code fix: `MeiliSearchService.suggest` requests `showRankingScore` and reads
   the score with a `0.0` default; the handler has a single code path inside `try/except`,
   so a MeiliSearch error degrades to `{"suggestions": []}` with HTTP 200.
3. Confirm `SearchSuggestHighErrorRate` resolves and `/suggest` returns 200 under load.

## Post-Incident

- Regression tests in `services/search-service/tests/test_search_api.py`
  (`TestSuggestEndpoint`) cover ranking order, hits without `_rankingScore`, and backend
  failures.
- Autocomplete is best-effort: never let a ranking or enrichment step escape the handler's
  error boundary.
