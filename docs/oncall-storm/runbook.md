# On-call storm alert runbook

Every storm alert carries `page="oncall"`, `oncall_group="folder-storm"`, its `service`, `severity`, the tenant `namespace`, and the chart labels `branch` and `fix_branch`. Alertmanager sends the whole group as one page, so read the group before any single alert: when the Postgres alerts and the document-service pool alerts fire together, the edge and gateway alerts are their downstream symptom and need no separate fix.

The commands below assume `NS=otterworks-oncall-before` (or the namespace on the alert) and cluster access. Port-forward Prometheus with `kubectl -n monitoring port-forward svc/prometheus-operated 9090` when a query needs it. The Grafana dashboard `oncall-storm` has one panel for each alert, in the same order as this page.

## Triage order

1. Open the Grafana dashboard for the namespace and note when p95 and 5xx left their baseline.
2. Check deploy history with `helm -n $NS history document-service`, and compare the newest revision time with the start of the storm. The Grafana annotation names the change.
3. Look at the Postgres row: CPU throttling, active connections and the `documents` sequential scan rate.
4. List what Postgres is running with `kubectl -n $NS exec deploy/oncall-postgres -c postgres -- psql -U otterworks -d otterworks -c "SELECT pid, now() - query_start AS age, left(query, 120) FROM pg_stat_activity WHERE state = 'active' ORDER BY age DESC"`.
5. Write down the one cause before you act on any single alert.

## EdgeErrorRatioHigh

More than 5% of requests for the tenant's hosts return 5xx at the shared ingress (`nginx_ingress_controller_requests`, `exported_namespace` equal to the tenant). Users see failed page loads. The ingress is a pass-through here, so check which upstream returns the errors: `api-gateway` for `api-t-*` hosts and `web-app` for `t-*` hosts. When `GatewayErrorRatioHigh` fires at the same time, start there.

## EdgeLatencyP95High

The ingress p95 for the tenant's hosts is above 0.5 s. Compare it with `GatewayLatencyP95High` and `FolderListLatencyHigh`. When all three rise together, the time is spent in document-service or below, and the ingress is healthy.

## GatewayErrorRatioHigh

More than 5% of `/api/v1/documents` requests through api-gateway return 5xx (`api_gateway_http_requests_total`). The gateway only forwards these requests, so a 502 or 504 here means document-service failed or timed out. Read the gateway log with `kubectl -n $NS logs deploy/api-gateway --since=10m | grep -c ' 50[0-9] '` and move on to `DocumentServiceErrorRateHigh`.

## GatewayLatencyP95High

The gateway p95 for `/api/v1/documents` is above 0.5 s (`api_gateway_http_request_duration_seconds_bucket`). A gateway p95 that tracks the document-service p95 within a few milliseconds puts the time behind the gateway.

## FolderListLatencyHigh

The document-service p95 for `GET /api/v1/documents/` is above 0.5 s (`http_request_duration_seconds_bucket`). A folder listing reads at most 50 rows, so a slow listing is waiting for a pool connection or for Postgres CPU. Open a slow trace in Tempo from the dashboard link: a long gap before the first SQL span is pool wait, and a long SQL span is the database.

## DocumentServiceErrorRateHigh

More than 5% of document-service responses are 5xx. Group the errors by cause in Loki with `{namespace="$NS", app="document-service"} |= "error"`. `db_statement_timeout` lines point at `DbStatementTimeouts`, and `QueuePool limit` or pool timeout lines point at `DbPoolSaturated`.

## DbPoolSaturated

At least 90% of the SQLAlchemy pool has been checked out for 2 minutes (`otterworks_db_pool_checked_out` over `otterworks_db_pool_capacity`). The pool holds 5 connections with no overflow on the on-call tenants, so 4 busy connections already fire the alert. Find the connection holders: the folder digest worker shares the API's pool, and its jobs show in `pg_stat_activity` as `SELECT count(*), max(documents.updated_at) FROM documents WHERE documents.folder_id = ...`. Raising the pool size moves the load onto a Postgres that is already throttled, so treat it as a last resort.

## DbStatementTimeouts

Statements are hitting the 3 second `statement_timeout` (`otterworks_db_statement_timeouts_total`), and Loki has the statement text on each `db_statement_timeout` line. Take the slowest statement to the tenant Postgres and run `EXPLAIN (ANALYZE, BUFFERS)` on it. A `Seq Scan on documents` with `Rows Removed by Filter` near 200,000 is a missing index, and the fix is a migration.

## FolderDigestBacklogGrowing

The folder digest queue is deeper than 200 jobs or its oldest job is older than 60 s (`otterworks_folder_digest_queue_depth`, `otterworks_folder_digest_oldest_job_age_seconds`). The worker enqueues every folder each interval, so a growing backlog means each job takes longer than the interval allows. Check when the worker was turned on with `helm -n $NS get values document-service | grep -A3 folderDigest` and `helm -n $NS history document-service`, then read `otterworks_folder_digest_job_duration_seconds` for the per-job cost.

## PostgresCPUThrottled

The tenant Postgres container spends more than 25% of CFS periods throttled (`container_cpu_cfs_throttled_periods_total`, container `postgres`). The container has a 1 CPU limit, so sustained throttling means the query mix needs more than one core. Check `pg_stat_user_tables_seq_scan` for `documents` on the dashboard and the top statements with `SELECT calls, round(mean_exec_time) AS ms, left(query, 100) FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 5`. Raising the CPU limit buys time, and an index on the scanned column removes the work.

## PostgresActiveConnectionsHigh

Active Postgres sessions are at or above 80% of the application pool capacity (`pg_stat_activity_count{state="active"}`). With a pool of 5, four active statements fire the alert. Compare the active queries with the digest worker's query text; when most of them are the folder count, the worker is holding the pool.

## PostgresLongRunningQueries

The longest open transaction is older than 2 s (`pg_stat_activity_max_tx_duration`). Use the `pg_stat_activity` query from the triage order to find the statement, and run `EXPLAIN (ANALYZE, BUFFERS)` on it with a real folder id from `SELECT folder_id FROM documents LIMIT 1`. Cancel a single runaway with `SELECT pg_cancel_backend(<pid>)` only to buy time, since the worker submits the same query on its next interval.

## Closing the incident

The incident is over when no storm alert fires for the namespace under the same k6 load and the folder-list p95 is back under 0.5 s. `make oncall-verify TENANT=<tenant> EXPECT=after` checks both conditions. The incident manager closes the incident from the channel after the RCA is posted.
