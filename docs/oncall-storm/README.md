# On-call alert storm demo

An Alertmanager page starts a Devin session with nobody typing a prompt. The page is a storm of about a dozen alerts across four services, and Devin has to read the telemetry, find the one cause behind the storm, fix it with a migration, prove the fix under the same load and close the incident in the channel where the on-call team is watching.

The demo runs the golden build of OtterWorks in two tenants side by side: the page fires in `oncall-before`, and `oncall-after` takes the fix. Both tenants run `main` until a reviewer merges Devin's pull request into `demo-oncall-after`.

## The failure

`make oncall-arm TENANT=oncall-before` seeds 200,000 documents in 400 folders into the tenant's own Postgres, then ships a config deploy (`helm upgrade --reuse-values --set folderDigest.enabled=true`) that turns on the folder digest worker, then starts a k6 Job browsing folders through the public API at 6 virtual users for 25 minutes. The worker counts every folder every 15 seconds, `documents.folder_id` has no index, and each count is a sequential scan of 200,000 rows on a Postgres limited to 1 CPU. Postgres throttles within a few minutes, the 5-connection pool drains, folder listings wait for a connection, statements hit the 3 second `statement_timeout`, and document-service, api-gateway and the ingress all start returning 5xx with p95 above 0.5 s.

Alertmanager groups every storm alert (labels `page="oncall"`, `oncall_group="folder-storm"`, one `namespace`) into one notification to the Devin automation after a 3 minute `group_wait`, and streams the same group to the incident channel every 30 seconds. `incident/oncall/faults.yaml` holds the alerts, sizes and timings as data, and `make oncall-verify` reads it.

The fix is migration 005 adding `ix_documents_folder_id_updated_at` on `documents (folder_id, updated_at DESC)`, built `CONCURRENTLY` after the SRE asks for that in the channel. The harness never creates that index, and `make oncall-reset` drops it.

## Surfaces

| Surface | Address | Shows |
|---|---|---|
| Incident channel | `https://incident.demo.otterworks.app` (basic auth, user `oncall`) | `#inc-otterworks`: the alert card, Devin's posts, the SRE and incident manager reply box |
| Grafana | dashboard uid `oncall-storm`, variable `namespace` | user impact, pool, timeouts, digest queue, Postgres CPU and seq scans, Loki logs, deploy annotations |
| Alertmanager | the shared `monitoring` Alertmanager | one `oncall-devin` group per tenant namespace |
| Devin session | linked from the channel thread once Devin posts | the investigation, child sessions, screenshots |
| GitHub | issue (incident record) and pull request against `demo-oncall-after` | RCA, before and after numbers, k6 summary |
| Tenant web app | `https://t-oncall-before.demo.otterworks.app` | the slow folder view, logged in as `oncall-demo@otterworks.example` |

The demo user's password lives in the tenant Secret `oncall-demo-user`. Read it with `kubectl -n otterworks-oncall-before get secret oncall-demo-user -o jsonpath='{.data.password}' | base64 -d` on your own terminal and keep it off the shared screen.

## Setup

You need cluster access (`aws eks update-kubeconfig --name otterworks-dev --region us-east-1`), `kubectl`, `helm`, `jq`, `curl`, `openssl` and `python3` with PyYAML. k6 runs inside the cluster, so the presenter laptop needs no k6.

```bash
make oncall-up            # tenants, tenant Postgres, incident channel, Loki/Tempo/routes
make oncall-status        # both tenants ready, worker off, nothing firing
```

`make oncall-up` pushes `origin/main` to `demo-oncall-before` and `demo-oncall-after` only when a branch does not exist yet, and CD (`.github/workflows/cd-tenant.yml`) builds the tenant from it. A run that finds both tenants already deployed only wakes them and reapplies Postgres, the channel and the platform pieces. Register the automation once per org from `automation.md`, then export `ONCALL_DEVIN_WEBHOOK_URL` and `ONCALL_DEVIN_WEBHOOK_SECRET` before `make oncall-platform-up` so the Alertmanager route reaches Devin. Export `ONCALL_SRE_USER_ID` and `ONCALL_IM_USER_ID` (the Devin user ids the two channel personas reply as) before `make oncall-up` so channel replies reach the session.

Arm the before tenant 10 minutes ahead of the slot where the page should land:

```bash
make oncall-arm TENANT=oncall-before
make oncall-verify TENANT=oncall-before EXPECT=before   # green from about minute 6
```

When the live page fails (automation disabled, webhook rejected), `make oncall-simulate` replays the recorded storm (`incident/oncall/fixtures/storm-payload.json`) to the channel, and to Devin as well when `ONCALL_DEVIN_WEBHOOK_URL` is set.

## Reset

```bash
make oncall-reset
```

Reset disarms both tenants with a Helm upgrade that turns the worker off, truncates the seeded rows, drops the fix index if a proof created it, stamps Alembic back to the last revision on `main`, force-pushes `demo-oncall-before` and `demo-oncall-after` to `origin/main` only when a branch differs, clears the channel threads and deletes `incident/oncall/.state`. CD redeploys a tenant whose branch moved, which takes about 8 minutes. Close Devin's pull request and issue by hand, since reset leaves GitHub history alone.

`make oncall-teardown` removes both tenants (through `scripts/teardown-tenant.sh`), the channel and the platform pieces. Use it after the event, since `make oncall-up` from nothing takes about 20 minutes.

## Files

| Path | Purpose |
|---|---|
| `incident/oncall/vars.env` | every knob, overridable from the environment |
| `incident/oncall/faults.yaml` | the storm as data: seed, deploy, load, alerts, gates |
| `incident/oncall/*.sh` | up, seed, arm, disarm, status, verify, simulate, reset, teardown |
| `incident/oncall/k8s/` | tenant Postgres with postgres-exporter, the k6 Job |
| `incident/oncall/k6/folders.js` | the folder browsing load |
| `infrastructure/helm/tenant-values/oncall-*/` | document-service overlays for each tenant |
| `.workshop/playbooks/oncall-storm.devin.md` | the `!oncall_storm` playbook the paged session follows |
| `.agents/skills/oncall-storm/SKILL.md` | the commands and rules the session loads |
| `docs/oncall-storm/runbook.md` | the alert runbook every storm alert links to |
| `docs/oncall-storm/automation.md` | the automation that answers the page |
| `docs/oncall-storm/talk-track.md` | what to say and which screen is up |
