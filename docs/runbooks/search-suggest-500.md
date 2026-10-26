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

3. Confirm the error rate behind the alert in Prometheus:
   ```promql
   sum(rate(search_service_requests_total{job="search-service",status=~"5.."}[1m]))
     / sum(rate(search_service_requests_total{job="search-service"}[1m]))
   ```

## Root Cause

`GET /api/v1/search/suggest` had a ranking-score enrichment path that sorted
suggestions with `s["_rankingScore"]`. MeiliSearch only includes `_rankingScore`
in hits when the search request sets `showRankingScore: true`, which the suggest
query did not, and the sort ran outside the handler's `try`/`except`, so a single
hit without the key raised `KeyError` and surfaced as a 500.

## Resolution Steps

1. Deploy a search-service build in which `MeiliSearchService.suggest` requests
   `showRankingScore: true`, orders hits by `_rankingScore` with a `0.0` fallback
   for hits that lack the field, and the API handler keeps every backend failure
   inside the `try`/`except` that returns an empty `200`.
2. If a build with the fix cannot be rolled out immediately, clear the chaos flag
   to disable the failing path: `redis-cli DEL chaos:search-service:suggest_500`.
3. Confirm recovery: the PromQL ratio above drops below 0.05 and
   `curl -s "$SEARCH_URL/api/v1/search/suggest?q=te"` returns `200` with a
   `suggestions` array.

## Post-Incident

- Keep the regression tests in
  `services/search-service/tests/test_search_api.py::TestSuggestEndpoint`
  (ranking order, hits without `_rankingScore`, backend failure) green.
- Any new result enrichment in the suggest pipeline must request the fields it
  reads from MeiliSearch and tolerate their absence.
