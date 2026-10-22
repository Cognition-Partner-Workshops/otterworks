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

3. Reproduce against the pod directly (bypasses the gateway cache):
   ```
   kubectl -n otterworks port-forward svc/search-service 8087:8087 &
   curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:8087/api/v1/search/suggest?q=te"
   ```
4. Confirm the alert math in Prometheus:
   ```
   sum(rate(search_service_requests_total{job="search-service",status=~"5.."}[1m]))
     / sum(rate(search_service_requests_total{job="search-service"}[1m]))
   ```

## Root Cause

`GET /api/v1/search/suggest` (`services/search-service/app/api/search.py`) gained a
ranking-score enrichment step that sorted suggestions with `s["_rankingScore"]`.
MeiliSearch only returns `_rankingScore` when the query sets `showRankingScore: true`,
and `MeiliSearchService.suggest` returned plain strings, so the lookup raised
`KeyError: '_rankingScore'`. That code sat outside the handler's `try/except`, so the
exception escaped as an HTTP 500 on every request instead of degrading to an empty list.

## Resolution Steps

1. Immediate mitigation: clear the chaos flag if it was set (`redis-cli DEL chaos:search-service:suggest_500`);
   the next request takes the safe path.
2. Code fix (`services/search-service`):
   - `MeiliSearchService.suggest` requests `showRankingScore: true`, merges hits from both
     indexes, and orders them by score with `hit.get("_rankingScore")` (missing or malformed
     scores sort last; nothing raises).
   - The `/suggest` handler has one code path, fully inside `try/except`; any backend failure
     logs `suggest_failed` and returns `200 {"suggestions": []}`.
   - Regression tests in `tests/test_search_api.py::TestSuggestRanking`.
3. Deploy, then watch `SearchSuggestHighErrorRate` resolve (5xx ratio drops to 0 within the
   1-minute evaluation window) and confirm autocomplete returns ordered suggestions.

## Post-Incident

- Any handler that enriches results with optional MeiliSearch fields (`_rankingScore`,
  `_formatted`, `_matchesPosition`) must request the field explicitly and read it with `.get`.
- Keep best-effort endpoints (autocomplete, analytics) wrapped so a backend fault degrades
  to an empty payload rather than a 5xx that pages on-call.
