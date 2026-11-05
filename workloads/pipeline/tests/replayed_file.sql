{{ config(tags=['doc_usage_dashboard']) }}
with original as (
 select 'account' as id,'2026-11-02'::date as _snapshot_date,'2026-11-02 01:00:00'::timestamp_ntz as _exported_at,
 'hash' as _row_hash,4563402752::number(19,0) as used_bytes
), reloaded as (
 select * from original union all select * from original union all select * from original
), reconciled as ({{ latest_rows('reloaded','id',true) }})
select 'replayed file changed its logical row' as failure
where (select count(*) from reconciled)<>1
or (select sum(used_bytes) from reconciled)<>4563402752
