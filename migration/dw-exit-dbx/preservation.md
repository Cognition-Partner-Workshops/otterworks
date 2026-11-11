# Control-table preservation evidence

Before total=332 manifest=270 outside=62; after total=339 manifest=277 outside=62.
Existing managed-field rows checked=332; nondefault status/parity/pr rows=74; changed outside rows=0; changed managed-field rows=0.

Snapshot statement: `01f1dd8a-f8b9-1fb4-af29-b9acbca8e824`. Verify statement: `01f1dd8b-1c7a-1dae-a580-85de0901063f`.

All outside rows compared across every column; every pre-existing row compared for status/parity/pr/updated_at. Seven previously absent manifest IDs were inserted; no pre-existing rows were removed.

## Every pre-reload row differing from planned / NULL / NULL defaults

| object_name | status | parity | pr | updated_at |
|---|---|---|---|---|
| 10f4c1497e21c2e2 | green | green: 300=300 hash 168177914759423658741 | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2747 | 2026-11-11 03:57:18.379294+00:00 |
| 146f470fd9ad85b0 | green | 450 rows; hash 252415578849307384316; 0 EXCEPT ALL differences each way | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2746 | 2026-11-11 03:58:28.339184+00:00 |
| 1c99845abc02a0ee | green | green: 2000=2000 hash 1154127577021005715171 | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2747 | 2026-11-11 03:57:18.379294+00:00 |
| 28768d7b47d87de6 | green | 300 rows; hash 169954062109575017629; 0 EXCEPT ALL differences each way | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2746 | 2026-11-11 03:58:28.339184+00:00 |
| 2fd0764be73a1733 | green | green: 6132=6132 hash 3550786035502688172146; ids 900001-906132 both | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2747 | 2026-11-11 03:57:18.379294+00:00 |
| 42981ab27802d974 | green | green: 2000=2000 hash 1133633439810954768679 | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2747 | 2026-11-11 03:57:18.379294+00:00 |
| 5fb967a05c4c2fd1 | red | 1000 rows; hash 581907916730381736522; 0 EXCEPT ALL differences each way | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2746 | 2026-11-11 03:58:28.339184+00:00 |
| 67f41d67d59f42ba | green | green: 2100=2100 hash 1205986979680478474179; 0 rejects | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2747 | 2026-11-11 03:57:18.379294+00:00 |
| 8717fb5b8e9b0976 | green | 300 rows; hash 169954062109575017629; 0 EXCEPT ALL differences each way | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2746 | 2026-11-11 03:58:28.339184+00:00 |
| billing__billing_adj | green | v2-fixed all 4 rungs/probes pass; hash 01f1dd83-cfe0-115b-b2b6-e48c8b8a9c23 | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2766 | 2026-11-11 04:21:17.822858+00:00 |
| billing__credit_note | green | v2-fixed all 4 rungs/probes pass; hash 01f1dd83-c770-192b-bdd1-fe96e08c3f1e | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2766 | 2026-11-11 04:21:17.822858+00:00 |
| billing__customer_account | green | v2-fixed all 4 rungs/probes pass; hash 01f1dd83-80bb-18d7-908f-a4b8503e3701 | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2766 | 2026-11-11 04:21:17.822858+00:00 |
| billing__gl_account | green | v2-fixed all 4 rungs/probes pass; hash 01f1dd83-9a84-13a2-9396-745cce11468a | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2766 | 2026-11-11 04:21:17.822858+00:00 |
| billing__gl_journal_line | green | v2-fixed all 4 rungs/probes pass; hash 01f1dd83-e0be-13cf-8b73-9bc446d4756e | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2766 | 2026-11-11 04:21:17.822858+00:00 |
| billing__in_documents_collab_session | green | v2-fixed all 4 rungs/probes pass; hash 01f1dd83-6f70-19ad-b61b-ee95d7d17b0b | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2766 | 2026-11-11 04:21:17.822858+00:00 |
| billing__in_documents_doc_version | green | v2-fixed tie-aware 01f1dd86-e884-1819-8839-7676554ef743; untied exact 01f1dd86-3b74-122b-893c-a20652c103b0; raw baseline difference observed | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2766 | 2026-11-11 04:21:17.822858+00:00 |
| billing__in_documents_m_storage_totals | green | v2-fixed all 4 rungs/probes pass; hash 01f1dd84-1bf7-1400-ba76-cd25dbcf46ee | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2766 | 2026-11-11 04:21:17.822858+00:00 |
| billing__in_documents_storage_usage_daily | green | v2-fixed all 5 rungs/probes pass; hash 01f1dd83-777c-100a-9538-0d2cccbca877 | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2766 | 2026-11-11 04:21:17.822858+00:00 |
| billing__in_users_app_user | green | v2-fixed all 5 rungs/probes pass; hash 01f1dd83-5639-11d4-a28d-a27dfcd3b48e | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2766 | 2026-11-11 04:21:17.822858+00:00 |
| billing__in_users_user_profile | green | v2-fixed all 4 rungs/probes pass; hash 01f1dd83-5f4b-1eb2-ac30-f8feafcaac39 | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2766 | 2026-11-11 04:21:17.822858+00:00 |
| billing__invoice_hdr | green | v2-fixed all 6 rungs/probes pass; hash 01f1dd83-ac34-1314-b1f2-be25a3722924 | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2766 | 2026-11-11 04:21:17.822858+00:00 |
| billing__invoice_line | green | v2-fixed all 4 rungs/probes pass; hash 01f1dd83-b7a1-1ea0-8e2f-d7554c8701c3 | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2766 | 2026-11-11 04:21:17.822858+00:00 |
| billing__m_currency_totals | green | v2-fixed all 4 rungs/probes pass; hash 01f1dd84-1438-1289-88d8-44bc3b8c05b8 | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2766 | 2026-11-11 04:21:17.822858+00:00 |
| billing__m_subscription_plans | green | v2-fixed all 5 rungs/probes pass; hash 01f1dd84-0cdb-14d0-8958-9918cbbaf961 | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2766 | 2026-11-11 04:21:17.822858+00:00 |
| billing__payment | green | v2-fixed all 4 rungs/probes pass; hash 01f1dd83-bf79-1948-8bda-0738f0ca4f87 | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2766 | 2026-11-11 04:21:17.822858+00:00 |
| billing__plan_catalog | green | v2-fixed all 4 rungs/probes pass; hash 01f1dd83-8906-1486-bd7f-e0bd25ea34a5 | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2766 | 2026-11-11 04:21:17.822858+00:00 |
| billing__subscription | green | v2-fixed all 5 rungs/probes pass; hash 01f1dd83-a35a-1c31-99cd-d843ba7748a2 | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2766 | 2026-11-11 04:21:17.822858+00:00 |
| billing__tax_rate | green | v2-fixed all 4 rungs/probes pass; hash 01f1dd83-91cd-1cce-8da8-a1865138edff | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2766 | 2026-11-11 04:21:17.822858+00:00 |
| billing__usage_daily | green | v2-fixed all 4 rungs/probes pass; hash 01f1dd83-d7fa-11a0-8429-98280f1bde6f | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2766 | 2026-11-11 04:21:17.822858+00:00 |
| billing__v_account_invoices | green | v2-fixed all 4 rungs/probes pass; hash 01f1dd83-e90d-1b5f-bb8a-3390ee459424 | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2766 | 2026-11-11 04:21:17.822858+00:00 |
| billing__v_invoice_base | green | v2-fixed all 4 rungs/probes pass; hash 01f1dd83-f199-151d-979e-beff8a4d169e | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2766 | 2026-11-11 04:21:17.822858+00:00 |
| billing__v_invoice_revenue | green | v2-fixed all 4 rungs/probes pass; hash 01f1dd83-fa36-1188-a33c-c2310d10c860 | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2766 | 2026-11-11 04:21:17.822858+00:00 |
| billing__v_subscription_plans | green | v2-fixed all 4 rungs/probes pass; hash 01f1dd84-0461-167c-8446-308f3b722c0f | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2766 | 2026-11-11 04:21:17.822858+00:00 |
| c90225d3fe85ae15 | green | green: 2100=2100 hash 1205986979680478474179 | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2747 | 2026-11-11 03:57:18.379294+00:00 |
| consumer:admin-service | green | pass: summary + overdue rows equal old path and contract | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2755 | 2026-11-11 04:02:33.383957+00:00 |
| consumer:analytics-service | red | pass | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2754 | 2026-11-11 04:01:29.344801+00:00 |
| consumer:bi-semantic | green | pass: 5/5 queries equal old path and expected/baseline; inputs equal before (6/6 count+hash) | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2752 | 2026-11-11 04:00:47.300419+00:00 |
| consumer:billing-service | green | 667 rows; all fields and CSV bytes equal; amount=248753.92 tax=31476.06 open=156116.27 | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2751 | 2026-11-11 04:07:55.562082+00:00 |
| consumer:finance-notebook | green | pass 4/4 queries vs old path and contract (as-of 2026-11-09) | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2764 | 2026-11-11 04:21:54.684107+00:00 |
| consumer:legacy-billing | red | AR aging pass; consumer cutover blocked by absent queue | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2750 | 2026-11-11 04:00:19.085850+00:00 |
| consumer:partner-extract | green | pass | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2749 | 2026-11-11 03:59:30.094678+00:00 |
| consumer:report-service | green | pass | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2773 | 2026-11-11 04:42:57.942562+00:00 |
| f0361b4304bd38fa | green | green: 300=300 hash 168177914759423658741 | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2747 | 2026-11-11 03:57:18.379294+00:00 |
| fc2757668ae7cdcd | green | 450 rows; hash 260733032028553989803; 0 EXCEPT ALL differences each way | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2746 | 2026-11-11 03:58:28.339184+00:00 |
| spark:audit_actor_activity_join | red | BLOCKED: Missing ACTION_COUNT in users__user_activity_daily and users__stg_user_activity_daily; USER_AGENT, RAW_LINE and IP_ADDRESS absent from users__login_event and users__stg_login_event. DOCUMENT_COUNT and CLIENT_TYPE are not equivalent. | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2756 | 2026-11-11 04:26:01.724287+00:00 |
| spark:audit_archive_resort | green | PASS: input count/hash, output count/hash and EXCEPT ALL both ways | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2756 | 2026-11-11 04:26:29.753513+00:00 |
| spark:audit_daily_summary | green | PASS: input count/hash, output count/hash and EXCEPT ALL both ways | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2756 | 2026-11-11 04:25:53.036623+00:00 |
| spark:billing_churn_score | green | 500 rows; hash 278703278045701988246; EXCEPT ALL empty both directions | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2757 | 2026-11-11 04:07:45.558875+00:00 |
| spark:billing_gl_trial_balance | red | not run | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2759 | 2026-11-11 04:08:27.880381+00:00 |
| spark:billing_invoice_summary_daily | green | pass | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2759 | 2026-11-11 04:08:13.326287+00:00 |
| spark:billing_payment_aging | red | not run | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2759 | 2026-11-11 04:08:24.753044+00:00 |
| spark:billing_revenue_by_plan | green | pass | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2759 | 2026-11-11 04:08:16.525468+00:00 |
| spark:billing_usage_append_daily | red | pass | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2759 | 2026-11-11 04:08:20.747548+00:00 |
| spark:collab_session_sessionize | green | pass | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2770 | 2026-11-11 04:26:23.918323+00:00 |
| spark:compliance_flag_rules | red | BLOCKED: Missing SEVERITY and USER_ID in audit__compliance_flag and audit__stg_compliance_flag; FLAG_TYPE is not a numeric severity or user identity. | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2756 | 2026-11-11 04:26:38.502621+00:00 |
| spark:doc_share_graph_reach | green | pass | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2770 | 2026-11-11 04:26:19.315344+00:00 |
| spark:doc_version_diff_stats | red | NOT RUN: missing required live input | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2757 | 2026-11-11 04:07:53.640781+00:00 |
| spark:docs_event_export_hourly | green | pass | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2760 | 2026-11-11 04:08:15.827065+00:00 |
| spark:docs_folder_legacy_report | red | count 200/200, hash equal, 0/0 EXCEPT ALL | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2758 | 2026-11-11 04:08:14.307733+00:00 |
| spark:docs_folder_tree_walk | red | red | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2770 | 2026-11-11 04:26:28.752865+00:00 |
| spark:docs_search_log_parse | red | none: no live input | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2765 | 2026-11-11 04:17:32.890839+00:00 |
| spark:docs_share_activity | green | count 539/539, hash equal, 0/0 EXCEPT ALL | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2758 | 2026-11-11 04:08:11.796092+00:00 |
| spark:docs_storage_by_owner | green | count 200/200, hash equal, 0/0 EXCEPT ALL | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2758 | 2026-11-11 04:08:09.183224+00:00 |
| spark:docs_tag_normalize | green | green: 1000=1000 rows, hash 586596083625798495746 both sides, EXCEPT ALL 0/0 | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2765 | 2026-11-11 04:17:26.573492+00:00 |
| spark:file_object_binary_extract | red | n/a (not migrated) | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2760 | 2026-11-11 04:08:22.805374+00:00 |
| spark:lake_compaction_audit | green | PASS: input count/hash, output count/hash and EXCEPT ALL both ways | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2756 | 2026-11-11 04:26:10.760829+00:00 |
| spark:lake_compaction_documents | green | pass | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2760 | 2026-11-11 04:08:19.116632+00:00 |
| spark:security_alert_anomaly | red | BLOCKED: Missing SCORE and ALERT_TYPE in audit__security_alert and audit__stg_security_alert; categorical SEVERITY_CD is not a numeric anomaly score. Exact local Z_SCORE parity also remains failed. | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2756 | 2026-11-11 04:26:20.522519+00:00 |
| spark:team_graph_components | green | pass | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2770 | 2026-11-11 04:26:14.805152+00:00 |
| spark:user_pref_json_flatten | red | none: no live input | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2765 | 2026-11-11 04:17:44.492490+00:00 |
| spark:users_active_daily | red | count 3/3, hash equal, 0/0 EXCEPT ALL | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2758 | 2026-11-11 04:08:17.444997+00:00 |
| spark:users_login_useragent_parse | red | none: no live input | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2765 | 2026-11-11 04:17:38.489481+00:00 |
| spark:users_risk_score | red | NOT RUN: missing required live input | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2757 | 2026-11-11 04:07:49.853741+00:00 |
| spark:users_team_rollup | green | count 20/20, hash equal, 0/0 EXCEPT ALL | https://github.com/Cognition-Partner-Workshops/otterworks/pull/2758 | 2026-11-11 04:08:21.806979+00:00 |
