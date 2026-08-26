# Demo Runbook — MongoDB Atlas + Devin showcase ("MongoDB catches it, Devin fixes it, the PR proves it")

**Duration:** ~20 minutes, on top of (or instead of) the before-state tour in
`runbook-mongodb.md`.
**Story:** the OtterWorks legacy estate (155-column Oracle billing table + EAV,
Postgres documents, DynamoDB file metadata) has already been migrated to MongoDB
Atlas by a fan-out of Devin child sessions, its stored-procedure logic extracted
into `billing-service` against the document store, and the platform now *guards*
the data: a reconciliation job grades the migrated namespace, and when it goes
red it hands the failure to Devin, which remediates and opens the audit PR.

Everything below was staged and rehearsed on run branch
`tp-run/mongodb-20260825T204423Z`. Nothing in this demo is on a schedule — every
beat is triggered by hand.

## What is already live (pre-staged, nothing to build on the day)

| Thing | Where |
|---|---|
| Migrated namespace | Atlas cluster `otterworks-demo`, databases `ow_tp_mongodb_demo` + `ow_tp_mongodb_demo_quarantine` |
| Collections | `customers` 25,000 · `invoices` 18,750 (149,963 embedded lines) · `documents` 2,000 (13,876 versions, 390 snapshots) · `files` 10,000 — every one with a strict `$jsonSchema` validator (`validationAction: error`) and its indexes |
| Quarantine | 81 customer + 37 invoice-line anomaly records, exactly the planted set from `testdata/legacy/manifests/demo.json` |
| Extracted services | `billing-service` rating + invoicing modules reading/writing the document store (hard cutover; `procs/routes.yaml` marks both `extracted`) |
| Shared infra | `infrastructure/terraform-atlas/` (namespace DB users + access list); `terraform plan` clean |
| Remediation automation | "OtterWorks Mongo recon failure — auto-remediate (MongoDB Atlas)", 1 concurrent run max, **no schedule** |

## Pre-demo setup

```bash
make infra-up                      # Postgres + LocalStack
make oracle-billing-up             # Oracle Free (first boot 10–20 min)
make seed-legacy NS=demo
make oracle-billing-seed NS=demo
make seed-legacy-validate NS=demo  # 15/15 checks PASS
```

Atlas credentials come from the environment by name only:
`MONGODB_ATLAS_URI`, `MONGODB_ATLAS_PUBLIC_KEY`, `MONGODB_ATLAS_PRIVATE_KEY`,
`MONGODB_ATLAS_PROJECT_ID`, plus `OW_TP_MONGO_RECON_WEBHOOK_SECRET` for the
recon → Devin webhook. Never printed, never committed.

## Beat 1 — The pain, in 90 seconds

```bash
make tp-pain-mongodb NS=demo
```

155 columns / 25,000 rows, the 158-column `_HIST` copy and its trigger, the
deterministic blast radius of "just add one field", and `TAX_REGION_OVERRIDE`
already living untyped in `ENTITY_ATTR_VALUE`. Punchline: *no schema means no
guarantee.*

## Beat 2 — The after-state: one document model, enforced

Show the target and that the contract is real, not decorative:

```bash
# preview (no connection)
make tp-break-oracle-mongodb NS=demo DRY_RUN=1
# live: a DD-MON-YY string date and a rogue 156th field both bounce with error 121
TP_MONGODB_URI="$MONGODB_ATLAS_URI" make tp-break-oracle-mongodb NS=demo
# undo (tag-scoped, safe, no-op after a rejection)
TP_MONGODB_URI="$MONGODB_ATLAS_URI" make tp-break-oracle-mongodb NS=demo UNDO=1
```

The `errInfo` naming the broken rule *is* the beat.

## Beat 3 — Reconciliation from the target, not from a log

Recompute every unit's reconciliation directly from Atlas and grade it:

```bash
export TP_MONGODB_URI="$MONGODB_ATLAS_URI"
MONGO_FILES_TARGET=live ./scripts/tp-mongo-live-rollup.sh demo
```

Expected (parent-run, uncontended, post-wave-2):

