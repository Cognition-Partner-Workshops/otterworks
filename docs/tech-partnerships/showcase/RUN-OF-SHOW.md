# MongoDB Showcase — Run of Show (Take-1)

Run branch: `tp-run/mongodb-20260817T233337Z` · persistent namespace: `demo` · rehearsal namespace: `rehearsal1` (torn down).

All commands need `MONGODB_ATLAS_URI` (data plane) in the environment; the `run-job` step
additionally needs `OW_TP_MONGO_RECON_WEBHOOK_SECRET`. Nothing runs on a schedule — every
step is triggered by hand.

## 1. Document contracts (validators)

```
make mongo-showcase CMD=validators NS=demo      # collMod $jsonSchema onto customers+invoices
make mongo-showcase CMD=validate-demo NS=demo   # stage moment: conforming insert lands;
                                                # DD-MON-YY string date, 156th ad-hoc field,
                                                # CSV blob all REJECTED by the database
```

Expected: `validate-demo: PASS` with each rejection naming the validator error.
Artifact: `mongo_validators.demo.live.json`. PR: #1180.

## 2. Finance report as one aggregation pipeline

```
make mongo-showcase CMD=report NS=demo
```

Expected: every bucket of the legacy month-end rollup equal to the golden report **to the
cent**; `report: MATCH`. Artifacts: `finance_report.demo.golden.json` (legacy Oracle
baseline), `finance_report.demo.live.json` (pipeline output). PR: #1181.

## 3. App hard cutover

Billing customer/invoice reads are served from the MongoDB document repositories (plans and
entitlements stay in PostgreSQL); CI uses the compose Mongo fixture — no live-target
dependency. Golden path green modulo the documented pre-existing document-service auth
failures on the run branch.

## 4. Recon + failure-to-Devin loop

Green path (webhook NOT fired):

```
make mongo-showcase CMD=recon NS=demo                       # 11/11 PASS, exit 0
make mongo-run-job NS=demo RUN_URL=<run-url>                # green → no POST
```

Artifacts: `recon.demo.green.json`, `run_job.demo.green.json`. PR: #1182.

Red path, rehearsal namespace only (`drift`/`teardown` refuse `demo`):

```
make oracle-billing-seed NS=rehearsal1 && make seed-legacy NS=rehearsal1
# migrate customers/invoices/documents/files with migrations/mongodb/*/migrate.py --ns rehearsal1
make mongo-showcase CMD=recon NS=rehearsal1                          # GREEN first
make mongo-showcase CMD=drift NS=rehearsal1 ARGS="--kind corrupt --n 100"  # REAL drift
make mongo-run-job NS=rehearsal1 RUN_URL=<run-url>                   # recon FAILED:
                                                                      #   customers-checksum
                                                                      # webhook fired (HTTP 200)
```

Artifacts: `recon.rehearsal1.green.json` (before drift), `recon.rehearsal1.red.json`
(failing check named). The webhook POST is
`{namespace, failing_checks, run_url, base_branch}` with the secret read only from
`OW_TP_MONGO_RECON_WEBHOOK_SECRET` (header `X-Webhook-Secret`).

The automation spawned a Devin session which diagnosed the +0.01 `balances.current` drift on
100 customers, remediated it via an idempotent migration re-run (recon back to 11/11 GREEN),
and opened its audit PR #1184 against the run branch. The staged failure was never
remediated by hand.

## 5. Reset

```
make tp-atlas-teardown NS=rehearsal1
```

Expected: both `ow_tp_mongodb_rehearsal1` and `ow_tp_mongodb_rehearsal1_quarantine` dropped
and verified absent. Persistent `demo` recon re-run afterwards: 11/11 GREEN
(`recon.demo.final.json`) with validators enforced and the app serving from the target.
