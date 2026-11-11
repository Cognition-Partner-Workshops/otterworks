/* run=dbx-d1111 act=scale step=parity consumer=m_SFX_DOC_SHARE */
WITH p AS (SELECT share_id,document_id,user_id,access_level,shared_dt FROM cpw.dbx_d1111_parity.documents__doc_share__pc_before),
    a AS (SELECT share_id,document_id,user_id,access_level,shared_dt FROM cpw.dbx_d1111_after.documents__doc_share),
    p_minus_a AS (SELECT * FROM p EXCEPT ALL SELECT * FROM a),
    a_minus_p AS (SELECT * FROM a EXCEPT ALL SELECT * FROM p),
    ps AS (SELECT count(*) AS count, coalesce(sum(cast(conv(substr(md5(concat_ws('|',coalesce(cast(share_id as string),'<NULL>'),coalesce(cast(document_id as string),'<NULL>'),coalesce(cast(user_id as string),'<NULL>'),coalesce(cast(access_level as string),'<NULL>'),coalesce(cast(shared_dt as string),'<NULL>'))),1,15),16,10) AS DECIMAL(38,0))),0) AS hash FROM p), ats AS (SELECT count(*) AS count, coalesce(sum(cast(conv(substr(md5(concat_ws('|',coalesce(cast(share_id as string),'<NULL>'),coalesce(cast(document_id as string),'<NULL>'),coalesce(cast(user_id as string),'<NULL>'),coalesce(cast(access_level as string),'<NULL>'),coalesce(cast(shared_dt as string),'<NULL>'))),1,15),16,10) AS DECIMAL(38,0))),0) AS hash FROM a)
    SELECT ps.count AS pc_count,ats.count AS after_count,ps.hash AS pc_hash,ats.hash AS after_hash,
      (SELECT count(*) FROM p_minus_a) AS pc_minus_after,
      (SELECT count(*) FROM a_minus_p) AS after_minus_pc,
      (SELECT to_json(collect_list(named_struct('row',canonical))) FROM
        (SELECT concat_ws('|',coalesce(cast(share_id AS STRING),'<NULL>'),coalesce(cast(document_id AS STRING),'<NULL>'),coalesce(cast(user_id AS STRING),'<NULL>'),coalesce(cast(access_level AS STRING),'<NULL>'),coalesce(cast(shared_dt AS STRING),'<NULL>')) AS canonical FROM p_minus_a LIMIT 20)) AS pc_sample,
      (SELECT to_json(collect_list(named_struct('row',canonical))) FROM
        (SELECT concat_ws('|',coalesce(cast(share_id AS STRING),'<NULL>'),coalesce(cast(document_id AS STRING),'<NULL>'),coalesce(cast(user_id AS STRING),'<NULL>'),coalesce(cast(access_level AS STRING),'<NULL>'),coalesce(cast(shared_dt AS STRING),'<NULL>')) AS canonical FROM a_minus_p LIMIT 20)) AS after_sample
    FROM ps CROSS JOIN ats;
