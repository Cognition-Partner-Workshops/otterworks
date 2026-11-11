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

<!-- TODO: Complete investigation steps -->

## Resolution Steps

1. If the chaos flag is set, clear it: `redis-cli DEL chaos:search-service:suggest_500`.
2. The code cause is the ranking-score enrichment in `suggest()`: it indexed
   `_rankingScore` on every hit, but MeiliSearch only returns that field when the
   query sets `showRankingScore: true`, and the handler ran the sort outside its
   `try/except`. The fix moves ranking into `MeiliSearchService.suggest`
   (`showRankingScore: true`, hits without a score sort last) so the handler
   always honours the "always 200" contract.
3. Confirm recovery: `curl -s "$API/api/v1/search/suggest?q=qu"` returns 200 and
   the `SearchSuggestHighErrorRate` alert resolves within ~2 minutes.

## Post-Incident

<!-- TODO -->
