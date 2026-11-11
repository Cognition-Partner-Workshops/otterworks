# Lineage

{'spark_ref': 'pr-2740', 'spark_commit': '40a2465c7eb30777a634abfa698d3a2e7ca17e47'}

Area-level overview; arrows represent feed/processing flow, not execution order. Detailed Spark reads/writes below are extracted from code literals.

```mermaid
flowchart LR
subgraph billing["billing"]
billing_landing["landing feeds"] --> billing_stg["staging"] --> billing_core["core"] --> billing_api["views / macros / procedures"] --> billing_etl["PowerCenter / BTEQ / Spark"]
end
subgraph documents["documents"]
documents_landing["landing feeds"] --> documents_stg["staging"] --> documents_core["core"] --> documents_api["views / macros / procedures"] --> documents_etl["PowerCenter / BTEQ / Spark"]
end
subgraph users["users"]
users_landing["landing feeds"] --> users_stg["staging"] --> users_core["core"] --> users_api["views / macros / procedures"] --> users_etl["PowerCenter / BTEQ / Spark"]
end
subgraph audit["audit"]
audit_landing["landing feeds"] --> audit_stg["staging"] --> audit_core["core"] --> audit_api["views / macros / procedures"] --> audit_etl["PowerCenter / BTEQ / Spark"]
end
subgraph data_platform["data-platform"]
data_platform_landing["landing feeds"] --> data_platform_stg["staging"] --> data_platform_core["core"] --> data_platform_api["views / macros / procedures"] --> data_platform_etl["PowerCenter / BTEQ / Spark"]
end
subgraph consumers["Consumers"]
c0["report-service"]
c1["analytics-service"]
c2["billing-service"]
c3["legacy-billing"]
c4["admin-service"]
c5["bi-semantic"]
c6["finance-notebook"]
c7["partner-extract"]
h0["svc_etl_audit"]:::hidden
h1["svc_etl_billing"]:::hidden
h2["svc_etl_docs"]:::hidden
h3["svc_etl_users"]:::hidden
end
classDef hidden fill:#ffe0e0,stroke:#b00020,stroke-width:3px
billing_etl --> c0
billing_etl --> c1
billing_etl --> c2
billing_etl --> c3
billing_etl --> c4
billing_etl --> c5
billing_etl --> c6
billing_etl --> c7
audit_etl --> h0
billing_etl --> h1
documents_etl --> h2
users_etl --> h3
```

## Spark code-level lineage

register/BatchSupport.register literals identify reads; save target literals identify writes. Tables are logical register names; runtime schema resolution is in common/runtime.py and BatchSupport.scala. External binary/lake inputs without register calls are shown as external.

