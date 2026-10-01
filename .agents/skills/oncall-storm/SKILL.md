---
name: oncall-storm
description: >
  Repo-specific mechanics for the OtterWorks on-call alert storm demo: two
  tenants (oncall-before pages, oncall-after takes the fix), the harness
  commands that arm, verify and reset them, the port-forwards to Prometheus,
  Alertmanager, Grafana, Loki and Tempo, the tenant Postgres commands for
  EXPLAIN and migrations, the incident channel API, the state and report file
  locations, and the secret handling rules. Load it with the !oncall_storm
  playbook when an Alertmanager group with page=oncall arrives.
---

# On-call storm: OtterWorks

The `!oncall_storm` playbook (`.workshop/playbooks/oncall-storm.devin.md`) says
what to do and in which order. This skill holds the commands. Presenter docs
are in `docs/oncall-storm/`.

## Tenants and names

| | Before | After |
|---|---|---|
| Tenant id | `oncall-before` | `oncall-after` |
| Namespace | `otterworks-oncall-before` | `otterworks-oncall-after` |
| Branch CD ships | `demo-oncall-before` | `demo-oncall-after` |
| Web | `https://t-oncall-before.demo.otterworks.app` | `https://t-oncall-after.demo.otterworks.app` |
| API | `https://api-t-oncall-before.demo.otterworks.app` | `https://api-t-oncall-after.demo.otterworks.app` |
| Role | pages, stays unfixed | takes migration 005 for the proof |

`make oncall-up` creates both branches from `origin/main`. Every alert carries
`fix_branch="demo-oncall-after"`, and the PR base is that branch. Branch your
fix from `origin/demo-oncall-after`, push only your own `devin/...` branch, and
leave the merge to a human reviewer.

Shared pieces: Prometheus, Alertmanager, Grafana, Loki and Tempo in namespace
`monitoring`; the incident channel (Service `incident-channel`, port 8080) in
`otterworks-platform` at `https://incident.demo.otterworks.app`; Grafana at
`https://grafana.otterworks.app`, dashboard uid `oncall-storm` with variable
`namespace`.

## Harness commands

All knobs are in `incident/oncall/vars.env`, and `incident/oncall/faults.yaml`
holds the storm as data (alerts, gates, fix). Run from the repository root.

| Command | What it does |
|---|---|
| `make oncall-status` | Helm revision, worker flag, seed counts, k6 Job, firing storm alerts, Alertmanager groups. Read-only. |
| `make oncall-arm TENANT=oncall-after` | Wakes the tenant if idle-suspend scaled it to zero, seeds 200,000 documents in 400 folders, runs `helm upgrade --reuse-values --set folderDigest.enabled=true` on document-service, annotates Grafana, starts Job `oncall-k6` (6 VUs, 25 minutes). `LOAD=0` stops before k6. On `oncall-after` only, `ONCALL_MIGRATE_REF=<your fix branch>` runs `alembic upgrade` to that branch's newest revision right after the rollout. With `LOAD=0` or a migrate ref, arm silences `page="oncall"` alerts in `otterworks-oncall-after` until k6 starts, for 15 minutes at most. |
| `make oncall-load TENANT=oncall-after` | Expires the arm's silence on the namespace, then replaces Job `oncall-k6` with a fresh 25-minute run. Restarts no pod. |
| `make oncall-verify TENANT=oncall-before EXPECT=before` | Green when at least 10 of the 12 storm alerts fire across all 4 services and Alertmanager holds exactly one `oncall-devin` group for the namespace. |
| `make oncall-verify TENANT=oncall-after EXPECT=after` | Green when k6 has run at least 300 s, the worker is on, no storm alert fires, Alertmanager holds no `oncall-devin` group and no harness silence for the namespace, folder-list p95 over 5m is at or under 0.5 s, and the request rate is at least 0.5/s. |
| `make oncall-quiet TENANT=oncall-after MINUTES=15` | Silences `page=oncall` on the namespace so the teardown after the close does not page again. Disarm expires it. |
| `make oncall-disarm TENANT=oncall-after` | Deletes the k6 Job, turns the worker off with a Helm upgrade, then expires harness silences. Refuses while the database is at 005. |
| `make oncall-simulate` | Replays the recorded page to the channel. Presenter fallback. |

`make oncall-up`, `make oncall-platform-up`, `make oncall-reset` and
`make oncall-teardown` are presenter commands. A paged session never runs them.

