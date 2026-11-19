{{ config(materialized='ephemeral') }}
select cast(20000000001 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_users', 'app_user') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_input_app_user') }}) as target_count
union all
select cast(20000000002 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_users', 'user_profile') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_input_user_profile') }}) as target_count
union all
select cast(20000000003 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_users', 'team') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_input_team') }}) as target_count
union all
select cast(20000000004 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_users', 'team_member') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_input_team_member') }}) as target_count
union all
select cast(20000000005 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_users', 'role_grant') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_input_role_grant') }}) as target_count
union all
select cast(20000000006 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_users', 'sso_identity') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_input_sso_identity') }}) as target_count
union all
select cast(20000000007 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_users', 'user_status_hist') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_input_user_status_hist') }}) as target_count
union all
select cast(20000000008 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_users', 'login_event') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_input_login_event') }}) as target_count
union all
select cast(20000000009 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_users', 'user_activity_daily') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_users_activity') }}) as target_count
union all
select cast(20000000010 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_billing', 'customer_account') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('customer_account') }}) as target_count
union all
select cast(20000000011 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_billing', 'plan_catalog') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_input_plan_catalog') }}) as target_count
union all
select cast(20000000012 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_billing', 'tax_rate') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_input_tax_rate') }}) as target_count
union all
select cast(20000000013 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_billing', 'subscription') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_input_subscription') }}) as target_count
union all
select cast(20000000014 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_billing', 'invoice_hdr') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_input_invoice_hdr') }}) as target_count
union all
select cast(20000000015 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_billing', 'invoice_line') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_invoice_line_keys') }}) as target_count
union all
select cast(20000000016 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_billing', 'payment') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_input_payment') }}) as target_count
union all
select cast(20000000017 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_billing', 'credit_note') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_input_credit_note') }}) as target_count
union all
select cast(20000000018 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_billing', 'billing_adj') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_input_billing_adj') }}) as target_count
union all
select cast(20000000019 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_billing', 'usage_daily') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_usage_keys') }}) as target_count
union all
select cast(20000000020 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_documents', 'folder') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_input_folder') }}) as target_count
union all
select cast(20000000021 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_documents', 'document') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_input_document') }}) as target_count
union all
select cast(20000000022 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_documents', 'doc_version') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_doc_versions') }}) as target_count
union all
select cast(20000000023 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_documents', 'doc_share') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_input_doc_share') }}) as target_count
union all
select cast(20000000024 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_documents', 'doc_tag') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_input_doc_tag') }}) as target_count
union all
select cast(20000000025 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_documents', 'file_object') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_input_file_object') }}) as target_count
union all
select cast(20000000026 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_documents', 'doc_comment') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_input_doc_comment') }}) as target_count
union all
select cast(20000000027 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_documents', 'collab_session') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_input_collab_session') }}) as target_count
union all
select cast(20000000028 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_documents', 'storage_usage_daily') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_input_storage_usage_daily') }}) as target_count
union all
select cast(20000000029 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_audit', 'audit_event') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_event') }}) as target_count
union all
select cast(20000000030 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_audit', 'access_review') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('access_review') }}) as target_count
union all
select cast(20000000031 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_audit', 'retention_policy') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('retention_policy') }}) as target_count
union all
select cast(20000000032 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_audit', 'data_export_req') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('data_export_req') }}) as target_count
union all
select cast(20000000033 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_audit', 'compliance_flag') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('compliance_flag') }}) as target_count
union all
select cast(20000000034 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_audit', 'security_alert') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('security_alert') }}) as target_count
union all
select cast(20000000035 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_audit', 'legal_hold') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('legal_hold') }}) as target_count
union all
select cast(20000000036 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_audit', 'audit_daily_summary') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_summary_final') }}) as target_count
union all
select cast(20000000037 as bigint) as recon_id,
    (select count(*) from {{ source('bronze_audit', 'audit_recon') }} where _business_date = to_date('{{ env_var("BUSINESS_DATE") }}', 'yyyyMMdd')) as source_count,
    (select count(*) from {{ ref('audit_recon') }} where recon_id < 10000000000) as target_count
