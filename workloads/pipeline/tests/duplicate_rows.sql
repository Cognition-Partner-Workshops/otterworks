{{ config(tags=['doc_usage_dashboard']) }}
with input as (
 select column1::varchar as id,column2::date as _snapshot_date,column3::timestamp_ntz as _exported_at,
 column4::varchar as _row_hash,column5::number as used_bytes from values
 ('account','2026-11-02','2026-11-02 01:00:00','a',10),
 ('account','2026-11-02','2026-11-02 01:00:00','a',10),
 ('account','2026-11-02','2026-11-02 02:00:00','b',20),
 ('account','2026-11-02','2026-11-02 02:00:00','b',20)
), reconciled as ({{ latest_rows('input','id',true) }})
select 'duplicates or stale versions won reconciliation' as failure
where (select count(*) from reconciled)<>1 or (select sum(used_bytes) from reconciled)<>20
