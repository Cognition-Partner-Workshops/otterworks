"""Fixture-first gate: the fixture tenant (policy.fixture_tenant, Tenant One) and the reference
rows it resolves through are identical on the frozen snapshot and on the Lakebase branch, before
the full dbx-recon run. Writes .migration/recon/slice-0/out/fixture_tenant_one.json."""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import lakebase_conn as lb

WAREHOUSE = "565cd2fd713738c4"
SNAPSHOT = "ow_tp.mig_unt19_20261030_src"
OUT = lb.REPO / ".migration" / "recon" / "slice-0" / "out" / "fixture_tenant_one.json"
TENANT = lb.POLICY["fixture_tenant"]["id"]

COLUMNS = {
    "tenant": ["id", "name", "tax_exempt_yn", "status_cd"],
    "tenant_status_code": ["code_type", "code_val", "code_desc"],
    "plans": ["id", "code", "tier_cd", "monthly_fee", "included_units", "overage_rate", "active_yn"],
    "audit_rows": ["n"],
}
SOURCE = {
    "tenant": f"SELECT id, name, tax_exempt_yn, status_cd FROM {SNAPSHOT}.tenants WHERE id = :tenant",
    "tenant_status_code": f"SELECT c.code_type, c.code_val, c.code_desc FROM {SNAPSHOT}.codes c "
                          f"JOIN {SNAPSHOT}.tenants t ON t.status_cd = c.code_val AND c.code_type = 'TENANT_STATUS' "
                          f"WHERE t.id = :tenant",
    "plans": f"SELECT id, code, tier_cd, monthly_fee, included_units, overage_rate, active_yn FROM {SNAPSHOT}.plans ORDER BY id",
    "audit_rows": f"SELECT COUNT(*) AS n FROM {SNAPSHOT}.billing_audit_log",
}
TARGET = {
    "tenant": "SELECT id, name, tax_exempt_yn, status_cd FROM mig_unt19_20261030_slice_0.tenants WHERE id = %(tenant)s",
    "tenant_status_code": "SELECT c.code_type, c.code_val, c.code_desc FROM mig_unt19_20261030_slice_0.codes c "
                          "JOIN mig_unt19_20261030_slice_0.tenants t ON t.status_cd = c.code_val AND c.code_type = 'TENANT_STATUS' "
                          "WHERE t.id = %(tenant)s",
    "plans": "SELECT id, code, tier_cd, monthly_fee, included_units, overage_rate, active_yn FROM mig_unt19_20261030_slice_0.plans ORDER BY id",
    "audit_rows": "SELECT COUNT(*) AS n FROM mig_unt19_20261030_slice_0.billing_audit_log",
}


def norm(v):
    if v is None:
        return None
    s = str(v)
    try:
        f = float(s)
        return format(f, ".6f")
    except ValueError:
        return s.rstrip()


def source_rows(cols: list[str], sql: str) -> list[list]:
    """The CLI returns a JSON array of {column: string} objects (keys sorted); re-order by column."""
    r = subprocess.run(["databricks", "experimental", "aitools", "tools", "query", "--warehouse", WAREHOUSE,
                        "--output", "json", "--param", f"tenant={TENANT}", sql],
                       check=True, capture_output=True, text=True)
    return [[norm(row[c]) for c in cols] for row in json.loads(r.stdout)]


def main() -> int:
    result = {"gate": "fixture-first", "fixture_tenant": lb.POLICY["fixture_tenant"],
              "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "checks": {}}
    ok = True
    with lb.connect() as cn, cn.cursor() as cur:
        for name in SOURCE:
            src = sorted(source_rows(COLUMNS[name], SOURCE[name]))
            cur.execute(TARGET[name], {"tenant": TENANT})
            tgt = sorted([norm(v) for v in row] for row in cur.fetchall())
            match = src == tgt and len(src) > 0
            ok &= match
            result["checks"][name] = {"source_rows": len(src), "target_rows": len(tgt), "match": match,
                                      **({"source": src, "target": tgt} if not match or len(src) <= 3 else {})}
    result["verdict"] = "PASS" if ok else "FAIL"
    OUT.write_text(json.dumps(result, indent=1) + "\n")
    print(json.dumps(result, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
