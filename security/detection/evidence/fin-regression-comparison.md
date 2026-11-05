# Fineract edge detection regression comparison

19/19 verdicts unchanged against demo-bank and the pre-Fineract detection build.

Actual demo-bank service-build scan retained from the earlier detection phase; no service swaps during this gateway-only extension.

Only gateway rebuilt/restarted; same minimal running stack and database. Docker Hub returned 429; local build used identical pinned-digest base images via mirror.gcr.io, with no repository Dockerfile edits. File/search services absent: two matching inconclusive verdicts are not security passes.

Baseline commit: `ae25fcdbeb86b4289fc6bc6fd11dfa350fb8a8da`.

| Finding | demo-bank | Before Fineract | After Fineract | Match |
|---|---|---|---|---|
| DAST-ANONYMOUS-ROUTE-SWEEP | secure | secure | secure | yes |
| DAST-BOLA-DOCUMENTS | secure | secure | secure | yes |
| DAST-CORS-ORIGIN-REFLECTION | secure | secure | secure | yes |
| DAST-CREDENTIAL-BRUTE-FORCE | vulnerable | vulnerable | vulnerable | yes |
| DAST-EXPOSED-TELEMETRY | vulnerable | vulnerable | vulnerable | yes |
| DAST-GATEWAY-BYPASS-IDENTITY | inconclusive | inconclusive | inconclusive | yes |
| DAST-IDENTITY-HEADER-SPOOF | secure | secure | secure | yes |
| DAST-MASS-ASSIGNMENT-OWNER | vulnerable | vulnerable | vulnerable | yes |
| DAST-MISSING-SECURITY-HEADERS | vulnerable | vulnerable | vulnerable | yes |
| DAST-PATH-TRAVERSAL-EXPORT | vulnerable | vulnerable | vulnerable | yes |
| DAST-RATE-LIMIT-BYPASS | vulnerable | vulnerable | vulnerable | yes |
| DAST-SEARCH-TENANT-LEAK | inconclusive | inconclusive | inconclusive | yes |
| DAST-SENSITIVE-DATA-IN-RESPONSE | secure | secure | secure | yes |
| DAST-SHARE-TOKEN-FORGERY | vulnerable | vulnerable | vulnerable | yes |
| DAST-SQLI-ERROR-BASED | vulnerable | vulnerable | vulnerable | yes |
| DAST-STORED-XSS-DOCUMENTS | secure | secure | secure | yes |
| DAST-UNAUTHENTICATED-ADMIN | secure | secure | secure | yes |
| DAST-UNSIGNED-JWT | secure | secure | secure | yes |
| DAST-VERBOSE-ERRORS | secure | secure | secure | yes |

## Running image provenance

```json
{
  "api-gateway": "sha256:30432cb481d2a9e1305695ad367b4328185333f67249c6ca204625bcee802a5b",
  "document-service": "sha256:401ec9bb8faeb87880cd908fb63f93b8a5f7b34810fbf24f3e50df750ca3c06c",
  "auth-service": "sha256:104c23a62d07e21f03f8c8e629809a1a7cc373b0db1b3112ec73785d3d1c8350"
}
```