```mermaid
flowchart LR
subgraph spark_billing["billing Spark transforms"]
j36e420fc9dda9a4a["billing_churn_score"]
tc539fadbfa["external lake/blob input"] --> j36e420fc9dda9a4a
j36e420fc9dda9a4a --> o36e420fc9dda9a4a["billing_churn_score lake output"]
j81f43bb8d0b21309["billing_gl_trial_balance"]
t305769d92e["CREDIT_NOTE"] --> j81f43bb8d0b21309
te578b8e7ef["GL_ACCOUNT"] --> j81f43bb8d0b21309
t399dbb86b0["GL_JOURNAL_LINE"] --> j81f43bb8d0b21309
j81f43bb8d0b21309 --> o81f43bb8d0b21309["sfx_billing.SPARK_GL_TRIAL_BALANCE"]
j31b693473f0cfb89["billing_invoice_summary_daily"]
t2231ca65af["INVOICE_HDR"] --> j31b693473f0cfb89
tb57dd7a56b["INVOICE_LINE"] --> j31b693473f0cfb89
j31b693473f0cfb89 --> o31b693473f0cfb89["sfx_billing.SPARK_INVOICE_SUMMARY"]
j240545304dd0cca3["billing_payment_aging"]
tc539fadbfa["external lake/blob input"] --> j240545304dd0cca3
j240545304dd0cca3 --> o240545304dd0cca3["sfx_billing.INVOICE_HDR, sfx_billing.PAYMENT"]
j3e8b07384080134a["billing_revenue_by_plan"]
tc539fadbfa["external lake/blob input"] --> j3e8b07384080134a
j3e8b07384080134a --> o3e8b07384080134a["billing_revenue_by_plan lake output"]
jc5c27426ee958835["billing_usage_append_daily"]
tdebfb8c14b["USAGE_DAILY"] --> jc5c27426ee958835
jc5c27426ee958835 --> oc5c27426ee958835["sfx_billing.SPARK_USAGE_DAILY"]
end
subgraph spark_documents["documents Spark transforms"]
j3656e055e27f9062["doc_share_graph_reach"]
t40cfc38d37["external lake/blob input"] --> j3656e055e27f9062
j3656e055e27f9062 --> o3656e055e27f9062["doc_share_graph_reach lake output"]
jdf9f11d44d3ae705["doc_version_diff_stats"]
t40cfc38d37["external lake/blob input"] --> jdf9f11d44d3ae705
jdf9f11d44d3ae705 --> odf9f11d44d3ae705["doc_version_diff_stats lake output"]
j449d7f13d2102104["docs_event_export_hourly"]
t40cfc38d37["external lake/blob input"] --> j449d7f13d2102104
j449d7f13d2102104 --> o449d7f13d2102104["docs_event_export_hourly lake output"]
j804e1a6d4791df03["docs_folder_legacy_report"]
t40cfc38d37["external lake/blob input"] --> j804e1a6d4791df03
j804e1a6d4791df03 --> o804e1a6d4791df03["docs_folder_legacy_report lake output"]
je2b2fad1957273cb["docs_folder_tree_walk"]
t40cfc38d37["external lake/blob input"] --> je2b2fad1957273cb
je2b2fad1957273cb --> oe2b2fad1957273cb["docs_folder_tree_walk lake output"]
j226fcb6125cd01af["docs_search_log_parse"]
t40cfc38d37["external lake/blob input"] --> j226fcb6125cd01af
j226fcb6125cd01af --> o226fcb6125cd01af["docs_search_log_parse lake output"]
j2b7a6d8d0e305a41["docs_storage_by_owner"]
t0718787605["APP_USER"] --> j2b7a6d8d0e305a41
t41e6750b47["DOCUMENT"] --> j2b7a6d8d0e305a41
t95c5430357["FILE_OBJECT"] --> j2b7a6d8d0e305a41
j2b7a6d8d0e305a41 --> o2b7a6d8d0e305a41["docs_storage_by_owner lake output"]
j1eb0f51fa396565a["docs_tag_normalize"]
t40cfc38d37["external lake/blob input"] --> j1eb0f51fa396565a
j1eb0f51fa396565a --> o1eb0f51fa396565a["docs_tag_normalize lake output"]
j71b09ce48eacf50e["docs_share_activity"]
t41e6750b47["DOCUMENT"] --> j71b09ce48eacf50e
t33f3b7af0e["DOC_SHARE"] --> j71b09ce48eacf50e
j71b09ce48eacf50e --> o71b09ce48eacf50e["docs_share_activity lake output"]
j2848accf505abb70["lake_compaction_documents"]
t40cfc38d37["external lake/blob input"] --> j2848accf505abb70
j2848accf505abb70 --> o2848accf505abb70["lake_compaction_documents lake output"]
end
subgraph spark_users["users Spark transforms"]
j82e7b20b053c63d2["user_pref_json_flatten"]
t06497fa033["external lake/blob input"] --> j82e7b20b053c63d2
j82e7b20b053c63d2 --> o82e7b20b053c63d2["user_pref_json_flatten lake output"]
j5202404d1a5ee738["users_active_daily"]
t06497fa033["external lake/blob input"] --> j5202404d1a5ee738
j5202404d1a5ee738 --> o5202404d1a5ee738["users_active_daily lake output"]
j93b3d7ca84bbf546["users_login_useragent_parse"]
t06497fa033["external lake/blob input"] --> j93b3d7ca84bbf546
j93b3d7ca84bbf546 --> o93b3d7ca84bbf546["users_login_useragent_parse lake output"]
j67c0593354ffde0a["users_team_rollup"]
tc7541aa91a["APP_USER"] --> j67c0593354ffde0a
t52980fc34e["TEAM"] --> j67c0593354ffde0a
tc838759863["TEAM_MEMBER"] --> j67c0593354ffde0a
j67c0593354ffde0a --> o67c0593354ffde0a["sfx_users.SPARK_TEAM_ROLLUP"]
je74cf4a953626a7e["team_graph_components"]
t06497fa033["external lake/blob input"] --> je74cf4a953626a7e
je74cf4a953626a7e --> oe74cf4a953626a7e["team_graph_components lake output"]
j3b611fa411d110e0["users_risk_score"]
t06497fa033["external lake/blob input"] --> j3b611fa411d110e0
j3b611fa411d110e0 --> o3b611fa411d110e0["sfx_users.SPARK_RISK_SCORE"]
end
subgraph spark_audit["audit Spark transforms"]
j3239a0ca48ca7071["audit_actor_activity_join"]
t619895e1a9["AUDIT_EVENT"] --> j3239a0ca48ca7071
tedbd430f84["LOGIN_EVENT"] --> j3239a0ca48ca7071
t8bdac745f3["USER_ACTIVITY_DAILY"] --> j3239a0ca48ca7071
j3239a0ca48ca7071 --> o3239a0ca48ca7071["audit_actor_activity_join lake output"]
jd505e2c0c31cf608["audit_archive_resort"]
t3878c3c83d["external lake/blob input"] --> jd505e2c0c31cf608
jd505e2c0c31cf608 --> od505e2c0c31cf608["audit_archive_resort lake output"]
j21023332aa8b55ce["lake_compaction_audit"]
t3878c3c83d["external lake/blob input"] --> j21023332aa8b55ce
j21023332aa8b55ce --> o21023332aa8b55ce["lake_compaction_audit lake output"]
je2e681f4b1b8c75f["audit_daily_summary"]
t619895e1a9["AUDIT_EVENT"] --> je2e681f4b1b8c75f
je2e681f4b1b8c75f --> oe2e681f4b1b8c75f["sfx_audit.SPARK_AUDIT_SUMMARY"]
end
subgraph spark_data_platform["data-platform Spark transforms"]
jec470285f065ed9c["collab_session_sessionize"]
tc469687dbd["external lake/blob input"] --> jec470285f065ed9c
jec470285f065ed9c --> oec470285f065ed9c["collab_session_sessionize lake output"]
j5378603daa2875d5["file_object_binary_extract"]
tc469687dbd["external lake/blob input"] --> j5378603daa2875d5
j5378603daa2875d5 --> o5378603daa2875d5["file_object_binary_extract lake output"]
j348248e32efac0da["security_alert_anomaly"]
tc469687dbd["external lake/blob input"] --> j348248e32efac0da
j348248e32efac0da --> o348248e32efac0da["sfx_audit.SPARK_ALERT_ANOMALY"]
jf8710c1a5ac6d3c9["compliance_flag_rules"]
tc469687dbd["external lake/blob input"] --> jf8710c1a5ac6d3c9
jf8710c1a5ac6d3c9 --> of8710c1a5ac6d3c9["sfx_audit.SPARK_COMPLIANCE_REVIEW"]
end
```

