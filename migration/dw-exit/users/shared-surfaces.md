# Users shared surfaces, callers and ownership

Read-only inventory of the checked-out manifest, source/conversion files, registry and
DBQL CSVs. No owner, schedule, non-users implementation, consumer or manifest was changed.
DBQL window: 2026-08-12 through 2026-11-09; 8,080 query-log rows, 20,443 object-usage
rows in the current checkout. These are repository fixtures, not live warehouse telemetry.
The manifest owner inference is pinned by `tools/assess.py:25-30,300-322` to BEFORE
commit `a48ea0e29c31ca5a5445e22074a99a0549d7d6b3`; current registry/DBQL may differ.

## A. Read/write and shared orchestration boundaries

Within the 55 users objects, all named relational reads/writes belong to SFX_USERS
(or the corresponding USERS/PC_CONTENT/SPARK_RAW_USERS/MART_SPARK target surfaces).
No users object's own mapping/SQL body directly reads or writes a manifest table
owned by billing, documents or audit. Spark feeds are **not** the TD tables merely
because their names match: LOGIN_EVENT has USER_AGENT/RAW_LINE, USER_PREF has PREF_JSON,
and activity has ACTION_COUNT in Spark; their TD layouts differ.

| Surface | Readers / writers and source evidence | Boundary / finding |
|---|---|---|
| SFX_USERS.APP_USER | BTEQ 01_load_users, PC m_SFX_APP_USER, Snowpark TRANSFORM.M_SFX_APP_USER; m_SFX_DOCUMENT lookup `etl/informatica/repository/SFX_CONTENT/mappings/m_SFX_DOCUMENT.XML:53` | Physical table is users. Documents reads it; no distinct documents mapping writes it. Shared content workflow contains its writer. Widening DISPLAY_NAME propagates into audit/user views; dependent schemas/contracts may need review. |
| SFX_USERS.STG_APP_USER | users_app_user FastLoad, m_SFX_STG_APP_USER; BTEQ/PC readers | Physical users table; shared content workflow contains its writer. |
| SFX_USERS.ROLE_GRANT | BTEQ 02_load_teams, m_SFX_ROLE_GRANT; documents m_SFX_DOC_SHARE lookup `m_SFX_DOC_SHARE.XML:65` | Physical users table; shared content workflow contains its writer. PC lookup key USER_ID is **not** the table's unique GRANT_ID, so documents' first-match assumption is a separate cross-area risk, not users APP_USER lookup proof. |
| SFX_USERS.LOGIN_EVENT | BTEQ 04_load_events, m_SFX_LOGIN_EVENT; P_ACTIVITY_DAILY reads | Shared workflow contains PC writer; BTEQ and PC are different legacy writer semantics (see quiet audit). |
| SFX_USERS.TEAM_MEMBER | BTEQ 02_load_teams; m_SFX_TEAM_MEMBER / s_m_SFX_TEAM_MEMBER | Shared workflow declares the session but **disables** it. It is not a daily writer in the actual capture; standalone execution is explicit evidence only. |
| SFX_USERS.SPARK_RISK_SCORE | `etl/spark/scala/src/main/scala/sfx/UsersRiskScore.scala:12`; `BatchSupport.scala:91-98` JDBC overwrite | Not a table object in the manifest (no subject-area assignment); logically users, but must not invent manifest ownership. 200-row **lake** output parity does not establish JDBC table schema/grants/content or consumers. No other checked-in code writer/reader found beyond job declaration/runtime. |
| SFX_USERS.SPARK_TEAM_ROLLUP | `etl/spark/jobs/py/users_team_rollup.py:10`; `common/runtime.py:51-56` JDBC overwrite | Likewise absent from manifest and separately unverified. Replacing MART_SPARK output alone does not retire this side table. No other checked-in writer/reader found beyond declaration/runtime and conversion documentation. |
| wf_SFX_CONTENT_DAILY | `etl/informatica/repository/SFX_CONTENT/wf_SFX_CONTENT_DAILY.XML:1296-1345`; manifest `subject_area: content`, proposed @otterworks/data-platform | Shared container, not a 56th users object. Includes five users sessions and three documents sessions (STG_DOCUMENT, DOCUMENT, DOC_SHARE). Aggregate declared outputs: the five users tables above plus SFX_DOCUMENTS.STG_DOCUMENT / DOCUMENT / DOC_SHARE. It is a cross-area **container** of writes, not evidence of a second independent documents writer to users tables. |
| Converted content build / DAG | `warehouse/parity/commands.py:25-44`; `warehouse/snowflake/pc_dag/content.yml:1-44` | Folder-wide dbt selection builds TEAM_MEMBER although the legacy daily workflow disabled it. Task DAG omits TEAM_MEMBER/ROLE_GRANT/LOGIN_EVENT and covers document chain; it is not complete users schedule parity. No task was deployed/executed. |

