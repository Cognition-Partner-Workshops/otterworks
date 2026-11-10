# Additive migration harness

Run `make sfx-pc-setup`, `make sfx-pc-licence`, and
`make sfx-pc-test` from the repository root using the shared warehouse venv.
Live commands require injected Snowflake credentials and enforce SFX_D1110_AFTER.
Setup loads only the 20261109 files referenced by workflow File Readers (no
headers), using staging column types from the runner fixture bootstrap, plus
its GL_ACCOUNT reference seed. LANDING_DIR or `python -m parity setup
--landing-dir PATH` overrides the fixture root. Run the module from warehouse/.
Setup truncates/reloads only PC_SRC tables; it does not execute mappings.

Workers own `mappings/sfx_billing.yml`, `sfx_content.yml`, `sfx_audit.yml`.
The YAML is a dictionary keyed by exact mapping name, with optional fields:
`key_columns` (list), `exclude_columns` (column-to-explicit-reason dictionary),
`dbt_model`, `after_table`, `before_table`, `session`, `workflow`, `patterns` (list).
Unknown mappings/fields fail validation. Exclusions are printed during setup.
Default before relations are PC_BEFORE.<target>; default after relations are
PC_<area>.<target>. STG targets have no primary key in XML or bootstrap, so their
default key list is empty: workers must explicitly choose an appropriate key.

MIGRATION_CONTROL is seeded with a guarded MERGE: existing rows are never
changed except to fill NULL OWNER_EFFORT. Ownership assignments live in
harness.py (owner_effort / ACT3_CONTENT); 12 belong to act3-workflow and eight
to migrations-page. require_owner is the reusable write-path ownership guard.
The counter counts AMBER as still requiring PowerCenter and reports per owner.

`PC_CONTROL_SCHEMA` (or `--control-schema`) selects the control schema, default
PUBLIC. Setup loads PC_SRC first, then seeds control. Use `setup --skip-control`
while waiting for control-schema access.

From warehouse/, use `python -m parity before|parity|idempotence|mark --mapping
m_SFX_PAYMENT`. `before` requires `make sfx-informatica-up`; it creates a fresh
local fixture database from bootstrap.sql, runs the full folder workflow to
populate staging/lookups, captures the target, then drops that isolated database.
It uses fresh sequence state under gitignored out/. The disabled TEAM_MEMBER
session is run explicitly after its folder workflow. NS defaults to
sfx-d1110-before; TD_PORT overrides the namespace-derived fixture port.

`parity` prints exclusions and compares normalised rows fetched on the parity
warehouse; keys without declared PK fall back to whole-row hash multisets.
This implementation fetches tables in memory; it is intended for fixture-sized
comparisons, not large-scale data volumes. Missing AFTER is a nonzero failure.
`idempotence` requires business keys (provide YAML keys for staging), builds
the selected model twice, and records row counts and excess duplicate-key rows.
`mark` reads gitignored JSON evidence, verifies configuration has not changed,
and guards ownership both before and inside the MERGE update. Default owner is
act3-workflow; --amber supplies a reason, --pr-url supplies provenance.
Idempotence refreshes parity after the second build. Capturing a new
BEFORE or running parity again invalidates the earlier duplicate-count evidence.

## Worker loop and ownership

```sh
make sfx-pc-setup                         # SKIP_CONTROL=1 if awaiting grants
make sfx-informatica-up NS=sfx-d1110-before
make sfx-pc-before MAPPING=m_SFX_PAYMENT
make sfx-pc-dbt MAPPING=m_SFX_PAYMENT      # or FOLDER=billing
make sfx-pc-parity MAPPING=m_SFX_PAYMENT
make sfx-pc-idempotence MAPPING=m_SFX_PAYMENT
make sfx-pc-mark MAPPING=m_SFX_PAYMENT OWNER=act3-workflow PR_URL=https://example.invalid/pr/1
make sfx-pc-licence
make sfx-pc-dag FOLDER=billing            # deploy suspended; RUN_ONCE=1 executes once
```

Workers own only their `warehouse/dbt/models/pc/<billing|content|audit>/`
models, `warehouse/parity/mappings/sfx_<folder>.yml`, and
`warehouse/snowflake/pc_dag/<folder>.yml`. No shared project configuration edits
are needed. The active branch has billing/content workers; audit scaffolding
is available but its control rows belong to migrations-page. Model names
`pc_billing__payment` resolve to exactly `PC_BILLING.PAYMENT` (analogous for
content/audit). Post-hooks set the required comment; a final on-run-end hook
reapplies it after adapter persist_docs and governance hooks, including for
table/view/incremental materializations.

Example `warehouse/parity/mappings/sfx_billing.yml`:

```yaml
m_SFX_PAYMENT:
  key_columns: [PAYMENT_ID]
  exclude_columns:
    METHOD_CD: "Approved normalization difference; tracked separately."
  dbt_model: pc_billing__payment
  after_table: PC_BILLING.PAYMENT
  before_table: PC_BEFORE.PAYMENT
  session: s_m_SFX_PAYMENT
  workflow: wf_SFX_BILLING_DAILY
  patterns: [Source Qualifier, Expression, Filter, Update Strategy]
```

Example `warehouse/snowflake/pc_dag/billing.yml` (SQL bodies are trusted worker
SQL; created objects in those bodies must carry the required run-token comment):

```yaml
root: START
tasks:
  START:
    sql: SELECT 1
  PAYMENT:
    after: [START]
    warehouse: SFX_D1110_TRANSFORM_WH  # optional; no other warehouse accepted
    sql: SELECT COUNT(*) FROM SFX_D1110_AFTER.PC_BILLING.PAYMENT
  FINISH:
    after: [PAYMENT]
    sql: SELECT 1
```

Task keys must be uppercase identifiers. The helper generates
`SFX_D1110_PC_BILLING_<KEY>` in `PC_BILLING`, validates one root and acyclic
dependencies, deploys suspended, and always suspends/verifies after run-once,
including failures. No worker folder DAG YAML is shipped by the harness.
`make sfx-pc-mark ... AMBER="One-sentence reason."` records an explicit exception;
AMBER remains counted as requiring PowerCenter.
