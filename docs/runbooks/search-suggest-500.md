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

3. Reproduce against the pod directly (bypasses the gateway) while the flag is set:
   ```
   kubectl -n otterworks port-forward svc/search-service 8087:8087 &
   curl -s -o /dev/null -w '%{http_code}\n' 'http://localhost:8087/api/v1/search/suggest?q=te'
   ```
   A `500` here with `KeyError: '_rankingScore'` or `TypeError: string indices must be integers`
   in the log confirms the ranking-score enrichment path in `suggest()`
   (`services/search-service/app/api/search.py`).

## Root Cause

The suggest handler has two paths. The default path returns plain title strings and
degrades to `200 {"suggestions": []}` on any error. The ranking-score path (selected by
the Redis flag) sorted the suggestions with `s["_rankingScore"]`, but:

- `MeiliSearchService.suggest` returns `list[str]`, so indexing a string raised `TypeError`;
- MeiliSearch only returns `_rankingScore` when `showRankingScore: true` is sent, so even
  dict hits would have raised `KeyError`;
- the path ran outside the handler's `try/except`, so Flask answered 500.

## Resolution Steps

1. Immediate mitigation: clear the flag so traffic takes the default path again.
   ```
   redis-cli DEL chaos:search-service:suggest_500
   ```
2. Code fix: `MeiliSearchService.suggest(prefix, ranked=True)` requests `showRankingScore`,
   sorts by `_rankingScore` with `0.0` for hits that lack one, and the handler runs both
   paths inside the same `try/except`, so a backend failure logs `suggest_failed` and
   returns `200 []` instead of a 500.
3. Verify: `cd services/search-service && .venv/bin/pytest tests/test_search_api.py -k Suggest`
   covers the ranked path (sorted output, missing score, empty index, backend failure).
4. Confirm `SearchSuggestHighErrorRate` resolves and the 5xx panel for search-service
   drops to zero on the Chaos Scenarios dashboard.

## Post-Incident

- The web app only consumes `suggestions: string[]`
  (`frontend/client-app/src/lib/api.ts`), so the ranked path must keep returning strings.
- Any new "enrichment" branch in `suggest()` belongs inside the existing fallback so a
  ranking bug degrades autocomplete rather than failing the request.
