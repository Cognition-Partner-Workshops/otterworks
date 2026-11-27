# Phase 0 dependency map: source to runtime (core estate)

Evidence date 2026-11-20. **Source** is what the code can call (repo at this
commit). **Runtime** is what is wired in `otterworks-dev` / namespace
`otterworks-main` (t-main), read from its ConfigMaps, Deployments, ServiceMonitors
and Prometheus targets with read-only calls. Phase 0 approval needs each owner to
sign their rows; a row nobody signs is a no-go item.

## Synchronous calls (request path)

| Caller | Callee | Path / mechanism | Source | t-main runtime |
|---|---|---|---|---|
| Ingress (shared NLB) | web-app, admin-dashboard, api-gateway | host/path rules | `infrastructure/helm/api-gateway/templates/ingress.yaml`, `scripts/deploy-tenant.sh` | wired; web-app and admin-dashboard metrics targets **down** |
| api-gateway | auth | `/api/v1/auth`, `/api/v1/settings` | `services/api-gateway/internal/config/config.go` `ServiceRoutes()` | wired |
| api-gateway | file | `/api/v1/files`, `/api/v1/folders` | same | wired |
| api-gateway | document | `/api/v1/documents`, `/api/v1/templates` | same | wired |
| api-gateway | collab | `/api/v1/collab`, `/socket.io` (WS upgrade) | same | wired |
| api-gateway | notification | `/api/v1/notifications`, `/api/v1/preferences` | same | wired |
| api-gateway | search | `/api/v1/search` | same | wired |
| api-gateway | analytics | `/api/v1/analytics` | same | wired |
| api-gateway | admin | `/api/v1/admin` | same | wired; target **down** (planted boot defect) |
| api-gateway | audit | `/api/v1/audit` | same | wired |
| api-gateway | report | `/api/v1/reports` | same | wired; pod Ready, metrics target **down** |
| api-gateway | Redis | chaos flags (empty host disables) | `services/api-gateway/internal/config/config.go` `RedisHost` | in-tenant `redis` |
| every backend | auth (JWT) | tokens issued by auth; each service's validation path to be confirmed by its owner | per-service JWT config | per-tenant Secret |
| search | document, file | HTTP `GET /api/v1/documents/`, `/api/v1/files` for reindex | `services/search-service/app/services/indexer.py` | wired (manual reindex only) |
| report | analytics, audit, auth | RestTemplate, synchronous | `services/report-service/.../config/AppConfig.java` | wired; failure of any callee fails the report |
| admin | all backends | `GET /health` fan-out | `services/admin-service/app/services/health_checker.rb` | down with admin |

## Asynchronous paths (events)

| Producer | Channel | Consumer | Schema | t-main runtime |
|---|---|---|---|---|
| file | SNS topic | notification (SQS), search (SQS), audit (SQS) | `shared/events/schemas/file-events.json` | **disabled** (`SNS_TOPIC_ARN` empty) |
| document | SNS topic | search, audit, notification | `shared/events/schemas/document-events.json` | **disabled** |
| collab | (in-process / Redis pub/sub) | collab replicas | `collaboration-events.json` | single replica |
| notification | SQS consumer | — | `notification-events.json` | **disabled** (`SQS_QUEUE_URL` empty) |
| audit | SNS→SQS consumer (`SnsConsumer.cs`) | — | `audit-events.json` | not receiving (no topics wired) |
| analytics | SQS consumer (optional, non-fatal) | — | `AnalyticsEvent` | not wired |
| search | SQS indexer | — | file/document events | `SQS_ENABLED=false` |

Eventing is disabled for all tenants by design (AGENTS.md: avoids cross-tenant
consumers). Every event-driven SLI (queue age, DLQ, index freshness, notification
fan-out) therefore has **no runtime evidence in t-main**; it needs an environment
that runs SNS/SQS before the Phase 0 gate.

## Data stores

| Store | Used by | Isolation in t-main | Shared blast radius |
|---|---|---|---|
| RDS PostgreSQL (one instance) | auth, document, analytics (when PostgreSQL backend), admin, report | database `otterworks_main` | **all tenants share the instance**; one DB outage stops auth, so every authenticated route |
| DynamoDB tables | file (metadata), notification, audit | owner-id prefix (Tier A) | tables shared across tenants |
| S3 buckets | file (objects), audit (archive), analytics (exports), report (optional archive) | key prefix (Tier A) | buckets shared |
| Redis | gateway (chaos flags), collab state, admin | in-tenant `redis` pod | tenant only; collab continues without it, so persistence loss is silent |
| MeiliSearch | search | in-tenant `meilisearch:7700` | tenant only |
| SES / webhooks | notification | not configured | — |

## Platform (shared, out of tenant isolation)

EKS cluster `otterworks-dev` (SPOT node group), ingress-nginx (single NLB),
cert-manager, monitoring namespace (Prometheus Operator, Prometheus with
**3d retention**, Grafana, Alertmanager, Jaeger). No HPA or PDB exists for t-main
deployments; each service runs one replica.

## Fault and capacity concentration (input to Phase 1 to 3 ordering)

1. **Shared RDS instance**: auth, document, admin, report and analytics share one
   instance; auth failure takes down every authenticated journey.
2. **API gateway**: single replica, every route; per-route metrics collapse six
   prefixes into `path="other"`, so a scoped failure cannot be attributed today.
3. **Report synchronous chain**: report → analytics + audit + auth, no isolation.
4. **Single replica everywhere, no PDB/HPA**: any node (SPOT) reclaim is a full
   outage for that service.
5. **Events disabled**: async contracts are checked in but unexercised at runtime.

## Core versus legacy estate

| Estate | Components | Phase 0 treatment |
|---|---|---|
| Core (in scope) | api-gateway, auth, file, document, collab, notification, search, analytics, admin, audit, report; web-app and admin-dashboard frontends | SLIs, baseline, journeys, owners |
| Core but legacy runtime | report (Java 8 / Spring Boot 2.5) | baseline only; migration is Phase 4 |
| Legacy and non-core (out of scope) | `services/legacy-portal`, `services/legacy-portal-lambda`, `services/legacy-billing` (Oracle), `services/billing-service`, `services/industry-solutions`, `etl/legacy-extra`, `integration/legacy-bw6`, `migration/` | inventory only; not deployed in t-main |
| Demo/platform tooling (not product) | `demo-platform/`, `incident/`, `scripts/inject-bug.sh`, chaos flags | excluded from SLIs |

## Open items for owners

- Confirm the report-service ServiceMonitor path (target down while pod is Ready).
- Confirm whether `search_service_requests_total` is incremented per request (no series exported).
- Decide where the event-driven SLIs are measured (an eventing-enabled tenant).
- Platform owner: raise Prometheus retention to at least 35d or add remote-write so
  the 30-day baseline lives in Prometheus, not only in daily snapshots.
