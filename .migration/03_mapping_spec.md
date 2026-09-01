# 03 — Mapping specification

**Mapping version:** `m1` · **Tolerance version:** `v1` · **Status:** ACCEPTED at STOP B (2026-09-01)
**Target database:** `ow_tp_mongodb_orc1` · **Source:** Oracle `OW_BILLING` (profile `mongo-migration/profiles/oracle.md`)

The authoritative, machine-readable spec is **`03_mapping_spec.json`** — that is what the
recon harness consumes and what every unit child cites. This file is the reviewable
narrative: the decisions, and the access-pattern evidence behind each one. Both are
generated/checked by `tools/build_mapping_spec.py`, which fails the build unless every one
of the 432 census columns lands in exactly one of `fields`, `folded`, or `dropped`.

Coverage table: `census/coverage.md`. Raw census: `census/*.json`.

## The estate is two lineages, not one

The census settled a question the table list alone does not answer. `OW_BILLING` holds two
disjoint sub-estates with no foreign key or shared key between them:

| Lineage | Tables | Rows | Character |
|---|---|---:|---|
| **Converted legacy estate** | `CUSTOMER_MASTER`(+`_HIST`), `ENTITY_ATTR_VALUE`, `INVOICE_HEADER`, `INVOICE_LINE` | 202,083 | No FKs at all, `batch_no`-scoped, 155-column wide table, dates in `VARCHAR2`, CSV lists, EAV side table |
| **Normalized billing application** | `TENANTS`, `PLANS`, `SUBSCRIPTIONS`(+`_HIST`), `USAGE_EVENTS`, `RATING_PERIODS`, `RATING_RESULTS`, `INVOICES`, `INVOICE_LINES`, `CREDIT_NOTES`, `DUNNING_ATTEMPTS`, `NOTIFICATIONS`, `BILLING_AUDIT_LOG` | 1,000 | 13 enforced FKs, driven by the 5 PL/SQL packages |

They share only `CODES` (the magic-number lookup) and `TENANTS`. This is why
`INVOICE_HEADER` → `invoices` and `INVOICES` → `subscription_invoices` are **two
collections and not one**: nothing in the source relates a row in one to a row in the
other, and merging them would be a modeling invention rather than a migration. If the
customer intends them to converge, that is a scope decision at STOP B, not a mapping row.

## Access-pattern evidence

Everything below cites `census/access_patterns.json` or a named source file; no embed
decision rests on shape alone.

| Evidence | Value | What it decides |
|---|---|---|
| `reports.py` `LINE_SQL` joins header→line on every month-end run; no query reads a line without its header | — | `invoice_line` **embeds** |
| Invoice line fan-out | min 1, max 23, avg 8.0; longest `item_desc` 29 chars | Embedded invoice ≈ 3 KB — three orders of magnitude under the 16 MB limit. Embed is safe |
| `reports.py` `BALANCES_SQL` aggregates balances across the whole batch; handbook lookups are by `cust_id`/`cust_no`/`cust_name_upper` | — | `customers` root doc + a case-insensitive collation index replacing the `CUST_NAME_UPPER` shadow column |
| `ENTITY_ATTR_VALUE` has no consumer of its own; 7 distinct attribute names, 0 orphans | 8,333 rows / 7,075 customers | EAV **embeds** into `customers.attributes[]` |
| 187 `(entity_id, attr_name)` pairs carry >1 row (up to 3) | — | `attributes` is an **array**, not a subdocument keyed by name — a keyed subdocument would silently drop the duplicates |
| `CUSTOMER_MASTER` column population | 113 of 155 columns NULL in all 25,000 rows | those columns are dropped as proposed-unused, with the count as evidence |
| `PKG_RATING.compute_rating` scans `USAGE_EVENTS` by `(tenant_id, occurred_at)`; append-only with its own write path | 814 rows | `usage_events` stays **referenced**, not embedded into periods |
| `RATING_RESULTS` is written only by `sp_finalize_rating` for its period and read only by `fn_usage_summary` for that period | — | results **embed** into `rating_periods` |
| `DUNNING_ATTEMPTS` grows unbounded over an invoice's life and is written by a nightly job long after issue | — | **referenced**, not embedded into the invoice |
| `CODES` is joined twice per report and by `f_code_desc` in all 5 packages | 32 rows | kept as a collection **and** denormalized as a label beside each code value, so the hot read path needs no `$lookup` |
| `all_source` ROWID scan | 0 objects | the profile's ROWID trap does not apply here |
| Only one `batch_no` present (`85559852` = `sha256("demo")` fold, `reports.py:ns_batch_no`) | 25,000 / 18,750 rows | scoping is the `${batch_no}` parameter, resolved per run — never a hard-coded literal in a mapping row |

