{{ config(tags=['dq', 'dq_doc_search_api', 'dq_freshness']) }}

-- The spec keeps only eligible searches; an export with none must not invent an output row.
with expected_items as (
    {{ dq_doc_search_api_expected_items() }}
), expected as (
    select max(window_end_date) as expected_window from expected_items
), actual as (
    select max(window_end_date) as actual_window from {{ ref('doc_search_api') }}
)
select expected_window, actual_window from expected cross join actual
where expected_window is not null and (actual_window is null or actual_window < expected_window)
