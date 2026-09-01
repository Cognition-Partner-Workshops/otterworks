# 04 — Progress ledger

Mapping version: `m1` (ACCEPTED at STOP B, 2026-09-01) · Tolerance version: `v1` (ACCEPTED at STOP A) · Recon mode: LIVE

Status: `pending` → `in_progress` → `recon_pass` → `merged`. A unit is done only when its
PR is **merged** into `tp-run/mongodb-20260901T033326Z`.

| Wave | Unit | Source objects | Write targets (registered) | Class | Status | Parity | Quarantine | Unverified paths | PR |
|---|---|---|---|---|---|---|---|---|---|
| 0 | `reference` | CODES, TENANTS, PLANS | `codes`, `tenants`, `plans` | reference | recon_pass | 104/104 docs, full keyed diff, 0 findings | 0 (no anomalies in source) | none | _open_ |
| 1 | `customers` | CUSTOMER_MASTER, ENTITY_ATTR_VALUE, CUSTOMER_MASTER_HIST | `customers`, `customers_quarantine` | wide-embed **XL** | pending | — | — | — | — |
| 1 | `subscriptions` | SUBSCRIPTIONS, SUBSCRIPTIONS_HIST | `subscriptions` | small-embed | pending | — | — | — | — |
| 2 | `invoices` | INVOICE_HEADER, INVOICE_LINE | `invoices`, `invoices_quarantine` | bulk-load **XL** | pending | — | — | — | — |
| 2 | `usage_rating` | USAGE_EVENTS, RATING_PERIODS, RATING_RESULTS | `usage_events`, `rating_periods` | small-embed | pending | — | — | — | — |
| 2 | `subscription_invoices` | INVOICES, INVOICE_LINES | `subscription_invoices` | small-embed | pending | — | — | — | — |
| 3 | `collections_ops` | CREDIT_NOTES, DUNNING_ATTEMPTS, NOTIFICATIONS, BILLING_AUDIT_LOG | `credit_notes`, `dunning_attempts`, `notifications`, `billing_audit_log` | reference | pending | — | — | — | — |
| 4 | `stored_logic` | 5 packages / 19 routines, 7 triggers, 2 jobs, 5 sequences | code only (no collections) | proc-heavy **XL** | pending | — | — | — | — |

Write targets are disjoint by construction: 13 collections + 2 quarantine collections, no
collection named by two units. A collision halts the wave immediately.

Out of scope: `FIXTURE_META` (estate bookkeeping, one row, no business data).

## Extract lease (source-load cap = 1)

The STOP A cap of 1 concurrent Oracle query is enforced here, not by narrowing the wave. A
child claims the lease before streaming from Oracle and releases it before transform/load,
so waves still run 3-wide. Only `customers` and `invoices` read enough rows to contend.

| Lease | Holder | Claimed (UTC) | Released (UTC) |
|---|---|---|---|
| `oracle:OW_BILLING` | _free_ | 2026-09-01 (claimed by `reference`) | 2026-09-01 (released) |

## Wave-boundary checks

Re-checked before each wave starts; a failure halts rather than degrades.

| Wave | Atlas storage headroom | Recon rerun budget used | Same-class failures |
|---|---|---|---|
| 0 | 324.16 MB free (187.84 MB used of 512; wave 0 adds ~104 docs) | 0/3 | 0/3 |
| 1 | not yet checked | 0/3 | 0/3 |
| 2 | not yet checked | 0/3 | 0/3 |
| 3 | not yet checked | 0/3 | 0/3 |
| 4 | n/a (code only) | 0/3 | 0/3 |

## Calibration cost ledger

One calibration unit per pattern class; later units of the class are expected to land
30–50% cheaper. A smaller discount is a regression, visible here.

| Class | Calibration unit | Calibration cost | Later units | Observed discount |
|---|---|---|---|---|
| reference | `reference` | — | `collections_ops` | — |
| wide-embed | `customers` | — | — | — |
| bulk-load | `invoices` | — | `usage_rating`, `subscription_invoices`, `subscriptions` | — |
| proc-heavy | `stored_logic` | — | — | — |
