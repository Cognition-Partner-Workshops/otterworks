# IB gateway detection regression comparison

19/19 verdicts unchanged against both demo-bank and the pre-IB detection build.

Actual demo-bank service-build scan retained from the earlier detection phase; no service swaps during this gateway-only extension.

Same minimal running stack and persistent database; only gateway rebuilt/restarted. File/search services remain absent: two matching inconclusive verdicts are not security passes.

Baseline commit: `ae25fcdbeb86b4289fc6bc6fd11dfa350fb8a8da`.

| Finding | demo-bank | Before IB | After IB | Match |
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
  "api-gateway": "sha256:56251f453537e9b738cbd15d277baad9bbd99200362fb5fa9d24fb3a63af62ff",
  "document-service": "sha256:401ec9bb8faeb87880cd908fb63f93b8a5f7b34810fbf24f3e50df750ca3c06c",
  "auth-service": "sha256:104c23a62d07e21f03f8c8e629809a1a7cc373b0db1b3112ec73785d3d1c8350"
}
```
