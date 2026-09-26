# MongoDB migration loaders — ow_billing_migration (local target)

Loaders for the offline OW_BILLING -> MongoDB migration units, one file per
batch. Each loader:

- reads the same-engine synthetic Oracle fixture (schema `OW_BILLING`,
  PDB `FREEPDB1`) via the DSN named by `--source-dsn-secret`;
- writes only its batch's collections in database `ow_billing_migration`
  on `MONGO_LOCAL_URI` (local `ow-mongo` container) and refuses any
  `--target-db` not listed in `.migration/allowed_targets.json`;
- drops and recreates only its own collections at the start of every run
  (idempotent: a re-run yields identical documents);
- maps fields per `.migration/03_mapping_spec.json` and quarantines rows
  that fail canonicalization rather than coercing them silently.

| Loader | Unit | Source | Target collection |
| --- | --- | --- | --- |
| `load_codes.py` | u-00-codes | `OW_BILLING.CODES` | `ow_billing_migration.codes` |

**Evidence class: `target_class=local` — NOT merge evidence.** Fixture-mode
recon against the local container is a rehearsal of the load path only
(AGENTS.md rules 8, 11); it never authorizes a merge. There is no live or
snapshot run in this engagement (`source_access=ddl_only`): the fixture copy
is the only source that exists.