| Unit | Checks | Result |
|---|---|---|
| `mongo_customers` | 18 | all pass, 81 quarantined |
| `mongo_invoices` | 19 | all pass, checksum `88a66751f0b08b476b492105a2efc537`, 37 orphan lines quarantined |
| `mongo_documents` | 20 | all pass |
| `mongo_files` | 10 | all pass |

`anomalies_missing: []` and `anomalies_unexpected: []` on every unit — the
migration found exactly the planted defect set, no more and no fewer — and each
unit is idempotent on a second run. Reports land in
`docs/tech-partnerships/recon/mongo_*.recon.json`.

## Beat 4 — Stored procedures, extracted and at parity

```bash
make procs-up NS=demo        # billing-service + fixtures
make procs-parity NS=demo    # → Parity PASS=19 FAIL=0 SKIP=5
```

Rating and invoicing are graded PASS against the recorded legacy transcripts;
dunning is deliberately SKIP (not in this run's scope). To prove the extracted
service runs against **Atlas** rather than the CI fixture, point the document
store at the cluster and re-run the same suite:

```bash
export BILLING_SVC_DOCUMENT_URI="$MONGODB_ATLAS_URI"
export BILLING_SVC_DOCUMENT_DB=ow_tp_billing_demo
make procs-up NS=demo && make procs-parity NS=demo   # → Parity PASS=19 FAIL=0 SKIP=5
```

## Beat 5 — The failure loop (the money beat)

MongoDB catches it → Devin fixes it → the PR proves it. Run this on a **throwaway
namespace**, never on `demo`:

```bash
# 1. stage the estate for a throwaway namespace (<= 13 chars)
make seed-legacy NS=rehearsal && make oracle-billing-seed NS=rehearsal
make seed-legacy-validate NS=rehearsal            # 15/15
export TP_MONGODB_URI="$MONGODB_ATLAS_URI"
MONGO_FILES_TARGET=live ./scripts/tp-mongo-live-rollup.sh rehearsal   # green baseline
```

```bash
# 2. capture the golden legacy report for that namespace and grade the target green
ORACLE_HOST=127.0.0.1 ORACLE_PORT=52521 ORACLE_SERVICE=FREEPDB1 ORACLE_USER=ow_billing \
  uv run --no-project --with-requirements services/legacy-billing/app/requirements.txt \
  gunicorn --chdir services/legacy-billing/app --bind 127.0.0.1:8096 app:app &
scripts/tp-mongo-showcase.sh --ns rehearsal --run-mode live baseline --legacy-url http://127.0.0.1:8096
scripts/tp-mongo-showcase.sh --ns rehearsal --run-mode live recon   # 16/16, failed_checks: []

# 3. stage real drift (deletes documents; refuses `demo` and anything in TP_MONGO_PERSISTENT_NS)
scripts/tp-mongo-showcase.sh --ns rehearsal --run-mode live drift --kind missing --count 5

# 4. run the recon job — red recon POSTs to the Devin automation webhook and exits non-zero
OW_TP_MONGO_RECON_WEBHOOK_URL=<automation webhook url> \
  scripts/tp-mongo-showcase.sh --ns rehearsal --run-mode live run-job \
  --base-branch tp-run/mongodb-20260825T204423Z --run-url <this run's url>
```

What this run actually produced (2026-08-26, parent-run, live Atlas):

| Beat | Evidence |
|---|---|
| Baseline | legacy RPT-114 for `rehearsal`, batch `15871060`: 3 status groups, 12 status/line-type groups, 25,000 customers, balance `38778083.99` |
| Green before drift | showcase recon `result: pass`, `failed_checks: []`, 16 checks, idempotency rerun `pass` |
| Drift staged | `missing` × 5 — invoices `REHEARSAL-000000000` … `-000000004` deleted from Atlas, recorded in `tp_showcase_drift_journal` |
| MongoDB catches it | recon `fail` naming `invoices-count`, `invoices-embedded-lines`, `invoice-lines-checksum`, `invoice-lines-checksum-coverage`, `report-golden-parity` |
| Webhook fired | `POST … -> HTTP 200 {"status":"accepted"}`, payload `{namespace, failing_checks, run_url, base_branch}`; secret sent as a header from `OW_TP_MONGO_RECON_WEBHOOK_SECRET`, never logged |
| Devin fixes it | session <https://partner-workshops.devinenterprise.com/sessions/a2218073e69c4cd394abbc4f26635d46> — diagnosed 5 deleted invoice documents and restored them by re-running the idempotent `mongo_invoices` migration (no manual data edit) |
| The PR proves it | audit PR <https://github.com/Cognition-Partner-Workshops/otterworks/pull/1305> into the run branch, CI green |
| Green again | parent-recomputed from Atlas after remediation: `result: pass`, `failed_checks: []`, 16 checks, idempotency rerun `pass` |

Raw reports for all three states are under `/home/ubuntu/tp-live-evidence/rehearsal-loop/`
(`recon-green-pre-drift.json`, `recon-red-after-drift.json`,
`recon-green-after-devin-remediation.json`). No human touched the data between
red and green.

Teardown afterwards (rehearsal namespaces never persist):

```bash
uv run --no-project --with 'pymongo[srv]==4.10.1' python - <<'PY'
import os
from pymongo import MongoClient
c = MongoClient(os.environ["MONGODB_ATLAS_URI"])
for d in ("ow_tp_mongodb_rehearsal", "ow_tp_mongodb_rehearsal_quarantine"):
    c.drop_database(d)
print(sorted(d for d in c.list_database_names() if d.startswith("ow_tp")))
PY
```

Verified absent after teardown — the only remaining namespace databases are
`ow_tp_billing_demo`, `ow_tp_mongodb_demo`, `ow_tp_mongodb_demo_quarantine`.
`demo` is never torn down.

## Beat 6 — One pipeline replaces the report (optional closer)

The legacy RPT-114 month-end report (three SQL statements, one of them a join to
`INVOICE_LINE`) is now a single `$facet` aggregation served by `billing-service`,
and the showcase recon grades against that same module:

```bash
scripts/tp-mongo-showcase.sh --ns demo --run-mode live report
scripts/tp-mongo-showcase.sh --ns demo --run-mode live recon   # 16/16, failed_checks: []
```

Parent-run on this branch: `result: pass`, `failed_checks: []`, 16 checks,
idempotency rerun `pass`, including `report-golden-parity` against the legacy
Oracle report captured in
`docs/tech-partnerships/recon/baseline/mongo_showcase.demo.json`.

## Artifacts from the staging run

| Artifact | Link |
|---|---|
| Run branch | `tp-run/mongodb-20260825T204423Z` |
| Foundation (Atlas Terraform, contracts, preflight probes) | [#1294](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1294) |
| Wave 1 — documents / invoices / customers / files | [#1295](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1295) · [#1296](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1296) · [#1297](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1297) · [#1298](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1298) |
| Wave 1 live-run fixes | [#1299](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1299) · [#1300](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1300) |
| Wave 2 — document-store fixture, rating, invoicing | [#1301](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1301) · [#1302](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1302) · [#1303](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1303) |
| Wave 3 — showcase report, recon job, failure loop | [#1304](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1304) |
| Failure-loop audit PR (opened by the remediation session) | [#1305](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1305) |
| Remediation session | <https://partner-workshops.devinenterprise.com/sessions/a2218073e69c4cd394abbc4f26635d46> |
| Recon workflow (manual dispatch only) | `.github/workflows/tp-mongo-recon.yml` |
| Showcase unit runbook | `docs/tech-partnerships/runbooks/mongo-showcase.md` |

## Cost and safety model

- Atlas M0 is free with a 512 MB cap → `SCALE=demo` only. Measured after the
  rehearsal teardown: 161 MB / 512 MB (`ow_tp_mongodb_demo` 160.5 MB).
- The real spend is ACUs: the remediation automation is capped at 1 concurrent
  run and has **no schedule** — every beat is triggered by hand.
- Known limitation of this run: the Atlas API key cannot create alert
  configurations (`alert-webhook-create: HTTP 401 USER_UNAUTHORIZED`), so the
  failure path is the recon job posting to the Devin automation webhook rather
  than an Atlas-native alert. Everything else in the preflight manifest is
  verified live (cluster read, wire write, access-list create+delete,
  `$jsonSchema` create, enforcement, `collMod`).
