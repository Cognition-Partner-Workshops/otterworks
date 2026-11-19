# Operational data layer

`odl_sync` synchronizes Db2, Oracle and PostgreSQL into deterministic MongoDB
golden customers, serves a gateway-authenticated read API, and independently
audits source/target parity. Python 3.12 is required.

## Components and document shape

The decided model is **option 1: one document per golden customer**, with embedded
source records, history/cases, provenance and exception references in
`odl.customers`. The authoritative mapping, indexes, K1–K8 normalization and
C1–C4 conflict decisions are in
[odl-source-mapping](../../.agents/skills/odl-source-mapping/SKILL.md), sections 3–7.

- `extract/{db2,oracle,postgres}.py`: independent source reads, mapped records and
  unplaced transformation/orphan records.
- `merge.py`: exact normalized name/address matching, deterministic UUID5 IDs,
  separate unconfirmed candidates and DST ambiguity references.
- `load.py`: indexed unordered bulk upserts, content-hash skipping of unchanged
  documents, and removal of stale customer/exception IDs. A source failure skips
  writes for the whole run rather than deleting the failed source's projection.
  Unique-key ownership is released before assigning changed keys; interrupted
  releases are retried on the next run. Snapshot publication is not transactional.
- `api.py`: FastAPI reads and a background sync loop in one process.
- `parity.py`: independent SQL versus MongoDB counts, column profiles, keyed
  hashes and deterministic sampled values for all seven source tables. Reports
  are upserted by `run_id` into `odl.parity_reports` and exported as CSV.

## Sources and environment

Source DDL and loaders live in `services/odl-sources`; CRM is loaded through
`scripts/seed.py --crm`. Each tenant uses namespace `otterworks-<ID>`.

| Source | In-cluster location | Tables |
| --- | --- | --- |
| Db2 | `db2-archive:50000`, database `ODL` | `ODL.CUSTMAST`, `ODL.ACCTHIST` |
| Oracle | `oracle:1521/FREEPDB1` | `ACCOUNTS`, `PRODUCTS` |
| PostgreSQL | Shared RDS, tenant database `otterworks_<ID>` | `crm.contacts`, `crm.service_cases`, `crm.subscription_snapshots` |

Supply credentials through environment variables, never tracked files or command
arguments. The chart reads these existing Secrets:

| Required variables | In-cluster value / Secret keys |
| --- | --- |
| `DB2_HOST`, `DB2_PORT`, `DB2_DATABASE` | `db2-archive`, `50000`, `ODL` |
| `DB2_USER`, `DB2_PASSWORD` | `db2-archive-credentials`: same keys |
| `ORACLE_DSN` | `oracle:1521/FREEPDB1` |
| `ORACLE_USER`, `ORACLE_PASSWORD` | `odl-oracle`: same keys |
| `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` | `odl-postgres`: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` |
| `MONGO_HOST`, `MONGO_PORT` | `operational-data-layer-mongo`, `27017` |
| `MONGO_USER`, `MONGO_PASSWORD` | `operational-data-layer-mongo`: `username`, `password` |
| `MONGO_DATABASE`, `MONGO_AUTH_SOURCE` | `odl`, `odl` |
| `JWT_SECRET` (API only) | `api-gateway-secrets`: `JWT_SECRET` |

For port-forwards, override hosts/ports and the Oracle DSN with loopback addresses.
Optional API settings: `ODL_HOST=0.0.0.0`, `ODL_PORT=8098`,
`ODL_SYNC_INTERVAL_SECONDS=60` (positive seconds between runs).

## Run locally

From `services/operational-data-layer`, with a private connection environment loaded:

```sh
python -m pip install -e '.[test]'
python -m odl_sync.sync --once
python -m odl_sync.api                         # API + background sync, metrics on :8098
python -m odl_sync.parity --run-id audit-001 --csv /tmp/odl-parity-audit-001.csv
```

Run IDs are 1–128 URL-safe letters/digits, dots, underscores or hyphens, starting
with a letter/digit. `latest` and IDs ending in `.csv` are reserved.

Standalone continuous sync is also available with
`python -m odl_sync.sync --interval 60`; it exposes metrics on port 9108.

## Read API

The gateway routes `/api/v1/odl` to `ODL_SERVICE_URL` (default
`http://operational-data-layer:8098`) and requires its normal bearer JWT. The
API also validates the same tenant JWT signature and expiration, including for
direct in-cluster reads. Only `/health` and `/metrics` are unauthenticated. Decimal values are
JSON strings; timestamps use UTC ISO-8601 with `Z`.

