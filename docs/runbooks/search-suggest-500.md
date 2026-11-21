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

3. Reproduce against a single pod with a two-character prefix:
   ```
   curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:8087/api/v1/search/suggest?q=te"
   ```

## Resolution Steps

1. Root cause: the suggest handler's ranking-score enrichment sorted hits with
   `hit["_rankingScore"]`, but MeiliSearch only returns `_rankingScore` when the
   query sets `showRankingScore: true`, so every request raised `KeyError` and
   Flask answered 500.
2. The fix is in `MeiliSearchService.suggest`: the query now requests
   `showRankingScore`, the score is read with a `0.0` fallback so an unscored hit
   sorts last instead of raising, and the handler's `except Exception` degrades
   any backend failure to `200 {"suggestions": []}` rather than a 5xx.
3. If the flag `chaos:search-service:suggest_500` is set on a demo tenant, clear
   it (`scripts/inject-bug.sh <ID> reset`); it has no effect on a fixed build.
4. Confirm recovery: the 5xx rate on the search-service panel drops to zero and
   `SearchSuggestHighErrorRate` resolves within one evaluation window.

## Post-Incident

- Regression tests: `tests/test_search_api.py::TestSuggestEndpoint`
  (`test_suggest_orders_by_ranking_score`,
  `test_suggest_missing_ranking_score_does_not_crash`,
  `test_suggest_backend_error_returns_200`).
- Any future enrichment of suggest hits must stay inside the handler's
  try/except and treat MeiliSearch metadata fields as optional.
