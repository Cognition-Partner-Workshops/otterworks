{{ config(tags=['dq', 'dq_doc_search_api', 'dq_accepted_range']) }}

select window_end_date, account_id, item_type, rank, search_count, zero_result_count
from {{ ref('doc_search_api') }}
where search_count < 1 or search_count > 9999999999
    or zero_result_count < 0 or zero_result_count > search_count
    or account_id = ''
    or last_searched_at::date < dateadd(day, -27, window_end_date)
    or last_searched_at::date > window_end_date
