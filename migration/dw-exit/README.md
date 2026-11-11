# Act 1: Assess

Offline only; no connections, credentials, or changes to the source estate.
Run from the repository root with Python 3, PyYAML and pytest installed:

```sh
python migration/dw-exit/tools/check.py # fails before generation
python migration/dw-exit/tools/assess.py
python migration/dw-exit/tools/check.py
python -m pytest migration/dw-exit/tests -q
```

The generator overwrites only the assessment outputs in this directory. Inputs
are the checked-out estate, registry, DBQL CSVs, licence YAML and planted risk
registers. Generated IDs use stable SHA-256 prefixes, lists and edges are sorted,
and no wall-clock values are used. See `plan.md` for interpretation and limits.

## Live assessment control plane

Install `requirements.txt` in a virtual environment outside the repository.
Bind SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_ROLE, SNOWFLAKE_DATABASE,
SNOWFLAKE_PRIVATE_KEY and SNOWFLAKE_RUN_TOKEN from the credential store per
invocation. The PEM key is parsed only in memory, never written or printed.
Only SFX_D1110_AFTER is accepted; the warehouse is fixed to SFX_D1110_OPS_WH.
Every connection starts with the compact assess/preflight QUERY_TAG, then sets
the phase tag before executing work. Every command suspends the warehouse in
its cleanup path, including a failed verification.

```sh
python migration/dw-exit/tools/control.py verify # expected missing-schema failure before first load
python migration/dw-exit/tools/control.py load
python migration/dw-exit/tools/control.py verify
python migration/dw-exit/tools/control.py report
python migration/dw-exit/tools/control.py history
```

`load` creates six tables and four views with the run/expiry comment. DML replaces
all input datasets in one transaction, preserving table definitions. It resets
statuses: do not rerun after later-act progress without intending that reset.
MANIFEST has mutable STATUS, UPDATED_AT and UPDATED_BY_ACT fields. Later acts
must explicitly update the latter two alongside status (no automatic trigger).
The licence view counts objects still present until status becomes done/retired;
planning a retirement alone does not reduce the counter. Spark is measured zero.

The hidden-consumer SQL anti-joins SELECT principals against repository scan
hits, excluding identities also observed as ETL/UTILITY/BATCH. Thus batch accounts
missing from repository text do not become hidden end-user consumers. The dead
view independently anti-joins TablesV against all DBQL usage in the 90-day window.
`query_history_assess.sql` is the exact proof query over the last day, up to 10,000
queries, grouped by phase and execution status. No renders are committed.

# Act 2: Billing — prove before promoting

This run migrates the billing estate into `SFX_D1110_AFTER.BILLING`. It does not
depend on the target scaffold or alter another subject area's control rows.
`TD_BASELINE` is a value-exact capture of the post-daily-chain emulator, not
expected values recomputed in Snowflake. Capture uses CREATE, never REPLACE,
and checks the uploaded rows against the source as a duplicate-preserving bag.
The baseline must not be recaptured between red and green.

## Reproduce

Use the existing org key-pair credentials in the environment. Never put a key
in a command, repository file or log. All Snowflake sessions use a JSON query
tag for run `sfx-d1110`, act `prove`; only `SFX_D1110_*` warehouses are used.
All explicitly created Snowflake objects carry
`run_token=sfx-d1110 expires=2026-11-24` as their COMMENT.

```sh
make sfx-teradata-up NS=sfx-d1110-before ROWS_PER_TABLE=20000
make sfx-teradata-run NS=sfx-d1110-before BUSINESS_DATE=20261109
make warehouse/.venv/.billing-requirements
# Install SnowConvert AI per warehouse/teradata/README.md first.
warehouse/.venv/bin/python migration/dw-exit/billing/snowconvert.py
# Fresh TD_BASELINE only. Refuses to overwrite existing capture tables.
make sfx-billing-capture NS=sfx-d1110-before BUSINESS_DATE=20261109

# Expected failure. Preserve this file before proceeding.
make sfx-billing-prove CANDIDATE=initial BUSINESS_DATE=20261109
# Same BEFORE, same tests, corrected conversion.
make sfx-billing-prove CANDIDATE=fixed BUSINESS_DATE=20261109

# Supplemental probes are a separate manifest, never counted as billing.
PYTHONPATH=migration/dw-exit warehouse/.venv/bin/python -m parity.ladder \
  --manifest migration/dw-exit/parity/supplemental.json \
  --step supplemental_red --output migration/dw-exit/.runs/supplemental-initial.json
warehouse/.venv/bin/python migration/dw-exit/billing/probes.py
PYTHONPATH=migration/dw-exit warehouse/.venv/bin/python -m parity.ladder \
  --manifest migration/dw-exit/parity/supplemental.json \
  --step supplemental_green --output migration/dw-exit/.runs/supplemental-fixed.json
make sfx-billing-promote
make sfx-billing-test
```

