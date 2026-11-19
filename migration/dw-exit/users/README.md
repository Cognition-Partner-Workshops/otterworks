# Users Teradata-chain conversion

Stages execute `10_load.sql` → `20_routines.sql` → `30_views.sql`.
`00_tables.sql` declares the kept core and staging tables. The macro's returned
resultset is measured as `SFX_USERS.M_TEAM_COUNTS_OUTPUT`; `10_activity_daily`
also declares `SFX_USERS.USER_ACTIVITY_DAILY`. PowerCenter rows now use independent
runner-versus-dbt proofs described below; the BTEQ relation measurement is retained
as supplementary evidence. The six kept Spark jobs have independent landing/lake
proofs below. The four Teradata objects have current-DBQL retirement evidence,
not green conversion parity or owner approval to delete them.

## Retirement evidence

The board reruns `assess.build(root=current checkout)` and checks current DBQL
over 2026-08-12 through 2026-11-09 inclusive. USER_PREF and V_USER_SETTINGS must
have zero reads and remain absent from usage; STG_USER_PREF and users_user_pref
must remain retired through dead-dependent propagation. Missing/empty evidence,
incomplete window coverage, new usage or a changed manifest declaration returns red.
The board records input SHA-256 hashes and links the manifest, absence/window logic,
propagation logic and three DBQL evidence files.

Successful rows are `retire_verified`, counted separately from green-migrated and
red. Migration status, licence counters and the Snowflake denial are unchanged.
**Keep the independent Spark USER_PREF/PREF_JSON landing feed** for the retained
user_pref_json_flatten job; Teradata DBQL absence does not retire this dependency.
External consumers and deletion/cutover approval are not established by these checks.

Make also generates `board/users-pr.md`: the exact users section of the board README
followed by one compact parity row per users object, with metric numbers linked to
the ladder implementation. It is ready to copy into a PR description.

## Stopped object: APP_USER implicit truncation

The local source chain silently truncates long display names. The BTEQ selects
`DISPLAY_NAME` unchanged (`warehouse/teradata/scripts/users/01_load_users.bteq:6–8`),
but staging declares `VARCHAR(200)` and core declares `VARCHAR(60)`
(`warehouse/teradata/ddl/users/00_tables.sql:7,16`). The emulator executes that
INSERT through `Runner.execute` (`warehouse/teradata/bteq/runner.py:158–169`);
`Runner.translate` inserts a destination-width character cast
(`warehouse/teradata/bteq/runner.py:336–355`). PostgreSQL's explicit cast truncates.

On the sfx1119 local dataset, 100 APP_USER display names differ from staging;
all 100 exactly equal the first 60 characters. For example, user 9000000001 has
78 staging characters and 60 source core characters. The converted SELECT
retains the full display name in DuckDB, whose VARCHAR length is not enforced.
No live Snowflake behavior was measured: preflight remains denied with 002003.

No substring, cast-based truncation, widened destination, or comparison
normalization has been added to hide this discrepancy. APP_USER and `01_load_users`
remain red with measured differences. The two PC APP_USER rows also remain stopped:
their isolated dbt proof on actual PC staging input does not clear this escalation.
The source emulator and target behavior are preserved pending a decision on this
newly discovered side effect; native Teradata behavior has not independently been tested.

## Independent PowerCenter proof

`parity/pc_users.py` captures the five initial target tables, runs the actual
`runner startworkflow -f SFX_CONTENT -mappings <five users mappings>
wf_SFX_CONTENT_DAILY`, captures its targets, then restores the local PostgreSQL
tables transactionally. TEAM_MEMBER requires `runner startsession -f SFX_CONTENT
-w wf_SFX_CONTENT_DAILY s_m_SFX_TEAM_MEMBER`: its workflow task is disabled
(`etl/informatica/repository/SFX_CONTENT/wf_SFX_CONTENT_DAILY.XML:1322`). Its green
result proves the explicitly invoked session, not automatic daily scheduling.

