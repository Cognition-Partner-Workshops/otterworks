-- The three product examples (and all 39 original accounts) stay unchanged.
INSERT INTO users
SELECT md5('SFEXT_20261105A:customer:' || i)::uuid,
 'customer' || i || '@example.invalid', 'not-a-credential', 'Customer ' || i,
 '2026-01-01', '2026-11-01', '2026-10-31T12:00:00Z'
FROM generate_series(1,1961) i ON CONFLICT DO NOTHING;
INSERT INTO admin_users
SELECT id,email,display_name,'active',created_at,updated_at FROM users
ON CONFLICT DO NOTHING;
INSERT INTO storage_quotas
SELECT id,5368709120,(('x' || substr(md5(id::text),1,7))::bit(28)::bigint),
 'free','2026-01-01','2026-11-01' FROM users ON CONFLICT DO NOTHING;
INSERT INTO documents
SELECT md5('SFEXT_20261105A:document:' || i)::uuid,'Generated document ' || i,
 md5('SFEXT_20261105A:customer:' || (1+(i-1)%1961))::uuid,false,false
FROM generate_series(1,49906) i ON CONFLICT DO NOTHING;
INSERT INTO document_versions
SELECT md5(id::text || ':v1')::uuid,id,1,title,'',owner_id,'2026-10-28T12:00:00Z'
FROM documents WHERE title LIKE 'Generated document %' ON CONFLICT DO NOTHING;
INSERT INTO analytics_events
SELECT md5('SFEXT_20261105A:search:' || i),'search.performed',
 '00000000-0000-4000-8000-000000000101',NULL,'search',
 json_build_object('query',CASE i WHEN 1 THEN 'Quarterly Report' WHEN 2 THEN 'quarterly  report ' ELSE 'budget' END,
 'result_count',CASE i WHEN 1 THEN '2' WHEN 2 THEN '1' ELSE '0' END,
 'document_hit_ids',CASE i WHEN 1 THEN '03ebe472-1e21-9b1c-20c5-18a0d26cbe6f,b48e999f-7174-4107-671b-e06d8e9abf30'
 WHEN 2 THEN '03ebe472-1e21-9b1c-20c5-18a0d26cbe6f' ELSE '' END)::text,
 (extract(epoch FROM CASE i WHEN 1 THEN '2026-10-20T10:00:00Z'::timestamptz
 WHEN 2 THEN '2026-10-25T09:00:00Z'::timestamptz WHEN 3 THEN '2026-10-30T15:00:00Z'::timestamptz
 ELSE '2026-09-01T12:00:00Z'::timestamptz END)*1000000000)::bigint
FROM generate_series(1,4) i ON CONFLICT DO NOTHING;
