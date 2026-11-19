{% set job = env_var('DOCUMENTS_SPARK_JOB', '') %}
{{ config(enabled=job in ['all', 'docs_folder_tree_walk', 'doc_share_graph_reach', 'collab_session_sessionize', 'doc_version_diff_stats', 'file_object_binary_extract']) }}
select 'empty' as failure where false
{% if job in ['all', 'docs_folder_tree_walk'] %}
union all
select 'folder_depth' from {{ ref('spark_docs_folder_tree_walk') }} where depth < 0 or depth > 20
{% endif %}
{% if job in ['all', 'doc_share_graph_reach'] %}
union all
select 'reach_distance' from {{ ref('spark_doc_share_graph_reach') }}
where distance < 0 or distance > 4 or (user_id = 1 and distance <> 0) or (distance = 0 and user_id <> 1)
{% endif %}
{% if job in ['all', 'collab_session_sessionize'] %}
union all
select 'session_bounds' from {{ ref('spark_collab_session_sessionize') }}
where session_number < 1 or end_at < start_at
union all
select 'session_key' from {{ ref('spark_collab_session_sessionize') }}
group by user_id, document_id, session_number having count(*) > 1
{% endif %}
{% if job in ['all', 'doc_version_diff_stats'] %}
union all
select 'similarity_range' from {{ ref('spark_doc_version_diff_stats') }} where similarity < 0 or similarity > 1
{% endif %}
{% if job in ['all', 'file_object_binary_extract'] %}
union all
select 'binary_contract' from {{ ref('spark_file_object_binary_extract') }}
where length(sha256) <> 64 or length(text) > 4096 or page_count < 0
or (error is not null and (media_type <> 'application/octet-stream' or text <> '' or page_count <> 0))
{% endif %}
