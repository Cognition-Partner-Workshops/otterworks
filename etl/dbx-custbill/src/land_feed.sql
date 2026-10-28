-- ow_tp_custbill_feed / land_feed
-- Converted sftp_ingest_poll + feed staging step.
--
-- The legacy chain polled an SFTP drop dir for CUSTBILL*.dat files, copied
-- them to incoming/, then parsed each 65-char CBCUST01 record. The converted
-- drop is the UC volume /Volumes/ow_tp/ow_tp_custbill/custbill_drop: the
-- extract snapshot lands as `CUSTBILL_<NS>_ORACLE.feed` JSONL
-- ({"invoice_id", "record"} per detail row) next to the byte-compatible
-- `.dat` artifact. HDR/TRL wrapper lines carry no invoice_id and are dropped
-- here (per spec latitude).
--
-- Idempotent snapshot load: MERGE on invoice_id from the current drop
-- contents (read_files over the task's drop_path parameter). A rerun re-reads
-- every feed file and converges to the same staged rows; files may be
-- re-dropped harmlessly. The drop is the snapshot: rows absent from the
-- current feeds are deleted, and duplicate invoice_ids resolve to the
-- most recently modified feed file.

MERGE INTO ow_tp.ow_tp_custbill.custbill_feed AS tgt
USING (
    SELECT
        invoice_id,
        TRIM(SUBSTRING(record, 1, 10)) AS cust_no,
        TRIM(SUBSTRING(record, 11, 30)) AS cust_name,
        TO_DATE(SUBSTRING(record, 41, 8), 'yyyyMMdd') AS period_end,
        CASE WHEN SUBSTRING(record, 64, 2) = '02' THEN -1 ELSE 1 END
            * CAST(CAST(SUBSTRING(record, 49, 12) AS BIGINT) AS DECIMAL(14, 2)) / 100
            AS total_amt,
        SUBSTRING(record, 61, 3) AS currency,
        SUBSTRING(record, 64, 2) AS record_type,
        'DET' AS record_tag,
        record AS raw_line,
        _metadata.file_path AS source_file,
        CAST(NULL AS BIGINT) AS batch_no,
        CURRENT_TIMESTAMP() AS landed_at
    FROM read_files(
        {{drop_path}} || '/*.feed',
        format => 'json',
        schema => 'invoice_id STRING, record STRING, tag STRING'
    )
    WHERE invoice_id IS NOT NULL AND record IS NOT NULL
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY invoice_id
        ORDER BY _metadata.file_modification_time DESC, _metadata.file_path
    ) = 1
) AS src
ON tgt.invoice_id = src.invoice_id
WHEN MATCHED THEN UPDATE SET
    cust_no = src.cust_no,
    cust_name = src.cust_name,
    period_end = src.period_end,
    total_amt = src.total_amt,
    currency = src.currency,
    record_type = src.record_type,
    record_tag = src.record_tag,
    raw_line = src.raw_line,
    source_file = src.source_file,
    landed_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    invoice_id, cust_no, cust_name, period_end, total_amt, currency,
    record_type, record_tag, raw_line, source_file, batch_no, landed_at
) VALUES (
    src.invoice_id, src.cust_no, src.cust_name, src.period_end, src.total_amt,
    src.currency, src.record_type, src.record_tag, src.raw_line,
    src.source_file, src.batch_no, src.landed_at
)
WHEN NOT MATCHED BY SOURCE THEN DELETE;