| Relative route | Purpose |
| --- | --- |
| `GET /customers/{id}` | Golden customer; 404 if absent |
| `GET /customers` | Filter by `db2_cust_no`, `oracle_account_id`, `crm_contact_id`, `match_status`; bounded `limit` and `_id` `cursor` pagination |
| `GET /exceptions`, `GET /exceptions/{id}` | Paged `reason`/`status` filtering or one exception |
| `GET /parity`, `GET /parity/latest` | Newest-first run summaries or latest summary |
| `GET /parity/{run_id}`, `GET /parity/{run_id}.csv` | Stored full report (large sample lists limited) or streamed CSV |

Internal `/health` checks MongoDB; `/metrics` emits Prometheus text. The Angular
`/odl-parity` page uses authenticated HttpClient requests, including CSV blobs.

## Mapping exceptions

`odl.mapping_exceptions` stores deterministic IDs, `source_keys`, `customer_ids`,
raw detail strings and `status: open`. Reasons are `transform_failed`,
`duplicate_match_key`, `orphan_history`, `orphan_service_case`,
`orphan_subscription`, `candidate_match_unconfirmed` and `ambiguous_local_time`.
Unplaceable rows are not merged. Candidate pairs stay separate single-source
customers; candidate and ambiguity exceptions are referenced by their owners.
Source updates preserve review-owned fields such as status, reviewer, notes and
resolution timestamps. Duplicate parents' attached child rows become orphan
exceptions rather than disappearing. Per-source name/address spellings are kept
in `source_records` for exact parity independently of the canonical display text.

## Images

After normal AWS/ECR authentication, build from the repository root with a unique
committed revision tag. ECR repositories are Terraform-managed:

```sh
REGISTRY=599083837640.dkr.ecr.us-east-1.amazonaws.com
REV=$(git rev-parse --short HEAD)
docker build -t "$REGISTRY/otterworks-odl/odl-sync:$REV" services/operational-data-layer
docker push "$REGISTRY/otterworks-odl/odl-sync:$REV"
docker build -t "$REGISTRY/otterworks/api-gateway:odl-$REV" services/api-gateway
docker push "$REGISTRY/otterworks/api-gateway:odl-$REV"
docker build --build-arg BASE_HREF=/admin/ -t "$REGISTRY/otterworks/admin-dashboard:odl-$REV" frontend/admin-dashboard
docker push "$REGISTRY/otterworks/admin-dashboard:odl-$REV"
```

Pin `sync.image` and the t-odl UI values files to the published tags/digests before
deploying. `BASE_HREF` is baked into the dashboard image, not a runtime variable;
omit the build argument for ordinary root-hosted dashboards.

## Deploy and remove

The target chart installs MongoDB and the combined API/sync Deployment and
ClusterIP Service on port 8098. `sync.enabled` defaults to true; `sync.image`,
`sync.intervalSeconds` and `sync.resources` configure the runtime.

```sh
scripts/odl/deploy-target-observability.sh
scripts/odl/deploy-odl.sh <ID> --mode after
# Restore just t-odl's pinned gateway and /admin/ dashboard:
scripts/odl/deploy-odl-ui.sh odl
# Or install only the target in an existing tenant:
helm upgrade --install operational-data-layer services/operational-data-layer/deploy \
  -n otterworks-<ID> --post-renderer scripts/odl/helm-labels.py \
  --labels run_token=odl-1795112287 --wait --timeout 3m
helm uninstall operational-data-layer -n otterworks-<ID>
```

Only `deploy-odl.sh odl --mode after` invokes the t-odl UI helper. Its committed
`scripts/odl/t-odl-{gateway,admin}.values.yaml` files preserve the published image
pins, gateway ODL URL, ClusterIP routing, and the `/admin(/|$)(.*)` shared-nginx
ingress on `t-odl.demo.otterworks.app`. It reuses the gateway's tenant Secrets
and installs no admin-service: login uses auth-service. Dashboard monitoring is
disabled because static nginx does not expose Prometheus metrics. Other tenant
IDs and `--mode before` do not receive these UI overrides.

