# Users Teradata-chain conversion

Stages execute `10_load.sql` → `20_routines.sql` → `30_views.sql`.
`00_tables.sql` declares the kept core and staging tables. The macro's returned
resultset is measured as `SFX_USERS.M_TEAM_COUNTS_OUTPUT`; `10_activity_daily`
also declares `SFX_USERS.USER_ACTIVITY_DAILY`. PowerCenter rows now use independent
runner-versus-dbt proofs described below; the BTEQ relation measurement is retained
as supplementary evidence. Spark conversion and the four retirement decisions
remain deferred.

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
