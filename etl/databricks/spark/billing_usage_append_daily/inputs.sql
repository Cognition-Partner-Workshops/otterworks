-- run_token=dbx-d1111 expires=2026-11-24
-- Input adapter: live cpw.dbx_d1111_before (Teradata-style names) -> Spark landing layout
-- (etl/spark/jobs/py/common/schemas.py). One SELECT per landing table; "-- landing:" names the PSV dir.
-- Columns without a defensible live equivalent are NULL and listed as unmapped.
-- FIRST FAILURE: USAGE_DAILY.AMOUNT (selected by SELECT *) has no live equivalent in billing__usage_daily
-- nor billing__stg_usage_daily. Failing statements: 01f1dd84-6b5e-14d4-a8dc-b1cd0ff4d07a, 01f1dd84-6bb5-1615-b6f6-f4f8be04d10a.
-- AMOUNT is left NULL (not derived) so the row/date-slice and rerun behaviour can still be measured.

-- landing: billing/USAGE_DAILY
/* run=dbx-d1111 act=spark step=inputs consumer=billing_usage_append_daily */
SELECT usage_id AS USAGE_ID, customer_id AS CUSTOMER_ID, usage_dt AS USAGE_DATE, units AS UNITS,
       CAST(NULL AS DECIMAL(18,2)) AS AMOUNT    -- unmapped: no usage amount live
FROM cpw.dbx_d1111_before.billing__usage_daily;
