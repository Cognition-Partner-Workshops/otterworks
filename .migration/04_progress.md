# Migration progress ledger

Run: `tp-run/mongodb-20260901T033738Z`

## Permitted target registrations

| Owner | Database / collection | Purpose | Status |
|---|---|---|---|
| Orchestrator setup | `ow_tp_preflight.*` | Temporary capability probes; every temporary collection must be deleted by the probe | VERIFIED CLEAN — 2026-09-01 |
| Unassigned | `ow_tp_mongodb_20260901t033738z.*` | Migration units must register exact collection targets here before any load | RESERVED |

## Units

| Wave / unit | Status | Parity | Quarantine rate | Unverified paths | Cost | PR |
|---|---|---|---|---|---|---|
| Pending approved census | SETUP | NOT RUN | N/A | Entire estate pending STOP A and census | 0 ACU / 0 source query-hours | — |

No migration unit has been launched and no target collection has been loaded.

Setup probe evidence: `evidence/atlas-capabilities.json` (8/8 verified, 0 denied).
