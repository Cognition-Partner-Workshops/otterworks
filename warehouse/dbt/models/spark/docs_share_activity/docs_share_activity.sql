-- Replaces the Spark lake output documents/docs_share_activity.
select
    d.OWNER_USER_ID,
    s.PERMISSION,
    count(*) as SHARES,
    count(distinct s.SHARED_WITH_USER_ID) as RECIPIENTS
from {{ source('spark_documents', 'DOC_SHARE') }} s
join {{ source('spark_documents', 'DOCUMENT') }} d on s.DOCUMENT_ID = d.DOCUMENT_ID
group by d.OWNER_USER_ID, s.PERMISSION