The requested Make wrapper rejected `NS=sfx1119-before` with:
`INFA_NS must be a nonempty namespace containing only letters, digits, and underscores, or a RunConfig-generated before/after namespace`.
RunConfig generates `sfx-1119-before`, whereas the running emulator uses
`sfx1119-before` (port 55224). The direct runner CLI used that existing local
emulator; neither namespace validation nor source behavior was changed.

The shipped `warehouse/dbt/models/pc/content/pc_content__*.sql` models and their
macros are rendered, lowered to DuckDB and executed with their own table/merge
configuration. Each proof starts from captured initial target state. Four models
read exactly the same landing PSVs; APP_USER reads the actual captured PC staging
output, isolating that mapping from the stopped staging conversion. This is not
an end-to-end converted workflow proof. No `TRANSFORM.M_SFX_APP_USER` Snowpark
implementation was found; its manifest assignment is unchanged and its board
row remains red. These are local emulator/dbt proofs, not live PowerCenter or
Snowflake certification. Snowflake still has recorded denial 002003.

The ignored `.runs/pc-users-sessions/` directory holds `capture.duckdb`, runner
stdout, session logs and checksummed capture metadata. The generated board embeds
the input hashes, command, and all ladder measurements. Evidence scope, input
fingerprints and capture/log checksums are validated before reuse. Re-capture
with `--output` in a new directory if inputs change; captures are never overwritten.
Example invocation (DSN supplied from the existing local environment):

```sh
RUN_TOKEN=sfx1119 PYTHONPATH=.:migration/dw-exit warehouse/.venv/bin/python \
  -m parity.pc_users --capture --dsn "$TD_PG_DSN" --namespace sfx1119-before
```

### Stopped: STG_APP_USER source-port truncation

`m_SFX_STG_APP_USER.XML:16,31,49` declares DISPLAY_NAME string precision 60
before expression normalization (`:54–56`), even though the target is VARCHAR(200).
The reached Source Qualifier path is `runner/engine.py:340–361` →
`coerce(:26–34)`, which slices string ports to their precision. The dbt staging
model (`pc_content__stg_app_user.sql:4–6`) trims display, lowercases email and
uppercases status, retaining up to 200 display characters.

Actual capture: 120 rows on each side, 100 display-name differences (ladder
multiset/hash difference 200). All source display names equal landing first-60
characters followed by trim; email/status normalization has zero mismatches.
This disproves case/trim normalization as the cause of the observed differences.
User 9000000001, for example:

```text
PC:  Nadia Norford - Senior Workspace Operations and Records Gove
dbt: Nadia Norford - Senior Workspace Operations and Records Governance Coordinator
```

Both STG mapping/session rows remain red. Neither conversion nor source was changed.

### Router and session semantics

- Ordinary generated LOGIN_EVENT landing: 200 rows, all SUCCESS; no default-route
  code. A separate captured same-schema landing probe appended UNROUTED, FAILED,
  LOCKED and MFA_FAILED. Actual runner read 204 and wrote 203; dbt also produced
  203 with zero keyed-hash differences. The default row was absent and the three
  failure routes present. Probe evidence is in `.runs/pc-users-sessions/router-probe/`.
- Router expressions/default are `m_SFX_LOGIN_EVENT.XML:60–64`; only success/failure
  writer connectors exist (`:108–119`). The shipped dbt macro reproduces the drop
  (`warehouse/dbt/macros/pc_content_login_event.sql:22–38`). BTEQ instead selects
  every staging row (`warehouse/teradata/scripts/users/04_load_events.bteq:4–6`).
- STG_APP_USER and ROLE_GRANT truncate (`wf_SFX_CONTENT_DAILY.XML:910,1005`);
  APP_USER, both LOGIN_EVENT writers and TEAM_MEMBER do not (`:956,1056,1068,1117`).
  Their dbt configurations correspond to table replacement versus incremental
  merge. Tests exercise unmatched-row retention and replacement on populated and
  empty inputs; the ordinary source run alone has no unmatched sentinel rows.
