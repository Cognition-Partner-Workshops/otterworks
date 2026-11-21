-- First-pass conversion output: dw.usp_build_producer_scorecard
CREATE OR REPLACE PROCEDURE DW.USP_BUILD_PRODUCER_SCORECARD(SCORECARD_DATE DATE, REGION_LIST VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
AS
$$
DECLARE
    sql_text VARCHAR;
    merged INT;
    region_cur CURSOR FOR
        SELECT region_code FROM DW.DIM_REGION
         WHERE ? IS NULL OR CHARINDEX(region_code, ?) > 0
         ORDER BY region_code;
BEGIN
    CREATE OR REPLACE TEMPORARY TABLE SCORECARD_WORK (
        region_code VARCHAR(4), producer_code VARCHAR(10), producer_name VARCHAR(80),
        agency_name VARCHAR(80), tier_name VARCHAR(20), policy_count INT, claim_count INT,
        written_premium NUMBER(14,2), row_status VARCHAR(10)
    -- FP-ERR 1004: table distribution and index options have no Snowflake equivalent; left as written
    ) WITH (DISTRIBUTION = ROUND_ROBIN, HEAP);

    OPEN region_cur USING (:REGION_LIST, :REGION_LIST);
    -- FP-WARN 2207: cursor FETCH loop rewritten to FOR ... IN cursor
    FOR rec IN region_cur DO
        LET region VARCHAR := rec.region_code;
        sql_text := '
            INSERT INTO SCORECARD_WORK
            SELECT f.region_code, f.producer_code, p.producer_name, p.agency_name, t.tier_name,
                   SUM(f.policy_count), SUM(f.claim_count), SUM(f.written_premium), ''PRODUCER''
              FROM STG.PRODUCER_FEED f
              LEFT JOIN DW.DIM_PRODUCER p ON p.producer_code = f.producer_code
              LEFT JOIN (SELECT producer_code, tier_name FROM DW.PRODUCER_TIER
                         -- FP-WARN 1120: TOP 1 rewritten to QUALIFY ROW_NUMBER()
                         QUALIFY ROW_NUMBER() OVER (PARTITION BY producer_code ORDER BY tier_effective_date DESC) = 1) t
                ON t.producer_code = f.producer_code
             WHERE f.region_code = ? AND f.feed_date = ?
             GROUP BY f.region_code, f.producer_code, p.producer_name, p.agency_name, t.tier_name';
        -- FP-WARN 2101: sp_executesql rewritten to EXECUTE IMMEDIATE ... USING; review bind order
        EXECUTE IMMEDIATE :sql_text USING (region, SCORECARD_DATE);

        INSERT INTO DW.ETL_LOG (proc_name, step, rows_affected)
        -- FP-WARN 2310: @@ROWCOUNT mapped to SQLROWCOUNT; review which statement it reads
        VALUES ('usp_build_producer_scorecard', 'region ' || :region, :SQLROWCOUNT);

        INSERT INTO SCORECARD_WORK (region_code, producer_code, policy_count, row_status)
        -- FP-WARN 2310: @@ROWCOUNT mapped to SQLROWCOUNT; review which statement it reads
        VALUES (:region, '~REGION', :SQLROWCOUNT, IFF(:SQLROWCOUNT = 0, 'NO_FEED', 'LOADED'));
    END FOR;

    MERGE INTO DW.PRODUCER_SCORECARD tgt
    USING SCORECARD_WORK src
       ON tgt.scorecard_date = :SCORECARD_DATE
      AND tgt.region_code = src.region_code
      AND tgt.producer_code = src.producer_code
    WHEN MATCHED THEN UPDATE SET
         producer_name = src.producer_name, agency_name = src.agency_name, tier_name = src.tier_name,
         policy_count = src.policy_count, claim_count = src.claim_count,
         written_premium = src.written_premium, row_status = src.row_status
    WHEN NOT MATCHED THEN INSERT
         (scorecard_date, region_code, producer_code, producer_name, agency_name, tier_name,
          policy_count, claim_count, written_premium, row_status)
         VALUES (:SCORECARD_DATE, src.region_code, src.producer_code, src.producer_name, src.agency_name,
                 src.tier_name, src.policy_count, src.claim_count, src.written_premium, src.row_status);
    -- FP-WARN 2310: @@ROWCOUNT mapped to SQLROWCOUNT; review which statement it reads
    merged := SQLROWCOUNT;

    IF (merged = 0) THEN
        INSERT INTO DW.ETL_LOG (proc_name, step, rows_affected) VALUES ('usp_build_producer_scorecard', 'nothing merged', 0);
    ELSE
        INSERT INTO DW.ETL_LOG (proc_name, step, rows_affected) VALUES ('usp_build_producer_scorecard', 'merge', :merged);
    END IF;

    DROP TABLE IF EXISTS SCORECARD_WORK;
    RETURN 'merged ' || merged;
EXCEPTION
    WHEN OTHER THEN
        INSERT INTO DW.ETL_LOG (proc_name, step, rows_affected)
        VALUES ('usp_build_producer_scorecard', LEFT('error: ' || :SQLERRM, 40), NULL);
        RAISE;
END;
$$;
