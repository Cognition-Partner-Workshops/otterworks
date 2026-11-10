-- The legacy log appends a row per call; the latest run per model and date is the answer.
select
    BUSINESS_DATE as business_date,
    'usp_' || STEP_NAME as object_name,
    'procedure' as object_type,
    iff(STATUS = 'SUCCESS', 'succeeded', 'failed') as status,
    ROW_COUNT as rows_written
from {{ target.database }}.OPS.ETL_RUN_LOG
where JOB_NAME = 'dbt'
qualify row_number() over (partition by BUSINESS_DATE, STEP_NAME order by COMPLETED_AT desc) = 1
