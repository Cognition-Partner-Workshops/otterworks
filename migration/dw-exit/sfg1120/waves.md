# sfg1120 warehouse exit waves

Assessment of `demo-snowflake-dw-exit` at `06096a70d67f54f88ce6c71c491093ac1253525d`.

- [Object manifest](manifest.json) contains all 87 tables, 14 views, 6 macros, 4 procedures and 20 mappings. Six of the Teradata objects are DBC system relations. BTEQ, FastLoad, TPT, PowerCenter sessions, Spark jobs and datasets appear as lineage context.
- [Clickable lineage](lineage.html) opens after downloading the HTML to a browser with access to `static.devin.ai`. Type a name or principal, select a result, and click its neighbors to move upstream or downstream. Use **Retire candidates** to review the nine proposed exclusions.
- [Evidence and reproduction](evidence.md) documents the observed history, local runs, and limits of the retirement decision.

## Sequence and exit criteria

The counts below cover the 131 inventory objects. Run cross-area jobs once all named upstream waves have passed their exit criteria.

| Wave | Scope | Objects | Exit criteria |
|---|---|---:|---|
| 1 | Shared landing, staging and telemetry | 52 | Connect FastLoad/TPT and flat-file mapping feeds to staged tables. Preserve date partitions, schema and reject handling. Reconcile landing/staging counts across all four areas. Replace the six DBC surfaces with Snowflake catalog and query/access-history equivalents. Confirm that the reconciliation reader can still retrieve object usage. |
| 2 | Users and identity | 15 | Verify `APP_USER`, `ROLE_GRANT`, `TEAM_MEMBER` and `LOGIN_EVENT` keys, duplicate handling, role grants and daily activity totals. Make the `APP_USER` and `ROLE_GRANT` lookup surfaces available before document mappings. `TEAM_MEMBER` remains in this wave via its BTEQ writer and reconciliation reader. |
| 3 | Documents and storage | 14 | Validate document-version selection, sharing permissions, file sizes and storage rollups. Replay `m_SFX_DOCUMENT` and `m_SFX_DOC_SHARE` with the Wave 2 lookups. Reconcile Spark landing file counts and compare lake outputs for downstream compaction. Carry monthly storage inputs and `M_STORAGE_TOTALS` forward to the billing gate. |
| 4 | Billing and GL | 24 | Validate invoice, payment, credit and journal totals by period, currency and account. Run the document storage-to-billing load alongside its `SUBSCRIPTION`, `INVOICE_HDR` and `USAGE_DAILY` dependencies. Verify monthly SPL, period-close behavior and the GL mapping's account lookup, sequence and rerun behavior. Replay billing exports, BI, SFTP and registered service contracts. Confirm and replay the unregistered finance analyst's reads. |
| 5 | Audit, compliance and cross-area reconciliation | 17 | Replay audit-event ingestion, daily summaries and audit controls. Validate actor joins against Wave 2 and every retained staging/core reconciliation pair across Waves 1–4. Compare source/target counts and control totals before swapping the audit reconciliation consumer. Verify the separate Spark archive feed and retention requirements. |
| 6 | Retirement review and cutover | 9 | Confirm ownership, legal retention and one full business cycle of current usage including month-end. Approve each candidate as an exclusion. Run the old and new inputs in parallel through each retained consumer's normal cadence, including query principals outside batch accounts. Preserve the old endpoint and schedule definitions for rollback until checks pass and owners approve cutover. |

Deploy a prior wave's shared lookups and feeds before switching dependent jobs. Within a wave, keep stateful mapping targets and any read/write cycles together for validation. When both BTEQ and PowerCenter write a target, compare the expected output and the order of the legacy writers before choosing the cutover writer.

## Retirement candidates

These objects had no successful reader or caller in the DBQL window and no
active downstream dependency in the assessed source, or no recent successful
PowerCenter execution and no enabled session. Retire dependent interfaces and
writers with their candidates only after the Wave 6 checks.

| Subject area | Candidate | Evidence and decision |
|---|---|---|
| Audit | `SFX_AUDIT.AUDIT_EVENT_ARCHIVE`, `SFX_AUDIT.M_ARCHIVE_OVERVIEW` | The macro is the table's only declared warehouse reader, and the macro has no observed calls. Confirm archive retention. Spark's `audit_archive_resort` reads the separate landing feed, which stays in scope. |
| Audit | `m_SFX_AUDIT_EVENT_ARCHIVE` | Disabled session, skipped locally, last historical success July 31. Confirm replacement of any required archive writes. |
| Documents | `SFX_DOCUMENTS.SEARCH_INDEX_LOG`, `SFX_DOCUMENTS.V_SEARCH_HISTORY` | The view is the table's only declared warehouse reader and has no observed reads. Preserve the separate `SEARCH_INDEX_LOG` landing feed for Spark. Keep `STG_SEARCH_INDEX_LOG` under first-day usage review. |
| Users | `SFX_USERS.STG_USER_PREF`, `SFX_USERS.USER_PREF`, `SFX_USERS.V_USER_SETTINGS` | The staging table had 20 writes and no observed reads. The view is the core table's only declared warehouse reader and has no observed reads. Continue providing the separate user-preference landing feed to Spark. |
| Users | `m_SFX_TEAM_MEMBER` | Disabled session, skipped locally, last historical success July 24. The table and its staging feed stay in scope for BTEQ, reconciliation and Spark landing consumers. |
