/* run=dbx-d1111 act=scale step=parity consumer=m_SFX_STG_APP_USER */
WITH p AS (SELECT user_id,display_name,email,status_cd,created_dt FROM cpw.dbx_d1111_parity.users__stg_app_user__pc_before),
    a AS (SELECT user_id,display_name,email,status_cd,created_dt FROM cpw.dbx_d1111_after.users__stg_app_user),
    p_minus_a AS (SELECT * FROM p EXCEPT ALL SELECT * FROM a),
    a_minus_p AS (SELECT * FROM a EXCEPT ALL SELECT * FROM p),
    ps AS (SELECT count(*) AS count, coalesce(sum(cast(conv(substr(md5(concat_ws('|',coalesce(cast(user_id as string),'<NULL>'),coalesce(cast(display_name as string),'<NULL>'),coalesce(cast(email as string),'<NULL>'),coalesce(cast(status_cd as string),'<NULL>'),coalesce(cast(created_dt as string),'<NULL>'))),1,15),16,10) AS DECIMAL(38,0))),0) AS hash FROM p), ats AS (SELECT count(*) AS count, coalesce(sum(cast(conv(substr(md5(concat_ws('|',coalesce(cast(user_id as string),'<NULL>'),coalesce(cast(display_name as string),'<NULL>'),coalesce(cast(email as string),'<NULL>'),coalesce(cast(status_cd as string),'<NULL>'),coalesce(cast(created_dt as string),'<NULL>'))),1,15),16,10) AS DECIMAL(38,0))),0) AS hash FROM a)
    SELECT ps.count AS pc_count,ats.count AS after_count,ps.hash AS pc_hash,ats.hash AS after_hash,
      (SELECT count(*) FROM p_minus_a) AS pc_minus_after,
      (SELECT count(*) FROM a_minus_p) AS after_minus_pc,
      (SELECT to_json(collect_list(named_struct('row',canonical))) FROM
        (SELECT concat_ws('|',coalesce(cast(user_id AS STRING),'<NULL>'),coalesce(cast(display_name AS STRING),'<NULL>'),coalesce(cast(email AS STRING),'<NULL>'),coalesce(cast(status_cd AS STRING),'<NULL>'),coalesce(cast(created_dt AS STRING),'<NULL>')) AS canonical FROM p_minus_a LIMIT 20)) AS pc_sample,
      (SELECT to_json(collect_list(named_struct('row',canonical))) FROM
        (SELECT concat_ws('|',coalesce(cast(user_id AS STRING),'<NULL>'),coalesce(cast(display_name AS STRING),'<NULL>'),coalesce(cast(email AS STRING),'<NULL>'),coalesce(cast(status_cd AS STRING),'<NULL>'),coalesce(cast(created_dt AS STRING),'<NULL>')) AS canonical FROM a_minus_p LIMIT 20)) AS after_sample
    FROM ps CROSS JOIN ats;
