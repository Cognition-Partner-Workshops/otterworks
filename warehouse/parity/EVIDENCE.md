# migrations-page evidence (UNT-2)

The local commands never connect to Snowflake. Live commands use the existing JWT
connector with an in-memory key and never write control rows.
HARNESS self-tests and two fresh oracle executions are **not mapping parity**.
The canonical XML and runner remain unchanged. `scope()` expands the owned config
with folder/workflow/session/targets, reject filenames, parameters, disabled-task
reasons and sequence initial values from canonical exports; the manifest records
that full resolved configuration.

## Reproduce local baseline

From repository root:

```sh
make warehouse/.venv/.sfx-installed
make sfx-informatica-up NS=sfx-d1110-before
cd warehouse
.venv/bin/python -m pytest parity/tests -q
.venv/bin/python -m parity.evidence manifest
.venv/bin/python -m parity.evidence oracle
```

The namespace-scoped compose target starts only local PostgreSQL and installs the
runner environment. Each capture creates and drops its own UUID database; logs
and state survive under `parity/out/evidence/unt2_oracle_*`. No shared PC_SRC or
PC_BEFORE uploads occur. Audit runs through `startworkflow`; the three owned
content sessions run through `startsession`, not `wf_SFX_CONTENT_DAILY`, because
that canonical workflow would execute five unowned mappings. Archive runs
standalone without enabling its canonical workflow task.

`manifest.json` freezes landing hashes/counts, resolved session parameters,
bootstrap hash, initial target/source tables and sequence defaults/storage.
Oracle verifies that manifest before each execution. Retain that file unchanged.
Per mapping, `oracle1/` and `oracle2/` contain target typed JSON and typed-cell CSV,
raw reject lines as JSON and CSV, and session results. Reject lines preserve the
runner's own lossy null/empty encoding rather than inventing values. The original
`.bad` files and session/workflow logs remain in each run directory.
`oracle_determinism.json` includes complete multiset differences and reject counts.

## Successor mapping replay protocol

Coordinate exclusive access to the exact owned target. Confirm unchanged source
hashes/parameters against the manifest and record initial target/sequence state.
Execute the scoped dbt node once, capture **all** target rows and rejects, then
execute that same node again without truncation, full-refresh, restore or source
changes. Capture all rows/rejects again and retain execution logs/query IDs.
These execution requirements cannot be proven by snapshot comparison alone.

Serialize each target snapshot as `{columns, types, rows}` using `snapshot()`'s
typed-cell layout. Preserve nulls, string whitespace, numeric precision/scale and
timestamp timezone/precision. Cross-engine type translation must be explicitly
reviewed and representation-only; this strict baseline grants no implicit
numeric-scale or timezone exclusions. Compare rejects separately with the same
complete multiset comparator after lossless typed export.

```sh
.venv/bin/python -m parity.evidence compare --mapping m_SFX_LOGIN_EVENT \
  --oracle parity/out/evidence/m_SFX_LOGIN_EVENT/oracle1/target.json --run1 /path/run1.json
.venv/bin/python -m parity.evidence replay --mapping m_SFX_LOGIN_EVENT \
  --oracle parity/out/evidence/m_SFX_LOGIN_EVENT/oracle1/target.json \
  --run1 /path/run1.json --run2 /path/run2.json
```

Outputs go under `out/evidence/<mapping>/compare.json` or `replay.json`; failures
exit nonzero. Replay requires both runs to equal oracle and each other, zero
duplicate business keys and stable generated IDs per key. Summary keys use the
actual aggregator grouping ports. Archive uses the retained event tuple because
the target lacks source EVENT_ID; tuple collisions deliberately fail the gate.
An empty archive baseline does not prove nonempty sequence allocation parity.

## Content workflow equivalence and live upload smoke

```sh
.venv/bin/python -m parity.evidence content-check
# Bind existing Snowflake secret references at execution time, never via files.
.venv/bin/python -m parity.evidence live-preflight
.venv/bin/python -m parity.evidence live
```

`content-check` runs the canonical full content workflow plus standalone
TEAM_MEMBER in a fresh throwaway local database and compares only the three
owned target multisets against the frozen standalone-session oracle. Nothing
from that extra workflow is uploaded. `content_workflow_equivalence.json` retains
results and local log paths. Routing notes in the manifest and per-asset files
explain eight filtered TIMEOUT logins and three rejected INFO security alerts.

Live preflight asserts 20 distinct control keys with exactly 8/12 owners, then
reads the five relevant PC_SRC landing tables and compares every row against
frozen inputs using shared-loader STG types. Internal audit dependencies remain
the frozen oracle tables, not additional landing inputs. PC_SRC timestamps use
bootstrap precision (0); baseline upload follows `commands.before` TIMESTAMP(9).
DESCRIBE verifies warehouse types before mapping exact representations into the
local snapshot metadata. Integer NUMBER(38,0) and typed PostgreSQL integers share
an exact integer representation; strings, decimal scales and timezone are not
trimmed or discarded. All query SQL, QIDs and results are retained under
`out/evidence/live`, with `transcript.txt` for human review.

`live` lists existing PC_BEFORE tables, replaces only eight owned targets,
uploads nonempty reject outputs into owned `__REJECTS` tables and checks full
readback fidelity. It uses only PC_BEFORE.CAPTURE_STAGE and the owned baselines.
It creates PC_EVIDENCE_SMOKE (fails if already present), tests identical copies
and separate duplicate/value/ID mutations, and drops its scratch schema in a
finally block. This is **HARNESS SMOKE — not mapping parity**; SECURITY_ALERT's
ID mutation tests identity stability, not a claim that ALERT_ID is generated.
Pre/post control snapshots must remain byte-identical, including on failures.

No metrics or success marking is performed. UNT-10 owns acceptance/marking with
owner `migrations-page`. Live mapping parity, DAG execution, CI/SonarQube and
final branch delivery are not certified by this harness smoke.
