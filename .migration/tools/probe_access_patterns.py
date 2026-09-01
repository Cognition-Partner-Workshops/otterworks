"""Read-only evidence probes backing the modeling decisions in 03_mapping_spec.md.

Answers, with counts rather than assertions: which wide-table columns actually carry data
(the proposed-unused bucket), what the EAV attribute set looks like, how the repeating
groups are populated, and the exact anomaly counts recon must reproduce.

Sequential by construction: one query at a time, honouring the STOP A source-load cap of 1.
"""

import json
import os
import pathlib
import sys

import oracledb

OUT = pathlib.Path(__file__).resolve().parents[1] / "census" / "access_patterns.json"
CENSUS = pathlib.Path(__file__).resolve().parents[1] / "census"


def main():
    dsn = os.environ.get("OW_ORACLE_BILLING_DSN")
    if not dsn:
        sys.exit("OW_ORACLE_BILLING_DSN is not set")
    user, _, rest = dsn.partition("/")
    password, _, conn_str = rest.partition("@")

    cols = json.loads((CENSUS / "columns.json").read_text())
    cm_cols = [c["column_name"] for c in cols if c["table_name"] == "CUSTOMER_MASTER"]

    ev = {}
    with oracledb.connect(user=user, password=password, dsn=conn_str) as con, con.cursor() as cur:
        # 1. population census of every CUSTOMER_MASTER column (one pass, not 155 queries)
        sel = ", ".join(f'COUNT("{c}")' for c in cm_cols)
        cur.execute(f"SELECT COUNT(*), {sel} FROM customer_master")
        row = cur.fetchone()
        total, counts = row[0], row[1:]
        ev["customer_master_population"] = {
            "total_rows": total,
            "non_null_by_column": dict(zip(cm_cols, counts)),
            "always_null_columns": [c for c, n in zip(cm_cols, counts) if n == 0],
        }

        # 2. EAV shape: which attributes exist, on what entity types, and their types
        cur.execute("""
            SELECT entity_type, attr_name, attr_type, COUNT(*) AS n,
                   COUNT(DISTINCT entity_id) AS entities
            FROM entity_attr_value GROUP BY entity_type, attr_name, attr_type
            ORDER BY entity_type, attr_name
        """)
        ev["eav_attributes"] = [
            dict(zip(("entity_type", "attr_name", "attr_type", "n", "entities"), r))
            for r in cur
        ]
        cur.execute("""
            SELECT MAX(cnt) FROM (
              SELECT entity_id, attr_name, COUNT(*) cnt FROM entity_attr_value
              GROUP BY entity_id, attr_name)
        """)
        ev["eav_max_rows_per_entity_attr"] = cur.fetchone()[0]
        cur.execute("""
            SELECT COUNT(*) FROM entity_attr_value e
            WHERE e.entity_type = 'CUSTOMER'
              AND NOT EXISTS (SELECT 1 FROM customer_master c WHERE c.cust_id = e.entity_id)
        """)
        ev["eav_orphans"] = cur.fetchone()[0]

        # 3. anomaly ledger: exact counts the recon harness must reproduce
        cur.execute("""
            SELECT COUNT(*) FROM invoice_line l
            WHERE NOT EXISTS (SELECT 1 FROM invoice_header h WHERE h.invoice_id = l.invoice_id)
        """)
        ev["orphan_invoice_lines"] = cur.fetchone()[0]
        for col in ("SIGNUP_DT", "LAST_ACTIVITY_DT", "LAST_INVOICE_DT",
                    "LAST_PAYMENT_DT", "TERMINATE_DT"):
            cur.execute(f"""
                SELECT COUNT(*) FROM customer_master
                WHERE {col} IS NOT NULL
                  AND VALIDATE_CONVERSION({col} AS DATE, 'DD-MON-YY') = 0
            """)
            ev.setdefault("unparseable_date_strings", {})[col] = cur.fetchone()[0]
        for col in ("RELATED_ACCT_IDS", "CHILD_ACCT_IDS", "PROMO_CODES_CSV"):
            cur.execute(f"""
                SELECT COUNT(*) FROM customer_master
                WHERE {col} IS NOT NULL
                  AND (REGEXP_LIKE({col}, ',\\s*,') OR {col} LIKE ',%' OR {col} LIKE '%,'
                       OR REGEXP_LIKE({col}, '[;|]'))
            """)
            ev.setdefault("malformed_csv", {})[col] = cur.fetchone()[0]
        cur.execute("""
            SELECT status_cd, COUNT(*) FROM customer_master GROUP BY status_cd ORDER BY 1
        """)
        ev["customer_status_distribution"] = {str(k): v for k, v in cur}
        cur.execute("""
            SELECT COUNT(*) FROM customer_master c WHERE c.status_cd IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM codes k
                              WHERE k.code_type='CUST_STATUS' AND k.code_val=c.status_cd)
        """)
        ev["customer_status_unmapped"] = cur.fetchone()[0]

        # 4. embed sizing: invoices are the only 1:N of consequence
        cur.execute("""
            SELECT MIN(n), MAX(n), AVG(n), COUNT(*) FROM (
              SELECT invoice_id, COUNT(*) n FROM invoice_line
              WHERE invoice_id IS NOT NULL GROUP BY invoice_id)
        """)
        mn, mx, avg, grp = cur.fetchone()
        ev["invoice_line_fanout"] = {
            "min": mn, "max": mx, "avg": float(avg), "distinct_invoice_ids": grp,
        }
        cur.execute("SELECT MAX(LENGTH(item_desc)), MAX(LENGTH(contact_notes)) FROM invoice_line, "
                    "(SELECT MAX(LENGTH(contact_notes)) contact_notes FROM customer_master)")
        ev["max_text_lengths"] = dict(zip(("invoice_line.item_desc", "customer_master.contact_notes"),
                                          cur.fetchone()))

        # 5. namespace scoping: batch_no is the run-scoping parameter the app filters on
        cur.execute("SELECT batch_no, COUNT(*) FROM invoice_header GROUP BY batch_no ORDER BY 1")
        ev["invoice_header_batches"] = {str(k): v for k, v in cur}
        cur.execute("SELECT conversion_batch_no, COUNT(*) FROM customer_master "
                    "GROUP BY conversion_batch_no ORDER BY 1")
        ev["customer_master_batches"] = {str(k): v for k, v in cur}

        # 6. the normalized proc estate: does anything reference the horror tables?
        cur.execute("SELECT COUNT(*) FROM invoice_header h WHERE NOT EXISTS "
                    "(SELECT 1 FROM customer_master c WHERE c.cust_id = h.cust_id)")
        ev["invoice_header_orphans"] = cur.fetchone()[0]

    OUT.write_text(json.dumps(ev, indent=2, default=str))
    print(json.dumps({k: v for k, v in ev.items() if k != "customer_master_population"},
                     indent=2, default=str))
    p = ev["customer_master_population"]
    print(f"customer_master: {p['total_rows']} rows, "
          f"{len(p['always_null_columns'])}/155 columns 100% NULL")


if __name__ == "__main__":
    main()
