# 06 — Access checklist & access model

Probed live on 2026-09-01 from this session's VM. Every row carries evidence.

## Probe results

| # | Path | Result | Evidence |
|---|---|---|---|
| A1 | Oracle read (source census) | **WORKS** | `SELECT COUNT(*)` across all 20 `OW_BILLING` tables + `user_objects`/`user_triggers`/`user_sequences` inventory returned (CUSTOMER_MASTER 25,000; INVOICE_LINE 150,000) |
| A2 | Oracle dedicated **read-only** principal | **BLOCKED** | Only the schema owner `OW_BILLING` (read-write) exists. Devin applies read-only discipline (SELECT only, no DDL/DML on the source), but the credential itself is not least-privilege. See request R1 |
| A3 | Atlas control plane (project/cluster/db-user read) | **WORKS** | `make tp-preflight-atlas`: 8 probes, 0 denied → `.tp-preflight/atlas-capabilities.json` |
| A4 | Atlas network access list (POST/DELETE) | **WORKS** | temporary entry created (HTTP 201) and deleted (HTTP 204); VM IP covered by 5 existing entries |
| A5 | Atlas data-plane **read** | **WORKS** | `listDatabases` → `ow_tp_demo1`, `ow_tp_mongodb_demo`; server 8.0.29 |
| A6 | Atlas data-plane **write** to the migration DB | **WORKS** | insert + count + `drop_collection` on `ow_tp_mongodb_orc1._preflight`; cluster user holds `readWriteAnyDatabase` + `dbAdminAnyDatabase` |
| A7 | Recon harness installed and runnable | **WORKS** | `recon selftest` → PASS, 9 canonicalization rules exercised (`pip install -e "harness[all]"`) |
| A8 | Atlas storage headroom | **CONSTRAINED** | M0 free tier: 512 MB cap, ~197 MB already used by `ow_tp_demo1` (66 MB) + `ow_tp_mongodb_demo` (131 MB). See request R2 |
| A9 | Sample-data approval (real customer data leaving the perimeter) | **N/A** | The estate is a self-contained local fixture; no third-party data is involved |
| A10 | Cutover repoint principal | **NOT HELD (by design)** | Customer-held; Devin never requests or holds it |

## Fired requests

| # | Request | Approver | Exact ask |
|---|---|---|---|
| R1 | Least-privilege source principal | engagement owner | Either accept the read-only *discipline* on `OW_BILLING` for this run (recorded as an explicit deviation), or provision `CREATE USER ow_migration_ro IDENTIFIED BY <secret>; GRANT CREATE SESSION, SELECT ANY TABLE ON SCHEMA OW_BILLING TO ow_migration_ro;` and store the DSN as a secret. Devin will not create this user itself — that is a source-system change |
| R2 | Storage headroom on the migration cluster | engagement owner | Confirm the estate may load into the ~315 MB of remaining M0 headroom (staged per wave, re-checked at each boundary), or upgrade the cluster tier to ≥ M10, or authorise dropping a stale demo database. Devin will not drop an existing namespace |

## Access model (for the security reviewer)

Three principal tiers, strictly separated:

1. **Assessment / extract** — Oracle `OW_BILLING`, referenced only as the env name
   `OW_ORACLE_BILLING_DSN`. Used for `SELECT` and catalog reads exclusively. The always-on
   plugin guardrail forbids any modification of the source system, its schema, or its data,
   including "harmless" fixes. Deviation on least privilege is registered as A2/R1.
2. **Migration (target writes)** — the Atlas cluster user behind `MONGODB_ATLAS_URI`, plus
   the Atlas API key (`MONGODB_ATLAS_PUBLIC_KEY` / `MONGODB_ATLAS_PRIVATE_KEY` /
   `MONGODB_ATLAS_PROJECT_ID`) for control-plane checks. Writes are confined to the
   migration database registered in `01_conventions.md`; no grants, users, or writes are
   created anywhere else, and existing demo databases are read-only for this run.
3. **Cutover repoint** — customer-held, never provisioned to Devin. The production repoint
   is executed by the customer's operator from the STOP C runbook.

Credential handling: secrets are referenced by name in every artifact, log, and PR body;
values are never written to files, commit messages, or PR content. The recon harness reads
credentials from the environment by name (`--source-dsn-secret`, `--target-uri-secret`).

Attributability: every Atlas data-plane action in this run is performed by the single
cluster user above and is visible in the Atlas project activity feed; control-plane calls
are attributable to the named API key; every source query originates from this session's
VM IP, which is registered on the Atlas access list for the duration of the run. Each unit's
work is additionally traceable to one branch, one PR, and one recon `result.json`.