Other users base/staging tables have only users producers in the inspected manifest/source
graph: USER_PROFILE, TEAM, SSO_IDENTITY, USER_STATUS_HIST, USER_ACTIVITY_DAILY,
USER_PREF and their staging tables; STG_LOGIN_EVENT, STG_ROLE_GRANT and STG_TEAM_MEMBER.
No direct foreign-area writer was found for these. Read-only audit reconciliation touches
them but writes AUDIT_RECON, not SFX_USERS (details below). Retirement does not authorize
removing the distinct Spark USER_PREF feed.

## B. External callers (not limited to literal SFX_USERS strings)

| Caller outside users | Read surface | Evidence and interpretation |
|---|---|---|
| Documents PC m_SFX_DOCUMENT / s_m_SFX_DOCUMENT | APP_USER lookup by USER_ID | `m_SFX_DOCUMENT.XML:42-60`; converted `warehouse/dbt/models/pc/content/pc_content__document.sql:2-6,17-19` refs pc_content__app_user. Its QUALIFY ROW_NUMBER ORDER BY USER_ID is not an original users tie rule; valid APP_USER keys make ties impossible in the legacy source, but Snowflake uniqueness is not enforced. |
| Documents PC m_SFX_DOC_SHARE / s_m_SFX_DOC_SHARE | ROLE_GRANT lookup by USER_ID | `m_SFX_DOC_SHARE.XML:65-70`; converted `pc_content__doc_share.sql:10-15,31` reads a **ROLE_GRANT landing source**, not the merged PC users output. Do not conflate those physical datasets. |
| Audit V_EVENT_ACTORS | APP_USER joined to AUDIT_EVENT.ACTOR_USER_ID; includes DISPLAY_NAME | `warehouse/teradata/ddl/audit/10_views.sql:1-3`. V_CUSTOMER_RECON in the same file does **not** read users; a file-wide match would be a false positive. |
| Audit 11_reconciliation | Nine users base/staging pairs: APP_USER, USER_PROFILE, TEAM, TEAM_MEMBER, ROLE_GRANT, SSO_IDENTITY, USER_STATUS_HIST, LOGIN_EVENT, USER_ACTIVITY_DAILY | `warehouse/teradata/scripts/audit/11_reconciliation.bteq:4-65`: read COUNTs, writes SFX_AUDIT.AUDIT_RECON. No USER_PREF reads. This is a real external dependency despite no user-facing registry entry. |
| Documents Spark docs_storage_by_owner | users APP_USER **landing feed**, not JDBC SFX_USERS.APP_USER | `etl/spark/jobs/py/docs_storage_by_owner.py:4-8`, runtime table-to-area lookup; converted `warehouse/dbt/models/spark/docs_storage_by_owner/docs_storage_by_owner.sql:9` uses source('spark_users','APP_USER'). Only non-users Spark caller found for these user feed names. |
| analytics-service (svc_analytics_dash) | V_TEAM_MEMBERS and underlying APP_USER / TEAM / TEAM_MEMBER | DBQL AppID **Analytics Dashboard**, 570 distinct queries; each of the four objects has 570 READ usage records. Registry `consumers/registry.yaml:20-26` assigns @otterworks/analytics but lists **billing-only** tables. Users dependency is missing from that declaration. |
| bi-semantic (svc_bi_semantic) | Same four objects | DBQL AppID **BI Semantic Service**, 134 queries / READ records per object. Registry `:88-94` assigns @otterworks/bi but again lists billing-only tables. |
| finance-notebook (nb_dsci_pkhan) | APP_USER **indirectly** through SFX_AUDIT.V_EVENT_ACTORS | DBQL AppID **JupyterLab/python**, 16 APP_USER READ usage records. QueryText selects EVENT_TYPE/COUNT from the audit view, so a literal SFX_USERS search misses it. Registry `:105-111` assigns @otterworks/data-science with billing-only tables. |
| users batch utility accounts (not external end users) | svc_etl_users / BTEQ reads APP_USER, LOGIN_EVENT, TEAM, TEAM_MEMBER, USER_ACTIVITY_DAILY and nine staging inputs | 90 READ usage records per surface. svc_fastload / FastLoad writes each of ten staging tables 20 times. These batch accounts are not evidence that a registry end-user team owns the writer. |

Counts join `objectusage.csv.QueryID` to `qrylog.csv.QueryID`, filter ObjectDatabaseName
SFX_USERS and UsageType READ, group by UserName/AppID/ObjectTableName. Underlying-object
usage expands views, so do **not** sum those four object counts as distinct queries.
The three external accounts above are the complete users READ principal/AppID set after
excluding svc_etl_users. Current QueryText-only searches add no additional principal.
USER_PREF / V_USER_SETTINGS have zero READ usage records (retirement evidence remains
window-limited, not proof of no future caller).

The registry has **zero** entries explicitly listing an SFX_USERS table. This does not
mean no callers: the DBQL expansion above disproves that. Searches of checked-in
services/consumers found no literal SFX_USERS SQL beyond the fixture/warehouse sources;
therefore current application execution of those historical queries is **unverified**.
No consumers, notebooks, reports or other-area jobs were executed in this audit.