The separate `odl-observability` release in `monitoring` sets
`mongodb.enabled=false,sync.enabled=false,observability.enabled=true`; its global
rules/dashboard survive removing a tenant target. Normal targets default to
`observability.enabled=false`, avoiding duplicate global rules. Prometheus
selects all rule namespaces; Grafana watches `grafana_dashboard=1` in all namespaces.

MongoDB uses the mirrored official `mongo:8.0.16` image. The chart preserves the
four credential Secret keys on upgrade; the init script creates only the
`odl_app` read/write user in database `odl`. Sync creates business collections and
indexes. Default data storage is **emptyDir**: pod deletion erases the copy, and
sync rebuilds it after wake. `persistence.existingClaim` may reference a PVC backed
by a Terraform-provisioned static volume; the chart provisions no PV/PVC or EBS.
MongoDB and sync carry `otterworks.io/scale-with-tenant: "true"`.

### Isolation limitation

MongoDB's NetworkPolicy permits only same-namespace pods on port 27017; the
tenant baseline excludes MongoDB from its broader allowances. The shared
cluster's VPC CNI was audited with `--enable-network-policy=false`, so declared
policies were not enforced and cross-namespace MongoDB TCP access was observed.
Authentication remains required. No CNI settings are changed by this runtime.

## Metrics contract

The combined API/sync process now emits this contract at `/metrics`; its
ServiceMonitor scrapes the HTTP port every 30 seconds. Kubernetes discovery
attaches the target's **namespace** label, not a user-supplied tenant parameter.
Lag is unpublished until a source first succeeds and then measures time since
that extract's start checkpoint. Missing series do not page.

| Exact metric | Type | Application labels | Unit / meaning |
| --- | --- | --- | --- |
| `odl_sync_lag_seconds` | gauge | `source` | Seconds since the newest successfully applied source change/checkpoint; publish 0 only when caught up, not when uninitialized |
| `odl_sync_records_total` | counter | `source` | Records successfully applied to MongoDB, including updates; increment only after successful writes |
| `odl_sync_errors_total` | counter | `source`, `reason` | Failed sync attempts; initialize known label combinations to 0 |
| `odl_read_requests_total` | counter | `route`, `status` | Completed read API requests; one increment per request |
| `odl_read_request_duration_seconds` | classic histogram | `route`, `status` | Server-side elapsed seconds per completed read request; emits `_bucket` (`le` added), `_sum`, `_count` |

`source` is exactly `db2`, `oracle`, or `postgres`. `reason` is one of `connect`,
`read`, `transform`, `write`. `route` is a bounded route template (for example
`/customers/{id}`), never a raw path or customer ID; `status` is a three-digit
HTTP status string. Do not use exception messages or identifiers as labels.
Histogram buckets in seconds: 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5,
5, 10, +Inf. Counters reset on process restart; consumers use `rate(...[5m])`.

`observability/prometheus/odl_rules.yml` defines recordings for maximum lag per
namespace/source, record/error rates, read request rate per namespace/route,
p50/p95/p99 read latency, and 5xx request ratio. The dashboard uses these same
recordings (derived by Prometheus, not emitted by the service):

| Recording name | Labels | Unit |
| --- | --- | --- |
| `odl:sync_lag_seconds:max` | namespace, source | seconds |
| `odl:sync_records:rate5m` | namespace, source | records/second |
| `odl:sync_errors:rate5m` | namespace, source | errors/second |
| `odl:read_requests:rate5m` | namespace, route | requests/second |
| `odl:read_request_duration_seconds:p50` | namespace, route | seconds |
| `odl:read_request_duration_seconds:p95` | namespace, route | seconds |
| `odl:read_request_duration_seconds:p99` | namespace, route | seconds |
| `odl:read_errors:ratio5m` | namespace, route | fraction, 0–1 |

Lag >120s for 10m warns; >300s for 10m pages. Read p95 >0.5s for 10m
warns and p99 >2s for 10m pages, both gated on >1 request/s. Only critical alerts
carry `page: devin`; all alerts carry severity. These are provisional operational
thresholds, not a document-model decision or a claim that a service exists.

Canonical rules/dashboard sources are copied into chart `files/` by
`scripts/sync-odl-chart-files.sh`; `--check` rejects drift. Validate rules with
`promtool check rules observability/prometheus/odl_rules.yml` and alert tests with
`promtool test rules observability/prometheus/odl_rules.test.yml`.
