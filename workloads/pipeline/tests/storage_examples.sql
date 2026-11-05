{{ config(tags=['doc_usage_dashboard']) }}
with expected as (
 select column1::date as snapshot_date, column2::varchar(36) as account_id,
 case when is_role_in_session('{{ var("run_token") }}_ANALYST') then column3 else '***MASKED***' end::varchar(255) as account_email,
 column4::varchar(16) as tier,column5::number(19,0) as quota_bytes,column6::number(19,0) as used_bytes,
 column7::number(19,0) as remaining_bytes,column8::number(7,2) as usage_pct,column9::varchar(16) as usage_band,
 column10::number(10,0) as active_document_count from values
 ('2026-11-02','00000000-0000-4000-8000-000000000101','ada@example.com','free',5368709120,4563402752,805306368,85.00,'near_limit',3),
 ('2026-11-02','00000000-0000-4000-8000-000000000102','ben@example.com','pro',214748364800,53687091200,161061273600,25.00,'ok',12),
 ('2026-11-02','00000000-0000-4000-8000-000000000103','cy@example.com','basic',53687091200,53687091200,0,100.00,'over_quota',40)
), actual as (
 select * from {{ ref('account_storage_usage') }} where snapshot_date='2026-11-02' and account_id in (select account_id from expected)
)
(select * from actual minus select * from expected) union all
(select * from expected minus select * from actual)
