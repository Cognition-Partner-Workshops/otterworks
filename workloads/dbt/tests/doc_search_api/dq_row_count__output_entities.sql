{{ config(tags=['dq', 'dq_doc_search_api', 'dq_row_count']) }}

with expected_items as (
    {{ dq_doc_search_api_expected_items() }}
), expected as (
    select window_end_date, account_id, item_type, count(*) as expected_count
    from expected_items group by 1, 2, 3
), actual as (
    select window_end_date, account_id, item_type, count(*) as actual_count
    from {{ ref('doc_search_api') }} group by 1, 2, 3
)
select coalesce(e.window_end_date, a.window_end_date) as window_end_date,
    coalesce(e.account_id, a.account_id) as account_id,
    coalesce(e.item_type, a.item_type) as item_type,
    coalesce(expected_count, 0) as expected_count, coalesce(actual_count, 0) as actual_count
from expected e full outer join actual a
    on e.window_end_date = a.window_end_date and e.account_id = a.account_id and e.item_type = a.item_type
where coalesce(expected_count, 0) <> coalesce(actual_count, 0)
