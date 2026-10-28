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

3. Reproduce against a pod or the local stack:
   ```
   curl -s -o /dev/null -w '%{http_code}\n' 'http://localhost:8087/api/v1/search/suggest?q=te'
   ```
   A `500` with `KeyError: '_rankingScore'` (or `TypeError: string indices must be integers`)
   in the log means the ranking-score enrichment path is running on hits that carry no score.

## Resolution Steps

Root cause: the ranking-score enrichment in `suggest()` (`services/search-service/app/api/search.py`)
sorted on `hit["_rankingScore"]`, but MeiliSearch only returns `_rankingScore` when the search
request sets `showRankingScore: true`, and the sort ran outside the handler's `try`/`except`.
Every call on that path raised and surfaced as a 500.

1. Immediate mitigation: clear the flag so traffic falls back to the plain prefix path:
   ```
   redis-cli DEL chaos:search-service:suggest_500
   ```
2. Permanent fix: `MeiliSearchService.suggest(prefix, ranked=True)` requests `showRankingScore`,
   sorts with a default of `0.0` for hits that have no score, and the handler wraps the ranked path
   in the same `try`/`except` as the plain path, so a MeiliSearch failure returns `200` with
   `{"suggestions": []}` instead of a 5xx.
3. Verify: `cd services/search-service && .venv/bin/pytest tests/test_search_api.py -k suggest`,
   then re-set the flag and confirm `/suggest` answers 200 with ordered suggestions.

## Post-Incident

- Confirm `SearchSuggestHighErrorRate` has resolved in Grafana and the search-service 5xx rate is back under 5%.
- Any new enrichment step on a hot read path should be covered by a test that feeds it hits without the
  optional MeiliSearch fields (`_rankingScore`, `_formatted`) before it ships.