## Collections

13 collections, 44,750 root documents, from 203,088 in-scope source rows (the difference is
child rows becoming embedded array elements).

| Wave | Collection | Sources | Model | `_id` | Docs |
|---|---|---|---|---|---:|
| 0 | `codes` | `CODES` | reference | `{code_type}:{code_val}` | 32 |
| 0 | `tenants` | `TENANTS` | reference | natural `id` | 69 |
| 0 | `plans` | `PLANS` | reference | natural `id` | 3 |
| 1 | `customers` | `CUSTOMER_MASTER` + `ENTITY_ATTR_VALUE` + `CUSTOMER_MASTER_HIST` | embed ×5 | natural `cust_id` | 25,000 |
| 1 | `subscriptions` | `SUBSCRIPTIONS` + `SUBSCRIPTIONS_HIST` | embed | natural `id` | 69 |
| 2 | `invoices` | `INVOICE_HEADER` + `INVOICE_LINE` | embed | natural `invoice_id` | 18,750 |
| 2 | `usage_events` | `USAGE_EVENTS` | reference | natural `id` | 814 |
| 2 | `rating_periods` | `RATING_PERIODS` + `RATING_RESULTS` | embed | natural `id` | 3 |
| 2 | `subscription_invoices` | `INVOICES` + `INVOICE_LINES` | embed | natural `id` | 3 |
| 3 | `credit_notes` | `CREDIT_NOTES` | reference | natural `id` | 5 |
| 3 | `dunning_attempts` | `DUNNING_ATTEMPTS` | reference | natural `id` | 1 |
| 3 | `notifications` | `NOTIFICATIONS` | reference | natural `id` | 1 |
| 3 | `billing_audit_log` | `BILLING_AUDIT_LOG` | reference | natural `log_id` | 0 |

Every `_id` is a natural key: the estate's surrogate sequences have no external consumer
(see `census/coverage.md`), so no `counters` collection is proposed.

### `customers` — the wide-embed unit

Five structural collapses, each with a declared element key so recon can value-grade
inside the arrays:

- `ADDR_LINE_1..6` → `address.lines[]` (ordinal key; NULL lines omitted, order preserved)
- `PHONE1..4` + `PHONE{n}_TYPE_CD` → `phones[]` of `{number, type_code, type}` (ordinal key)
- `EMAIL_1..3` → `emails[]` (ordinal key)
- `ENTITY_ATTR_VALUE` → `attributes[]` of `{name, value, type, created_at}` (key `[attr_name, created_dt]`)
- `CUSTOMER_MASTER_HIST` → `history[]` (key `[hist_id]`)

The mailing-address block is 100% NULL and is dropped with the rest of the 113 unused
columns; `CUST_NAME_UPPER` is dropped in favour of a collation index.

### Cardinality rules recon must enforce

```
customers:              count(docs) == 25,000
                        sum(attributes[].length)   == 8,333          (all EAV rows, 0 orphans)
                        sum(address.lines[].length) == count(non-null ADDR_LINE_*)
                        sum(phones[].length)       == count(non-null PHONE1..4)
                        sum(emails[].length)       == count(non-null EMAIL_1..3)
                        sum(history[].length)      == 0              (explicit empty PASS, T14)
invoices:               count(docs) == 18,750
                        sum(lines[].length)        == 150,000 - 37   == 149,963
rating_periods:         sum(results[].length)      == 3
subscription_invoices:  sum(lines[].length)        == 2
subscriptions:          sum(history[].length)      == 0              (explicit empty PASS, T14)
billing_audit_log:      count(docs) == 0                             (explicit empty PASS, T14)
```

### Quarantine expectations (must be found, not tolerated)

| Collection | Class | Exact count |
|---|---|---:|
| `invoices_quarantine` | `INVOICE_LINE` rows whose `invoice_id` has no header — dropped by the legacy report's inner join, which is why they must surface here | 37 |
| `customers_quarantine` | unparseable `SIGNUP_DT` strings (`31-FEB-24`, `N/A`, …) | 50 |
| `customers_quarantine` | malformed `RELATED_ACCT_IDS` CSV lists | 31 |

Confirmed against the live source; `LAST_ACTIVITY_DT`, `CHILD_ACCT_IDS` and
`PROMO_CODES_CSV` are clean (0 each), and every `STATUS_CD` value resolves in `CODES`
(0 unmapped).

## Type mapping

Applied by rule from the profile's type table, not per column by hand:

