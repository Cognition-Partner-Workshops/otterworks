#!/usr/bin/env python3
from insurance_connection import connect, prepare


def main():
    with connect() as conn, conn.cursor() as cursor:
        prepare(cursor, """CREATE TABLE claims_payment_daily_summary (
            pol_cd_x VARCHAR2(12), payment_count NUMBER, payment_total NUMBER(18,4))""")
        cursor.execute("DELETE FROM claims_payment_daily_summary")
        cursor.execute("""INSERT INTO claims_payment_daily_summary
            SELECT p.pol_cd_x, COUNT(*), SUM(f.pay_amt)
              FROM fact_claim_payment f JOIN dim_claim c ON c.clm_id=f.clm_id
              JOIN dim_policy p ON p.pol_id=c.pol_id
             GROUP BY p.pol_cd_x""")
        conn.commit()
        print("Daily claims payment summary complete")


if __name__ == "__main__":
    main()
