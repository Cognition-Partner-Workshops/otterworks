{{ config(tags=['dq', 'dq_doc_search_api', 'dq_accepted_range']) }}

select window_end_date, account_id, item_type, rank from {{ ref('doc_search_api') }}
where (item_type = 'document' and (
        term is not null or zero_result_count is not null
        or document_id is null
    ))
    or (item_type = 'term' and (
        document_id is not null or document_title is not null
        or term is null or zero_result_count is null
        or term in ('', '*') or term <> lower(trim(regexp_replace(term, '\\s+', ' ')))
    ))
