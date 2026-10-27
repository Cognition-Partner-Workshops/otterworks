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

3. Confirm the failing code path: `suggest()` in `services/search-service/app/api/search.py`
   sorts hits by `hit["_rankingScore"]`. MeiliSearch only returns `_rankingScore` when
   `showRankingScore: true` is sent, and the sort ran outside the handler's `try/except`,
   so a hit without the key (or an empty index) raised straight through as a 500.

## Resolution Steps

1. Deploy the fix: `MeiliSearchService.suggest()` requests `showRankingScore: true`,
   orders hits by `_rankingScore` with a `0.0` fallback for hits that lack it, and the
   handler keeps every backend call inside the existing `try/except` that degrades to an
   empty suggestion list (HTTP 200).
2. Verify: `curl -s "http://<search-service>/api/v1/search/suggest?q=te"` returns
   `200` with `{"suggestions": [...], "query": "te"}` and `search_service_requests_total{status=~"5.."}`
   stops increasing. `SearchSuggestHighErrorRate` resolves within the 1-minute window.
3. Unit coverage: `cd services/search-service && .venv/bin/pytest tests/test_search_api.py -k suggest`.

## Post-Incident

<!-- TODO -->
