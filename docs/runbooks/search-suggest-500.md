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

3. Confirm the 5xx rate is concentrated on `GET /api/v1/search/suggest`; `/search/` and
   `/search/advanced` catch their own exceptions and should be unaffected.

## Root Cause

The ranking-score enrichment in the `suggest()` handler
(`services/search-service/app/api/search.py`) sorted suggestions with `s["_rankingScore"]`:

- `MeiliSearchService.suggest` never requested `showRankingScore`, so MeiliSearch never
  returned `_rankingScore` (`KeyError` on an empty hit, `TypeError` on the plain strings
  the service actually returns).
- The enrichment ran outside the handler's `try/except`, so the exception escaped Flask
  as a 500 instead of the endpoint's empty-suggestions fallback.

## Resolution Steps

1. Deploy a search-service build in which `MeiliSearchService.suggest` requests
   `showRankingScore: true`, sorts hits with a tolerant score lookup (missing or malformed
   score sorts last), and `suggest()` has a single code path inside `try/except`, so a
   backend failure returns `{"suggestions": []}` with 200.
2. Verify `curl -s -o /dev/null -w '%{http_code}' 'http://<search-service>:8087/api/v1/search/suggest?q=te'`
   returns `200` and `SearchSuggestHighErrorRate` resolves within one evaluation window.
3. Until the build ships, clearing the flag (`redis-cli DEL chaos:search-service:suggest_500`)
   takes the broken ranking path out of service.

## Post-Incident

- Regression tests live in `services/search-service/tests/test_search_api.py`
  (`TestSuggestEndpoint`): ordering by score, hits without `_rankingScore`, MeiliSearch failure.
- Any future enrichment of suggestions must request every MeiliSearch field it reads and stay
  inside the handler's `try/except`.