The SnowConvert wrapper encrypts the runtime `.p8` with a random in-memory
passphrase, passed to the child through its environment. The existing connection
writer keeps the key and TOML outside the repo with mode 600. SnowConvert's
ignored conversion/report directories preserve its original output; `billing/initial`
contains the minimally executable red candidate after syntax-only repairs, not a
claim that raw converter output compiles. `billing/` contains the corrected SQL.
Never run capture or conversion unattended in CI; CI runs offline regressions only.

## Conversion map

| Source | Target |
|---|---|
| Billing DDL, staging tables | `billing/00_tables.sql` |
| Load BTEQ 01–05 | `billing/10_load.sql` |
| Incoming storage billing from documents BTEQ 10 | `billing/15_storage.sql`, from captured `STORAGE_USAGE_INPUT` |
| Subscription and currency report BTEQ 10–11, macros | Snowflake SQL table-returning procedures in `billing/20_routines.sql`; output snapshots |
| Monthly invoice BTEQ 12, stored procedure | `P_MONTHLY_INVOICE`, Snowflake Scripting with explicit transaction and SQLROWCOUNT |
| Period-close BTEQ 13, exports | `billing/40_close.sql`, `billing/reports.py` |
| Stacked views 10/20 | `billing/30_views.sql` |

The input loads and monthly calculation remain separate. Staging is loaded from
the captured raw input, not copied from final expected billing tables. The
monthly procedure calculates invoice lines, taxes, currency control totals and
balanced journal entries from those inputs. BTEQ export directives become
queryable result tables. `promote.py` rechecks every billing relation before
upserting billing-only rows in `SFX_D1110_AFTER.MIGRATION_CONTROL.OBJECTS`.
The shared assessment schema is reused; `MANIFEST` and other subjects' rows
are not modified. Staging inputs get a separate fresh parity check before
their object rows are verified. FastLoad jobs are outside this act and are
not marked verified. Missing control schema/table is bootstrapped with the
required run-token COMMENT. No PUBLIC schema or parallel register is used.
The red candidate intentionally omits the incoming storage boundary; green
includes its conversion. No final billing output is copied to make green pass.

## Parity contract

`parity/billing.json` lists only billing relations. The reusable ladder accepts
fully qualified relations and explicit keys. It runs every stage even if the
previous stage failed: counts; per-column null/min/max/distinct profiles;
SHA-256 hashes grouped by key **and multiplicity**; then exact value comparisons
for deterministic mismatch keys (or deterministic matching keys on green).
Hash differences count unmatched row occurrences on both sides; they are not
distinct business-key counts. Decimal serialization ignores declared scale, not
numeric value. Text is never trimmed or case-folded by the parity tool.
Profiles and full hashes cover all rows; value diffs are a sample, not an
exhaustive display. JSON output includes executed SQL and query IDs.

`SFX_LIVE_PARITY=1` enables the manifest-driven pytest. Without credentials, the
live cases are explicitly skipped; offline tests still prove fail-closed behavior,
padding sensitivity, SQL identifier validation and duplicate multiplicity.

Render side-by-side evidence with `python -m parity.report --red <billing-red.json>
--green <billing-fixed.json> --supplemental-red <probe-red.json>
--supplemental-green <probe-green.json> --output <report.md>`, with
`PYTHONPATH=migration/dw-exit` and the warehouse virtualenv's Python.

## Semantic ownership

Billing exercises CHAR padding, NOT CASESPECIFIC joins/grouping, FORMAT casts
and Teradata integer-date arithmetic. Conversion fixes belong in load/routine/
view SQL, never the oracle or parity tests. The date FORMAT must be explicit and
must survive a session using a different display format.

The source billing tables are MULTISET. SET suppression, truncation and QUALIFY
ties therefore live in **supplemental probes** under `BILLING_PROBES`, with a
separate unchanged baseline and manifest. The fixture explicitly chooses the
highest version ID when timestamps tie; it does not pretend tied ROW_NUMBER is
deterministic without that contract. MULTISET duplicates stay intact.

Finance decision: preserve legacy SET exact-duplicate suppression and expose
suppressed rows for review. `BILLING_PROBES.SET_ROWS` still uses full-row
DISTINCT, never business-key deduplication. The supplemental view
`SFX_D1110_AFTER.BILLING_PROBES.SET_DUPLICATE_QUARANTINE` groups the preserved
raw FEED by every payload column (ID and VALUE) and includes only repeated
rows. INPUT_COUNT counts all copies, RETAINED_COUNT is one, and
SUPPRESSED_COUNT is INPUT_COUNT minus one. Null payloads group together;
different values sharing a key remain separate. The view does not feed totals
or change any billing MULTISET rows. It reflects the retained FEED, not an
append-only history across future feed replacements.

Finance can review the exact payload and counts with:

```sql
SELECT ID, VALUE, INPUT_COUNT, RETAINED_COUNT, SUPPRESSED_COUNT
FROM SFX_D1110_AFTER.BILLING_PROBES.SET_DUPLICATE_QUARANTINE
ORDER BY ID, VALUE;
```

Run `query_history.sql` to retrieve the tagged audit trail, including failed
conversion attempts, both parity runs, promotion and control-table verification.
