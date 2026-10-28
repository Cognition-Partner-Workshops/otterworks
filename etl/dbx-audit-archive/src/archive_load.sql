-- ow_tp_analytics_audit_archive / archive_load
-- Converted etl/scripts/audit_archive_weekly.py.
--
-- The legacy job scanned DynamoDB otterworks-audit-events for events older
-- than 90 days, wrote them as JSONL.gz to the GLACIER audit archive, then
-- batch-deleted them from the source table, and emitted a compliance report
-- (s3://.../reports/compliance/audit-archive/<ds>/report.json). In the
-- converted pipeline the source side is the staged ledger
-- ow_tp.ow_tp_analytics_src.audit_events / compliance_report (what
-- audit_archive_run materializes each week).
--
-- Quarantine semantics are preserved as ledger rows: the target keeps every
-- staged archived event and this job NEVER deletes from the source staging.
-- INSERT OVERWRITE replaces the target wholesale so a rerun lands exactly
-- the current staged ledger — idempotent, and no MERGE: the staged event_id
-- is not a row identifier (it carries the event type), so keyed matching
-- would be wrong here.
INSERT OVERWRITE ow_tp.ow_tp_analytics.audit_archive
SELECT event_id, action, actor, resource, tenant, timestamp, archived_at, archive_s3_key
FROM ow_tp.ow_tp_analytics_src.audit_events;

-- Report metrics are keyed by metric, so an idempotent MERGE is correct:
-- metrics absent from the current report are dropped the same way the legacy
-- job rewrote the complete report.json each run.
MERGE INTO ow_tp.ow_tp_analytics.audit_archive_report AS tgt
USING (
    SELECT metric, metric_value, report_date, generated_at
    FROM ow_tp.ow_tp_analytics_src.compliance_report
) AS src
ON tgt.metric = src.metric
WHEN MATCHED THEN UPDATE SET
    metric_value = src.metric_value,
    report_date = src.report_date,
    generated_at = src.generated_at
WHEN NOT MATCHED THEN INSERT *
WHEN NOT MATCHED BY SOURCE THEN DELETE;
