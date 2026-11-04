"""Prove dashboard_matches_admin_service: 0 rows on the live dashboard, failing rows on deliberately wrong copies.

Read-only. Run after `dbt compile`/`build`; perturbations replace the dashboard relation with a subquery.
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'workloads/pipeline'))
import pipeline  # noqa: E402

WORKLOAD = 'doc_usage_dashboard'
ACCOUNT = '00000000-0000-4000-8000-000000000101'
COLUMNS = ('snapshot_date, account_id, account_email, tier, quota_bytes, used_bytes, remaining_bytes, '
           'usage_pct, usage_band, active_document_count')
CASES = {
    'live dashboard': None,
    'one account shown at 98% instead of its admin figure': (
        f"select {COLUMNS.replace('used_bytes,', 'iff(account_id = $a, floor(quota_bytes * 0.98), used_bytes) as used_bytes,')} "
        f"from {{rel}}"),
    'usage_pct rounded differently for one account': (
        f"select {COLUMNS.replace('usage_pct,', 'iff(account_id = $a, usage_pct + 0.01, usage_pct) as usage_pct,')} "
        f"from {{rel}}"),
    'one account missing from the latest snapshot': (
        f"select {COLUMNS} from {{rel}} where not (account_id = $a and snapshot_date = (select max(snapshot_date) from {{rel}}))"),
    'every row filed one day late': f"select dateadd(day, 1, snapshot_date)::date as {COLUMNS} from {{rel}}",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiled', type=Path, required=True, help='compiled dashboard_matches_admin_service.sql')
    parser.add_argument('--session-url', required=True)
    args = parser.parse_args()
    pipeline.SESSION_URL = args.session_url
    sql = args.compiled.read_text()
    relation = pipeline.attr.names([WORKLOAD])[f'db_{WORKLOAD}'] + '.ANALYTICS.' + WORKLOAD
    pattern = re.compile(re.escape(relation) + r'(?![A-Za-z0-9_])', re.IGNORECASE)
    if len(pattern.findall(sql)) != 1:
        raise ValueError(f'expected one reference to {relation} in the compiled test')
    failures = 0
    with pipeline.connect(WORKLOAD) as con:
        cur = con.cursor()
        cur.execute('USE SECONDARY ROLES NONE')
        cur.execute(f"SET a = '{ACCOUNT}'")
        for name, replacement in CASES.items():
            query = sql if replacement is None else pattern.sub(lambda _: f'({replacement.format(rel=relation)})', sql)
            rows = cur.execute(f'select count(*) from ({query})').fetchone()[0]
            ok = rows == 0 if replacement is None else rows > 0
            failures += not ok
            print(f"{'ok  ' if ok else 'FAIL'} {name}: test returns {rows} failing row(s)", flush=True)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
