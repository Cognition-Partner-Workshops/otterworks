# Audit parity — all 57 objects

Run sfg1120 (RUN_TOKEN=sfx-sfg1120-audit). Local DuckDB: **48 green / 3 approved deviations / 6 retired / 0 red**. Snowflake: **red** — Snowflake login down for run sfg1120; no live capture/prove.

Spark compares actual legacy lake and JDBC outputs against shipped dbt models on the same landing PSVs. Batch and isolated PowerCenter runs are separate evidence paths. Six owner-approved retirements carry DBQL evidence. Local evidence is not live Snowflake proof.

| Object | Rows before/after | Profile diffs | Hash Δ | DuckDB | Snowflake | Board row and provenance |
|---|---:|---:|---:|---|---|---|
| m_SFX_AUDIT_DAILY_SUMMARY | 60/60 | 0 | 0 | approved_deviation | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L113-L504) |
| m_SFX_AUDIT_EVENT | 200/200 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L505-L706) |
| m_SFX_AUDIT_EVENT_ARCHIVE | — | — | — | retired | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L707-L890) |
| m_SFX_SECURITY_ALERT | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L2248-L2438) |
| m_SFX_STG_AUDIT_EVENT | 200/200 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L2456-L2655) |
| s_m_SFX_AUDIT_DAILY_SUMMARY | 60/60 | 0 | 0 | approved_deviation | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L3109-L3500) |
| s_m_SFX_AUDIT_EVENT | 200/200 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L3501-L3702) |
| s_m_SFX_AUDIT_EVENT_ARCHIVE | — | — | — | retired | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L3703-L3886) |
| s_m_SFX_SECURITY_ALERT | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L5244-L5434) |
| s_m_SFX_STG_AUDIT_EVENT | 200/200 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L5452-L5651) |
| wf_SFX_AUDIT_DAILY | 470/470 | 0 | 0 | approved_deviation | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L6088-L6844) |
| 01_load_events | 200/200 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L8301-L8494) |
| 02_load_controls | 50/50 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L8546-L9022) |
| 03_load_reviews | 74/74 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L9998-L10734) |
| 10_summary_daily | 22/22 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L12121-L12302) |
| 11_reconciliation | 40/40 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L12320-L12727) |
| SFX_AUDIT.M_ARCHIVE_OVERVIEW | — | — | — | retired | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L15078-L15261) |
| SFX_AUDIT.M_RECON_TOTALS | 39/39 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L15262-L15406) |
| SFX_AUDIT.P_DAILY_SUMMARY | 22/22 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L15475-L15656) |
| SFX_AUDIT.P_RECON_COUNTS | 40/40 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L15657-L16072) |
| SFX_AUDIT.ACCESS_REVIEW | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L16107-L16270) |
| SFX_AUDIT.AUDIT_DAILY_SUMMARY | 22/22 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L16271-L16444) |
| SFX_AUDIT.AUDIT_EVENT | 200/200 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L16445-L16638) |
| SFX_AUDIT.AUDIT_EVENT_ARCHIVE | — | — | — | retired | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L16639-L16822) |
| SFX_AUDIT.AUDIT_RECON | 40/40 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L16823-L17230) |
| SFX_AUDIT.COMPLIANCE_FLAG | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L17231-L17407) |
| SFX_AUDIT.DATA_EXPORT_REQ | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L17408-L17583) |
| SFX_AUDIT.LEGAL_HOLD | 2/2 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L17584-L17759) |
| SFX_AUDIT.RETENTION_POLICY | 20/20 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L17760-L17923) |
| SFX_AUDIT.SECURITY_ALERT | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L17924-L18106) |
| SFX_AUDIT.STG_ACCESS_REVIEW | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L18107-L18268) |
| SFX_AUDIT.STG_AUDIT_DAILY_SUMMARY | 2/2 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L18269-L18430) |
| SFX_AUDIT.STG_AUDIT_EVENT | 200/200 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L18431-L18622) |
| SFX_AUDIT.STG_AUDIT_EVENT_ARCHIVE | — | — | — | retired | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L18623-L18806) |
| SFX_AUDIT.STG_AUDIT_RECON | 2/2 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L18807-L18980) |
| SFX_AUDIT.STG_COMPLIANCE_FLAG | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L18981-L19154) |
| SFX_AUDIT.STG_DATA_EXPORT_REQ | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L19155-L19328) |
| SFX_AUDIT.STG_LEGAL_HOLD | 2/2 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L19329-L19502) |
| SFX_AUDIT.STG_RETENTION_POLICY | 20/20 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L19503-L19664) |
| SFX_AUDIT.STG_SECURITY_ALERT | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L19665-L19838) |
| audit_access_review | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L24844-L25005) |
| audit_audit_daily_summary | 2/2 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L25006-L25167) |
| audit_audit_event | 200/200 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L25168-L25359) |
| audit_audit_event_archive | — | — | — | retired | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L25360-L25543) |
| audit_audit_recon | 2/2 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L25544-L25717) |
| audit_compliance_flag | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L25718-L25891) |
| audit_data_export_req | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L25892-L26065) |
| audit_legal_hold | 2/2 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L26066-L26239) |
| audit_retention_policy | 20/20 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L26240-L26401) |
| audit_security_alert | 10/10 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L26402-L26575) |
| SFX_AUDIT.V_CUSTOMER_RECON | 40/40 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L26746-L26901) |
| SFX_AUDIT.V_EVENT_ACTORS | 200/200 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L26902-L27059) |
| audit_actor_activity_join | 470/470 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L28645-L28826) |
| audit_archive_resort | 200/200 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L28827-L28996) |
| audit_daily_summary | 84/84 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L28997-L29218) |
| compliance_flag_rules | 400/400 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L29352-L29573) |
| lake_compaction_audit | 42/42 | 0 | 0 | green | red | [evidence](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/board.json#L29764-L29909) |

[Source, converted SQL and metric implementation code-line links](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/board/README.md#audit-parity-provenance).

Approved PowerCenter stable summary ID contract (raw hash Δ retained separately): see [decision](https://github.com/Cognition-Partner-Workshops/otterworks/blob/devin/sfg1120-audit/migration/dw-exit/audit/README.md#owner-approved-summary-ids).
