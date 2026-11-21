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

3. Reproduce locally against the service's test suite: `cd services/search-service && .venv/bin/pytest tests/test_search_api.py -k suggest`.

## Resolution Steps

1. The crash is in the suggest ranking step: suggestions were sorted on `hit["_rankingScore"]`,
   but MeiliSearch only includes `_rankingScore` when the search request sets
   `showRankingScore: true`, and the ranking step ran outside the handler's `try/except`.
2. The fix (`MeiliSearchService.suggest`) requests `showRankingScore`, reads the score with a
   `0.0` default, and keeps the whole suggest path inside the handler's error boundary so any
   backend failure degrades to an empty suggestion list (HTTP 200) instead of a 500.
3. Roll the fixed search-service image out; `SearchSuggestHighErrorRate` resolves within one
   evaluation window once the 5xx rate drops.
4. If the chaos flag was set for a demo, clear it: `./scripts/inject-bug.sh <ATTENDEE_ID> reset`.

## Post-Incident

- Autocomplete is best-effort UX: the `/suggest` handler must never return 5xx for a
  ranking/enrichment problem. Keep enrichment inside the error boundary and add a test for
  every new field read from a MeiliSearch hit.
