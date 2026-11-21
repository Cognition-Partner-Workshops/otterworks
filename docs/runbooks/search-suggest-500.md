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
   ```
   sum(rate(search_service_requests_total{job="search-service",status=~"5.."}[1m]))
     / sum(rate(search_service_requests_total{job="search-service"}[1m]))
   ```
4. Reproduce against the pod: `curl -i "http://<search-service>:8087/api/v1/search/suggest?q=te"`.
   A healthy service always answers `200` with a `suggestions` list (possibly empty).

## Root Cause

The `/suggest` handler gained a "ranking-score enrichment" step that sorted
suggestions with `s["_rankingScore"]`. Two things made that step crash:

- `MeiliSearchService.suggest()` returns plain title strings, so indexing a
  string with `"_rankingScore"` raises `TypeError`; the empty-index fallback
  (`[{}]`) raises `KeyError: '_rankingScore'`.
- MeiliSearch only emits `_rankingScore` when the query sets
  `showRankingScore: true`; the suggest query never asked for it.

The enrichment path also ran outside the handler's `try/except`, so the
exception surfaced as an unhandled 500 instead of degrading to an empty list.

## Resolution Steps

1. Deploy the fix: ranking lives in `MeiliSearchService.suggest()`, which requests
   `showRankingScore`, reads the score with a `0.0` fallback and sorts highest-first;
   the handler keeps every backend failure inside `try/except` and answers `200`
   with `suggestions: []`.
2. If the chaos flag is set on a demo tenant, clear it:
   `./scripts/inject-bug.sh <ATTENDEE_ID> reset` (or `redis-cli DEL chaos:search-service:suggest_500`).
3. Verify the 5xx ratio returns to 0 and `SearchSuggestHighErrorRate` resolves; confirm
   autocomplete renders in the web app search bar.

## Post-Incident

- Regression tests: `services/search-service/tests/test_search_api.py::TestSuggestEndpoint`
  and `tests/test_indexer.py::TestSuggest` cover missing `_rankingScore`, empty indexes
  and MeiliSearch failures.
- Any future enrichment of MeiliSearch hits must read optional fields with `.get()`
  and request them explicitly in the query.
