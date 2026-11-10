# UNT-8 — TEAM_MEMBER (depends on PR #2682)

Scope: only `SFX_D1110_AFTER.PC_CONTENT.TEAM_MEMBER` and the new
`SFX_D1110_AFTER.PC_FX_UNT8_TEAM_MEMBER` schema. This change appends one entry
to `parity/mappings/sfx_content.yml`; it does not change existing mappings,
PowerCenter exports, runner, parameters, prior fixtures, or control rows.

## Contract

The authoritative sources are
`etl/informatica/repository/SFX_CONTENT/mappings/m_SFX_TEAM_MEMBER.XML:6-57`
and `wf_SFX_CONTENT_DAILY.XML:1079-1126,1303-1306`.
The feed is UTF-8 pipe-separated, without quotes or header, with fields
TEAM_MEMBER_ID, TEAM_ID, USER_ID, ROLE_CD, JOINED_DT. The session reads
`$PMSourceFileDir/users/TEAM_MEMBER/$$LOAD_DATE.psv`; the unchanged parameter
file supplies LOAD_DATE=20261109. Empty fields are NULL in the runner; the
XML's `*` null character is not implemented by the emulator.

The source ports truncate to 20/20/20/12/10 characters before expressions.
Three TO_BIGINT expressions accept Python-strip whitespace, signed decimal
digit prefixes, optional fractions truncated toward zero, and trailing junk.
No numeric prefix drops the row; NULL propagates. ROLE_CD is trimmed of ASCII
spaces only, uppercased, then truncated to 12 characters. JOINED_DT uses a
full-match YYYY-MM-DD expression (one or two month/day digits allowed), with
calendar validation. Transformation errors drop rows, not `.bad` records.
Writer rejects are NULL keys, any of the three integers outside signed bigint,
and PostgreSQL's unsupported NUL character in the final ROLE_CD. Rejected
updates leave existing values unchanged. The target's other columns are nullable.
Non-key overflow/NUL binding can reject the UPDATE statement even for an absent
key (UPDATE `.bad` row type 1); null/out-of-range keys with valid non-key fields
reach failed fallback INSERT (row type 0). Raw reject comparison preserves that
distinction. Initial CHAR(12) seeds are padded exactly as PostgreSQL stores them.

The session treats rows as Update, enables Update else Insert, and explicitly
disables truncation. There is no delete path. Stop on errors=0 means expression
errors do not fail the session. Writer errors are row-local. Bad rows are written
to `$PMBadFileDir/team_member1.bad`; the runner removes an empty reject file.

The model follows UNT-6's incremental MERGE materialization, not UNT-7's table
replacement. TEAM_MEMBER_ID is the unique merge key; full_refresh=false prevents
replacement through full refresh. Matched candidates update; unmatched insert;
unmentioned rows survive. The unchanged second run must preserve row values and
the target object. Initial production creation is permitted only after absent-target
preflight. Fixture targets are pre-created and seeded before either merge.

PC_SRC.TEAM_MEMBER has exactly the five staging columns and no ordinal. Ordered
last-successful-row-wins cannot be recovered from it. Duplicate accepted keys
therefore trigger a division-by-zero guard in the source query before MERGE can
apply changes. The separate dup_key fixture is explicitly **NOT PARITY**: the
oracle applies SECOND while dbt must fail atomically and preserve the initial table.

## Unicode and whitespace

Python's `str.strip()` covers 29 code points (including U+001C–U+001F, U+0085,
NBSP and Unicode separator spaces), not merely ASCII or an assumed Snowflake
POSIX whitespace class. The generated `unt8_python_unicode.sql` enumerates that
set, normalizes all Python Unicode decimal digits before prefix/date parsing,
and applies Python's complete per-character uppercase mapping, including
expansions such as ß→SS. ROLE trim remains ASCII-space-only.

`parity/fixtures/unt8/generate_unicode.py` reproducibly generates that macro
using Python's Unicode database (14.0.0 in this environment). No live UDF,
package installation in Snowflake, or unrelated object is required. The
collector records hashes of both generator and generated output, all dbt/parity/
Snowflake implementation files, and Informatica inputs for every execution.
Offline SQL parsing cannot certify Snowflake higher-order TRANSFORM/lambda,
JSON Unicode decoding, regex or date execution. Those remain live-parity gates,
not claims of runtime certification. A different Python Unicode database requires
explicit regeneration and review, not silently substituting Snowflake UPPER.

## Oracle and fixtures

The canonical task remains disabled. `startworkflow` skips it, but the direct
`startsession` path does not check task-instance enabled status:

```text
python -m runner startsession -f SFX_CONTENT -w wf_SFX_CONTENT_DAILY s_m_SFX_TEAM_MEMBER
```

`evidence_unt8 oracle` creates a uniquely named unt8_* PostgreSQL database on an
isolated local PostgreSQL endpoint, bootstraps it, stages only TEAM_MEMBER input,
seeds its initial target, and runs that exact session twice without resetting
the target or input. It captures typed targets, session logs/results, writer
statistics and raw `.bad` rows, compares against the runner-derived route
contract, proves replay equality, and drops only that uniquely named database.

