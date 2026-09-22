# 06_access_checklist — `recon_mode: offline`

| Item | State | Evidence / note |
|---|---|---|
| Source read-only principal (assessment tier) | OPEN — not probed | No source connectivity in this run. Cannot confirm `CREATE SESSION` + `SELECT` on in-scope tables + `SELECT_CATALOG_ROLE` only. Must be confirmed by the customer before any LIVE/SNAPSHOT recon. |
| Source egress / network path from the recon runner | OPEN — not probed | Offline by design. |
| Source query cap (`source_concurrency = 1`) honoured by the customer's DBA | OPEN — not probed | Recorded as a contract value; enforcement unverified. |
| Migration cluster (Atlas) read | NOT APPLICABLE | No Atlas in this run. `MONGODB_ATLAS_URI` is present in the environment and deliberately unset for every command. |
| Migration cluster write | NOT APPLICABLE | as above |
| Cutover principal | NOT APPLICABLE / customer-held | Devin never holds it (rule 5). |
| MCP servers | NONE | plugin ships none; `offline_guard.py` checks for `.mcp.json`. |
| Local target `MONGO_LOCAL_URI` | WORKS (guard) | see proof below; a live write is exercised in playbook 3 |
| Local Oracle Free fixture image | AVAILABLE | `container-registry.oracle.com/database/free:latest` and `mongo:7` are in the local Docker cache (`docker images`). |

## Offline guard proof (2026-09-22)

Command run in `/home/ubuntu/repos/otterworks`:

```
env -u MONGODB_ATLAS_URI MONGO_LOCAL_URI=mongodb://localhost:27017 \
  python3 /home/ubuntu/repos/mongo-migration-plugin/skills/schema-modeling/offline_guard.py --repo .
```
Result: see `08_connectivity.json` → `offline_guard.pass_output`.

Negative proof (guard must refuse when the Atlas URI is present):

```
MONGO_LOCAL_URI=mongodb://localhost:27017 \
  python3 /home/ubuntu/repos/mongo-migration-plugin/skills/schema-modeling/offline_guard.py --repo .
```
Result: see `08_connectivity.json` → `offline_guard.refuse_output` (exit 1).

## Access model (for the security reviewer)

| Tier | Purpose | Secret name (env var) | This run |
|---|---|---|---|
| 1 Assessment read-only | census, recon reads on the source | (customer to name; canonical JSON `{"user","password","dsn"}`) | not provisioned; DDL scripts only |
| 2 Migration write | writes to the migration database only | `MONGODB_ATLAS_URI` | present but unused; replaced by `MONGO_LOCAL_URI` (localhost) |
| 3 Cutover | production repoint | customer-held | never requested |

Local fixture only: `ORACLE_FIXTURE_PWD` (Oracle Free container password). Audit: every write this run makes goes to `mongodb://localhost:27017/ow_billing_offline`; git history of `tp-run/mongodb-20260922T142645Z` is the activity log.
