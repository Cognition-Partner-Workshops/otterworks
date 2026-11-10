"""Read-only, pipeline-scoped verification snapshots and tagged history."""
import argparse

from sf import connect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args()
    with connect("observe", "SFX_D1110_OPS_WH") as connection:
        with connection.cursor() as cursor:
            cursor.execute("""SELECT s.USAGE_DATE, COUNT(*) AS ROW_COUNT,
                COUNT_IF(s.AMOUNT IS NULL) AS NULL_AMOUNT,
                COUNT_IF(s.CURRENCY_CODE IS NULL) AS NULL_CURRENCY_CODE,
                COUNT_IF(s.CREATED_AT IS NULL) AS NULL_CREATED_AT
                FROM CORE_BILLING.STG_BILLING__USAGE_DAILY s
                JOIN RAW_BILLING.USAGE_DAILY r ON s.USAGE_ID=r.USAGE_ID
                WHERE r._SRC_FILE LIKE 'pipeline/%'
                GROUP BY 1 ORDER BY 1""")
            print([column[0] for column in cursor.description])
            for row in cursor.fetchall():
                print(row)
            if args.history:
                cursor.execute("""SELECT QUERY_ID, QUERY_TYPE, WAREHOUSE_NAME,
                    EXECUTION_STATUS, QUERY_TAG
                    FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(RESULT_LIMIT=>1000))
                    WHERE REPLACE(QUERY_TAG,' ','') LIKE '%"act":"operate"%'
                    AND QUERY_TYPE IN ('COPY','DELETE','REMOVE_FILES','SELECT','CREATE_VIEW')
                    QUALIFY ROW_NUMBER() OVER (
                        PARTITION BY TRY_PARSE_JSON(QUERY_TAG):step::STRING, QUERY_TYPE
                        ORDER BY START_TIME DESC)=1
                    ORDER BY START_TIME DESC""")
                print([column[0] for column in cursor.description])
                for row in cursor.fetchall():
                    print(row)


if __name__ == "__main__":
    main()
