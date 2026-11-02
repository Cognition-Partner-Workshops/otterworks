"""Behavioural smoke test of pkg_ow_util on the Lakebase branch, run inside one transaction that
is rolled back (the audit log must stay at its snapshot content for recon). Expected values are
the Oracle semantics from packages/01_pkg_util.sql; the fixture tenant is Tenant One."""
import json
import sys

import lakebase_conn as lb

CHECKS = [
    ("f_md5_uuid('Tenant One') is md5 in 8-4-4-4-12 form",
     "SELECT pkg_ow_util.f_md5_uuid('Tenant One') = "
     "regexp_replace(md5('Tenant One'), '^(.{8})(.{4})(.{4})(.{4})(.{12})$', '\\1-\\2-\\3-\\4-\\5')"),
    ("f_code_desc('TENANT_STATUS', 10) = CODES row",
     "SELECT pkg_ow_util.f_code_desc('TENANT_STATUS', 10) = "
     "(SELECT code_desc FROM mig_unt19_20261030_slice_0.codes WHERE code_type = 'TENANT_STATUS' AND code_val = 10)"),
    ("f_code_desc unknown -> UNKNOWN(n)", "SELECT pkg_ow_util.f_code_desc('TENANT_STATUS', 4242) = 'UNKNOWN(4242)'"),
    ("f_code_desc NULL -> UNKNOWN(-1)", "SELECT pkg_ow_util.f_code_desc('TENANT_STATUS', NULL) = 'UNKNOWN(-1)'"),
    ("f_dt2str DD-MON-YY upper-case English", "SELECT pkg_ow_util.f_dt2str(TIMESTAMP '2026-03-07 13:45:00') = '07-MAR-26'"),
    ("f_str2dt round-trips", "SELECT pkg_ow_util.f_str2dt('07-MAR-26') = TIMESTAMP '2026-03-07 00:00:00'"),
    ("f_str2dt dirty -> NULL", "SELECT pkg_ow_util.f_str2dt('not a date') IS NULL"),
    ("fixture tenant present", "SELECT COUNT(*) = 1 FROM mig_unt19_20261030_slice_0.tenants "
                               "WHERE id = '00000000-0000-0000-0000-000000000001' AND name = 'Tenant One'"),
]


def main() -> int:
    results = {}
    ok = True
    with lb.connect() as cn, cn.cursor() as cur:
        for label, q in CHECKS:
            cur.execute(q)
            (passed,) = cur.fetchone()
            results[label] = bool(passed)
            ok &= bool(passed)
        cur.execute("CALL pkg_ow_util.log_msg(%s, %s)", ("SMOKE", "x" * 5000))
        cur.execute("SELECT module, length(message), log_id IS NOT NULL FROM mig_unt19_20261030_slice_0.billing_audit_log")
        rows = cur.fetchall()
        results["log_msg inserts one row, message capped at 4000, identity assigned"] = rows == [("SMOKE", 4000, True)]
        ok &= results["log_msg inserts one row, message capped at 4000, identity assigned"]
        cn.rollback()
        cur.execute("SELECT COUNT(*) FROM mig_unt19_20261030_slice_0.billing_audit_log")
        (n,) = cur.fetchone()
        results["rolled back: audit log rows"] = n
    print(json.dumps({"passed": ok, "checks": results}, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
