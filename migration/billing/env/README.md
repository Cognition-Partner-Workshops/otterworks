# Billing migration worker environment

Environment for the Oracle `OW_BILLING` -> MongoDB Atlas migration workers on the
`tp-run/mongodb-*` branches. Standard tools only: mongosh, Atlas CLI, MongoDB
Database Tools, python-oracledb (thin mode) and pymongo, `uv` for the repo's
validators, plus the offline fallback (`mongo:7` container and the repo's
`make oracle-billing-up` Oracle Free fixture).

## Connectivity policy (d-connectivity-policy: auto, decided)

| `OW_BILLING_ENV_MODE` | Atlas                                    | Oracle                                              |
|-----------------------|------------------------------------------|-----------------------------------------------------|
| `online`              | `MONGODB_ATLAS_URI` must ping            | `OW_TP_ORACLE_RO_DSN` must answer `SELECT 1`        |
| `auto` (default)      | live if set and reachable, else `mongo:7` | live if set and reachable, else the Oracle fixture  |

Secrets are referenced by name only (`MONGODB_ATLAS_URI`, `OW_TP_ORACLE_RO_DSN`;
the latter is JSON `{user,password,dsn}` or a plain connect string) and never
printed. `OW_BILLING` is read-only. A result marked `fallback` came from a local
fixture and is never merge evidence.

## Post-setup checks

```sh
migration/billing/env/postsetup-check.sh          # setup + checks (auto)
migration/billing/env/postsetup-check.sh check    # checks only
OW_BILLING_ENV_MODE=online migration/billing/env/postsetup-check.sh check
```

`setup` ensures the `~/.venvs/ow-billing` venv (python-oracledb 2.5.1 thin,
pymongo 4.10.1, via `uv`) and the `mongo:7` image. `check` runs, in order:

1. `mongosh` ping against `MONGODB_ATLAS_URI` (fallback: `ow-billing-mongo`
   container on `127.0.0.1:27117`);
2. python-oracledb thin `SELECT 1 FROM dual` as the read-only principal
   (fallback: the fixture at `localhost:52521/FREEPDB1`, which must already be
   up via `make oracle-billing-up`; note the fixture login is the schema owner);
3. `make tp-validate-schemas`.

Each run appends a redacted log to `reports/` (git-ignored) and exits non-zero
if any check failed.

## Blueprint proposal

`blueprint-proposal.diff` is the proposed (not applied) change to the
`Cognition-Partner-Workshops/otterworks` repo blueprint: it adds the worker venv,
the `mongo:7` pre-pull, the auto-mode post-setup checks to `initialize`, and a
`billing-migration-workers` knowledge entry. A human applies it in Devin's
environment settings; this directory does not change how the snapshot is built.
