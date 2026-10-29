# Runbook: Search Autocomplete 500 Errors

**Severity:** Critical

## Alert

`SearchSuggestHighErrorRate` -- fires when search-service 5xx rate exceeds 5% over a 1-minute window.

## Symptoms

- Autocomplete suggestions stop appearing in the web app search bar.
- The Chaos Scenarios dashboard shows elevated error rates on the search-service panel.
- Application logs contain `KeyError: '_rankingScore'` (empty result set) or
  `TypeError: string indices must be integers` (non-empty result set) raised from
  the ranking-score sort in the suggest endpoint handler.

## Investigation Steps

1. Confirm the error in search-service logs:
   ```
   kubectl logs -l app=search-service --tail=100 -n otterworks | grep -i "KeyError\|rankingScore\|500"
   ```
2. Check whether the chaos flag `chaos:search-service:suggest_500` is set in Redis:
   ```
   redis-cli EXISTS chaos:search-service:suggest_500
   ```

3. Confirm the 5xx share on the endpoint from the service's own counter:
   ```
   curl -s http://search-service:8087/metrics | grep 'search_service_requests_total{endpoint="/api/v1/search/suggest"'
   ```
4. Reproduce with one request: `GET /api/v1/search/suggest?q=te` returns 500 while the flag
   is set and 200 once it is cleared.

## Resolution Steps

1. **Mitigate**: clear the flag so traffic takes the fail-soft path again:
   ```
   redis-cli DEL chaos:search-service:suggest_500
   ```
   The alert resolves on the next 1-minute window.
2. **Fix**: the ranking-score enrichment sorted `MeiliSearchService.suggest()` output
   (a `list[str]`) by `s["_rankingScore"]`, and MeiliSearch only returns that field when
   `showRankingScore` is requested. The durable fix moves ranking into
   `MeiliSearchService.suggest()` (requests `showRankingScore`, reads the score with a
   `0.0` fallback, sorts descending) and removes the unguarded branch from the handler so a
   backend problem degrades to `{"suggestions": []}` with HTTP 200 instead of a 5xx.
3. Deploy the fixed `search-service` image and confirm `status="500"` stops incrementing
   on `search_service_requests_total` for the suggest endpoint.

## Post-Incident

- Regression tests: `services/search-service/tests/test_search_api.py::TestSuggestEndpoint`
  (missing `_rankingScore` → 200, ranking order across both indexes, backend error → 200).
- Any future enrichment of suggest results must live inside the handler's `try/except` and
  must only read fields it asked MeiliSearch to return.
