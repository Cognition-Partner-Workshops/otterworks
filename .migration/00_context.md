# 00 — Engagement context

Status legend: **FACT** (probed or user-confirmed) · **PROPOSED** (Devin's recommended default, pending STOP A)

## Engagement

| Item | Value | Status |
|---|---|---|
| Engagement | OtterWorks billing/customer estate → MongoDB Atlas | FACT |
| Scope statement | "Move the entire Oracle estate to Mongo" | FACT |
| Source family | `oracle` (profile `mongo-migration/profiles/oracle.md`) | FACT |
| Source | Oracle Free 23ai, PDB `FREEPDB1`, schema `OW_BILLING`, host port 52521 (container port 1521) | FACT |
| Target | MongoDB Atlas 8.0.29, project `otterworks-demos`, free-tier M0 | FACT |
| Repo | `Cognition-Partner-Workshops/otterworks` | FACT |
| Working branch | `tp-run/mongodb-20260901T033326Z` (cut from `tech-partnerships`) | FACT |
| Namespace | `NS=demo` for the source estate; migration namespace `orc1` | PROPOSED |
| Recon mode | LIVE (dual connections: Oracle + Atlas both reachable from this VM) | FACT |

## Source topology (probed 2026-09-01, schema OW_BILLING)

20 tables · 25 indexes · 5 packages (+5 bodies) · 7 triggers · 2 scheduler jobs · 5 sequences.
Column type mix: VARCHAR2 259, NUMBER 102, CHAR 51, DATE 15, TIMESTAMP(6) 5.

| Table | Rows | Note |
|---|---|---|
| CUSTOMER_MASTER | 25,000 | 155 columns; CSV list columns; `DD-MON-YY` string dates; magic `*_CD` codes |
| CUSTOMER_MASTER_HIST | 0 | full-row-copy history, trigger-populated |
| ENTITY_ATTR_VALUE | 8,333 | EAV escape hatch (untyped attributes) |
| INVOICE_HEADER / INVOICE_LINE | 18,750 / 150,000 | 37 orphaned lines |
| INVOICES / INVOICE_LINES | 3 / 2 | second, near-empty invoice pair (disposition TBD in census) |
| SUBSCRIPTIONS / SUBSCRIPTIONS_HIST | 69 / 0 | |
| TENANTS | 69 | 9 shared baseline rows + 60 `demo::*` rows |
| USAGE_EVENTS | 814 | |
| RATING_PERIODS / RATING_RESULTS | 3 / 3 | |
| PLANS / CODES | 3 / 32 | reference data |
| CREDIT_NOTES / DUNNING_ATTEMPTS / NOTIFICATIONS | 5 / 1 / 1 | |
| BILLING_AUDIT_LOG | 0 | purged nightly by `JOB_PURGE_AUDIT_LOG` |
| FIXTURE_META | 1 | fixture bookkeeping — proposed OUT of scope |

Stored logic in scope for conversion: `PKG_OW_UTIL`, `PKG_PLANS`, `PKG_RATING`, `PKG_INVOICING`,
`PKG_DUNNING`; triggers `TRG_CUSTOMER_MASTER_HIST`, `TRG_CUSTOMER_MASTER_SEQ`,
`TRG_ENTITY_ATTR_VALUE_SEQ`, `TRG_SUBSCRIPTIONS_HIST`, `TRG_SUB_NO_UNCANCEL`,
`TRG_USAGE_EVENTS_CHECK`, `TRG_BILLING_AUDIT_LOG_ID`; jobs `JOB_NIGHTLY_DUNNING`,
`JOB_PURGE_AUDIT_LOG`; 5 sequences.

## Interaction contract (pinned once, never renegotiated)

- Stops A/B/C are routed to this Devin session's chat as blocking messages; the user's reply is the approval of record.
- Questions are batched: one message per stop, every row carrying a recommended default.
- Approver: the requesting user (session owner). Production repoint is customer-held and never executed by Devin.
- No notification webhook configured — wave-close and halt notices land in this chat only. PROPOSED.

## Credentials (names only — never values)

| Tier | Principal | Secret / env name |
|---|---|---|
| Assessment + extract (source, read-only discipline) | Oracle `OW_BILLING` | `OW_ORACLE_BILLING_DSN` (session env) |
| Migration (target writes) | Atlas cluster user (`readWriteAnyDatabase`) | `MONGODB_ATLAS_URI` |
| Atlas control plane | Atlas API key | `MONGODB_ATLAS_PUBLIC_KEY` / `MONGODB_ATLAS_PRIVATE_KEY` / `MONGODB_ATLAS_PROJECT_ID` |
| Cutover repoint | customer-held | not held by Devin — by design |
