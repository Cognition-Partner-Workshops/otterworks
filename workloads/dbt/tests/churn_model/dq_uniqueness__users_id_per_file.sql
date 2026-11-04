{{ config(tags=['dq', 'dq_churn_model', 'dq_uniqueness']) }}
-- RAW inputs in the churn_model dev database are SYNTHETIC pipeline exports (workloads/pipeline/pipeline.py export).
-- Source key id must be unique inside each export file of RAW.AUTH_USERS. A whole file replayed under
-- another name is expected (the key includes _file_name); a duplicate inside one file is an export defect.
select _file_name, id, count(*) as copies
from {{ source('raw_churn_model', 'AUTH_USERS') }}
group by 1, 2
having count(*) > 1
