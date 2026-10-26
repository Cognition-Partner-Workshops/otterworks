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

3. Reproduce locally without MeiliSearch or Redis: `cd services/search-service && .venv/bin/pytest tests/test_search_api.py -k suggest`.
   `test_suggest_with_chaos_flag_set_still_returns_200` exercises the exact path the alert describes.

## Root Cause

`suggest()` in `app/api/search.py` had a second, unguarded code path (gated on the
`chaos:search-service:suggest_500` Redis flag) that sorted suggestions with
`s["_rankingScore"]`. `MeiliSearchService.suggest()` returns plain strings, and
MeiliSearch only includes `_rankingScore` when `showRankingScore` is requested, so the
lookup raised (`TypeError` on strings, `KeyError` on hits without a score) outside the
handler's `try/except` and every request answered 500.

## Resolution Steps

1. Ranking now lives in `MeiliSearchService.suggest()`: it requests `showRankingScore`,
   merges hits from both indexes, and sorts by `_rankingScore` with `0.0` as the default
   for hits that lack it.
2. The handler has a single code path wrapped in `try/except`; any backend failure
   returns `200` with an empty list. The chaos flag no longer changes behaviour.
3. Confirm recovery: `SearchSuggestHighErrorRate` resolves within one evaluation window
   once the fixed image is rolled out; `curl "$API/api/v1/search/suggest?q=te"` returns 200.

## Post-Incident

- Keep best-effort endpoints (autocomplete) inside their error boundary; a ranking or
  enrichment step must never be able to turn an optional feature into a 5xx.
- Any new MeiliSearch field used in code must be requested explicitly
  (`attributesToRetrieve` / `showRankingScore`) and read with `.get()`.
