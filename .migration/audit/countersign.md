# Independent cutover audit: countersign (s6.2-catch-up-recon)

Independent auditor session for the OtterWorks legacy billing migration
(PostgreSQL `billing` → MongoDB Atlas `billing_migration`). The auditor migrated
nothing: read-only on the legacy fixture and on Atlas, writes only to a disposable
local procs namespace and session tmpfs, no consumer repointed, no principal requested.

## Identity

| Item | Value |
|---|---|
| Branch | `devin/1792034161-s6.2-catch-up-recon` (based on `tp-run/mongodb-1792003347`, merge-base `4b285bda`) |
| Commit audited | `63966cb9656a091996d16cb2177f4b36b823da27` (gates 1a–1c were re-run at `8ba0b660b`; the two commits on top, `ab4049018` and `63966cb96`, touch only `.migration/cutover_runbook.md` §5–7 and `.migration/recon/freeze/run_freeze.sh`'s parity-red handling; the `recon run` command re-run in 1b is byte-identical in both) |
| Plugin | `Cognition-Partner-Workshops/mongo-migration-plugin` `main` @ `d6d72e8` |
| Recon CLI | `~/.venvs/recon/bin/recon` (harness from the plugin checkout) |
| Mapping | `.migration/mapping_spec.json` v2, sha256 `6567c33adeada1a45ce93ab4096f2efb484e410263346dd66ed68f149a6e6704` |
| Tolerances | `.migration/recon_tolerances.json` tol-v1, sha256 `829cbb4d2de0d3cf5296d29622973d4bb11915382b0634ab88ad9f040ef5c9c2` |
| Source axis | PostgreSQL fixture `billing_mig` schema `billing`, role `billing_ro` (SELECT only), `127.0.0.1:55433`, access `live` |
| Target axis | Atlas cluster `otterworks-demo`, database `billing_migration`, `target_class=migration_cluster` |
| Write fence | `.migration/allowed_targets.json` = `billing_migration` only; `.migration/authorizations.json` empty (no legacy write authorized) |
| Secrets | by name only: `OW_BILLING_PG_RO_DSN` (→ `POSTGRESQL_RO_DSN`), `MONGODB_ATLAS_URI`, `RECON_REDACT_SALT` |

## 1. Gates re-run by the auditor (from the evidence, not the prose)

### 1a. Freeze watermark (deterministic local fixture)

Fixture started with `NS=mig PROCS_DB_PORT=55433 BILLING_RO_PASSWORD=<session-local, tmpfs only> .migration/fixtures/legacy_billing_source.sh`
(reported `billing_mig` / `billing_ro` / 55433 / 49 rows across 11 tables). `POSTGRESQL_RO_DSN` exported as the
`billing_ro` JSON DSN from tmpfs. Command:

```
~/.venvs/recon/bin/python .migration/recon/freeze/watermark.py --check .migration/recon/freeze/watermark.json
```

| Field | Committed `watermark.json` | Auditor re-run |
|---|---|---|
| tables | 11 | 11 |
| rows_total | 49 | 49 |
| per-table sha256 | declared | all 11 match (`moved: {}`) |
| freeze_held | — | `true` |
| wal_lsn | `0/19DF898` | `0/19961C0` (fresh container; LSN is context only per README and `watermark.py`, not part of the gate) |

Result: **freeze held**. The fixture is deterministic as claimed.

### 1b. Full recon gate at the watermark, read-only against Atlas

Exact `recon run` from `.migration/recon/freeze/run_freeze.sh` step 3, with `--out /tmp/audit-recon/` and a
session-local `RECON_REDACT_SALT` (the named secret is not injected in sessions; see A1):

```
~/.venvs/recon/bin/recon run --unit freeze-watermark --family postgresql \
  --mapping .migration/mapping_spec.json --tolerances .migration/recon_tolerances.json \
  --canonicalization ~/repos/mongo-migration-plugin/skills/mongo-migration/profiles/postgresql.md \
  --mode live --target-class migration_cluster \
  --source-dsn-secret POSTGRESQL_RO_DSN --target-uri-secret MONGODB_ATLAS_URI \
  --target-db billing_migration --allowed-targets-file .migration/allowed_targets.json \
  --source-concurrency 1 --seed 1 --out /tmp/audit-recon/
```

| Field | Committed `.migration/recon/freeze/recon/result.json` | Auditor `/tmp/audit-recon/result.json` |
|---|---|---|
| verdict | PASS | PASS |
| merge_eligible | true | true |
| mode | live | live |
| target_class | migration_cluster | migration_cluster |
| mapping_sha256 | `6567c33a…6704` | `6567c33a…6704` (match) |
| tolerance_sha256 | `829cbb4d…9c2` | `829cbb4d…9c2` (match) |
| redacted / redaction_salted | true / true | true / true |
| warnings / error | [] / null | [] / null |
| tier 1 counts_through_mapping | passed, checks_run 24, findings 0 | passed, checks_run 24, findings 0 |
| tier 2 per_field_aggregates | passed, checks_run 30, findings 0 | passed, checks_run 30, findings 0 |
| tier 3 keyed_diffs | passed, checks_run 49, findings 0 | passed, checks_run 49, findings 0 |
| generated_at | worker run | auditor run (only differing field) |

The harness package was scanned for target write operations (`insert_*`, `update_*`, `replace_one`, `delete_*`,
`drop`, `create_collection`, `bulk_write`): none. Recon read Atlas only. Independent read of
`billing_migration` after the run: collections `invoices 3, notifications 1, plans 3, ratingPeriods 3,
subscriptions 9, tenants 9, usageEvents 10` (= 38 docs, matching the committed delta evidence) plus
`_connectivity_probe` (0 docs, still present; see A4).

### 1c. Additional sampled gates

- `make -s procs-rules-gate ALL=1` → `Rules gate PASS: dunning`, `invoicing`, `plans`, `rating`.
- `sha256sum .migration/mapping_spec.json .migration/recon_tolerances.json` → both hashes equal the values recorded
  in every committed `result.json` (waves 1–3, parallel-run, freeze). Pinned hashes are the committed files.

Not re-run (committed evidence accepted as-is, not re-verified): `.migration/recon/freeze/parity/parity.json`
(24 PASS / 0 FAIL / 0 SKIP), `delta.json`, `delta-rerun.json`. Re-running parity or `app.delta` against Atlas
would write to Atlas, which this audit was forbidden to do.

## 2. Findings

| # | Finding | Severity | Blocks cutover? |
|---|---|---|---|
| A1 | `OW_BILLING_PG_RO_DSN` and `RECON_REDACT_SALT` are not injected in sessions (absent in this session as well; `MONGODB_ATLAS_URI` is). Both reruns above used session-local values held in tmpfs. The runbook already lists both named secrets as production preconditions (§2.2, §2.3), so the recon PASS is valid for the gate but the production catch-up recon cannot be executed with the committed command until the two secrets exist by name. | Medium | No for the countersign; yes for the production repoint until the secrets are provisioned by name (already a runbook precondition). |
| A2 | Runbook references `plan.yaml` ("open in plan.yaml") but no `plan.yaml` exists in the repo; it is the board plan. Reader cannot resolve the reference from the branch. | Low | No. |
| A3 | Route rows 3/4/5 change HTTP shape, not only the path (legacy form-POST `/plans/<t>/change` → JSON `POST /api/tenants/{t}/plan-change`; legacy `POST /api/rating/preview` with body → `GET /api/tenants/{t}/rating?period=`). The runbook's "keep the external paths/shapes the client fixture already uses" is correct for `procs/routes.yaml` (billing-service contract) but legacy Flask callers need the app.py shim, which the runbook does require. Wording should say so explicitly. | Low | No. |
| A4 | `billing_migration._connectivity_probe` still exists (0 docs), as the runbook states; its drop is a customer step (§3). Left untouched by this audit. | Info | No. |
| A5 | Waves 1–3 and parallel-run `result.json` have `redaction_salted: false` (unsalted redaction hashes); only the freeze gate is salted. Already open issue #2 in the evidence pack; the merge-authority gate (freeze) is salted. | Low | No. |

No gate re-run by the auditor disagreed with the committed evidence. No `mongo_guard` block occurred.

## 3. Runbook review against the code

Checked `.migration/cutover_runbook.md` against `services/legacy-billing/app/app.py`,
`services/billing-service/app/main.py`, `procs/routes.yaml`, `services/legacy-billing/db/schema.sql`,
`.migration/fixtures/legacy_billing_ro.sql`, `docker-compose.procs.yml`.

- [x] Every `app.py` route is listed and mapped to a route that exists in `main.py` / `routes.yaml`: `GET /health`→`/health`; `GET /` and `GET /plans` (same handler)→`GET /api/plans`; `GET /plans/<t>/entitlement`→`GET /api/tenants/{t}/entitlement`; `POST /plans/<t>/change`→`POST /api/tenants/{t}/plan-change`; `POST /api/rating/preview`→`GET /api/tenants/{t}/rating`; `POST /api/rating/finalize`→`POST /api/tenants/{t}/rating-periods`; `GET /api/invoices/<t>/preview`→`GET /api/tenants/{t}/invoice-preview`; `POST /api/invoices/<t>/issue`→`POST /api/tenants/{t}/invoices`; `GET /api/invoices/<id>/lines`→`GET /api/invoices/{id}/lines`; `GET /api/dunning/overdue`→`GET /api/dunning/overdue-accounts`; `POST /api/dunning/schedule`→`POST /api/dunning/schedule-runs`; `POST /api/dunning/suspend`→`POST /api/dunning/suspension-runs`. 13 decorators, 12 handlers, all covered (A3 on shape).
- [x] `fn_usage_summary` gap is real: `GET /api/tenants/{t}/usage-summary` exists in `main.py` and `routes.yaml`; no `app.py` route calls `fn_usage_summary`. Correctly recorded as exposed with no legacy HTTP consumer.
- [x] "app.py data-layer change, not a connection-string swap" is supported: `db_connect()` connects as `DB_USER` default `billing` (the `CREATE SCHEMA billing` principal, superuser in the compose fixture) and every handler calls `billing.fn_*` / `billing.sp_*` via `select()`/`execute()`; there is no repository layer to repoint. `legacy_billing_ro.sql` grants `billing_ro` SELECT only and revokes EXECUTE on functions, so the read-only recon principal cannot reach the routines either.
- [x] `_connectivity_probe` drop: present as a customer-executed step with the exact command, after the recon PASS and before repoint; Devin excluded from it.
- [x] UTC pin: `TZ=UTC` / `PGTZ=UTC` precondition present (§2.5), matching the fixture's `timestamptz` canonicalisation.
- [x] `OW_BILLING_PG_RO_DSN` / `RECON_REDACT_SALT` preconditions: present (§2.2, §2.3) with the JSON DSN shape and the salted-hash requirement; status "not injected" is accurate (A1).
- [x] `BILLING_SVC_ALLOW_INTERNAL_RESET` must be unset in production: present; `main.py` returns 404 when `settings.allow_internal_reset` is false (`config.py`, env prefix `BILLING_SVC_`).
- [x] Rollback: trigger, point of no return, and steps (repoint back to Flask/PostgreSQL, keep Atlas for forensics) present; executed by the customer principal, not Devin.
- [x] Executor named: Dhrov Subramanian; production steps run under the customer-held cutover principal.
- [x] "What Devin does not do": present and consistent with this session (no cutover principal, no `billing` owner password, no legacy schema/data/grant/routine/job change, no probe drop, no `app.py` or consumer-config edit, no rollback, does not declare cutover done).
- [x] Secret values / tmpfs paths in committed artifacts: grep over `.migration/`, `procs/`, `services/legacy-billing/`, `services/billing-service/` found no DSN, password, URI, or salt values and no `/dev/shm` or `/run/shm` paths. The only hit is the fixture script's documented extraction of the password from the named secret (code, not a value).

## 4. What the auditor wrote

| Location | Write | Disposable? |
|---|---|---|
| Docker project `mig` (`docker-compose.procs.yml`, namespace `NS=mig`, port 55433) | local PostgreSQL fixture container + volume, torn down after the audit | yes (local only) |
| `/dev/shm/audit/` (tmpfs) | session-local `billing_ro` password, DSN JSON, redaction salt, watermark check output; shredded after the audit | yes (never in repo) |
| `/tmp/audit-recon/` | `result.json`, `report.md`, `recon.summary.md` from the independent recon | yes (local only) |
| `make procs-rules-gate ALL=1` | ran in the local checkout; no files committed | yes |
| `.migration/audit/countersign.md` | this file, one commit on `devin/1792034161-s6.2-catch-up-recon` | the only repo write |

Not written: the live legacy source (fixture only, `billing_ro` SELECT-only role), Atlas (`billing_migration`
read only; no `app.delta`, no `/internal/reset`, no drop; `_connectivity_probe` intact), any consumer
configuration, any other repo file. No cutover principal requested.

## Verdict

Freeze watermark held (49 rows, 11 tables, all hashes match). Independent live recon against Atlas at
`target_class=migration_cluster` reproduced the committed PASS tier for tier (24/30/49 checks, 0 findings,
same mapping and tolerance hashes). Rules gate PASS for all four modules. Runbook routes, data-layer rationale,
preconditions, rollback, executor and Devin boundaries check out against the code. Findings A1–A5 are
non-blocking for this countersign; A1 remains a production precondition the runbook already carries.

COUNTERSIGNED: the freeze-watermark recon PASS and the runbook stand
