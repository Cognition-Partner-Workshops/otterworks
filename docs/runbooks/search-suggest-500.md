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

3. Confirm the error rate is isolated to `GET /api/v1/search/suggest` (the full-text
   and advanced search endpoints are unaffected).

## Root Cause

`suggest()` in `services/search-service/app/api/search.py` ran a ranking-score
enrichment step outside its `try`/`except`: it sorted the suggestions with
`s["_rankingScore"]`. `MeiliSearchService.suggest()` returns plain strings, and
MeiliSearch only emits `_rankingScore` when `showRankingScore` is requested, so
the lookup raised `TypeError` / `KeyError` and Flask answered 500.

## Resolution Steps

1. Immediate mitigation on an affected tenant: clear the chaos flag with
   `scripts/inject-bug.sh <ID> reset` (or `redis-cli DEL chaos:search-service:suggest_500`).
2. Code fix: `MeiliSearchService.suggest()` requests `showRankingScore` and orders
   hits by `_rankingScore` itself (missing scores sort last); the handler has a
   single code path inside `try`/`except`, so a backend failure degrades to an
   empty suggestion list with HTTP 200 instead of a 5xx.
3. Verify: `cd services/search-service && .venv/bin/pytest tests/test_search_api.py -k suggest`
   and watch `SearchSuggestHighErrorRate` resolve on the Chaos Scenarios dashboard.

## Post-Incident

- Keep ranking logic in the service layer and keep every handler path inside its
  error boundary; `/suggest` is best-effort and must never 5xx.
- Regression tests: `test_suggest_orders_by_ranking_score` and
  `test_suggest_backend_failure_degrades_to_empty` in
  `services/search-service/tests/test_search_api.py`.
