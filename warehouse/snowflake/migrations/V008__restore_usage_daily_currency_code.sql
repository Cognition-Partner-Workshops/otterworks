-- Restores RAW_BILLING.USAGE_DAILY.CURRENCY_CODE to the V002 contract, CHAR(3).
-- Nightly drift sweep (sfx-d1110) found the live column widened to VARCHAR(10)
-- outside the migration history. Snowflake cannot narrow a VARCHAR in place, so the
-- column is rebuilt through a temporary column; the table, its COPY history and
-- Time Travel are kept. Rows whose CURRENCY_CODE exceeds three characters came from
-- an out-of-contract load and must be removed or replayed before this migration runs.
-- Every DDL statement autocommits, so the block reads the current column layout
-- first and resumes from whichever step an interrupted run reached.
EXECUTE IMMEDIATE $$
DECLARE
    declared_length INTEGER;
    rebuild_columns INTEGER;
    overlength_rows INTEGER;
    overlength_values EXCEPTION (-20110, 'sfx-d1110 V008: RAW_BILLING.USAGE_DAILY.CURRENCY_CODE holds values longer than three characters; remove or replay those rows, then redeploy');
BEGIN
    SELECT MAX(IFF(COLUMN_NAME = 'CURRENCY_CODE', CHARACTER_MAXIMUM_LENGTH, NULL)),
           COUNT_IF(COLUMN_NAME = 'CURRENCY_CODE_SFX_D1110')
    INTO :declared_length, :rebuild_columns
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'RAW_BILLING' AND TABLE_NAME = 'USAGE_DAILY'
      AND COLUMN_NAME IN ('CURRENCY_CODE', 'CURRENCY_CODE_SFX_D1110');
    IF (declared_length = 3 AND rebuild_columns = 0) THEN
        RETURN 'CURRENCY_CODE already matches CHAR(3)';
    END IF;
    IF (declared_length IS NULL AND rebuild_columns = 1) THEN
        ALTER TABLE RAW_BILLING.USAGE_DAILY RENAME COLUMN CURRENCY_CODE_SFX_D1110 TO CURRENCY_CODE;
        RETURN 'CURRENCY_CODE restored to CHAR(3) (resumed after DROP COLUMN)';
    END IF;
    SELECT COUNT(*) INTO :overlength_rows FROM RAW_BILLING.USAGE_DAILY WHERE LENGTH(CURRENCY_CODE) > 3;
    IF (overlength_rows > 0) THEN
        RAISE overlength_values;
    END IF;
    ALTER TABLE RAW_BILLING.USAGE_DAILY ADD COLUMN IF NOT EXISTS CURRENCY_CODE_SFX_D1110 CHAR(3) COMMENT 'sfx-d1110 V008 rebuild';
    UPDATE RAW_BILLING.USAGE_DAILY SET CURRENCY_CODE_SFX_D1110 = CURRENCY_CODE;
    ALTER TABLE RAW_BILLING.USAGE_DAILY DROP COLUMN CURRENCY_CODE;
    ALTER TABLE RAW_BILLING.USAGE_DAILY RENAME COLUMN CURRENCY_CODE_SFX_D1110 TO CURRENCY_CODE;
    RETURN 'CURRENCY_CODE restored to CHAR(3)';
END;
$$;