The seeded fixture exercises updates/inserts/survival, nulls, overflow in all
three numeric fields, malformed numbers/dates, numeric suffixes/fractions/signs,
input truncation, ASCII/non-ASCII whitespace/digits, and é/ß/CJK role values.
Accepted keys are unique. A rejected update follows the valid update of 101;
999 must survive without input. The negative duplicate fixture has the same
typed initial rows in oracle and Snowflake.

Example local-only setup (no shared database reuse):

```bash
docker run -d --name sfx-unt8-postgres -e POSTGRES_HOST_AUTH_METHOD=trust \
  -p 127.0.0.1:55488:5432 postgres:16
cd warehouse
.venv/bin/python -m parity.evidence_unt8 oracle --subject production
.venv/bin/python -m parity.evidence_unt8 oracle --subject seeded
.venv/bin/python -m parity.evidence_unt8 oracle --subject dup_key
.venv/bin/python -m pytest parity/tests -q
```

Every collector entry point refuses a dirty git tree. Commit implementation
before collecting evidence; evidence outputs are ignored under parity/out/evidence/unt8.
Fresh captures never overwrite existing evidence. Archive an earlier capture
before deliberately collecting a new one. UNT8_PG_PORT can select another
isolated loopback PostgreSQL endpoint; default is 55488.

Offline parse twice, with inert profile values and telemetry disabled:

```bash
SNOWFLAKE_ACCOUNT=offline.invalid SNOWFLAKE_USER=offline SNOWFLAKE_ROLE=offline \
SNOWFLAKE_DATABASE=SFX_D1110_AFTER DBT_ENV_SECRET_SNOWFLAKE_PRIVATE_KEY=offline-placeholder \
DBT_SEND_ANONYMOUS_USAGE_STATS=false SFX_QUERY_TAG='{"run":"sfx-d1110","mapping":"m_SFX_TEAM_MEMBER"}' \
.venv/bin/dbt parse --project-dir dbt --profiles-dir dbt --no-partial-parse
# Repeat with SFX_UNT8_TEAM_FIXTURE=1; unset it for the first parse.
```

## Live commands (NOT run during offline implementation)

After explicit approval and provisioned credentials, from warehouse:

```bash
.venv/bin/python -m parity.evidence_unt8 preflight
.venv/bin/python -m parity.evidence_unt8 fixture-load
# For each subject: production, seeded, dup_key, in that order:
.venv/bin/python -m parity.evidence_unt8 run --subject production --run 1
.venv/bin/python -m parity.evidence_unt8 run --subject production --run 2
.venv/bin/python -m parity.evidence_unt8 compare --subject production
.venv/bin/python -m parity.evidence_unt8 postflight
```

Each build launches exactly
`[python, warehouse/snowflake/run_dbt.py, build, --select, <single model>,
--step, <subject/run step>, --mapping, m_SFX_TEAM_MEMBER]`.
Selections are pc_content__team_member, pc_content__unt8_fixture_seeded,
pc_content__unt8_fixture_dup_key. No full-refresh, global build/setup, reset,
truncate, mark or control write is run. Fixture models require
SFX_UNT8_TEAM_FIXTURE=1 and write only to PC_FX_UNT8_TEAM_MEMBER.
Reject compilation selects only unt8_team_member_rejects with unt8_subject.

Preflight requires the target and fixture schema absent, checks full typed
frozen input against PC_SRC.TEAM_MEMBER, and records PC_BEFORE existence and
contents read-only. Fixture creation is restricted to the new schema, with
typed input/seed readbacks. Builds check unchanged input/control/protected
snapshots first. Compare uses typed bidirectional multisets, key multiplicities,
classification counts and typed/raw writer rejects. Duplicate preservation is
verified separately and must not be presented as target-value parity.

Controls: all 20 rows must remain byte-identical, with SHA256. Required protected
targets are PC_CONTENT.{STG_APP_USER,APP_USER,STG_DOCUMENT,DOCUMENT,DOC_SHARE,
LOGIN_EVENT,ROLE_GRANT} (the five act-3 content tables plus UNT-6/7), and
PC_AUDIT.{STG_AUDIT_EVENT,AUDIT_EVENT,AUDIT_EVENT_ARCHIVE,AUDIT_DAILY_SUMMARY,
SECURITY_ALERT}. LOGIN_EVENT must have 412 rows and ROLE_GRANT 149.
The collector also snapshots every existing PC_CONTENT/PC_AUDIT/PC_BILLING
table and every prior PC_FX_* or *FIXTURE* schema, excluding only its own new
schema and production target. It records the exact discovered relation set
alongside the full sorted typed snapshots and SHA256; absent required targets
fail the gate. Prior fixture objects are read only, including UNT-7.

SHOW/INFORMATION_SCHEMA CREATED and available ACCOUNT_USAGE TABLE_ID are
captured before/after builds and across the run boundary. Any observed identity
change fails. ACCOUNT_USAGE can lag: absent numeric TABLE_ID is explicitly
reported as uncertified, never invented. Successful intervening non-read target
statements fail the gate; failed statements are retained separately. Postflight
checks successful tagged write scope and refuses unparsed/out-of-scope writes.
History is current-user only, not an account-wide or other-user writer audit.

No live Snowflake parity or object-stability claim is made by this offline step.
Any PR for this branch must state its dependency on #2682.
