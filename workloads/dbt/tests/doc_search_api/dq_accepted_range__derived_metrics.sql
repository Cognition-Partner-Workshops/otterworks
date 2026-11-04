{{ config(tags=['dq', 'dq_doc_search_api', 'dq_accepted_range']) }}

with expected as (
    {{ dq_doc_search_api_expected_items() }}
), actual as (
    select * from {{ ref('doc_search_api') }}
)
select coalesce(e.window_end_date, a.window_end_date) as window_end_date,
    coalesce(e.account_id, a.account_id) as account_id,
    coalesce(e.item_type, a.item_type) as item_type, coalesce(e.rank, a.rank) as rank,
    e.search_count as expected_search_count, a.search_count as actual_search_count,
    e.zero_result_count as expected_zero_count, a.zero_result_count as actual_zero_count
from expected e full outer join actual a
    on e.window_end_date = a.window_end_date and e.account_id = a.account_id
    and e.item_type = a.item_type and e.rank = a.rank
where e.window_end_date is null or a.window_end_date is null
    or not equal_null(e.term, a.term)
    or not equal_null(e.document_id, a.document_id)
    or not equal_null(e.document_title, a.document_title)
    or not equal_null(e.search_count, a.search_count)
    or not equal_null(e.zero_result_count, a.zero_result_count)
    or not equal_null(e.last_searched_at, a.last_searched_at)
