#!/usr/bin/env python3
from insurance_connection import connect, prepare


def main():
    with connect() as conn, conn.cursor() as cursor:
        prepare(cursor, """CREATE TABLE agent_territory_snapshot (
            snapshot_dt DATE, ag_cd VARCHAR2(16), territory_cd VARCHAR2(12), pol_count NUMBER)""")
        cursor.execute("DELETE FROM agent_territory_snapshot")
        cursor.execute("""INSERT INTO agent_territory_snapshot
            SELECT TRUNC(SYSDATE), ag_cd, pol_cd_x, COUNT(*)
              FROM dim_policy GROUP BY ag_cd, pol_cd_x""")
        conn.commit()
        print("Agent territory snapshot complete")


if __name__ == "__main__":
    main()
