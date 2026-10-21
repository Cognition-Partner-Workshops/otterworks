-- Builds the daily producer scorecard, one region at a time.
-- Regions with no feed for the day still get a region summary row.
CREATE PROCEDURE dw.usp_build_producer_scorecard
    @scorecard_date DATE,
    @region_list    NVARCHAR(200) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @region VARCHAR(4), @sql NVARCHAR(MAX), @rc INT, @merged INT;

    BEGIN TRY
        CREATE TABLE #scorecard_work (
            region_code     VARCHAR(4),
            producer_code   VARCHAR(10),
            producer_name   VARCHAR(80),
            agency_name     VARCHAR(80),
            tier_name       VARCHAR(20),
            policy_count    INT,
            claim_count     INT,
            written_premium DECIMAL(14,2),
            row_status      VARCHAR(10)
        ) WITH (DISTRIBUTION = ROUND_ROBIN, HEAP);

        DECLARE region_cur CURSOR LOCAL FAST_FORWARD FOR
            SELECT region_code
            FROM dw.dim_region
            WHERE @region_list IS NULL OR CHARINDEX(region_code, @region_list) > 0
            ORDER BY region_code;

        OPEN region_cur;
        FETCH NEXT FROM region_cur INTO @region;
        WHILE @@FETCH_STATUS = 0
        BEGIN
            SET @sql = N'
                INSERT INTO #scorecard_work
                SELECT f.region_code,
                       f.producer_code,
                       p.producer_name,
                       p.agency_name,
                       (SELECT TOP 1 t.tier_name
                          FROM dw.producer_tier t
                         WHERE t.producer_code = f.producer_code
                         ORDER BY t.tier_effective_date DESC),
                       SUM(f.policy_count),
                       SUM(f.claim_count),
                       SUM(f.written_premium),
                       ''PRODUCER''
                  FROM stg.producer_feed f
                  LEFT JOIN dw.dim_producer p ON p.producer_code = f.producer_code
                 WHERE f.region_code = @r AND f.feed_date = @d
                 GROUP BY f.region_code, f.producer_code, p.producer_name, p.agency_name';
            EXEC sp_executesql @sql, N'@r VARCHAR(4), @d DATE', @r = @region, @d = @scorecard_date;
            SET @rc = @@ROWCOUNT;

            INSERT INTO dw.etl_log (proc_name, step, rows_affected)
            VALUES ('usp_build_producer_scorecard', 'region ' + @region, @rc);

            INSERT INTO #scorecard_work (region_code, producer_code, policy_count, row_status)
            VALUES (@region, '~REGION', @rc, CASE WHEN @rc = 0 THEN 'NO_FEED' ELSE 'LOADED' END);

            FETCH NEXT FROM region_cur INTO @region;
        END
        CLOSE region_cur;
        DEALLOCATE region_cur;

        MERGE dw.producer_scorecard AS tgt
        USING #scorecard_work AS src
           ON tgt.scorecard_date = @scorecard_date
          AND tgt.region_code    = src.region_code
          AND tgt.producer_code  = src.producer_code
        WHEN MATCHED THEN UPDATE SET
             producer_name   = src.producer_name,
             agency_name     = src.agency_name,
             tier_name       = src.tier_name,
             policy_count    = src.policy_count,
             claim_count     = src.claim_count,
             written_premium = src.written_premium,
             row_status      = src.row_status
        WHEN NOT MATCHED BY TARGET THEN INSERT
             (scorecard_date, region_code, producer_code, producer_name, agency_name,
              tier_name, policy_count, claim_count, written_premium, row_status)
             VALUES (@scorecard_date, src.region_code, src.producer_code, src.producer_name,
                     src.agency_name, src.tier_name, src.policy_count, src.claim_count,
                     src.written_premium, src.row_status);
        SET @merged = @@ROWCOUNT;

        IF @merged = 0
            INSERT INTO dw.etl_log (proc_name, step, rows_affected)
            VALUES ('usp_build_producer_scorecard', 'nothing merged', 0);
        ELSE
            INSERT INTO dw.etl_log (proc_name, step, rows_affected)
            VALUES ('usp_build_producer_scorecard', 'merge', @merged);

        DROP TABLE #scorecard_work;
    END TRY
    BEGIN CATCH
        INSERT INTO dw.etl_log (proc_name, step, rows_affected)
        VALUES ('usp_build_producer_scorecard', LEFT('error: ' + ERROR_MESSAGE(), 40), NULL);
        THROW;
    END CATCH
END
GO
