{{ config(enabled=env_var('DOCUMENTS_SPARK_JOB', '') in ['all', 'file_object_binary_extract']) }}
select storage_key, file_object_id, document_id, size_bytes, checksum, media_type, text, page_count, sha256, error
from {{ source('documents_spark_runtime', 'spark_runtime_file_object_binary_extract') }}
where _business_date = '{{ env_var("BUSINESS_DATE") }}'
