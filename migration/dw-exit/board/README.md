# Migration board

| Count | Wave 1 | Wave 2 | Wave 3 | Wave 4 |
|---|---:|---:|---:|---:|
| Total | 108 | 51 | 82 | 11 |
| by_kind: bteq | 0 | 12 | 13 | 0 |
| by_kind: catalog | 6 | 0 | 0 | 0 |
| by_kind: fastload | 22 | 0 | 0 | 0 |
| by_kind: macro | 1 | 0 | 5 | 0 |
| by_kind: mapping | 6 | 9 | 5 | 0 |
| by_kind: procedure | 0 | 0 | 4 | 0 |
| by_kind: session | 6 | 9 | 5 | 0 |
| by_kind: spark_job | 0 | 0 | 30 | 0 |
| by_kind: table | 45 | 21 | 18 | 0 |
| by_kind: tpt | 20 | 0 | 0 | 0 |
| by_kind: view | 2 | 0 | 0 | 9 |
| by_kind: workflow | 0 | 0 | 1 | 2 |
| by_kind: worklet | 0 | 0 | 1 | 0 |
| by_target: compatibility_view | 0 | 0 | 0 | 9 |
| by_target: dbt_model | 49 | 35 | 55 | 0 |
| by_target: retire | 20 | 0 | 0 | 0 |
| by_target: snowflake_scripting | 39 | 12 | 24 | 2 |
| by_target: snowpark | 0 | 4 | 3 | 0 |

## Licence counters

| Counter | Remaining | Target |
|---|---:|---:|
| teradata_objects | 178 | 0 |
| powercenter_mappings | 20 | 0 |
| powercenter_objects | 44 | 0 |
| spark_jobs | 30 | 0 |
| licence_dependencies | 252 | 0 |

All objects remain not_started. Parity measurements do not migrate or retire objects.

## Content parity provenance

BEFORE: actual PowerCenter workflow on the Teradata emulator; AFTER: shipped procedure body on DuckDB,
using identical landing inputs and typed pre-workflow tables. TEAM_MEMBER remains untouched.
Snowflake: **red** — Snowflake login down.

| Object | Local DuckDB | Snowflake | Source | Converted procedure | Metrics |
|---|---|---|---|---|---|
| wf_SFX_CONTENT_DAILY | red | red | [etl/informatica/repository/SFX_CONTENT/wf_SFX_CONTENT_DAILY.XML:1–1359](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-content/etl/informatica/repository/SFX_CONTENT/wf_SFX_CONTENT_DAILY.XML#L1-L1359) | [migration/dw-exit/content/workflow.sql:1–173](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-content/migration/dw-exit/content/workflow.sql#L1-L173) | [migration/dw-exit/parity/object_board.py:58–89](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-content/migration/dw-exit/parity/object_board.py#L58-L89)<br>[migration/dw-exit/parity/object_board.py:43–55](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-content/migration/dw-exit/parity/object_board.py#L43-L55)<br>[migration/dw-exit/parity/object_board.py:58–89](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-content/migration/dw-exit/parity/object_board.py#L58-L89) |

pending owner decision: exact stored CHAR padding; see content/decisions.json

Decision evidence: [etl/informatica/repository/SFX_CONTENT/wf_SFX_CONTENT_DAILY.XML:16–16](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-content/etl/informatica/repository/SFX_CONTENT/wf_SFX_CONTENT_DAILY.XML#L16-L16)<br>[etl/informatica/repository/SFX_CONTENT/wf_SFX_CONTENT_DAILY.XML:179–179](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-content/etl/informatica/repository/SFX_CONTENT/wf_SFX_CONTENT_DAILY.XML#L179-L179)<br>[etl/informatica/repository/SFX_CONTENT/wf_SFX_CONTENT_DAILY.XML:197–197](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-content/etl/informatica/repository/SFX_CONTENT/wf_SFX_CONTENT_DAILY.XML#L197-L197)<br>[warehouse/dbt/models/pc/content/pc_content__stg_app_user.sql:4–4](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-content/warehouse/dbt/models/pc/content/pc_content__stg_app_user.sql#L4-L4)

| Relation | BEFORE rows | AFTER rows | Profiles | Keyed hashes |
|---|---:|---:|---|---|
| SFX_DOCUMENTS.DOCUMENT | 90 | 90 | differ | 180 unmatched occurrences |
| SFX_DOCUMENTS.DOC_SHARE | 100 | 100 | differ | 200 unmatched occurrences |
| SFX_DOCUMENTS.STG_DOCUMENT | 90 | 90 | match | match |
| SFX_USERS.APP_USER | 120 | 120 | differ | 240 unmatched occurrences |
| SFX_USERS.LOGIN_EVENT | 200 | 200 | match | match |
| SFX_USERS.ROLE_GRANT | 20 | 20 | match | match |
| SFX_USERS.STG_APP_USER | 120 | 120 | differ | 200 unmatched occurrences |
| SFX_USERS.TEAM_MEMBER | 40 | 40 | match | match |

Samples for every differing key are recorded in `board.json` → `sampled_differences`.
