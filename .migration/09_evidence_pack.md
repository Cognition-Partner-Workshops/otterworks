# 09 Evidence pack — OtterWorks billing, Oracle `OW_BILLING` → Atlas `ow_billing_migration`

Assembled for STOP C. Everything here is a link to evidence in this branch, not a restatement
of it. Watermark: **2026-09-15T06:00:42Z** (last loader finished; no source write since).

## 1. Coverage

Thirteen collections, exactly the PRD's list. Counts recomputed from Atlas after the
watermark catch-up.

| Collection | Docs | Source | Unit | Wave |
|---|---:|---|---|---|
| plans | 3 | `PLANS` | U1-reference | 0 |
| codes | 32 | `CODES` | U1-reference | 0 |
| tenants | 69 | `TENANTS` + `SUBSCRIPTIONS` (embedded) | U1-reference | 0 |
| subscription_history | 0 | `SUBSCRIPTIONS_HIST` (empty at source) | U1-reference | 0 |
| customers | 25,000 | `CUSTOMER_MASTER` + `ENTITY_ATTR_VALUE` (8,333 embedded) | U2-customers | 1 |
| customer_history | 0 | `CUSTOMER_MASTER_HIST` (empty at source) | U2-customers | 1 |
| invoices | 18,753 | `INVOICE_HEADER`+`INVOICE_LINE` (18,750, `source: "conversion"`) and `INVOICES`+`INVOICE_LINES`+`DUNNING_ATTEMPTS` (3, `source: "billing"`); 149,965 embedded lines | U3-invoices | 1 |
| invoice_lines_orphaned | 37 | `INVOICE_LINE` rows with no header | U3-invoices | 1 |
| usage_events | 814 | `USAGE_EVENTS` | U4-usage | 1 |
| rating_periods | 3 | `RATING_PERIODS` + `RATING_RESULTS` | U4-usage | 1 |
| credit_notes | 5 | `CREDIT_NOTES` | U5-ancillary | 1 |
| notifications | 1 | `NOTIFICATIONS` | U5-ancillary | 1 |
| audit_log | 0 | `BILLING_AUDIT_LOG` (empty at source); 90-day TTL index present | U5-ancillary | 1 |

No table in the census is unaccounted for: the ones not listed are either the sources of an
embedded array above, or dropped by an approved Open item (80 null `FLAG_*`/`UDF_*` columns).

## 2. Approved mapping spec

`03_mapping_spec.json`, **version 1**, approved at STOP B (decision row 5). One grading-only
amendment since (row 6, pre-authorised at STOP A): `codes` compares on the `codeType`/`codeVal`
pair because the harness needs equal-length key tuples. Document identity is unchanged.

## 3. Wave reports

| Wave | Batches | Result | Report |
|---|---|---|---|
| 0 | 1 (`w0-b01`) | PASS, 0 exceptions | `waves/wave-0.result.json`, `waves/wave-0.brief.md`, PR #1563 |
| 1 | 4 (`w1-b01`…`w1-b04`) | all 4 PASS; result file FAIL on verifier output shape only | `waves/wave-1.result.json`, `waves/wave-1.brief.md`, PRs #1567 #1568 #1565 #1564 |

The wave-1 file reads `closed: false` because the independent verifier keyed its verdicts by
collection name where the workflow expects batch ids. Every finding inside it is a PASS.
Recorded as a reporting-shape failure in decision row 9, not a unit failure, and the four
units are re-proven at the watermark in §5 below.

## 4. Parallel run

**Not performed.** No dual-write and no coexistence window were built: the source is a quiet
fixture with both scheduler jobs disabled and no application writing during the migration
(`07_dependency_register.md` D1-1, D1-2). The point-in-time copy is therefore the whole
migration. This is a risk acceptance and is restated as its own line at STOP C.

## 5. Watermark recon

Full live recon gate re-run against the source at the watermark, after the final catch-up
load, for all five units. All five PASS, `merge_eligible: true`:

`recon/watermark/U1-reference.result.json` · `U2-customers` · `U3-invoices` · `U4-usage` ·
`U5-ancillary` (each is the harness `result.json` with its four tiers).

Anomaly budget matched exactly at the watermark, as a set: **37** orphaned invoice lines,
**50** unparseable `SIGNUP_DT` values kept raw under `legacy`, **31** malformed
`RELATED_ACCT_IDS` lists kept raw. Not more, not fewer.

Idempotency: every unit proved it by an actual second load
(`recon/*/idempotency.json`); the watermark catch-up was itself a second load of all five
units and changed no document.

## 6. Open issues and dispositions

| Issue | Disposition |
|---|---|
| 50 tenant ids referenced by `customers`/`invoices` do not exist in `TENANTS` | Carried across unchanged. Pre-existing source gap, not a migration defect. No repair — silent repair is forbidden. |
| 68,340 invoice lines have a service period ending before it starts | Carried across unchanged, same reason. |
| `FLAG_*`/`UDF_*` (80 columns) 100% null | Dropped, Open item 1, approved at STOP B. |
| `SEGMENT_CD`/`REGION_CD`/`TERRITORY_CD`/`CHANNEL_CD`/`RATE_CLASS_CD` have no owner | Carried as integers. Open, D5-1. Decoding later is a one-pass update, not a re-migration. |
| `audit_log` TTL untested | Source table is empty, so the 90-day TTL index exists but has never expired a document. Untested path. |
| Y/N, CSV, `DD-MON-YY` and CODES-decoded fields have no canonicaliser rule | Graded by tier 4 operations instead of tier 3, stated in every recon report. Raised as profile feedback in `canonicalization.json`, not patched into the harness. |
| Wave-1 verifier output shape | Decision row 9; skill feedback filed. |

## 7. Dependency register

`07_dependency_register.md`: D1-1, D1-2, D2-1, D2-2, D3-1, D3-2, D3-3 and D4-1 are all
DECIDED with an owner and a plan. **D5-1 is FOUND, not resolved**, and is deferred to the
billing data owner by the STOP B answer to Open item 5.

## 8. Business logic

**This is a data migration; no stored-proc logic was converted.** The five PL/SQL packages
stay on Oracle (D3-1) — logic extraction is the separate stored-procs track. Only the rules
that shape the data were carried: `f_str2dt`'s `DD-MON-YY` parse with NULL on failure,
`f_code_desc`'s `UNKNOWN(<n>)` fallback, and the `USAGE_EVENTS` trigger check as a
`$jsonSchema` validator.

Consequence for cutover, stated plainly and repeated as §1 of the runbook: **reads can
repoint at Atlas; writes cannot.** Nothing in Atlas implements invoicing, rating or dunning.
This is a partial cutover.

## 9. Access posture

Source access was SELECT-only by discipline, not by grant: no read-only Oracle account exists
and creating one would have written to the source (D4-1, on record at STOP A). Writes were
allowlisted to `ow_billing_migration` (`allowed_targets.json`) and the guard enforced it.
Secrets referenced by name only: `ORACLE_BILLING_URI`, `MONGODB_ATLAS_URI`.

## 10. Scale caveat

Demo scale on an M0 cluster: ~44k documents, largest collection 25,000. Nothing here proves
behaviour at production volume — no sharding, no index-size pressure, no load test.
