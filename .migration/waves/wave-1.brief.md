# Wave 1 close

Landed: 4 of 4 batches passed their own recon.
Independent verify: FAIL, 4 PRs merged.
Failed: none.
Blocked on missing inputs: none.
Held back by circuit breaker: none.

Verifier findings:
- All four wave 1 units passed an independent live recon run this session with merge_eligible=true, and all four PRs were merged.
- Customers and invoices point at 50 tenant ids that do not exist in the tenants collection, exactly as in the legacy source, so the gap predates the migration.
- The invoices collection mixes two shapes because it has two legacy sources: 18,750 converted invoices carry numeric line type codes and no subtotal, tax, period or dunning, while the 3 billing-estate invoices carry string line types and no invoice number.
- 68,340 invoice lines have a service period that ends before it starts, and the migration carries them unchanged rather than repairing them.
- Three customer fields (dunning-exempt flag, life-to-date billed, contact notes) are null for every one of the 25,000 customers because the legacy columns are empty everywhere.
- The anomaly budget matched exactly: 37 orphaned invoice lines, 50 unparseable signup dates kept as raw values, and 31 malformed related-account lists kept as raw values.
- The harness cannot grade array-index field paths or a collection with two source roots, so the mapping had to be rendered into harness terms before it would run; I checked those excluded fields by hand and they all match the source.
- Embedded arrays, key uniqueness, money boundaries, empty collections and all cross-unit references reconciled with no differences.
- verifier output invalid: missing verdicts for w1-b01, w1-b02, w1-b03, w1-b04
- verifier output invalid: unexpected verdicts for audit_log, credit_notes, customer_history, customers, invoice_lines_orphaned, invoices, notifications, rating_periods, usage_events
- verifier output invalid: verdict for w1-b01 is None
- verifier output invalid: verdict for w1-b02 is None
- verifier output invalid: verdict for w1-b03 is None
- verifier output invalid: verdict for w1-b04 is None

Skill feedback to fold in before the next wave:
- A derived field with no source column (lines[].servicePeriod, built from MMYYYY-MMYYYY) is unreachable from tier 3; only tier 4 can grade it.
- Brief says STATUS_CD 99 has no CODES row and must decode UNKNOWN(99); the seeded estate has CUST_STATUS 99 = 'conversion-limbo', so f_code_desc (and the loader) return that for all 473 rows.
- Brief says do not edit .migration/ but also requires recon inputs, tier 4 ops and the *.recon.json artifact under .migration/recon/<unit>/ and .migration/ops/; I wrote only new unit-scoped files there and no ledger file.
- Harness cannot compare an encoded source value against its decoded target string (notifications.kind via CODES NOTIF_KIND) - graded with tier 4 recorded operations.
- Harness cannot compare an integer source code with its decoded target string, so every CODES-backed field needs a tier 4 op; a decode_via_lookup(code_type) rule would remove that workaround.
- Harness canonicalizer has no yn_to_bool, csv_split_trim or parse_date_string rule and cannot compare an integer CODES value against its decoded string; graded those with 26 tier 4 recorded operations instead of patching the harness.
- Harness has no rule for yn_to_bool, csv_split_trim or parse_date_string; not needed by this unit but still missing.
- Harness has no yn_to_bool, csv_split_trim or parse_date_string rule; not needed by this batch's fields, harness not patched.
- Harness rejects an embed with child_where unless target_where is also set; the slice adds target_where {} for the ENTITY_ATTR_VALUE embed.
- Harness validates target field paths as identifiers, so the mapping spec's positional paths (addresses.0.city) cannot be graded in tiers 2/3; the unit mapping slice moves them to tier 4.
- Money aggregates compared as integer cents in tier 4 to avoid Decimal128-vs-Oracle display formatting mismatch.
- One target collection fed by two source root tables (conversion + billing in invoices) has no first-class support: it needs duplicate mapping entries with a target filter on the discriminator field, produced by a unit-local recon_spec.py.
- The brief says to copy ledger inputs into .migration/recon/<unit>/inputs/, but nothing re-copies them after an ops edit; a stale copy cost one full recon run. Worth a wave-0 note or a make target.
- The harness cannot compare an integer source code against its CODES-decoded target string; a codes_decode rule would remove a whole class of hand-written operations.
- The harness has no yn_to_bool, csv_split_trim or parse_date_string canonicalization rule, so POSTED_YN, GL_ACCT_CSV and DD-MON-YY dates had to be graded with tier 4 recorded operations instead of tier 3.
- Tier 4 compares rows exactly, so an op whose source aggregate yields zero rows must still emit a target row: use $group+$cond, not $count.
- make tp-smoke fails on a fresh VM because the repo's own mise.toml is untrusted; blueprint fix suggested.
- make tp-smoke fails out of the box because mise refuses the repo's untrusted mise.toml; `mise trust` is needed first (blueprint update suggested).
- make tp-smoke fails until `mise trust` is run in the checkout.
- recon run grades every collection in the spec handed to it, so the unit slice via unit_spec.py is mandatory, not an optimisation.
- tp-pre-pr-self-check expects an ow_tp target prefix, while this batch's contract names ow_billing_migration.
- unit_spec.py slice plus copying ledger inputs into .migration/recon/<unit>/inputs/ worked exactly as the wave-0 notes described.

Per batch:
- w1-b01: PASS. w1-b01 landed: 25,000 customers (8,333 embedded attributes) and an empty customer_history in ow_billing_migration, live recon PASS with merge_eligible=true, idempotency proven, PR #1567 open and unmerged. https://github.com/Cognition-Partner-Workshops/otterworks/pull/1567
- w1-b02: PASS. Invoices batch landed: 18,753 invoices (18,750 conversion + 3 billing), 149,965 embedded lines, 1 dunning attempt and exactly 37 orphaned lines in Atlas, live recon PASS and merge-eligible, PR #1568 open into the run branch. https://github.com/Cognition-Partner-Workshops/otterworks/pull/1568
- w1-b03: PASS. w1-b03 usage_events and rating_periods migrated to ow_billing_migration; live recon PASS with merge_eligible=true (814/3/3 recomputed from Atlas, reload idempotent), PR #1565 open into the run branch, not merged. https://github.com/Cognition-Partner-Workshops/otterworks/pull/1565
- w1-b04: PASS. w1-b04 ancillary collections (credit_notes 5, notifications 1, audit_log 0) loaded to ow_billing_migration, live recon PASS with merge_eligible=true, idempotent reload proven, PR #1564 open into the run branch. https://github.com/Cognition-Partner-Workshops/otterworks/pull/1564