## Spark code-level references

| Job | Read/write evidence (code literals; physical paths also retained) | Source |
|---|---|---|
| audit_actor_activity_join | AUDIT_EVENT, LOGIN_EVENT, USER_ACTIVITY_DAILY | etl/spark/jobs/py/audit_actor_activity_join.py |
| audit_archive_resort | AUDIT_EVENT_ARCHIVE, AUDIT_EVENT_ARCHIVE_ID, EVENT_AT, EVENT_TYPE | etl/spark/jobs/py/audit_archive_resort.py |
| billing_churn_score | CHURN_SCORE, CUSTOMER_ID, STATUS, SUBSCRIPTION | etl/spark/jobs/py/billing_churn_score.py |
| billing_gl_trial_balance | CREDIT_NOTE, GL_ACCOUNT, GL_JOURNAL_LINE, sfx_billing.SPARK_GL_TRIAL_BALANCE | etl/spark/jobs/py/billing_gl_trial_balance.py |
| billing_invoice_summary_daily | INVOICE_HDR, INVOICE_LINE, sfx_billing.SPARK_INVOICE_SUMMARY | etl/spark/jobs/py/billing_invoice_summary_daily.py |
| billing_payment_aging | INVOICE_HDR, PAYMENT, sfx_billing.INVOICE_HDR, sfx_billing.PAYMENT | etl/spark/jobs/py/billing_payment_aging.py |
| billing_revenue_by_plan | INVOICE_LINE, PLAN_CATALOG | etl/spark/jobs/py/billing_revenue_by_plan.py |
| billing_usage_append_daily | USAGE_DAILY, sfx_billing.SPARK_USAGE_DAILY | etl/spark/jobs/py/billing_usage_append_daily.py |
| collab_session_sessionize | COLLAB_SESSION | etl/spark/jobs/py/collab_session_sessionize.py |
| doc_share_graph_reach | DOC_SHARE | etl/spark/jobs/py/doc_share_graph_reach.py |
| doc_version_diff_stats | BODY, DOCUMENT_ID, DOC_VERSION, PREVIOUS_BODY, SIMILARITY, VERSION_NUMBER | etl/spark/jobs/py/doc_version_diff_stats.py |
| docs_event_export_hourly | DOCUMENT, DOCUMENT_ID, EXPORT_BUCKET | etl/spark/jobs/py/docs_event_export_hourly.py |
| docs_folder_legacy_report | DOCUMENT, FOLDER | etl/spark/jobs/py/docs_folder_legacy_report.py |
| docs_folder_tree_walk | FOLDER | etl/spark/jobs/py/docs_folder_tree_walk.py |
| docs_search_log_parse | PARSED_ACTION, RAW_LINE, SEARCH_INDEX_LOG | etl/spark/jobs/py/docs_search_log_parse.py |
| docs_storage_by_owner | APP_USER, DOCUMENT, FILE_OBJECT | etl/spark/jobs/py/docs_storage_by_owner.py |
| docs_tag_normalize | DOC_TAG, NORMALIZED_TAG, TAG | etl/spark/jobs/py/docs_tag_normalize.py |
| file_object_binary_extract | ERROR, EXTRACT, FILE_OBJECT, MEDIA_TYPE, PAGE_COUNT, SHA256, STORAGE_KEY, TEXT | etl/spark/jobs/py/file_object_binary_extract.py |
| lake_compaction_audit |  | etl/spark/jobs/py/lake_compaction_audit.py |
| security_alert_anomaly | SECURITY_ALERT, sfx_audit.SPARK_ALERT_ANOMALY | etl/spark/jobs/py/security_alert_anomaly.py |
| user_pref_json_flatten | PREF_JSON, USER_PREF | etl/spark/jobs/py/user_pref_json_flatten.py |
| users_active_daily | USER_ACTIVITY_DAILY | etl/spark/jobs/py/users_active_daily.py |
| users_login_useragent_parse | BROWSER, LOGIN_EVENT, USER_AGENT | etl/spark/jobs/py/users_login_useragent_parse.py |
| users_team_rollup | APP_USER, TEAM, TEAM_MEMBER, sfx_users.SPARK_TEAM_ROLLUP | etl/spark/jobs/py/users_team_rollup.py |
| audit_daily_summary | AUDIT_EVENT, sfx_audit.SPARK_AUDIT_SUMMARY | etl/spark/scala/src/main/scala/sfx/AuditDailySummary.scala |
| compliance_flag_rules | COMPLIANCE_FLAG, COMPLIANCE_FLAG_ID, DISPOSITION, DOCUMENT_ID, FLAG_ID, SEVERITY, STATUS, sfx_audit.SPARK_COMPLIANCE_REVIEW | etl/spark/scala/src/main/scala/sfx/ComplianceFlagRules.scala |
| docs_share_activity | DOCUMENT, DOC_SHARE | etl/spark/scala/src/main/scala/sfx/DocsShareActivity.scala |
| lake_compaction_documents |  | etl/spark/scala/src/main/scala/sfx/LakeCompactionDocuments.scala |
| team_graph_components | COMPONENT_ID, TEAM_ID, TEAM_MEMBER, USER_ID | etl/spark/scala/src/main/scala/sfx/TeamGraphComponents.scala |
| users_risk_score | ACTION_COUNT, LOGIN_COUNT, RISK_SCORE, USER_ACTIVITY_DAILY, sfx_users.SPARK_RISK_SCORE | etl/spark/scala/src/main/scala/sfx/UsersRiskScore.scala |
