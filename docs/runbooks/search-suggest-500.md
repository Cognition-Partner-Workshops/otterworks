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

3. Reproduce locally: `curl -i "http://localhost:8087/api/v1/search/suggest?q=te"` returns
   `500` while the flag is set, and the traceback points at the `_rankingScore` lookup in
   `app/api/search.py` `suggest()`.

## Root Cause

The ranking-score enrichment in `suggest()` indexed `_rankingScore` on every hit, but
`MeiliSearchService.suggest()` never asked MeiliSearch for the score (`showRankingScore`),
so the lookup raised `KeyError` (or `TypeError` on plain-string suggestions). The sort ran
outside the handler's `try`/`except`, so the exception surfaced as a 500.

## Resolution Steps

1. Clear the flag to stop the bleeding: `redis-cli DEL chaos:search-service:suggest_500`.
2. The code fix moves ranking into `MeiliSearchService.suggest()`: it requests
   `showRankingScore`, reads the score with a default (`_ranking_score`), merges hits from
   both indexes, and the handler keeps every failure inside `try`/`except` so `/suggest`
   degrades to an empty list with 200 instead of 500.
3. Confirm recovery: the `SearchSuggestHighErrorRate` alert resolves within one evaluation
   window and `/suggest` returns 200 with or without the flag.

## Post-Incident

<!-- TODO -->
