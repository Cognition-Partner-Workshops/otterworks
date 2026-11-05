{{ config(tags=['doc_usage_dashboard']) }}
select 'storage' as model from {{ ref('account_storage_usage') }}
group by snapshot_date,account_id having count(*)<>1 or snapshot_date is null or account_id is null
union all
select 'search' from {{ ref('top_search_items') }}
group by window_end_date,account_id,item_type,rank
having count(*)<>1 or window_end_date is null or account_id is null or item_type is null or rank is null
union all
select 'churn' from {{ ref('weekly_churn_scores') }}
group by week_start_date,account_id having count(*)<>1 or week_start_date is null or account_id is null