State: `incident/oncall/.state/<tenant>.json` (arm stages, Helm revisions,
annotation id, verify results). Reports: `incident/oncall/reports/<tenant>-<before|after>-<utc>.json`,
one per verify run. Both are git-ignored, so name the report files in the PR
instead of committing them.

## Cluster access and port-forwards

```bash
aws eks update-kubeconfig --name otterworks-dev --region us-east-1
kubectl -n monitoring port-forward svc/prometheus-prometheus 9090:9090 >/dev/null 2>&1 &
kubectl -n monitoring port-forward svc/prometheus-alertmanager 9093:9093 >/dev/null 2>&1 &
kubectl -n monitoring port-forward svc/prometheus-grafana 3000:80 >/dev/null 2>&1 &
kubectl -n monitoring port-forward svc/oncall-loki 3100:3100 >/dev/null 2>&1 &
kubectl -n monitoring port-forward svc/oncall-tempo 3200:3200 >/dev/null 2>&1 &
```

Loki and Tempo are the on-call platform's own single-binary installs
(`incident/oncall/platform/`). Grafana also reaches both through its datasources
(uids `loki` and `tempo`), so Explore in the browser works without those two
forwards.

Queries that answer the playbook's telemetry step, with `NS` set to the namespace:

```bash
q() { curl -fsS -G http://localhost:9090/api/v1/query --data-urlencode "query=$1" | jq -c '.data.result'; }
q "ALERTS{alertstate=\"firing\",page=\"oncall\",namespace=\"$NS\"}"
q "histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{namespace=\"$NS\",handler=\"/api/v1/documents/\"}[5m])))"
q "otterworks_db_pool_checked_out{namespace=\"$NS\"} / otterworks_db_pool_capacity{namespace=\"$NS\"}"
q "sum by (source) (rate(otterworks_db_statement_timeouts_total{namespace=\"$NS\"}[5m]))"
q "otterworks_folder_digest_queue_depth{namespace=\"$NS\"}"
q "rate(container_cpu_cfs_throttled_periods_total{namespace=\"$NS\",container=\"postgres\"}[5m]) / rate(container_cpu_cfs_periods_total{namespace=\"$NS\",container=\"postgres\"}[5m])"
q "rate(pg_stat_user_tables_seq_scan{namespace=\"$NS\",relname=\"documents\"}[5m])"
curl -fsS -G http://localhost:3100/loki/api/v1/query_range \
  --data-urlencode "query=sum by (event) (count_over_time({namespace=\"$NS\", app=\"document-service\"} | json | event=~\"db_statement_timeout|folder_digest_job_failed\" [15m]))" | jq -c '.data.result'
curl -fsS -G http://localhost:3200/api/search --data-urlencode "tags=service.name=document-service" \
  --data-urlencode 'minDuration=1s' --data-urlencode 'limit=5' | jq -c '.traces'
```

Grafana's login is in Secret `monitoring/grafana-admin` (keys `admin-user`,
`admin-password`). Read it into variables and type it into the browser
login, without printing it.

## Tenant Postgres

Deployment and Service `oncall-postgres` (Postgres 15, 1 CPU, `pg_stat_statements`
loaded, postgres-exporter sidecar) in each tenant namespace. Database and user
are both `otterworks`. document-service reads `DOC_SVC_DATABASE_URL` from
Secret `oncall-postgres` key `url`.

```bash
psql_t() { kubectl -n "$NS" exec -i deploy/oncall-postgres -c postgres -- psql -U otterworks -d otterworks -v ON_ERROR_STOP=1 "$@"; }
psql_t -c '\d documents'
psql_t -c "SELECT pid, now() - query_start AS age, wait_event_type, left(query, 100) FROM pg_stat_activity WHERE state = 'active' ORDER BY age DESC"
psql_t -c "SELECT calls, round(mean_exec_time) AS mean_ms, left(query, 100) FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 5"
F="$(psql_t -Atc 'SELECT folder_id FROM documents WHERE folder_id IS NOT NULL LIMIT 1')"
psql_t -c "EXPLAIN (ANALYZE, BUFFERS) SELECT count(*), max(updated_at) FROM documents WHERE folder_id = '$F' AND is_deleted = false"
psql_t -c "EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM documents WHERE folder_id = '$F' AND is_deleted = false ORDER BY updated_at DESC LIMIT 50"
```