- APP_USER lookup policy is `Use First Value` (`m_SFX_APP_USER.XML:46`), with
  `IIF(ISNULL(lkp_USER_ID), DD_INSERT, DD_UPDATE)` at `:74`. Captured source logging
  reports 120 updates, zero inserts. The dbt merge gives matching isolated output;
  tests separately exercise update/insert and unmatched-row retention. Duplicate
  lookup keys were not generated, so multiple-match behavior is not empirically
  proven. BTEQ deletes all then inserts (`01_load_users.bteq:4–8`).

## Users Spark landing/lake proof

All six actual jobs ran through `make sfx-spark-run RUN_TOKEN=sfx1119
NS=sfx1119-before ROWS_PER_TABLE=200 JOB=<name>` after pulling the configured
Spark 3.5.3 mirror image and running `make sfx-spark-up` with the same scope.
Spark fixture initialization had changed generated host log ownership to UID 185;
ownership of that ignored logs directory was restored to the host user before
execution. No Spark source, submission configuration or conversion was changed.
The Scala compiler's deprecation warning is from the existing source/API, not a
missing environment dependency; the jobs all completed successfully.

`parity/spark_users.py` loads the same Spark landing PSV schemas (not the different
Teradata/PowerCenter PSV schemas), reads the actual lake Parquet and compares via
the ordinary exact ladder. `users_active_daily` and `users_team_rollup` execute
their shipped dbt SELECTs. The other four execute extracted shipped Python UDF
bodies and projections from `warehouse/snowpark/`; the graph job executes its
shipped UDTF process/end_partition body. Those existing Snowpark implementations
are measured alternatives; manifest `target_type: dbt_model` assignments are
unchanged, and no duplicate dbt models were invented.

| Job | Actual / converted count | Hash difference |
|---|---:|---:|
| team_graph_components | 200 / 200 | 0 |
| user_pref_json_flatten | 200 / 200 | 0 |
| users_active_daily | 7 / 7 | 0 |
| users_login_useragent_parse | 200 / 200 | 0 |
| users_risk_score | 200 / 200 | 0 |
| users_team_rollup | 200 / 200 | 0 |

All profiles agree and sampled differences are empty. No float tolerance,
rounding, string normalization or algorithmic convergence was added to force
these results. Tests cover populated/empty results, malformed JSON, missing-key
empty strings and Python stringification, unmatched browser `Other`, null risk
inputs, a graph longer than six hops, isolated/self-only members, stale/missing
Parquet and unsupported conversion bodies. The generated board declares all six
lake relations and includes source/conversion/ladder provenance and
`spark_evidence` landing hashes. Snowflake remains denied with 002003.

`user_pref_json_flatten` deliberately still reads the kept `users/USER_PREF`
landing feed, with PREF_JSON (`etl/spark/jobs/py/user_pref_json_flatten.py:7–19`).
This is not the retired Teradata USER_PREF's PREF_NAME/PREF_VALUE schema. Retiring
those Teradata tables is not permission to remove this landing feed or job.

### JDBC side outputs and consumers

`UsersRiskScore.scala:12` also overwrites `sfx_users.SPARK_RISK_SCORE` via
`BatchSupport.scala:91–98`; `users_team_rollup.py:10` overwrites
`sfx_users.SPARK_TEAM_ROLLUP` via `common/runtime.py:51–56`. Both actual tables were
queried in the local Spark PostgreSQL emulator (port 55432): each has 200 rows,
and exact ladder comparisons against its lake output have hash difference 0.
These side tables are not separate manifest objects/output declarations or named
consumer-registry entries. The rollup dbt schema description names its JDBC table;
the risk Snowpark module docstring names its JDBC table. Repository-wide reference
search found no readers beyond those producer/descriptive references; local
PostgreSQL view definitions also contain no readers. External consumers were not
queried, so their absence is not established.

Spark startup regenerated billing landing too, so its six actual jobs were rerun
to preserve freshness evidence. The append-mode billing usage lake output was
archived as `billing_usage_append_daily-pre-step-c` before its clean initial-build
rerun, avoiding mixed-run files; no billing code/comparison rules were changed.
