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

3. Reproduce against the running service and watch the handler log line:
   ```
   curl -s -o /dev/null -w '%{http_code}\n' 'http://localhost:8087/api/v1/search/suggest?q=te'
   ```
   A 500 with `suggest_failed` absent from the logs means the exception escaped the
   handler's `try` block (the ranking-score enrichment ran outside it).

## Root Cause

The suggest handler sorted suggestions by `_rankingScore` without asking MeiliSearch
for it (`showRankingScore` was not set), so the key was missing on every hit and the
lookup raised `KeyError` (or `TypeError` on plain-string suggestions) outside the
handler's error handling, turning every `/suggest` call into a 500.

## Resolution Steps

1. `MeiliSearchService.suggest` now requests `showRankingScore: true`, merges hits from
   both indices by `_rankingScore`, and falls back to `0.0` for any hit without a score,
   so a missing score can never fail the request.
2. The ranking path runs inside the handler's existing `try`/`except`, which degrades to
   an empty suggestion list (HTTP 200) on any backend error.
3. Confirm recovery: `/suggest` returns 200 and `SearchSuggestHighErrorRate` resolves
   within one evaluation window (1 minute).

## Post-Incident

- The `search-suggest-500` scenario in `scripts/bug-catalog.yaml` (chaos flag
  `chaos:search-service:suggest_500`) no longer alters behaviour once this fix is deployed.
- Regression tests: `services/search-service/tests/test_search_api.py::TestSuggestEndpoint`.
