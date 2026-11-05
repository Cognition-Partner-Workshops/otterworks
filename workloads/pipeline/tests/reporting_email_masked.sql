{{ config(tags=['doc_usage_dashboard']) }}
select account_id from {{ ref('account_storage_usage') }}
where not is_role_in_session('{{ var("run_token") }}_ANALYST')
and account_email <> '***MASKED***'
