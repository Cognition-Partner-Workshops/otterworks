{% set job = env_var('DOCUMENTS_SPARK_JOB', '') %}
{{ config(enabled=job != '') }}
select 'empty' as failure where false
{% if job in ['all', 'docs_storage_by_owner'] %}
union all
select 'storage_count' from {{ ref('spark_docs_storage_by_owner') }} where file_count <= 0
{% endif %}
{% if job in ['all', 'docs_share_activity'] %}
union all
select 'share_counts' from {{ ref('spark_docs_share_activity') }}
where shares <= 0 or recipients < 0 or recipients > shares
{% endif %}
{% if job in ['all', 'docs_folder_legacy_report'] %}
union all
select 'folder_counts' from {{ ref('spark_docs_folder_legacy_report') }} where documents < 0
{% endif %}
{% if job in ['all', 'docs_search_log_parse'] %}
union all
select 'parsed_action' from {{ ref('spark_docs_search_log_parse') }}
where parsed_action is not null and (parsed_action = '' or instr(raw_line, concat('action=', parsed_action)) = 0)
{% endif %}
{% if job in ['all', 'docs_tag_normalize'] %}
union all
select 'normalized_tag' from {{ ref('spark_docs_tag_normalize') }}
where normalized_tag is null or normalized_tag rlike r'(?U)\s'
{% endif %}
{% for name in ['docs_event_export_hourly', 'lake_compaction_documents'] %}
{% if job in ['all', name] %}
union all
select 'export_bucket' from {{ ref('spark_' ~ name) }}
where not (export_bucket <=> pmod(document_id, 10000))
{% endif %}
{% endfor %}
