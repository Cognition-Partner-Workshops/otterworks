# Runbook: KYC Document Upload Latency

**Severity:** Critical (`KycUploadLatencyP99High`, pages the platform on-call rotation) / Warning (`KycUploadLatencyP99Elevated`, platform channel only)

## Alert

Branch staff upload customer KYC documents (passport scans, proof of address) through
the kyc-docs flow, which stores them in document-service as `POST /api/v1/documents/`.

- Objective: 99% of KYC document uploads finish in under 2 seconds, measured over 30 days
  (`job:kyc_upload_within_2s:ratio_rate30d`, target >= 0.99).
- `KycUploadLatencyP99High` -- the 5-minute upload p99 (`job:kyc_upload_duration_seconds:p99`)
  has stayed above 2 s for 10 minutes. Pages.
- `KycUploadLatencyP99Elevated` -- the same p99 has stayed above 1.5 s for 15 minutes. Warning only.

Rules: `observability/prometheus/kyc_upload_slo.yml`. Routing: `team=platform` in
`observability/alertmanager/alertmanager.yml.tmpl`. Dashboard: **OtterWorks - KYC Upload
Latency** (`otterworks-kyc-upload-latency`; on the shared cluster the bank tenant's copy is
`kyc-otterworks-bank`).

## Symptoms

- The onboarding desk watches the upload spinner for several seconds per document; customers
  leave without an account opened.
- The p99 line on the KYC Upload Latency dashboard sits above the red 2 s line.
- Every upload is slow (service or storage) **or** a subset is slow (one branch, big scans).

## Investigation Steps

### What to check first (five minutes)

1. **Is it still happening, and is it everyone?** On the dashboard compare p50, p95 and p99.
   p50 and p99 both high means every upload is slow (look at the service and its storage).
   p50 normal with p99 high means a minority of uploads is slow (look at the clients and
   payload sizes).
2. **Is document-service healthy?** Check `DocumentServiceErrorRateHigh`, restarts and CPU
   throttling:
   ```
   kubectl -n otterworks-bank get pods -l app.kubernetes.io/name=document-service
   kubectl -n otterworks-bank top pod -l app.kubernetes.io/name=document-service
   kubectl -n otterworks-bank describe pod -l app.kubernetes.io/name=document-service | grep -A3 "Last State"
   ```
   Locally: `docker compose ps document-service` and `make incident-status`.
3. **Did anything change?** `helm -n otterworks-bank history document-service` and the recent
   merges to `demo-bank`. A rollout that landed at the start of the slow window is the answer.
4. **Is a chaos flag set?** `chaos:document-service:slow_queries` injects 3-5 s into every
   document create. It must never be set on t-main or the bank tenant; if it is, clear it:
   ```
   scripts/inject-bug.sh bank reset          # tenant
   redis-cli DEL chaos:document-service:slow_queries   # local Compose
   ```
5. **Where does the time go?** Open the traces link on the alert (Jaeger, service
   `document-service`, operation `POST /api/v1/documents/`, min duration 2 s) and read one
   slow trace. The span tree says which of the two cases below you are in.

### Slow storage backend or slow client?

document-service writes the document (metadata and content) to PostgreSQL in one request; on
the shared cluster that is the shared RDS instance, locally the `postgres` container. There
is no object store on this path, so "storage" means Postgres.

| Signal | Slow storage backend | Slow client |
|--------|----------------------|-------------|
| Jaeger trace of a slow upload | The `INSERT` / `COMMIT` SQL spans take most of the request span | The SQL spans are milliseconds; the request span is long before the first SQL span (reading the body) |
| `Storage backend` panel (`otterworks_db_query_duration_seconds` p95, SQL seconds per upload) | Rising with the p99 | Flat |
| `Client` panel (`http_request_size_bytes` mean) | Flat | Rising, or spiky, with the p99 |
| ingress-nginx vs api-gateway `duration_ms` (CloudWatch log groups in [`docs/observability/mobile-latency.md`](../observability/mobile-latency.md)) | Both long: the time is inside the service | ingress long, api-gateway and document-service short: the time is spent receiving the body from the branch |
| `X-Request-Duration-Ms` / `X-DB-Queries` response headers | Duration high | Duration low for the same client-observed wait |
| Which uploads | All of them, p50 moves too | A branch, a client IP, a user agent, or large files only |

Queries for the storage side:

```promql
histogram_quantile(0.95, sum by (le) (rate(otterworks_db_query_duration_seconds_bucket{job="document-service"}[5m])))
sum(rate(otterworks_db_query_duration_seconds_sum{job="document-service"}[5m]))
  / sum(rate(http_requests_total{job="document-service",handler=~"/api/v1/documents/?",method="POST"}[5m]))
```

Then look at Postgres itself: `pg_stat_activity` for waits and locks, RDS `WriteLatency`,
`DiskQueueDepth`, `FreeStorageSpace` and `DatabaseConnections` in CloudWatch, and the
`postgres` panels on the Infrastructure dashboard. Long `COMMIT`s with a flat statement count
point at the volume; many short statements per upload point at the application (see the
n-plus-one incident in [`incident/README.md`](../../incident/README.md)).

Queries for the client side:

```promql
sum(rate(http_request_size_bytes_sum{job="document-service",handler=~"/api/v1/documents/?",method="POST"}[5m]))
  / sum(rate(http_request_size_bytes_count{job="document-service",handler=~"/api/v1/documents/?",method="POST"}[5m]))
```

```
# ingress-nginx log group for the tenant: client wait per upload, by client
filter route = "/api/v1/documents" and method = "POST"
| stats pct(duration_ms, 99) as p99_ms, avg(duration_ms) as avg_ms, count(*) as uploads by client
```

Run the same query on the api-gateway log group. If ingress is slow and the gateway is not,
the time is on the wire from the branch (scanner resolution, branch WAN, a VPN) and not in
OtterWorks.

## Resolution Steps

- **Storage backend slow:** check RDS for an ongoing maintenance window, a storage burst
  balance at zero or a long-running lock holder; kill the blocking session, scale the
  instance class or storage, or fail over. For a regression from a deploy, roll back
  (`helm -n otterworks-bank rollback document-service <previous>`) and fix forward on
  `demo-bank`.
- **Slow client:** confirm with the branch which scanner profile and connection they use;
  lower the scan resolution, or raise the ingress client body timeout for the upload route
  only. Nothing to roll back in OtterWorks.
- **Service regression:** revert the merge on `demo-bank`; the tenant redeploys from the
  branch (`.github/workflows/cd-tenant.yml`).

The alert resolves on its own once the 5-minute p99 drops below 2 s (the warning below
1.5 s); Alertmanager sends the resolved notification to the same receivers.

## Post-Incident

- Record the window and cause against the 30-day objective; if
  `job:kyc_upload_within_2s:ratio_rate30d` fell below 0.99 the error budget for the month is
  spent and further risky changes to document-service wait.
- If the cause was a slow client, add the branch to the known-slow list and consider per-client
  latency panels rather than tightening the service alert.
- Re-run the promtool tests after any change to the thresholds:
  `promtool test rules observability/prometheus/tests/kyc_upload_slo_test.yml`.
