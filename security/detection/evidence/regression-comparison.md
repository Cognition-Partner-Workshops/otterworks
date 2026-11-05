# DAST instrumentation regression comparison

19/19 verdicts match.

Baseline commit: `ae25fcdbeb86b4289fc6bc6fd11dfa350fb8a8da`.

Same minimal local stack and persistent database for both builds. File/search services absent: gateway-bypass and search-tenant-leak are inconclusive in both, not security passes. 17/19 probes reached verdicts.

First instrumented scan raced startup: gateway connection refused at 13:11:18Z, document startup completed at 13:11:19Z, opening its circuit breaker. Discarded for regression comparison; added Compose --wait and compared the health-ready scan.

| Finding | Before | Instrumented | Match |
|---|---|---|---|
| DAST-ANONYMOUS-ROUTE-SWEEP | secure | secure | yes |
| DAST-BOLA-DOCUMENTS | secure | secure | yes |
| DAST-CORS-ORIGIN-REFLECTION | secure | secure | yes |
| DAST-CREDENTIAL-BRUTE-FORCE | vulnerable | vulnerable | yes |
| DAST-EXPOSED-TELEMETRY | vulnerable | vulnerable | yes |
| DAST-GATEWAY-BYPASS-IDENTITY | inconclusive | inconclusive | yes |
| DAST-IDENTITY-HEADER-SPOOF | secure | secure | yes |
| DAST-MASS-ASSIGNMENT-OWNER | vulnerable | vulnerable | yes |
| DAST-MISSING-SECURITY-HEADERS | vulnerable | vulnerable | yes |
| DAST-PATH-TRAVERSAL-EXPORT | vulnerable | vulnerable | yes |
| DAST-RATE-LIMIT-BYPASS | vulnerable | vulnerable | yes |
| DAST-SEARCH-TENANT-LEAK | inconclusive | inconclusive | yes |
| DAST-SENSITIVE-DATA-IN-RESPONSE | secure | secure | yes |
| DAST-SHARE-TOKEN-FORGERY | vulnerable | vulnerable | yes |
| DAST-SQLI-ERROR-BASED | vulnerable | vulnerable | yes |
| DAST-STORED-XSS-DOCUMENTS | secure | secure | yes |
| DAST-UNAUTHENTICATED-ADMIN | secure | secure | yes |
| DAST-UNSIGNED-JWT | secure | secure | yes |
| DAST-VERBOSE-ERRORS | secure | secure | yes |

## Build provenance

```json
{
  "otterworks-api-gateway:before": "sha256:296830cdbc618e1753488689c9c245682b62afb8e4336d706243643a6c4982bd",
  "otterworks-document-service:before": "sha256:9ee728ad44cb912d793d04d04af7c66d85aa3079a5eeb37eeceac088352578ac",
  "otterworks-api-gateway:latest": "sha256:0ca179ab9505c30892777c99f4b46ddcf7b06ca866862bb13e37a55fba1ff84a",
  "otterworks-document-service:latest": "sha256:401ec9bb8faeb87880cd908fb63f93b8a5f7b34810fbf24f3e50df750ca3c06c",
  "otterworks-auth-service:latest": "sha256:104c23a62d07e21f03f8c8e629809a1a7cc373b0db1b3112ec73785d3d1c8350"
}
```
