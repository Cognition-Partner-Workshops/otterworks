#!/usr/bin/env python3
from insurance_connection import connect, prepare


def main():
    with connect() as conn, conn.cursor() as cursor:
        prepare(cursor, """CREATE TABLE claims_payment_weekly_summary (
            pol_cd_x VARCHAR2(12), payment_count NUMBER, payment_total NUMBER(18,4))""")
        cursor.execute("DELETE FROM claims_payment_weekly_summary")
        cursor.execute("""INSERT INTO claims_payment_weekly_summary
            SELECT p.pol_cd_x, SUM(c.pay_count), SUM(c.pay_amt)
              FROM (SELECT clm_id, COUNT(*) pay_count, SUM(pay_amt) pay_amt
                      FROM fact_claim_payment GROUP BY clm_id) c,
                   dim_claim d, dim_policy p
             WHERE c.clm_id=d.clm_id AND d.pol_id=p.pol_id
             GROUP BY p.pol_cd_x""")
        conn.commit()
        print("Weekly claims payment summary complete")


if __name__ == "__main__":
    main()
