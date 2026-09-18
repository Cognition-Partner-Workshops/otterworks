# 06_access_checklist.md

| Item | State | Evidence |
|---|---|---|
| Source read (production Oracle) | NOT APPLICABLE | recon_mode offline: no production connectivity by design. Local Oracle fixture container is read via `ORACLE_BILLING_DSN` (read-only session) for fixture recon only. |
| Migration database read/write (Atlas) | NOT APPLICABLE | recon_mode offline: the only target is `MONGO_LOCAL_URI` on this machine. |
| Offline guard | WORKS | `offline guard: OK (no MCP config, no Atlas URI, MONGO_LOCAL_URI is local)` |
| Recon harness | WORKS | `recon selftest PASS: 9 canonicalization rules exercised` |
| Cutover principal | NOT HELD | customer-held; Devin never requests it. |

## Access model (for the security reviewer)

| Tier | Purpose | Secret name (env var on this machine) |
|---|---|---|
| 1 assessment read-only | census, discovery, recon reads | `ORACLE_BILLING_DSN` (fixture only here; the customer's read-only principal in a real run) |
| 2 migration write | writes to `ow_billing` only | `MONGO_LOCAL_URI` (Atlas `MONGODB_ATLAS_URI` in a real run) |
| 3 cutover | production repoint | customer-held, never in a Devin session |

Audit: every plugin command in this run is in the screen recording and in `~/e2e/logs/`.
