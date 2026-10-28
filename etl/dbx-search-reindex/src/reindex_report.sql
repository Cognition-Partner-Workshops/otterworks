-- ow_tp_analytics_search_reindex / reindex_report
-- Converted search_reindex_weekly.py count report.
--
-- The legacy job validated MeiliSearch stats (numberOfDocuments per index
-- against the indexed counts) and wrote per-metric rows. The staged report
-- at ow_tp.ow_tp_analytics_src.reindex_report carries those metrics
-- (documents_expected/indexed, files_expected/indexed, validation); the
-- converted report lands them keyed by metric.
--
-- Idempotent snapshot load: MERGE on metric; metrics absent from the
-- current report drop out, matching the legacy rewrite-per-run posture.

MERGE INTO ow_tp.ow_tp_analytics.search_reindex_report AS tgt
USING (
    SELECT metric, metric_value, report_date, generated_at
    FROM ow_tp.ow_tp_analytics_src.reindex_report
) AS src
ON tgt.metric = src.metric
WHEN MATCHED THEN UPDATE SET
    metric_value = src.metric_value,
    report_date = src.report_date,
    generated_at = src.generated_at
WHEN NOT MATCHED THEN INSERT *
WHEN NOT MATCHED BY SOURCE THEN DELETE;
