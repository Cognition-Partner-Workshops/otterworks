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

3. Confirm the failure is isolated to `GET /api/v1/search/suggest` (the `/search/` and
   `/search/advanced` handlers catch exceptions and the Grafana panel should show the
   5xx rate concentrated on one route).

## Root Cause

The ranking-score enrichment in the `suggest()` handler (`services/search-service/app/api/search.py`)
sorted suggestions with `s["_rankingScore"]`:

- `MeiliSearchService.suggest` never requested `showRankingScore`, so MeiliSearch never
  returned `_rankingScore` and the lookup raised (`KeyError`, or `TypeError` because
  `suggest()` returns plain strings, not hit dicts).
- The enrichment ran outside the handler's `try/except`, so the exception escaped
  Flask as a 500 instead of the endpoint's empty-suggestions fallback.

## Resolution Steps

1. Deploy a search-service build in which `MeiliSearchService.suggest` requests
   `showRankingScore: true`, sorts hits with a tolerant `_ranking_score()` (missing or
   malformed score sorts last), and the `suggest()` handler has a single code path inside
   `try/except` so backend failures return `{"suggestions": []}` with 200.
2. Verify: `curl -s -o /dev/null -w '%{http_code}' 'http://<search-service>:8087/api/v1/search/suggest?q=te'`
   returns `200`, and `SearchSuggestHighErrorRate` resolves within one evaluation window.
3. If a rollback is needed instead, clear the chaos flag
   (`redis-cli DEL chaos:search-service:suggest_500`) to take the ranking path out of
   service until the fix ships.

## Post-Incident

- Regression tests in `services/search-service/tests/test_search_api.py`
  (`TestSuggestEndpoint`) cover ordering by score, hits without `_rankingScore`, and
  MeiliSearch failures.
- Any future enrichment of suggestions must stay inside the handler's `try/except` and
  request every MeiliSearch field it reads.