## C. All 55 manifest owners

Exact values, not reassigned owners. Abbreviations:

- **A** = `@otterworks/analytics`; owner_source = `DBQL readership via consumers/registry.yaml`.
- **P** = `@otterworks/data-platform`; owner_source = `proposed`.

| Object | Owner / owner_source | Review flag |
|---|---|---|
| m_SFX_APP_USER | A | Multi-consumer / producer ownership not established |
| m_SFX_LOGIN_EVENT | P | Proposed, no owner acceptance recorded |
| m_SFX_ROLE_GRANT | P | Proposed; documents lookup caller |
| m_SFX_STG_APP_USER | P | Proposed; same chain as analytics-owned APP_USER |
| m_SFX_TEAM_MEMBER | A | Reader-derived owner; daily disabled |
| s_m_SFX_APP_USER | A | Multi-consumer / producer ownership not established |
| s_m_SFX_LOGIN_EVENT | P | Proposed |
| s_m_SFX_ROLE_GRANT | P | Proposed; documents lookup caller |
| s_m_SFX_STG_APP_USER | P | Proposed; chain ownership split |
| s_m_SFX_TEAM_MEMBER | A | Reader-derived owner; daily disabled |
| 01_load_users | A | Reader-derived owner; USER_PROFILE co-output has P |
| 02_load_teams | A | Reader-derived owner; ROLE_GRANT co-output has P |
| 03_load_identity | P | Proposed |
| 04_load_events | P | Proposed; disagrees with PC writer on default routes |
| 10_activity_daily | P | Proposed |
| users_app_user | P | Proposed; chain ownership split |
| users_login_event | P | Proposed |
| users_role_grant | P | Proposed |
| users_sso_identity | P | Proposed |
| users_team | P | Proposed; chain ownership split |
| users_team_member | P | Proposed; chain ownership split |
| users_user_activity_daily | P | Proposed |
| users_user_pref | P | Proposed; retirement is not owner acceptance |
| users_user_profile | P | Proposed |
| users_user_status_hist | P | Proposed |
| SFX_USERS.M_TEAM_COUNTS | P | Proposed; analytics reads its base tables |
| SFX_USERS.P_ACTIVITY_DAILY | P | Proposed |
| SFX_USERS.APP_USER | A | Also BI, data-science, audit and documents callers |
| SFX_USERS.LOGIN_EVENT | P | Proposed |
| SFX_USERS.ROLE_GRANT | P | Proposed; documents lookup caller |
| SFX_USERS.SSO_IDENTITY | P | Proposed |
| SFX_USERS.STG_APP_USER | P | Proposed; chain ownership split |
| SFX_USERS.STG_LOGIN_EVENT | P | Proposed |
| SFX_USERS.STG_ROLE_GRANT | P | Proposed |
| SFX_USERS.STG_SSO_IDENTITY | P | Proposed |
| SFX_USERS.STG_TEAM | P | Proposed; chain ownership split |
| SFX_USERS.STG_TEAM_MEMBER | P | Proposed; chain ownership split |
| SFX_USERS.STG_USER_ACTIVITY_DAILY | P | Proposed |
| SFX_USERS.STG_USER_PREF | P | Proposed; retirement |
| SFX_USERS.STG_USER_PROFILE | P | Proposed |
| SFX_USERS.STG_USER_STATUS_HIST | P | Proposed |
| SFX_USERS.TEAM | A | Also BI consumer; producer ownership not established |
| SFX_USERS.TEAM_MEMBER | A | Also BI consumer; producer ownership not established |
| SFX_USERS.USER_ACTIVITY_DAILY | P | Proposed |
| SFX_USERS.USER_PREF | P | Proposed; retirement |
| SFX_USERS.USER_PROFILE | P | Proposed; same BTEQ chain as A APP_USER |
| SFX_USERS.USER_STATUS_HIST | P | Proposed |
| SFX_USERS.V_TEAM_MEMBERS | A | Also BI consumer |
| SFX_USERS.V_USER_SETTINGS | P | Proposed; retirement |
| team_graph_components | P | Proposed; Spark feed ownership not TD base ownership |
| user_pref_json_flatten | P | Proposed; independent non-retired PREF_JSON feed |
| users_active_daily | P | Proposed |
| users_login_useragent_parse | P | Proposed |
| users_risk_score | P | Proposed; JDBC side-table owner absent from manifest |
| users_team_rollup | P | Proposed; JDBC side-table owner absent from manifest |

Total: **10 A / 45 P**. Analytics assignments are consistent with the highest DBQL
readership, but that heuristic establishes a consumer contact, **not** exclusive producer
ownership or approval to widen downstream contracts. Registry table declarations are
incomplete for all three users-consuming accounts. Proposed platform owners are unapproved
defaults, not verified team decisions; shared workflow's proposed platform owner must
coordinate with documents, audit, analytics and BI. These are review flags, not evidence
that another specific team should automatically replace the manifest owner.
