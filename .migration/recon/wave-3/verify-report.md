run_id: ticket-e6d86904b1da4d4199c2cf96ce5cd566
manifest_sha: 399f5a4f0b82

# Wave 3 (Invoicing + Dunning) — independent verification (plan step `s4.3.verify`, ticket BILMG-16)

The verifier migrated nothing in wave 3. Everything below was re-run in this session from the committed spec on the merged run branch; nothing is copied from the batch workers' evidence.

## Verdict

| batch | units | verdict | basis |
|---|---|---|---|
| `w3-b01` | `invoicing` | **PASS** | own live re-run `.migration/recon/wave-3/w3-b01/invoicing/result.json`: verdict PASS, mode `live`, target_class `migration_cluster`, `merge_eligible: true`, 0 warnings, 0 findings; probes past the gate clean; rules gate PASS; harness parity invoicing 6/6 (full run 24/24) on the disposable stack; own read-only replay 3/3; own write-path replay (`sp_issue_invoice` ×3: credit drawdown, finalize_rating, invoice document) consistent with the recorded transcripts |
| `w3-b02` | `dunning` | **PASS** | own live re-run `.migration/recon/wave-3/w3-b02/dunning/result.json`: verdict PASS, mode `live`, target_class `migration_cluster`, `merge_eligible: true`, 0 warnings, 0 findings; probes past the gate clean; rules gate PASS; harness parity dunning 5/5 (full run 24/24); own read-only replay 1/1; own write-path replay (`sp_schedule_dunning` ×3 incl. a repeated as_of, `sp_suspend_overdue` ×2 incl. the double run) consistent with the recorded transcripts and the procedure semantics |

Wave verdict: **PASS**.

## Identity

