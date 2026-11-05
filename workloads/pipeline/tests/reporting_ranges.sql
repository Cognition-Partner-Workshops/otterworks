{{ config(tags=['doc_usage_dashboard']) }}
select 'storage' as model from {{ ref('account_storage_usage') }}
where remaining_bytes<0 or active_document_count<0 or usage_band not in ('no_quota','near_limit','over_quota','ok')
union all
select 'search' from {{ ref('top_search_items') }}
where rank not between 1 and 10 or window_days<>28 or search_count<1 or item_type not in ('term','document')
union all
select 'churn' from {{ ref('weekly_churn_scores') }}
where churn_score not between 0 and 100 or model_version<>'rules_v1'
