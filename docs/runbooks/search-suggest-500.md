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

3. Reproduce against the service directly and confirm the status code:
   ```
   kubectl -n otterworks port-forward svc/search-service 8087:8087 &
   curl -s -o /dev/null -w '%{http_code}\n' 'http://localhost:8087/api/v1/search/suggest?q=te'
   ```
   `500` with `KeyError: '_rankingScore'` (or `TypeError: string indices must be integers`)
   in the logs confirms the ranking-score enrichment path is the cause.

## Root Cause

The ranking-score enrichment in `suggest()` (`services/search-service/app/api/search.py`)
sorted hits with `s["_rankingScore"]`. MeiliSearch only includes `_rankingScore` when the
query sets `showRankingScore: true`, which `MeiliSearchService.suggest()` never did, so the
lookup raised and the sort ran outside the handler's `try`, surfacing as a 500.

## Resolution Steps

1. Mitigate immediately by clearing the flag that routes traffic onto the broken path:
   ```
   redis-cli DEL chaos:search-service:suggest_500
   ```
   (`scripts/inject-bug.sh <tenant> reset` on a demo tenant.) Error rate should drop within
   one scrape interval.
2. Deploy the fix: `MeiliSearchService.suggest()` requests `showRankingScore`, ranks hits
   by `_rankingScore` with a tolerant lookup (a missing or malformed score ranks last), and
   the handler keeps a single guarded path that degrades to `200` + `[]` on any backend error.
3. Confirm `SearchSuggestHighErrorRate` resolves and autocomplete returns ordered results.

## Post-Incident

- Regression tests in `tests/test_search_api.py::TestSuggestEndpoint` cover ranking order,
  hits without a score, and backend failure.
- Any future enrichment of suggest results must stay inside the handler's `try` and must
  request the attributes it reads from MeiliSearch.
