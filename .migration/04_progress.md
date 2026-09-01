# 04 — Progress ledger

Mapping version: _pending STOP B_ · Tolerance version: `v1` · Recon mode: LIVE

Status: `pending` → `in_progress` → `recon_pass` → `merged`. A unit is done only when its
PR is **merged** into `tp-run/mongodb-20260901T033326Z`.

| Wave | Unit | Source objects | Write targets (registered) | Status | Parity | Quarantine rate | Unverified paths | PR |
|---|---|---|---|---|---|---|---|---|
| 1 | `reference` | CODES, PLANS, TENANTS | `codes`, `plans`, `tenants` | pending | — | — | — | — |
| 2 | `customers` | CUSTOMER_MASTER, ENTITY_ATTR_VALUE, CUSTOMER_MASTER_HIST | `customers`, `customers_quarantine` | pending | — | — | — | — |
| 2 | `invoices` | INVOICE_HEADER, INVOICE_LINE | `invoices`, `invoices_quarantine` | pending | — | — | — | — |
| 2 | `subscriptions` | SUBSCRIPTIONS, SUBSCRIPTIONS_HIST | `subscriptions` | pending | — | — | — | — |
| 3 | `usage_rating` | USAGE_EVENTS, RATING_PERIODS, RATING_RESULTS | `usage_events`, `rating_results` | pending | — | — | — | — |
| 3 | `collections_ops` | CREDIT_NOTES, DUNNING_ATTEMPTS, NOTIFICATIONS, BILLING_AUDIT_LOG | `credit_notes`, `dunning_attempts`, `notifications`, `billing_audit_log` | pending | — | — | — | — |
| 3 | `legacy_invoices_v2` | INVOICES, INVOICE_LINES (3/2 rows) | disposition decided in census (fold or retire) | pending | — | — | — | — |
| 4 | `stored_logic` | PKG_OW_UTIL, PKG_PLANS, PKG_RATING, PKG_INVOICING, PKG_DUNNING, 7 triggers, 2 jobs, 5 sequences | code only (no collections) | pending | — | — | — | — |

Out of scope (proposed): `FIXTURE_META` (fixture bookkeeping, not business data).

Waves are dependency-ordered; shared state is re-checked at each wave boundary (Atlas
storage headroom, `terraform plan` cleanliness where applicable). Write-target collisions
halt the wave immediately.
