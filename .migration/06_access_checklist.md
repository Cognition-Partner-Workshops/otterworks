# 06 Access checklist

## Environment fix (intake one-liner, run once 2026-09-26 17:05 UTC)
`~/.venvs/recon/bin/python -m pip install -U pip setuptools && ~/.venvs/recon/bin/python -m pip install -e "$(ls -d /opt/.devin/plugins/cache/*mongo-migration-plugin*/*/skills/mongo-recon-harness/harness | head -1)[all,test]" && ~/.venvs/recon/bin/recon selftest`
- Outcome: **WORKS**. pip 22.0.2 -> 26.2.1, setuptools 84.0.0, editable `mongo-recon-harness-0.3.2` installed, pymongo 4.18.2 in the venv. `recon selftest PASS: 9 canonicalization rules exercised`.

## Connectivity probe (policy `online`, 2026-09-26 17:09 UTC)
Command (as the setup playbook writes it, but with the recon venv interpreter — system `python3` has no pymongo and the first run returned `driver_missing` on both sides):
`~/.venvs/recon/bin/python skills/mongo-migration/connectivity_probe.py --policy online --family mongodb-atlas --source-dsn-secret MONGODB_MMP_RT_SOURCE_URI --source-db mmp_rt_src --source-mode live --target-uri-secret MONGODB_MMP_RT_TARGET_N_URI --target-db mmp_rt_billing_n`

| Item | Result | Detail |
|---|---|---|
| Source `mmp_rt_src` via `MONGODB_MMP_RT_SOURCE_URI` | **WORKS** — `source: live (probe_ok)` | principal has `read` on `mmp_rt_src`, no write-capable role (privilege_excess check passed) |
| Target `mmp_rt_billing_n` via `MONGODB_MMP_RT_TARGET_N_URI` | **WORKS** — `target: migration_cluster (probe_ok)` | roles confined to the allowlisted database; insert+delete of one probe document succeeded |
| Offline guard | `offline guard: OK (source=live target=migration_cluster MONGODB_ATLAS_URI checked)` | run as printed by the probe (venv interpreter) |
| Resolved axes | `source_access: live`, `target_access: migration_cluster` | `08_connectivity.json`, `blocked: false` |
| `MONGODB_MMP_RT_TARGET_N_URI` availability | present in a fresh shell (was MISSING at 17:05, present at 17:09 after the customer stored it) | never use `MONGODB_MMP_RT_TARGET_URI` / `MONGODB_ATLAS_URI` |
| `RECON_REDACT_SALT` | NOT SET (not blocking) | live recon output is redacted with an unsalted hash; requested as DEP-004 |
| `mongosync` | NOT INSTALLED (not blocking) | DEP-005; mongodump/mongorestore/mongosh/atlas CLI present |
| Network path | open (Atlas SRV) from this VM; children can reach both sides | intake FACT, confirmed by the probe |

BLOCKED items: none.

## Access model (for the security reviewer)
| Tier | Purpose | Secret name (Devin Secrets, org-scoped; same env-var name in every session) | Scope |
|---|---|---|---|
| 1 Assessment read-only | census, live recon reads | `MONGODB_MMP_RT_SOURCE_URI` | read@`mmp_rt_src` only; probe rejects any write-capable role |
| 2 Migration write | scoped loaders, recon target reads, probe insert/delete | `MONGODB_MMP_RT_TARGET_N_URI` (Atlas user `mmp_rt_target_n`) | readWrite@`mmp_rt_billing_n` only; probe rejects roles outside `allowed_targets.json` |
| 3 Cutover | production repoint | held by the customer app owner; Devin never holds or requests it | — |

Audit: every session (orchestrator and children) connects as one of the two Atlas users above; filter the Atlas project `otterworks-demos` database access log by user `mmp_rt_target_n` (writes) or the source read-only user (reads) and by the run timestamps in `04_progress.md` / wave result files. Devin session URLs are recorded in `00_context.md` and each wave result.

## Guard interference recorded (not an access item)
The co-installed `dbx-migration-factory` plugin's PreToolUse hook parses `.migration/allowed_targets.json` and blocked every tool call in this workspace until the file carried a non-empty `catalogs` list; it then blocked the mongo `connectivity_probe.py` run as an "unresolvable Python statement". `allowed_targets.json` therefore carries `catalogs` (mirror of `databases`) and `guard_mode: "warn"`. The mongo tools read only `databases`; the mongo allowlist is unchanged.
