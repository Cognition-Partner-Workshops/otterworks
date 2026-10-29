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

3. Reproduce against the service directly (bypassing the gateway) and watch the
   status code and the log line it emits:
   ```
   curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:8087/api/v1/search/suggest?q=te"
   ```
   A `500` paired with `KeyError: '_rankingScore'` (or `TypeError: string indices
   must be integers`) in the logs confirms the ranking-score enrichment path is
   the cause rather than MeiliSearch itself.
4. Confirm MeiliSearch is healthy so the error is not misattributed:
   ```
   curl -s http://localhost:7700/health
   ```

## Root Cause

The `/suggest` handler sorted suggestions by `_rankingScore` without requesting
it. MeiliSearch only includes `_rankingScore` in a hit when the search is made
with `showRankingScore: true`; the call used `attributesToRetrieve` only, so the
key was absent and the lookup raised `KeyError`. `MeiliSearchService.suggest()`
also returned plain title strings, so indexing them with `["_rankingScore"]`
raised `TypeError`. The sort ran outside the handler's `try`/`except`, so every
request on that path returned 500 instead of degrading.

## Resolution Steps

1. Ship the fix in `services/search-service`:
   - `MeiliSearchService.suggest()` requests `showRankingScore: true`, reads the
     score with a `0.0` fallback, merges hits from both indexes and returns them
     highest score first (`app/services/meilisearch_client.py`).
   - The `/suggest` handler has a single code path inside `try`/`except`, so a
     backend error returns `200` with an empty list rather than a 5xx
     (`app/api/search.py`).
   - Regression tests cover ranking order, missing/malformed scores and backend
     failure (`tests/test_search_api.py`, `tests/test_indexer.py`).
2. Deploy search-service and confirm the error rate falls below 5%:
   ```
   kubectl rollout status deploy/search-service -n otterworks
   curl -s "http://localhost:8087/api/v1/search/suggest?q=te"
   ```
3. If the chaos flag was set as part of a lab, clear it so the dashboard
   baseline is clean: `scripts/inject-bug.sh <tenant> reset`.
4. Verify `SearchSuggestHighErrorRate` resolves in Grafana / Alertmanager.

## Post-Incident

- Any field read from a MeiliSearch hit that is not a document attribute
  (`_rankingScore`, `_formatted`, `_matchesPosition`) must be requested
  explicitly and read with a default; add a unit test with a hit that lacks it.
- Keep relevance ordering inside `MeiliSearchService` so handlers only shape the
  response; the handler's `try`/`except` must wrap every call that can raise.
- Consider adding a per-endpoint 5xx panel for `/suggest` so the error is
  attributable before the service-wide 5% threshold trips.