| item | value |
|---|---|
| run branch | `tp-run/mongodb-1792003347` @ `2ac253f0f` (w3-b01 merged as `62a60d015`, PR #2055; w3-b02 merged as `2ac253f0f`, PR #2056) |
| batch results graded | `.migration/recon/w3-b01.json` (worker evidence `.migration/recon/invoicing/result.json`, 2026-10-15T01:14:26Z) and `.migration/recon/w3-b02.json` (`.migration/recon/dunning/result.json`, 2026-10-15T01:32:21Z) |
| plugin | mongo-migration-plugin `main` @ `d6d72e8` (recon harness 0.3.3, editable install in `/home/ubuntu/.venvs/recon`; the clone was fast-forwarded to that SHA before the runs) |
| mapping | `v2`, sha256 `6567c33adeada1a45ce93ab4096f2efb484e410263346dd66ed68f149a6e6704` (= committed `.migration/mapping_spec.json`, = `mapping_sha256` in both result.json) |
| tolerances | `tol-v1`, sha256 `829cbb4d2de0d3cf5296d29622973d4bb11915382b0634ab88ad9f040ef5c9c2` (= committed `.migration/recon_tolerances.json`, = `tolerance_sha256` in both result.json), source_concurrency 1 |
| axes | `source_access: live` (local PostgreSQL 16 fixture `billing_mig` on 127.0.0.1:55433, role `billing_ro`, session TimeZone `Etc/UTC`) × `target_access: migration_cluster` (Atlas `otterworks-demo`, db `billing_migration`) |
| manifest_sha | `399f5a4f0b82` — reproduced with `preflight.py --wave` from the wave-3 spec fields (wave 3, w3-b01 `invoicing` → `billing_migration.invoices`, w3-b02 `dunning` → `billing_migration.notifications`, fixture manifest / versions / sha256s from `.migration/units.json`) with `auto_merge: true`; `auto_merge: false` gives `930fb5b1efdb` |
| secrets | `MONGODB_ATLAS_URI` (by name); `OW_BILLING_PG_RO_DSN` was not visible to this session, so the fixture was started with a session-local `BILLING_RO_PASSWORD` kept in memory (tmpfs, never on disk or committed) and `POSTGRESQL_RO_DSN` assembled in-shell; see finding V1 |
| the verifier wrote | nothing on Atlas (every Atlas access was a read: harness, probes, replays), nothing on the `billing_ro` fixture; the only writes were to the disposable procs namespace `v3` (`make procs-up NS=v3` … `make procs-down NS=v3`, local mongo:7 + the service's `/internal/reset`) |

## 1. Recon re-runs (one live run per unit, source concurrency 1)

Commands (from the workspace root, branch `recon/wave-3`; `<plugin>` = the mongo-migration-plugin clone at `d6d72e8`):

```
recon run --unit invoicing --family postgresql --mapping .migration/mapping_spec.json --collections invoices \
  --tolerances .migration/recon_tolerances.json --canonicalization <plugin>/skills/mongo-migration/profiles/postgresql.md \
  --mode live --target-class migration_cluster --source-dsn-secret POSTGRESQL_RO_DSN --target-uri-secret MONGODB_ATLAS_URI \
  --target-db billing_migration --allowed-targets-file .migration/allowed_targets.json --source-concurrency 1 --seed 1 \
  --out .migration/recon/wave-3/w3-b01/invoicing/
recon run --unit dunning ... --collections notifications ... --out .migration/recon/wave-3/w3-b02/dunning/
```

| unit | result | generated | tier 1 counts_through_mapping | tier 2 per_field_aggregates | tier 3 keyed_diffs |
|---|---|---|---|---|---|
| `invoicing` (`invoices`) | **PASS**, `merge_eligible: true`, warnings `[]`, error `null` | 2026-10-15T01:52:05Z | 5 checks PASS; source invoices 3; both declared indexes present | 7 checks PASS; `issuedAt`, `status` deferred to tier 3 by rule | 6 checks PASS; full diff, population 3, 0 duplicate source keys; embeds graded `invoiceLines` 2 elements, `dunningAttempts` 1 element |
| `dunning` (`notifications`) | **PASS**, `merge_eligible: true`, warnings `[]`, error `null` | 2026-10-15T01:52:07Z | 2 checks PASS; source notifications 1; the unique (`tenantId`, `kind`, `sentAt`) index present | 3 checks PASS; `kind`, `sentAt` deferred to tier 3 by rule | 1 check PASS; full diff, population 1 |

Source counts were identical in the harness runs and in the probe runs a few minutes later (invoices 3 / invoice_lines 2 / dunning_attempts 1 / notifications 1 / credit_notes 5): no drift observed, so the source side was not re-read a third time.

## 2. Probes past the gate (read-only; `evidence/probe.py` → `evidence/probes.json`)

| probe | invoices | notifications |
|---|---|---|
| docs vs rows | 3 / 3 | 1 / 1 |
| duplicate `_id` | 0 | 0 |
| natural key duplicates, both sides | `periodId` shared by two invoices: 1 / 1 (the seed, see V5) | (`tenantId`, `kind`, `sentAt`) 0 / 0 |
| missing fields on target | none | none |
| explicit nulls on target (source NULLs) | 0 (0) | 0 (0) |
| BSON types (every doc) | `_id`, `tenantId`, `periodId` binData uuid subtype 4; `issuedAt` date; `subtotal`, `tax`, `total` decimal; `status` string | `_id`, `tenantId` uuid 4; `kind` string; `sentAt` date |
| undeclared fields | none | none |
| exact value diff vs source (all fields, canonicalised) | 0 | 0 |
| docs not in source | 0 | 0 |
| indexes vs spec `collections[].indexes` | 2/2 (`invoiceLines.lineNo`; `status`, `issuedAt`) | 1/1 unique (`tenantId`, `kind`, `sentAt`) |
| `$jsonSchema` validator present, level strict | yes | yes |

Embed `invoices.invoiceLines` (1:N array of `invoice_lines`, child key `lineNo`): 2 source child rows → 2 elements; per-invoice lengths equal the source child counts for all 3 invoices (fan-out distribution {2: 1, 0: 2} on both sides), 0 arrays missing, 0 non-array values, 0 elements without a source row, 0 source rows without an element, 0 duplicate `lineNo` in an array, arrays ordered by `lineNo`; 0 element value diffs over `id`, `lineNo`, `lineType`, `description`, `amount` (types uuid 4 / int / string / string / decimal); no `invoiceId` copied into the element and no undeclared element field.

Embed `invoices.dunningAttempts` (1:few array of `dunning_attempts`, child key `id`): 1 source child row → 1 element on the right invoice ({1: 1, 0: 2} both sides), 0 length mismatches, 0 duplicate `attemptNo`, 0 element value diffs over `id`, `tenantId`, `attemptNo`, `scheduledFor`, `status` (uuid 4 / uuid 4 / int / date / string), element `tenantId` equals the invoice's `tenantId` (0 / 0 differ), no `invoiceId` copied in, no undeclared field; the attempt sits on an `overdue` invoice on both sides (1 / 1).

Boundaries (source = target): `issuedAt` 2026-02-01T00:00Z..2026-02-28T00:00Z; `status` domain {issued, overdue} with counts {overdue 2, issued 1}; `subtotal` 49..149 (sum 347.00), `tax` 4.04..12.29 (sum 28.62), `total` 53.04..161.29 (sum 375.62), scale ≤ 2 everywhere, no negative amount; `total = subtotal + tax` for 3/3 on both sides; `invoiceLines.lineType` domain {plan, usage}, `amount` 12.29..149, `lineNo` 1..2, no leading/trailing whitespace; `dunningAttempts.scheduledFor` 2026-02-16 (a Monday: 0 weekend dates, 0 dates before the invoice's issue date), `attemptNo` 1, `status` {sent}; `notifications.sentAt` 2026-02-16T09:00Z, `kind` {dunning}. Every target field mapped from a source DATE (`scheduledFor`: 1 value) is a BSON date at exactly 00:00:00.000 UTC; both TIMESTAMPTZ fields (`issuedAt` 3, `sentAt` 1) are BSON dates whose millisecond-truncated multiset equals the source's (the source carries no sub-millisecond precision).

Overdue predicates the dunning routines use (`fn_overdue_accounts`: `status = 'overdue' AND issued_at::date < as_of`; `sp_suspend_overdue`: `issued_at::date <= as_of - 14`), evaluated on both sides for the three recorded `as_of` dates: 2026-02-14 → 2 invoices / 0 tenants, 2026-02-17 → 2 / 1, 2026-02-28 → 2 / 2, equal on both sides.

## 3. Cross-unit consistency

Earlier-wave collections are unchanged in count (plans 3 / tenants 9 / subscriptions 9 / usageEvents 10 / ratingPeriods 3 on both sides). References from wave 3 into them: `invoices.tenantId` → tenants dangling 0 (source 0), `invoices.periodId` → ratingPeriods dangling 0 (source 0), `dunningAttempts.tenantId` → tenants dangling 0, `notifications.tenantId` → tenants dangling 0 (source 0). All 3 invoices reference a rating period that belongs to a different tenant — on both sides (3 / 3), a property of the seed, not of the load (V5). Overdue invoices split 1 suspended / 1 active tenant on both sides.

The collections wave 3 writes through owner APIs are byte-for-value equal to the source after the wave-3 loads: `tenants.creditNotes` 5 elements = 5 `credit_notes` rows (0 missing, 0 extra, 0 on the wrong tenant, 0 value diffs over `issuedOn`, `amount`, `remainingAmount`; `remainingAmount` sum 145.00 both sides, no `remainingAmount > amount`); `tenants.status` {active 8, suspended 1} with 0 diffs; `subscriptions.status`/`suspendedOn` {active 8, suspended 1}, 1 `suspendedOn` set, 0 diffs.

Write fence: `billing_migration` holds exactly the seven mapped collections plus the empty `_connectivity_probe` already reported in waves 1 and 2 (V2); no mapped collection is missing and nothing outside the batches' write targets was created.

## 4. Parity replay (`procs/scenarios/invoicing`, `procs/scenarios/dunning`)

- Fingerprints: recomputed `SOURCE_SHA 2b98f8dc…1929` and `FIXTURE_SHA 53b308f5…06da` equal `procs/transcripts/*_SHA` and every INVOICE-00x / DUNNING-00x transcript, so the transcripts are current.
- Rules gate: `make procs-rules-gate ALL=1` → `Rules gate PASS` for dunning, invoicing, plans, rating.
- Harness replay: `make procs-up NS=v3` + `make procs-parity NS=v3` (all modules) → `Parity PASS=24 FAIL=0 SKIP=0` (plans 5, rating 8, invoicing 6, dunning 5), 0 contract errors (`evidence/procs_parity.{json,md}`), matching the ticket's expected 24/0/0. This ran against the disposable local compose stack (billing-service + `mongo:7` replica set, `target_class local`): parity evidence for the extracted code, **not merge evidence**; the stack was torn down afterwards and Atlas was never written by the verifier.
- Own read-only replay (`evidence/parity_replay.py` → `evidence/parity_replay.json`): INVOICE-001 and INVOICE-002 (`fn_invoice_preview`, tenants 6 and 3 for 2026-02), INVOICE-006 (`fn_invoice_lines`, invoice 1) and DUNNING-001 (`fn_overdue_accounts`, 2026-02-28) re-executed as SELECTs under `billing_ro` on the live fixture (no EXECUTE; `fn_usage_rating` inlined as in the wave-2 replay and the preview's five lines, 8.25 % tax split in two, credit cap `LEAST(credit, round(fee + overage + tax, 2))` mirrored from `invoicing.sql`) and as the equivalent reads on Atlas `billing_migration` with the same arithmetic mirrored in the script (not the billing-service code). Every returned column is compared legacy vs target (`line_no`, `line_type`, `description`, `amount`, `tax_amount`, `credit_applied`, `total`; `tenant_id`, `invoice_id`, `total`, `days_overdue`, `tenant_status`), and the pinned business-field subset against the committed transcripts: 4/4 equal on both comparisons, covering the STARTER/SCALE plan lines, a tax-exempt tenant (INVOICE-002: all tax amounts 0.00), the persisted lines of the imported invoice, and the 27-/15-day overdue ages.
- Own write-path replay (`evidence/writes_replay.py` → `evidence/writes_replay.json`), on the disposable `v3` stack reset from the legacy before-state before each scenario and driven through the service's HTTP API, the resulting documents read straight from the local mongo (this is the probe the ticket asks for: recon only grades the loaded `notifications` row and the one seeded `dunningAttempts` element, Devin Review flag on #2056):
  - `sp_schedule_dunning` → `invoices.dunningAttempts` via `append_dunning_attempt`: DUNNING-002 (2026-02-14, a Saturday) and DUNNING-003 (2026-02-17) append exactly one attempt per overdue invoice with `attemptNo = max + 1` (1 and 2), ids `md5(invoice_id || attempt_no)`, `scheduledFor` moved to Monday 2026-02-16 / kept at 2026-02-17, status `scheduled`, element `tenantId` = invoice `tenantId`, the seeded `sent` attempt untouched, 0 duplicate `attemptNo`, 0 attempts on non-overdue invoices; the full attempt list equals the transcripts' `schedule_rows` probe (3 rows each) and the pinned business fields. A second call on the same `as_of` adds one more attempt per invoice (5 rows, 0 duplicates), i.e. idempotent on (`invoiceId`, `attemptNo`) like `ON CONFLICT DO NOTHING`, not on `as_of` — the legacy behaviour.
  - `sp_suspend_overdue` → `tenants`/`subscriptions` via `suspend_tenant`, `notifications` via `insert_notification`: DUNNING-004 (2026-02-28) suspends exactly the tenants the procedure's predicate selects on the before-state (tenant 5: active, overdue invoice issued 02-13 ≤ 02-14), flips its one active subscription to `suspended` with `suspendedOn = 2026-02-28`, leaves already-suspended tenant 2 and its subscription untouched, and inserts one `suspension` notification with id `md5(tenant_id || 'suspension' || as_of)` = `8cd558f5-d843-8d3d-be19-fb94c21ab81f`, equal to the transcript's `suspension_notifications` probe; the seeded `dunning` notification is untouched. DUNNING-005 (the same run twice) ends in the same state with still exactly one suspension notification (0 duplicates on the unique key), matching the transcript.
  - `sp_issue_invoice` → `tenants.creditNotes` via `apply_credit`, `ratingPeriods` via `finalize_rating`, `invoices`: INVOICE-003 (tenant 9, notes 5.00 of 01-31 and 55.00 of 02-01) and INVOICE-004 (tenant 4, two 30.00 notes of the same date, drawn in id order) draw exactly `min(available, subtotal + tax)` = 53.04, in (`issuedOn`, `id`) order with the earlier note exhausted first, leaving remaining [0.00, 6.96] — equal to the transcripts' `credit_ids`/`issued_on`/`remaining`; INVOICE-005 (tenant 6, no notes) draws 0.00. In all three the new invoice has id `md5(period_id || 'invoice')`, five lines with ids `md5(invoice_id || line_no)` (plan, usage, tax, tax, credit), `total = subtotal + tax − drawn`, the credit line = −drawn, `issuedAt` = period end, an empty `dunningAttempts`, and the tenant's 2026-02 `ratingPeriods` document now carries the finalized `rating` subdocument; the invoice state equals the transcripts' `invoice_state` probe and other tenants' credit notes are unchanged.
  - Legacy side of this replay = the committed transcripts (the recorded legacy post-state), per the ticket clarification; see V8 for why not a live re-CALL.

## 5. Findings (none blocks the verdict)

- V1 — secret visibility (still open from waves 1 and 2): `OW_BILLING_PG_RO_DSN` is not injected into this worker session, so the fixture ran on a session-local `BILLING_RO_PASSWORD`; the verdict is unaffected because the role, grants and data are the committed fixture, but the org/repo secret scope is still not fixed.
- V2 — stray collection (still open from wave 1): `billing_migration._connectivity_probe` (0 documents) is still present; outside mapping spec v2 and every batch's write targets, untouched by the verifier; drop it under the write fence before cutover evidence.
- V3 — redaction salt (still open): `RECON_REDACT_SALT` was unset for the batch runs and these re-runs (`redaction_salted: false`), so recon artifacts carry unsalted hashes of low-entropy values.
- V4 — imported identities: none of the seeded ids follows the procedure identity rule (`invoices` 0/3 = `md5(period_id || 'invoice')`, `invoice_lines` 0/2, `dunning_attempts` 0/1, `notifications` 0/1; source = target, so not a defect), while every id the extracted code created in the replay does (§4). Consequence on both sides alike: re-issuing an imported invoice's period through `sp_issue_invoice` derives a new invoice id and creates a second invoice for that period instead of updating the imported one. The legacy behaves the same; flag it for the cutover runbook, not for the wave.
- V5 — seed quality carried over as-is: all 3 invoices reference a `ratingPeriods` document of another tenant (period `4000…01`/`…02` belong to tenant 1, the invoices to tenants 2, 5, 6), and the imported invoice `6000…01` has lines plan 149.00 + usage 12.29 but `subtotal` 149.00 / `tax` 12.29 (the usage line carries what the header books as tax), so a lines-based total disagrees with the header on both sides (`total_eq_subtotal_plus_tax_minus_credit_lines` false for 1/3 on both sides). Strict recon is right to PASS (source = target), but any report rebuilt from lines or joined to periods by tenant will differ from the legacy headers — a data-quality item for the estate owner.
- V6 — coverage limit of the loaded data: live recon exercises `notifications` on one `dunning` row and `invoices.dunningAttempts` on one `sent` element; the `suspension` kind, the unique-key upsert in `insert_notification`, the `scheduled` attempts, the weekend shift, the credit drawdown and `suspend_tenant` are proven only by the harness parity and the verifier's write-path replay on the disposable stack (§4), never on Atlas. Expected for runtime write paths; recorded so the cutover evidence does not mistake the recon PASS for coverage of them.
- V7 — `make tp-smoke` does not exist on the run branch (cut from `main`); CI's procs parity workflow stands in, as for the batch PRs and the earlier verify PRs.
- V8 — guard block (reported, not routed around): the first version of `evidence/writes_replay.py` also re-ran each `CALL` on the disposable namespace's own PostgreSQL (`billing_v3`, inside a transaction rolled back after reading the tables) to diff whole tables against the Mongo post-state; the dbx-migration-factory guard rejected it ("Python statement or connection is built at run time; the guard cannot resolve a non-read statement", allowlist `.migration/allowed_targets.json` has no `target_hosts`/`fixture_endpoints` for the procs namespaces). The script was reduced to HTTP calls plus read-only mongo reads, and the legacy side of the write replay is the committed transcripts' recorded post-state. If the manager wants whole-table legacy diffs for write scenarios, the allowlist needs a reviewed `fixture_endpoints` entry for the procs namespaces; the verifier does not edit it.
- V9 — local stack flake: the disposable stack's `mongo:7` aborted once during the first write-replay attempt (WiredTiger fassert 50853, `__posix_directory_sync` error 24 on `/data/db`), which surfaced as HTTP 500 from `/internal/reset`; `docker start` of the container recovered it and the harness parity run (24/24) and the replay completed without recurrence. Local compose stack only (overlay storage), Atlas not involved; worth knowing if the parity CI job ever fails on a reset.

## Evidence on this branch

- `.migration/recon/wave-3/w3-b01/invoicing/{result.json,report.md,recon.summary.md}` and `.migration/recon/wave-3/w3-b02/dunning/{result.json,report.md,recon.summary.md}` — the verifier's live re-runs (redacted)
- `.migration/recon/wave-3/verify-result.json` — the verify result JSON for `preflight.py --verify`
- `.migration/recon/wave-3/evidence/` — `probe.py`/`probes.json`, `parity_replay.py`/`parity_replay.json`, `writes_replay.py`/`writes_replay.json`, `procs_parity.{json,md}`
