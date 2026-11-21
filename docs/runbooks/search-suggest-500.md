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

3. Reproduce with one request through the gateway (any prefix of 2+ chars):
   ```
   curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $TOKEN" \
     "https://api-t-<ID>.demo.otterworks.app/api/v1/search/suggest?q=re"
   ```

## Root Cause

`suggest()` in `services/search-service/app/api/search.py` had a ranking-score
enrichment step that did `hit["_rankingScore"]` on every suggestion. Two things
were wrong with it: `MeiliSearchService.suggest()` returns plain strings, so the
index lookup raised `TypeError`, and even on dict hits MeiliSearch only includes
`_rankingScore` when the query sets `showRankingScore: true`, so the lookup raised
`KeyError`. The branch ran outside the handler's `try/except`, so every call
returned HTTP 500.

## Resolution Steps

1. If the chaos flag is set, clear it to stop the bleeding immediately:
   ```
   ./scripts/inject-bug.sh <ATTENDEE_ID> reset
   ```
2. Ship the code fix: the ranking logic lives in
   `MeiliSearchService.suggest()`, which requests `showRankingScore`, reads the
   score with a `0.0` default, and sorts before returning. The handler always
   degrades to `{"suggestions": []}` with HTTP 200 on any backend error.
3. Confirm the alert resolves: `SearchSuggestHighErrorRate` clears within one
   evaluation window once the 5xx rate drops below 5%.

## Post-Incident

- Regression tests: `services/search-service/tests/test_search_api.py::TestSuggestEndpoint`
  cover ordering by score, hits without a score, and backend failures.
- Autocomplete is a best-effort feature: any new enrichment of suggestions must
  stay inside the handler's `try/except` and tolerate missing fields.
