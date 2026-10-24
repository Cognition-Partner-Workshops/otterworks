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

3. Reproduce locally without MeiliSearch: in `services/search-service`, run
   `.venv/bin/pytest tests/test_search_api.py -k suggest`. The handler must return
   `200` for hits with and without `_rankingScore`.

## Root Cause

The ranking-score enrichment in `GET /api/v1/search/suggest` sorted hits with
`hit["_rankingScore"]`. MeiliSearch only returns `_rankingScore` when the query
sets `showRankingScore: true`, and `MeiliSearchService.suggest()` returned plain
strings, so the lookup raised `KeyError` / `TypeError` outside the handler's
`try` block and every suggest call answered `500`.

## Resolution Steps

1. Immediate mitigation: clear the flag so the unranked path serves traffic:
   `redis-cli DEL chaos:search-service:suggest_500`.
2. Permanent fix (shipped): `MeiliSearchService.suggest()` requests
   `showRankingScore`, sorts by `_rankingScore` with a `0.0` default for hits
   that lack it, and the handler keeps every failure inside the `try` so suggest
   degrades to an empty list with `200` instead of a `5xx`.
3. Confirm recovery: `SearchSuggestHighErrorRate` resolves within two evaluation
   windows once the 5xx ratio drops below 5%.

## Post-Incident

- Verify autocomplete returns suggestions in the web app search bar.
- Add a regression test whenever a handler reads a field from a search hit;
  MeiliSearch omits optional fields (`_rankingScore`, `_formatted`) unless requested.
