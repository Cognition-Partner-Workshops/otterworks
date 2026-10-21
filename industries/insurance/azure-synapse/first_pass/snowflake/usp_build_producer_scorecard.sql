CREATE OR REPLACE PROCEDURE DW.USP_BUILD_PRODUCER_SCORECARD(SCORECARD_DATE DATE, REGION_LIST VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
DECLARE
    region VARCHAR(4);
    sql_text VARCHAR;
    rc INT;
    merged INT;
    err_msg VARCHAR;
    regions RESULTSET;
BEGIN
    CREATE OR REPLACE TEMPORARY TABLE DW.SCORECARD_WORK (
        region_code     VARCHAR(4),
        producer_code   VARCHAR(10),
        producer_name   VARCHAR(80),
        agency_name     VARCHAR(80),
        tier_name       VARCHAR(20),
        policy_count    INT,
        claim_count     INT,
        written_premium NUMBER(14,2),
        row_status      VARCHAR(10)
    );

    regions := (SELECT region_code
                  FROM DW.DIM_REGION
                 WHERE :REGION_LIST IS NULL OR CHARINDEX(UPPER(region_code), UPPER(:REGION_LIST)) > 0
                 ORDER BY region_code);
    LET region_cur CURSOR FOR regions;

    FOR rec IN region_cur DO
        region := rec.region_code;
        sql_text := '
            INSERT INTO DW.SCORECARD_WORK
            SELECT MIN_BY(f.region_code, f.feed_id),
                   MIN_BY(f.producer_code, f.feed_id),
                   p.producer_name,
                   p.agency_name,
                   t.tier_name,
                   SUM(f.policy_count),
                   SUM(f.claim_count),
                   SUM(f.written_premium),
                   ''PRODUCER''
              FROM STG.PRODUCER_FEED f
              LEFT JOIN DW.DIM_PRODUCER p ON UPPER(p.producer_code) = UPPER(f.producer_code)
              LEFT JOIN (SELECT producer_code, tier_name
                           FROM DW.PRODUCER_TIER
                         QUALIFY ROW_NUMBER() OVER (PARTITION BY UPPER(producer_code)
                                                    ORDER BY tier_effective_date DESC NULLS LAST) = 1) t
                ON UPPER(t.producer_code) = UPPER(f.producer_code)
             WHERE UPPER(f.region_code) = UPPER(?) AND f.feed_date = ?
             GROUP BY UPPER(f.region_code), UPPER(f.producer_code), p.producer_name, p.agency_name, t.tier_name';
        EXECUTE IMMEDIATE :sql_text USING (region, SCORECARD_DATE);
        rc := SQLROWCOUNT;

        INSERT INTO DW.ETL_LOG (proc_name, step, rows_affected)
        VALUES ('usp_build_producer_scorecard', 'region ' || :region, :rc);

        INSERT INTO DW.SCORECARD_WORK (region_code, producer_code, policy_count, row_status)
        VALUES (:region, '~REGION', :rc, IFF(:rc = 0, 'NO_FEED', 'LOADED'));
    END FOR;

    MERGE INTO DW.PRODUCER_SCORECARD tgt
    USING DW.SCORECARD_WORK src
       ON tgt.scorecard_date = :SCORECARD_DATE
      AND UPPER(tgt.region_code) = UPPER(src.region_code)
      AND UPPER(tgt.producer_code) = UPPER(src.producer_code)
    WHEN MATCHED THEN UPDATE SET
         producer_name   = src.producer_name,
         agency_name     = src.agency_name,
         tier_name       = src.tier_name,
         policy_count    = src.policy_count,
         claim_count     = src.claim_count,
         written_premium = src.written_premium,
         row_status      = src.row_status
    WHEN NOT MATCHED THEN INSERT
         (scorecard_date, region_code, producer_code, producer_name, agency_name,
          tier_name, policy_count, claim_count, written_premium, row_status)
         VALUES (:SCORECARD_DATE, src.region_code, src.producer_code, src.producer_name,
                 src.agency_name, src.tier_name, src.policy_count, src.claim_count,
                 src.written_premium, src.row_status);
    merged := SQLROWCOUNT;

    IF (merged = 0) THEN
        INSERT INTO DW.ETL_LOG (proc_name, step, rows_affected)
        VALUES ('usp_build_producer_scorecard', 'nothing merged', 0);
    ELSE
        INSERT INTO DW.ETL_LOG (proc_name, step, rows_affected)
        VALUES ('usp_build_producer_scorecard', 'merge', :merged);
    END IF;

    DROP TABLE IF EXISTS DW.SCORECARD_WORK;
    RETURN 'merged ' || merged;
EXCEPTION
    WHEN OTHER THEN
        err_msg := LEFT('error: ' || SQLERRM, 40);
        INSERT INTO DW.ETL_LOG (proc_name, step, rows_affected)
        VALUES ('usp_build_producer_scorecard', :err_msg, NULL);
        DROP TABLE IF EXISTS DW.SCORECARD_WORK;
        RAISE;
END;
$$;
