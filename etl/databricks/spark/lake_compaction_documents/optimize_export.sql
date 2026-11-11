/* run=dbx-d1111 act=spark step=run consumer=lake_compaction_documents */
-- run_token=dbx-d1111 expires=2026-11-24
-- Compaction of the export layout becomes OPTIMIZE on the Delta export table.
OPTIMIZE cpw.dbx_d1111_after.documents__spark_docs_event_export_hourly
