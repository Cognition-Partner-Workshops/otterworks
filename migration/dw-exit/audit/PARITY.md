# Audit parity — all 57 objects

Local DuckDB: **48 green / 9 red**. Snowflake: **red** — role SFX_D1110_ROLE not authorized on SFX_1119 (002003); live capture/prove not run.

Spark compares actual legacy lake and JDBC outputs against shipped dbt models on the same landing PSVs. Batch and isolated PowerCenter runs are separate evidence paths. Six retirement proposals remain unconverted. Local evidence is not live Snowflake proof.

| Object | Rows before/after | Profile diffs | Hash Δ | DuckDB | Snowflake | Board row and provenance |
|---|---:|---:|---:|---|---|---|
| m_SFX_AUDIT_DAILY_SUMMARY | 60/60 | 0 | 84 | red | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L113-L397) |
| m_SFX_AUDIT_EVENT | 200/200 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L398-L592) |
| m_SFX_AUDIT_EVENT_ARCHIVE | — | — | — | red | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L593-L656) |
| m_SFX_SECURITY_ALERT | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L1926-L2109) |
| m_SFX_STG_AUDIT_EVENT | 200/200 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L2127-L2319) |
| s_m_SFX_AUDIT_DAILY_SUMMARY | 60/60 | 0 | 84 | red | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L2897-L3181) |
| s_m_SFX_AUDIT_EVENT | 200/200 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L3182-L3376) |
| s_m_SFX_AUDIT_EVENT_ARCHIVE | — | — | — | red | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L3377-L3440) |
| s_m_SFX_SECURITY_ALERT | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L4710-L4893) |
| s_m_SFX_STG_AUDIT_EVENT | 200/200 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L4911-L5103) |
| wf_SFX_AUDIT_DAILY | 470/470 | 0 | 84 | red | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L5664-L6277) |
| 01_load_events | 200/200 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L8693-L8885) |
| 02_load_controls | 50/50 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L8937-L9418) |
| 03_load_reviews | 74/74 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L10138-L10867) |
| 10_summary_daily | 22/22 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L11928-L12108) |
| 11_reconciliation | 40/40 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L12246-L12658) |
| SFX_AUDIT.M_ARCHIVE_OVERVIEW | — | — | — | red | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L15799-L15862) |
| SFX_AUDIT.M_RECON_TOTALS | 39/39 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L15863-L16012) |
| SFX_AUDIT.P_DAILY_SUMMARY | 22/22 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L16333-L16513) |
| SFX_AUDIT.P_RECON_COUNTS | 40/40 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L16514-L16934) |
| SFX_AUDIT.ACCESS_REVIEW | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L17595-L17763) |
| SFX_AUDIT.AUDIT_DAILY_SUMMARY | 22/22 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L17764-L17936) |
| SFX_AUDIT.AUDIT_EVENT | 200/200 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L17937-L18129) |
| SFX_AUDIT.AUDIT_EVENT_ARCHIVE | — | — | — | red | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L18130-L18193) |
| SFX_AUDIT.AUDIT_RECON | 40/40 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L18194-L18606) |
| SFX_AUDIT.COMPLIANCE_FLAG | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L18607-L18788) |
| SFX_AUDIT.DATA_EXPORT_REQ | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L18789-L18969) |
| SFX_AUDIT.LEGAL_HOLD | 2/2 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L18970-L19150) |
| SFX_AUDIT.RETENTION_POLICY | 20/20 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L19151-L19319) |
| SFX_AUDIT.SECURITY_ALERT | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L19320-L19501) |
| SFX_AUDIT.STG_ACCESS_REVIEW | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L19502-L19668) |
| SFX_AUDIT.STG_AUDIT_DAILY_SUMMARY | 2/2 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L19669-L19835) |
| SFX_AUDIT.STG_AUDIT_EVENT | 200/200 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L19836-L20026) |
| SFX_AUDIT.STG_AUDIT_EVENT_ARCHIVE | — | — | — | red | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L20027-L20090) |
| SFX_AUDIT.STG_AUDIT_RECON | 2/2 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L20091-L20269) |
| SFX_AUDIT.STG_COMPLIANCE_FLAG | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L20270-L20448) |
| SFX_AUDIT.STG_DATA_EXPORT_REQ | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L20449-L20627) |
| SFX_AUDIT.STG_LEGAL_HOLD | 2/2 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L20628-L20806) |
| SFX_AUDIT.STG_RETENTION_POLICY | 20/20 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L20807-L20973) |
| SFX_AUDIT.STG_SECURITY_ALERT | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L20974-L21152) |
| audit_access_review | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L26602-L26768) |
| audit_audit_daily_summary | 2/2 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L26769-L26935) |
| audit_audit_event | 200/200 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L26936-L27126) |
| audit_audit_event_archive | — | — | — | red | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L27127-L27190) |
| audit_audit_recon | 2/2 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L27191-L27369) |
| audit_compliance_flag | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L27370-L27548) |
| audit_data_export_req | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L27549-L27727) |
| audit_legal_hold | 2/2 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L27728-L27906) |
| audit_retention_policy | 20/20 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L27907-L28073) |
| audit_security_alert | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L28074-L28252) |
| SFX_AUDIT.V_CUSTOMER_RECON | 40/40 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L28423-L28583) |
| SFX_AUDIT.V_EVENT_ACTORS | 200/200 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L28584-L28746) |
| audit_actor_activity_join | 470/470 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L29485-L29669) |
| audit_archive_resort | 200/200 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L29670-L29842) |
| audit_daily_summary | 84/84 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L29843-L30067) |
| compliance_flag_rules | 400/400 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L31101-L31325) |
| lake_compaction_audit | 42/42 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/board.json#L31516-L31664) |

[Source, converted SQL and metric implementation code-line links](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/board/README.md#audit-parity-provenance).

Unresolved PowerCenter summary sequence assignment: see [diagnosis](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfx1119-audit-migration/migration/dw-exit/audit/README.md#unresolved-source-ordering-side-effect-leave-red).
