# Operational data layer target scaffold

The future operational data layer will synchronize the three tenant sources into
MongoDB and serve a read API over that operational copy. This branch supplies
only an empty authenticated target and observability contracts. It implements
neither synchronization nor a read API, and chooses no customer document model.

## Sources

The source implementation and deployment wrapper live on
`devin/1795112287-odl-sources`; merge that branch before running the combined flow.
Each tenant uses namespace `otterworks-<ID>`:

| Source | Location | Default business tables |
| --- | --- | --- |
| Db2 | `db2-archive:50000`, database `ODL`; chart `infrastructure/helm/db2-archive` | `ODL.CUSTMAST` (50,000), `ODL.ACCTHIST` (400,000) |
| Oracle Free | `oracle:1521/FREEPDB1`; `services/odl-sources/oracle` | `ACCOUNTS` (40,000), `PRODUCTS` (4) |
| PostgreSQL | Shared RDS, tenant database `otterworks_<ID>`, schema `crm` | `contacts` (30,000), `service_cases` (60,000), `subscription_snapshots` (30,000) |

Source DDL, deterministic configuration, and loaders are in
`services/odl-sources`; CRM is loaded through `scripts/seed.py --crm`.
See the [ODL manifest](../../demos/app/complexity-manifest.json#odl).

## Deploy and remove

The chart is `services/operational-data-layer/deploy`; the sources wrapper's
`--mode after` installs it with release name **operational-data-layer**. It adds
MongoDB only, not an application Deployment. Install the cluster-wide monitoring
release once (the wrapper may call this idempotent script):

```sh
scripts/odl/deploy-target-observability.sh
# With the sources branch merged:
scripts/odl/deploy-odl.sh <ID> --mode after
# Or install just this target in an existing tenant:
helm upgrade --install operational-data-layer services/operational-data-layer/deploy \
  -n otterworks-<ID> --labels run_token=odl-1795112287 --wait --timeout 3m
helm uninstall operational-data-layer -n otterworks-<ID>
```

The monitoring script uses a separate **odl-observability** Helm release in
`monitoring`, with `mongodb.enabled=false,observability.enabled=true`. Its global
rules and namespace-selectable dashboard survive removing a tenant target. The
normal target defaults to `observability.enabled=false`, avoiding duplicate
cluster-wide recording rules across tenants. The Prometheus selectors select
all rule namespaces; Grafana watches `grafana_dashboard=1` in all namespaces.

MongoDB Community is the official `mongo:8.0.16` image mirrored into the
Terraform-managed `otterworks-odl/mongo` ECR repository. A single StatefulSet and
ClusterIP Service expose `operational-data-layer-mongo:27017`. Authentication is
mandatory. Secret `operational-data-layer-mongo` contains `root-username`,
`root-password`, `username`, `password`; Helm lookup preserves all four on
upgrade. Do not print credentials or put them on command arguments. The init
script creates only a read/write application user in logical database `odl`:
no business collections, indexes, or example customer documents are created.

Default data storage is emptyDir: deleting the pod erases data and recreates
only the user. `persistence.existingClaim` may name an existing PVC backed by a
**Terraform-provisioned static volume**; this chart creates neither PVs nor PVCs
and must never trigger dynamic EBS provisioning. Preserve the credential Secret
outside the release before uninstalling if retaining a volume for reuse.
Resources default to 100m/256Mi requested and 1 CPU/1Gi limited, with a 256Mi
WiredTiger cache. Tune explicitly before loading a real projection.

The MongoDB NetworkPolicy permits only same-namespace pods on port 27017.
Kubernetes policies are additive: the tenant baseline must exclude pods labeled
`app.kubernetes.io/name=operational-data-layer-mongo` from its broader allowances.
This branch updates `scripts/deploy-tenant.sh` accordingly. For an existing
tenant created before that change, apply the equivalent selector before install:

```sh
kubectl -n otterworks-<ID> patch networkpolicy tenant-isolation --type=merge -p \
  '{"spec":{"podSelector":{"matchExpressions":[{"key":"app.kubernetes.io/name","operator":"NotIn","values":["operational-data-layer-mongo"]}]}}}'
```

## Known gaps

The shared cluster's VPC CNI runs with `--enable-network-policy=false`, so the
MongoDB NetworkPolicy is declared but not enforced. Cross-namespace MongoDB TCP
access was observed; MongoDB authentication is still required. Enforcement was
deliberately left off because enabling it activates existing policies
cluster-wide: 18 policies across 14 namespaces at the isolation audit. No CNI
settings are changed by this scaffold.

## Metrics contract

The future service must expose Prometheus text/OpenMetrics at `/metrics`.
Kubernetes discovery must attach the target's **namespace** label to every
series; it is not a user-supplied tenant parameter. No metrics are fabricated by
this scaffold, and missing series do not page. Scrape wiring belongs with the
future service, not with MongoDB.

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

## Open question: customer document shape

Competing options, intentionally undecided:

1. One document per golden customer with embedded source records and provenance.
2. Per-source documents/collections plus a separate link collection (crosswalk).
3. A canonical read projection plus separately stored source snapshots/history.

Still to decide: identity/link ownership, source precedence and conflict policy,
one-to-many accounts/contacts, embedding versus references, deletion semantics,
schema evolution, and authorization/PII boundaries. No sync implementation,
collections, indexes, or schema choices should be inferred from this scaffold.