| Oracle | BSON | Applied to |
|---|---|---|
| `NUMBER(p,0)`, p ≤ 18 | `long` | all integer/code columns |
| `NUMBER(p,s)`, s > 0 | `Decimal128` | all money and rate columns — never `double` |
| `DATE`, `TIMESTAMP(6)` | `date` | UTC, truncated to ms |
| `VARCHAR2` holding `DD-MON-YY` | `date` | `SIGNUP_DT`, `LAST_ACTIVITY_DT`, `INVOICE_DT`, `DUE_DT`, `HIST_DT`, EAV `CREATED_DT` — unparseable values quarantined, never coerced |
| `VARCHAR2` holding a CSV list | `array<string>` | `RELATED_ACCT_IDS`, `PROMO_CODES_CSV`, `GL_ACCT_CSV` — malformed values quarantined |
| `CHAR(1)` | `bool` | every `*_YN` flag: `rstrip_spaces` then `Y`→`true` |
| `VARCHAR2`/`CHAR` otherwise | `string` | Oracle `''` == NULL → **field omitted** |

`*_CD` columns keep their numeric value **and** gain a denormalized label resolved through
`CODES` at load time (`status_cd: 1` + `status: "active"`), so no read path needs a
`$lookup` against a 32-row table.

## Unit list and wave plan

A unit owns disjoint collections and is one PR into `tp-run/mongodb-20260901T033326Z`.

| Wave | Unit | Collections | Pattern class | Source rows | Notes |
|---|---|---|---|---:|---|
| 0 | `reference` | `codes`, `tenants`, `plans` | reference | 104 | Serial, alone in its wave: every other unit resolves code labels through it |
| 1 | `customers` | `customers`, `customers_quarantine` | **wide-embed** (calibration) | 33,333 | **XL** — 155 columns, 5 embeds, 3 anomaly classes. Contract PR before implementation |
| 1 | `subscriptions` | `subscriptions` | small-embed | 69 | |
| 2 | `invoices` | `invoices`, `invoices_quarantine` | **bulk-load** (calibration) | 168,750 | **XL** — 150k child rows; holds the extract lease for its run |
| 2 | `usage_rating` | `usage_events`, `rating_periods` | small-embed | 820 | |
| 2 | `subscription_invoices` | `subscription_invoices` | small-embed | 5 | |
| 3 | `collections_ops` | `credit_notes`, `dunning_attempts`, `notifications`, `billing_audit_log` | reference | 7 | Includes two explicit empty-collection PASSes |
| 4 | `stored_logic` | none (code only) | **proc-heavy** (calibration) | — | **XL** — 19 routines, 7 triggers, 2 jobs, 5 sequences. Graded against `procs/transcripts/`, not against row counts |

Waves are dependency-ordered: wave 0 supplies the code labels every later unit
denormalizes; wave 1 supplies the customer keys wave 2's invoices reference; wave 4 needs
the collections its rewritten logic reads to exist.

**Fan-out width: 3** (waves 1–3), against a **source-load cap of 1** from STOP A. These are
not in conflict: the cap is enforced by an **extract lease** registered in `04_progress.md`
— a child holds it only while streaming from Oracle and releases it before the transform
and load. Only `customers` and `invoices` have extracts long enough to contend; the other
six units read fewer than 1,000 rows each. Waves therefore run genuinely 3-wide rather than
collapsing to width-1.

**Calibration:** one unit per new pattern class runs first and its cost is recorded —
`reference` (wave 0), then `customers` (wide-embed) and `invoices` (bulk-load) as their
waves' calibration units, then `stored_logic` (proc-heavy). Every subsequent unit in a
class fans out in parallel. Expected cost discount for the non-calibration units:
**30–50%** against the calibration unit of the same class; a smaller discount is a
regression and shows in the ledger.

**XL units** — `customers`, `invoices`, `stored_logic` — get a decision-first contract PR
(collection shape, element keys, quarantine contract; no loader code) before
implementation. The other five units are one PR each.

## Open decisions for STOP B

1. **Two invoice lineages kept separate** (`invoices` vs `subscription_invoices`). Correct
   as a migration; a merge would be a scope change.
2. **`attributes` as an array rather than a keyed subdocument**, forced by the 187
   duplicate `(entity_id, attr_name)` pairs. A keyed subdocument is possible only with an
   explicit "last write wins" data-loss decision.
3. **113 always-NULL `CUSTOMER_MASTER` columns dropped.** They are empty in this estate;
   if any is populated in the production estate the spec needs the production population
   census before load.
4. **`_id` = natural key everywhere, all 5 sequences retired.** Assumes no external
   consumer reads `cust_seq_no` or `log_id`.
5. **Application repoint stays out of scope** for this run (the Java billing service keeps
   reading Oracle). This run delivers the loaded, reconciled target and the stored-logic
   rewrite.

The spec is append-only after STOP B; changes go through `05_decisions.md` with an explicit
re-verification scope for already-merged waves.