Let the arm apply the fix on `oncall-after`. `demo-oncall-after` ships no
revision 005 while the PR is open, and document-service runs
`alembic upgrade head` on start, so a document-service pod that starts while
the database is at 005 crash-loops. The migration therefore has to follow the
arm rollout. But the arm turns the worker on against the unindexed table, and
the worker alone fires `page="oncall"` alerts within about three minutes,
which would page Devin and open a channel thread for the fixed tenant. Push
your fix branch first. Then
`ONCALL_MIGRATE_REF=<branch> make oncall-arm TENANT=oncall-after LOAD=0`
waits for the rollout and runs `alembic upgrade 005` from that branch inside a
ready document-service pod right away, well inside the alerts' `for:` windows.
The arm also silences the namespace's `page="oncall"` alerts from just before the
deploy until `make oncall-load` starts k6, so nothing in that gap can page.
Arm and disarm both roll document-service and refuse to run once the database
is at 005. Wake the tenant first, since idle-suspend scales the whole
namespace, `oncall-postgres` included, to zero after an hour without ingress
traffic:

```bash
scripts/tenant-scale.sh oncall-after up
kubectl -n otterworks-oncall-after rollout status deploy/oncall-postgres deploy/document-service deploy/api-gateway --timeout=5m
git push origin HEAD
ONCALL_MIGRATE_REF="$(git branch --show-current)" make oncall-arm TENANT=oncall-after LOAD=0
make oncall-load TENANT=oncall-after
```

To run Alembic from your branch by hand (a downgrade, or an upgrade after a
change to the migration), go through a port-forward, with the database URL
read from Secret `oncall-postgres`:

```bash
kubectl -n otterworks-oncall-after port-forward svc/oncall-postgres 15432:5432 >/dev/null 2>&1 &
cd services/document-service
DOC_SVC_DATABASE_URL="$(kubectl -n otterworks-oncall-after get secret oncall-postgres -o jsonpath='{.data.url}' | base64 -d | sed 's#@oncall-postgres:5432/#@localhost:15432/#')" \
  alembic upgrade 005
cd ../..
```

Use `alembic downgrade 004` the same way to rebuild the index after a change to
the migration, and once more before `make oncall-disarm`. Run
`make oncall-quiet TENANT=oncall-after` before that last downgrade: dropping
the index while the worker is still on throttles Postgres again and pages. `make oncall-reset`
drops the index and stamps Alembic back before it disarms, so the proof leaves
nothing behind even when a session stopped at 005.

## Deploy history

```bash
helm -n "$NS" history document-service
helm -n "$NS" get values document-service --revision <n>
kubectl -n "$NS" get deploy document-service -o jsonpath='{.spec.template.spec.containers[0].image}'
```

The arm step records the revision it created in `.state/<tenant>.json` under
`.steps.deploy.revision` and posts the Grafana annotation
`document-service rev N: folder digest worker enabled`. A checkout that did not
arm the tenant has no `.state`, so `make oncall-verify` reads the live
`monitoring.rules.extraLabels.oncall_run` from `helm get values` and the deploy
time from `helm history` (the oldest revision in the run carrying that label),
then caches both in `.state`.

## Incident channel

`POST https://incident.demo.otterworks.app/api/threads/{groupKey}/messages` with
`Authorization: Bearer $INCIDENT_CHANNEL_TOKEN` and JSON
`{"author": "Devin", "text": "...", "session_url": "...", "session_id": "devin-...", "org_id": "org-...", "attachments": ["https://..."]}`.
URL-encode the `groupKey`, or use `latest` for the newest thread. The playbook's
`channel_post` function does both. Replies from the SRE and the incident manager
arrive in the session as user messages through the Devin API once a post has
bound the thread to the session.

## k6

Job `oncall-k6` runs `incident/oncall/k6/folders.js` from ConfigMap
`oncall-k6-script` and signs its own HS256 JWT with the tenant's
`api-gateway-secrets` JWT secret, passed in by `secretKeyRef`. It browses
`GET /api/v1/documents/?folder_id=<f>&page=1&size=50` across the 400 seeded
folders with 1 to 3 s think time. When the run ends, its log holds the k6 table
and one line starting `K6_SUMMARY_JSON`:

```bash
kubectl -n "$NS" logs job/oncall-k6 | tail -n 40
```

## Secret rules

Never print, log, post or commit: `$INCIDENT_CHANNEL_TOKEN`, Secret
`oncall-postgres` (`url`, `password`), Secret `oncall-demo-user`,
`api-gateway-secrets`, `monitoring/grafana-admin`, Alertmanager config, AWS
credentials. Read them into environment variables, pipe them through stdin,
and keep `set -x` off. Redact them from screenshots.
