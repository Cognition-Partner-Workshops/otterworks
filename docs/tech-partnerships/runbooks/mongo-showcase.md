# MongoDB platform showcase and failure loop

This runbook is manual. It has no scheduled or cron-triggered operation.

> **Provenance:** verified against the local fixture; live evidence is captured by
> the run owner.

## Local fixture setup

Use a namespace that is not persistent and has no immutable legacy manifest:

```bash
export NS=mongofx
export TP_MONGO_FIXTURE_URI='mongodb://localhost:57432/?directConnection=true'
ss -ltnp | grep ':57432'
PROCS_TARGET_DOCS_PORT=57432 make procs-up NS=ci
```

Expected output includes a healthy `billing-service-docs` container and the
fixture listener on `127.0.0.1:57432`. The explicit port override keeps the
fixture URI stable; the Makefile otherwise derives a namespace-specific port.

Seed the deterministic, validator-backed estate. The command is idempotent and
only deletes documents carrying `NS` in the two namespace databases:

```bash
make tp-mongo-showcase-seed-fixture NS=$NS
```

Expected summary counts are 40 customers, 30 invoices, 10 documents,
5 document snapshots, 12 files, 3 quarantined customers, and 2 quarantined
invoice lines. The summary names `validationAction: error`.

## Baseline, report, and recon

Capture a rehearsal baseline from the target, then recompute it:

```bash
make tp-mongo-showcase-report NS=$NS
scripts/tp-mongo-showcase.sh --ns "$NS" --run-mode fixture baseline --from-target
scripts/tp-mongo-showcase.sh --ns "$NS" --run-mode fixture recon
make tp-validate-recon FILE=docs/tech-partnerships/recon/mongo_showcase.$NS.recon.json
```

For the persistent demo namespace, the run owner can regenerate its baseline
from the legacy-billing report. This command reads the legacy Oracle report,
writes `docs/tech-partnerships/recon/baseline/mongo_showcase.demo.json`, and
upserts the same golden report into
`ow_tp_mongodb_demo.tp_showcase_baseline`:

```bash
scripts/tp-mongo-showcase.sh --ns demo --run-mode live baseline \
  --legacy-url http://localhost:8096
```

Recon grades only these five migrated collections and two quarantine
collections, by their explicit names: `customers`, `invoices`, `documents`,
`document_snapshots`, `files`, `customers_quarantine`, and
`invoice_lines_quarantine`. The `tp_showcase_baseline` and
`tp_showcase_drift_journal` collections are operational metadata and are never
graded as unexpected extra collections.

The report prints the RPT-114 status and line-type tables. Recon prints
`"result": "pass"` and `"failed_checks": []`; schema validation prints:

```text
validated 1 recon file(s)
PASS
```

The report is served by the billing service with:

```bash
cd services/billing-service
BILLING_SVC_DOCUMENT_URI="$TP_MONGO_FIXTURE_URI" \
  BILLING_SVC_ESTATE_DB_PREFIX=ow_tp_mongodb \
  uv run uvicorn app.main:app --host 127.0.0.1 --port 8097
curl 'http://localhost:8097/api/reports/month-end?ns=mongofx'
curl 'http://localhost:8097/api/reports/reconciliation?ns=mongofx'
```

Both endpoint bodies carry `generated_at` with a trailing `Z`. The month-end
body keys are `report`, `namespace`, `batch_no`, `source`, `generated_at`,
`by_status`, and `by_status_line_type`; `source.engine` is `mongodb`.

## Failure loop and local webhook receiver

First prove that a green dry run does not post:

```bash
make tp-mongo-showcase-job NS=$NS \
  BASE_BRANCH=tp-run/mongodb-20260825T204423Z \
  RUN_URL=local://green \
  DRY_RUN=1
```

The command exits zero for a green recon and does not call the webhook.

For a local receiver, use a loopback-only HTTPS endpoint if the notifier's
HTTPS guard is enabled. The receiver must log the method, path, headers, and
body to `/home/ubuntu/showcase-evidence/webhook.log`; redact the
`X-Webhook-Secret` value before retaining the file. Set the secret only in the
shell environment:

```bash
export OW_TP_MONGO_RECON_WEBHOOK_SECRET='local-only-secret'
export OW_TP_MONGO_RECON_WEBHOOK_URL='https://127.0.0.1:18443/recon'
```

Do not use the Devin webhook URL in a fixture rehearsal.

Stage and exercise each failure independently, reseeding between kinds:

```bash
for KIND in missing corrupt stale; do
  make tp-mongo-showcase-seed-fixture NS=$NS
  make tp-mongo-showcase-drift NS=$NS KIND=$KIND COUNT=5
  make tp-mongo-showcase-job NS=$NS \
    BASE_BRANCH=tp-run/mongodb-20260825T204423Z \
    RUN_URL=local://$KIND
done
make tp-mongo-showcase-seed-fixture NS=$NS
scripts/tp-mongo-showcase.sh --ns "$NS" --run-mode fixture recon
```

Each broken run exits nonzero and prints named check IDs. The receiver payload
shape is:

```json
{
  "namespace": "mongofx",
  "failing_checks": ["customers-count"],
  "run_url": "local://missing",
  "base_branch": "tp-run/mongodb-20260825T204423Z"
}
```

The request includes `X-Webhook-Secret`; retain only a redacted header value.
A green final recon prints `"failed_checks": []`.

## CI/manual operation

The `tp-mongo-recon.yml` workflow is `workflow_dispatch` only. Supply `ns` and
optionally change `base_branch`. It reads `MONGODB_ATLAS_URI` and
`OW_TP_MONGO_RECON_WEBHOOK_SECRET` from repository secrets and
`OW_TP_MONGO_RECON_WEBHOOK_URL` from repository variables by name. It uploads:

```text
docs/tech-partnerships/recon/mongo_showcase.<ns>.recon.json
```

as the `mongo-showcase-recon-<ns>` artifact and fails when recon or notification
fails.

## Legacy SQL versus MongoDB pipeline

The legacy implementation is in `services/legacy-billing/app/reports.py`.
`STATUS_SQL` groups `INVOICE_HEADER` rows by a `CODES` outer join and
`LINE_SQL` joins `INVOICE_LINE`, decodes line types with Oracle `DECODE`, and
formats money with `TO_CHAR(..., 'FM999999999999990.00')`. `BALANCES_SQL`
aggregates customer balances by `conversion_batch_no`.

The migrated implementation is in `migrations/mongodb/finance_report.py`.
`month_end_pipeline(ns)` matches `ns` and `source.batch_no`, then uses one
MongoDB `$facet` with `by_status` and `by_status_line_type`; inline expressions
decode status and line types, and Decimal128 arithmetic preserves cent values.
`balances_pipeline(ns)` aggregates migrated customer Decimal128 balances.
The service and showcase import this same module rather than maintaining a
second report implementation.

## Artifacts and evidence

Committed baseline and fixture recon artifacts live under:

```text
docs/tech-partnerships/recon/baseline/mongo_showcase.demo.json
docs/tech-partnerships/recon/mongo_showcase.<rehearsal>.recon.json
```

Local raw command output and redacted receiver logs belong under:

```text
/home/ubuntu/showcase-evidence/
```

The live-derived `mongo_showcase.demo.recon.json` is intentionally not a
fixture commit artifact; the run owner captures live proof.
