-- Replaces the Spark lake output documents/docs_storage_by_owner.
select
    u.USER_ID,
    u.EMAIL,
    count(*) as FILE_COUNT,
    sum(f.SIZE_BYTES) as SIZE_BYTES
from {{ source('spark_documents', 'DOCUMENT') }} d
join {{ source('spark_documents', 'FILE_OBJECT') }} f on d.DOCUMENT_ID = f.DOCUMENT_ID
join {{ source('spark_users', 'APP_USER') }} u on d.OWNER_USER_ID = u.USER_ID
group by u.USER_ID, u.EMAIL
