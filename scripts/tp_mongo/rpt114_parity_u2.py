"""Compare the legacy Oracle RPT-114 rows with the MongoDB implementation."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import oracledb

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services/legacy-billing/app"))
import reports

LEGACY_STATUS_SQL = """
SELECT NVL(st.code_desc, 'UNKNOWN(' || TO_CHAR(h.status_cd) || ')') AS status_desc,
       COUNT(*)                                   AS invoice_count,
       TO_CHAR(SUM(h.total_amt), 'FM999999999999990.00') AS header_total_amt
  FROM invoice_header h,
       codes st
 WHERE h.batch_no = :batch_no
   AND st.code_type (+) = 'INV_STATUS'
   AND st.code_val  (+) = h.status_cd
 GROUP BY NVL(st.code_desc, 'UNKNOWN(' || TO_CHAR(h.status_cd) || ')')
 ORDER BY 1
"""

LEGACY_LINE_SQL = """
SELECT NVL(st.code_desc, 'UNKNOWN(' || TO_CHAR(h.status_cd) || ')') AS status_desc,
       DECODE(l.line_type_cd, 1, 'CHARGE',
                              2, 'CREDIT',
                              3, 'ADJUSTMENT',
                              9, 'MISC',
                              'UNKNOWN(' || TO_CHAR(l.line_type_cd) || ')')
                                                  AS line_type,
       COUNT(*)                                   AS line_count,
       TO_CHAR(SUM(l.amount),  'FM999999999999990.00') AS line_amount,
       TO_CHAR(SUM(l.tax_amt), 'FM999999999999990.00') AS line_tax,
       COUNT(DISTINCT h.invoice_id)               AS invoices_touched
  FROM invoice_header h,
       invoice_line   l,
       codes          st
 WHERE h.batch_no = :batch_no
   AND h.invoice_id = l.invoice_id
   AND st.code_type (+) = 'INV_STATUS'
   AND st.code_val  (+) = h.status_cd
 GROUP BY NVL(st.code_desc, 'UNKNOWN(' || TO_CHAR(h.status_cd) || ')'),
          DECODE(l.line_type_cd, 1, 'CHARGE',
                                 2, 'CREDIT',
                                 3, 'ADJUSTMENT',
                                 9, 'MISC',
                                 'UNKNOWN(' || TO_CHAR(l.line_type_cd) || ')')
 ORDER BY 1, 2
"""


def parse_dsn(value: str) -> tuple[str, str, str]:
    try:
        user, password, dsn = value.split("/", 2)
    except ValueError as exc:
        raise ValueError("DSN secret must have the form user/password/dsn") from exc
    return user, password, dsn


def legacy_rows(sql: str, batch_no: int):
    user, password, dsn = parse_dsn(os.environ["OW_BILLING_FIXTURE_DSN"])
    with oracledb.connect(user=user, password=password, dsn=dsn) as connection, connection.cursor() as cursor:
        cursor.execute(sql, {"batch_no": batch_no})
        return cursor.fetchall()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-no", type=int, default=85559852)
    parser.add_argument("--out", default=".migration/recon/U2/rpt114_parity.json")
    args = parser.parse_args(argv)

    oracle_rows = {
        "status": legacy_rows(LEGACY_STATUS_SQL, args.batch_no),
        "line": legacy_rows(LEGACY_LINE_SQL, args.batch_no),
    }
    mongo_status, mongo_line = reports.mongo_report_rows(args.batch_no)
    mongo_rows = {"status": mongo_status, "line": mongo_line}
    diffs = []
    for key in ("status", "line"):
        if oracle_rows[key] != mongo_rows[key]:
            diffs.append(
                {
                    "row_group": key,
                    "oracle": [list(row) for row in oracle_rows[key]],
                    "mongo": [list(row) for row in mongo_rows[key]],
                }
            )
    report = {
        "batch_no": args.batch_no,
        "status_rows_match": oracle_rows["status"] == mongo_rows["status"],
        "line_rows_match": oracle_rows["line"] == mongo_rows["line"],
        "oracle_rows": {
            key: [list(row) for row in rows] for key, rows in oracle_rows.items()
        },
        "mongo_rows": {
            key: [list(row) for row in rows] for key, rows in mongo_rows.items()
        },
        "diffs": diffs,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        "RPT-114 parity: "
        f"batch_no={args.batch_no} status_rows_match={report['status_rows_match']} "
        f"line_rows_match={report['line_rows_match']} diffs={len(diffs)}"
    )
    return 0 if not diffs else 1


if __name__ == "__main__":
    raise SystemExit(main())
