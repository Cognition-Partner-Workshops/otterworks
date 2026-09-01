# 01 — Target conventions

All rows ACCEPTED at STOP A (2026-09-01) unless marked FACT.

## Atlas naming

| Item | Value | Status |
|---|---|---|
| Project | `otterworks-demos` | FACT |
| Cluster | existing free-tier M0 (no new clusters; no cluster DDL) | FACT |
| Migration database | `ow_tp_mongodb_orc1` | ACCEPTED (STOP A) |
| Collections | `snake_case`, plural: `customers`, `invoices`, `subscriptions`, `usage_events`, `rating_results`, `credit_notes`, `dunning_attempts`, `notifications`, `billing_audit_log`, `plans`, `codes`, `tenants` | ACCEPTED (STOP A) |
| Quarantine | one `<unit>_quarantine` collection per unit; never mixed into the live collection | ACCEPTED (STOP A) |
| Field names | `snake_case`; Oracle column names lower-cased; no column-name abbreviations preserved where the mapping spec renames them | ACCEPTED (STOP A) |
| Untouchable | `ow_tp_mongodb_demo`, `ow_tp_demo1` (existing demo namespaces) are read-only for this run | ACCEPTED (STOP A) |

Storage note (FACT): the M0 tier caps at 512 MB and ~197 MB is already used by the two
existing demo databases. The full Oracle estate at `SCALE=demo` is estimated to fit in the
remaining headroom; the load is staged wave-by-wave and storage is re-checked at each wave
boundary. If headroom runs out, the run halts and escalates rather than dropping an
existing namespace.

## Driver / code conventions

| Item | Value | Status |
|---|---|---|
| Driver language in scope | Python (loaders + harness) | ACCEPTED (STOP A) |
| App-side service language | Java (billing-service) — app repoint is out of scope for this run unless STOP B says otherwise | ACCEPTED (STOP A) |
| Stored-procedure conversion | prefer aggregation pipelines for set-based logic; app-side code for row-at-a-time/transactional logic; Atlas triggers only where the source trigger is a genuine data-integrity invariant | ACCEPTED (STOP A) |
| Sequences | `_id` is a natural business key where one exists (e.g. `customer_id`), else ObjectId; a `counters` collection only where an external consumer needs the numeric sequence | ACCEPTED (STOP A) |
| Loads | idempotent: drop-and-reload of the unit's own collections, or upsert-by-key; retries always start clean | ACCEPTED (STOP A) |

## Branch / PR conventions

| Item | Value |
|---|---|
| Run branch (PR target) | `tp-run/mongodb-20260901T033326Z` |
| Unit branch | `migrate/billing/<wave>-<unit>` |
| PRs per unit | exactly ONE (never a stack) |
| Review budget | 2 rounds per unit PR |
| Gate | `mongo-recon-harness` verdict in `result.json` + the repo's `tp-golden-smoke` CI gate |

## PR-evidence contract

Every unit PR body is exactly three parts, ~2,000 chars max, unverified paths first:

1. **Decisions** — mapping/tolerance decisions applied, and any deviation from the mapping spec.
2. **Code** — what was written/changed, and the load procedure (idempotency statement).
3. **Evidence** — the ~30-line `recon.summary.md` rendered inline; `result.json` and
   `report.md` linked as artifacts, never pasted; recon mode, mapping version and tolerance
   version cited.
