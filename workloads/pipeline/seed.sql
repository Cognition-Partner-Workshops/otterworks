-- Do not run proof/masking_side_by_side.py on this fixture: its cleanup deletes these account IDs.
SET TIME ZONE 'UTC';
INSERT INTO users (id,email,password_hash,display_name,created_at,updated_at,last_login_at)
SELECT ('00000000-0000-4000-8000-' || lpad(i::text,12,'0'))::uuid,
 CASE i WHEN 101 THEN 'ada' WHEN 102 THEN 'ben' WHEN 103 THEN 'cy' ELSE 'synthetic' || i END || '@example.com',
 'not-a-credential', 'Synthetic ' || i, '2026-01-01', '2026-11-01',
 CASE i WHEN 101 THEN '2026-09-25T18:00:00Z'::timestamptz
 WHEN 102 THEN '2026-10-17T09:30:00Z'::timestamptz ELSE '2026-10-31T22:15:00Z'::timestamptz END
FROM generate_series(101,139) i;
INSERT INTO admin_users (id,email,display_name,status,created_at,updated_at)
SELECT id,email,display_name,CASE WHEN right(id::text,3)='103' THEN 'suspended' ELSE 'active' END,created_at,updated_at FROM users;
INSERT INTO storage_quotas (user_id,quota_bytes,used_bytes,tier,created_at,updated_at)
SELECT id,CASE right(id::text,3) WHEN '102' THEN 214748364800 WHEN '103' THEN 53687091200 ELSE 5368709120 END,
 CASE right(id::text,3) WHEN '101' THEN 4563402752 WHEN '102' THEN 53687091200 WHEN '103' THEN 53687091200 ELSE 1000000 END,
 CASE right(id::text,3) WHEN '102' THEN 'pro' WHEN '103' THEN 'basic' ELSE 'free' END,'2026-01-01','2026-11-01' FROM users;
INSERT INTO documents (id,title,owner_id,is_deleted,is_template)
SELECT md5(u.id::text || ':' || n)::uuid,'Synthetic document ' || n,u.id,
 right(u.id::text,3)='101' AND n=4, right(u.id::text,3)='103' AND n>40
FROM users u CROSS JOIN LATERAL generate_series(1,CASE right(u.id::text,3) WHEN '101' THEN 4 WHEN '102' THEN 12 WHEN '103' THEN 42 ELSE 1 END) n;
INSERT INTO document_versions (id,document_id,version_number,title,content,created_by,created_at)
SELECT md5(u.id::text || ':version:' || n)::uuid,
 (SELECT min(d.id::text)::uuid FROM documents d WHERE d.owner_id=u.id),n,'Synthetic revision','',u.id,
 CASE WHEN n <= CASE WHEN right(u.id::text,3)='101' THEN 20 ELSE 8 END
 THEN '2026-10-10'::timestamptz ELSE '2026-10-28'::timestamptz END
FROM users u CROSS JOIN LATERAL generate_series(1,CASE right(u.id::text,3) WHEN '101' THEN 21 WHEN '103' THEN 11 ELSE 9 END) n;
INSERT INTO analytics_events (event_id,event_type,user_id,resource_id,resource_type,occurred_at)
SELECT id::text,'user.logged_in',id::text,id::text,'user',1793448000000000000 FROM users;
