"""Live checks of ARCHIVE.RETENTION_PKG against a seeded Oracle stand-in.

Skipped unless LDM_TEST_ORACLE_DSN / LDM_TEST_ORACLE_USER / LDM_TEST_ORACLE_PASSWORD point at a
database initialised from migration/source/oracle/ddl and seeded with `python -m seed.oracle`
(any --scale). The seed generator is the oracle: every predicate the package encodes is compared
with the row the generator says it produced.
"""

from __future__ import annotations

import datetime as dt
import os
from collections import Counter
from decimal import Decimal

import pytest

from seed import spec, tables
from seed.spec import Sizes

oracledb = pytest.importorskip("oracledb")

DSN = os.environ.get("LDM_TEST_ORACLE_DSN")
USER = os.environ.get("LDM_TEST_ORACLE_USER")
PASSWORD = os.environ.get("LDM_TEST_ORACLE_PASSWORD")
pytestmark = pytest.mark.skipif(not (DSN and USER and PASSWORD), reason="LDM_TEST_ORACLE_* not set")

EXPECTED_OBJECTS = {
    ("PACKAGE", "RETENTION_PKG"),
    ("PACKAGE BODY", "RETENTION_PKG"),
    ("VIEW", "V_POLICY_LINEAGE"),
    ("VIEW", "V_ELIGIBLE_DOCS"),
    ("VIEW", "V_CLASS_TOTALS"),
    ("VIEW", "V_LEGAL_HOLDS"),
    ("TRIGGER", "TRG_DOCARCH_HOLD_AUDIT"),
    ("SEQUENCE", "SEQ_FILEAUD_TRG"),
    ("TABLE", "CLASS_TOTAL_SNAP"),
    ("JOB", "NIGHTLY_DISPOSITION"),
}
CUTOFF = dt.datetime(2019, 1, 1)


@pytest.fixture(scope="module")
def conn():
    c = oracledb.connect(user=USER, password=PASSWORD, dsn=DSN)
    yield c
    c.rollback()
    c.close()


@pytest.fixture(scope="module")
def sizes(conn) -> Sizes:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM ARCHIVE.DOCARCH")
        n = int(cur.fetchone()[0])
    for scale in (1.0, 0.1, 0.05, 0.02, 0.01, 0.005, 0.002, 0.001):
        try:
            s = Sizes(scale)
        except ValueError:
            continue
        if s.docarch_generated + len(tables.planted_docarch()) == n:
            return s
    pytest.fail(f"DOCARCH has {n} rows, not a known --scale")


def _scalar(conn, sql: str, **binds):
    with conn.cursor() as cur:
        cur.execute(sql, binds)
        return cur.fetchone()[0]


def _ts(row: tables.DocarchRow) -> dt.datetime:
    base = dt.datetime.fromtimestamp(row.last_access_secs, dt.UTC).replace(tzinfo=None)
    return base.replace(microsecond=row.last_access_frac // 10**6)


def test_objects_installed_and_valid(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT OBJECT_TYPE, OBJECT_NAME, STATUS FROM DBA_OBJECTS WHERE OWNER = 'ARCHIVE'")
        rows = cur.fetchall()
    present = {(t, n) for t, n, _ in rows}
    assert EXPECTED_OBJECTS <= present, EXPECTED_OBJECTS - present
    invalid = [(t, n) for t, n, s in rows if s != "VALID"]
    assert invalid == []
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM DBA_ERRORS WHERE OWNER = 'ARCHIVE'")
        assert cur.fetchone()[0] == 0
        cur.execute(
            "SELECT ENABLED, STATE FROM DBA_SCHEDULER_JOBS WHERE OWNER = 'ARCHIVE' AND JOB_NAME = 'NIGHTLY_DISPOSITION'"
        )
        assert cur.fetchone() == ("FALSE", "DISABLED")
        cur.execute(
            "SELECT TRIGGERING_EVENT, STATUS FROM DBA_TRIGGERS"
            " WHERE OWNER = 'ARCHIVE' AND TRIGGER_NAME = 'TRG_DOCARCH_HOLD_AUDIT'"
        )
        event, status = cur.fetchone()
        assert "UPDATE" in event and status == "ENABLED"


def test_source_is_retrievable_for_assessment(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT DBMS_METADATA.GET_DDL('PACKAGE_BODY', 'RETENTION_PKG', 'ARCHIVE') FROM DUAL")
        ddl = cur.fetchone()[0].read()
    for oracleism in (
        "PRAGMA AUTONOMOUS_TRANSACTION",
        "SYS_REFCURSOR",
        "RAISE_APPLICATION_ERROR",
        "ROWNUM",
        "UTL_RAW.CONVERT",
    ):
        assert oracleism in ddl


def test_resolve_class_follows_successor_chain(conn):
    for row in tables.retnplcy_rows():
        expected = row.policy_code
        for _ in range(8):
            years_code = expected
            succ = next(r.successor_code for r in tables.retnplcy_rows() if r.policy_code == years_code).strip()
            if not succ:
                break
            expected = succ
        got = _scalar(conn, "SELECT ARCHIVE.RETENTION_PKG.RESOLVE_CLASS(:c) FROM DUAL", c=row.policy_code)
        assert got.strip() == expected, row.policy_code
        got_years = _scalar(conn, "SELECT ARCHIVE.RETENTION_PKG.RETENTION_YEARS(:c) FROM DUAL", c=row.policy_code)
        assert int(got_years) == spec.RETENTION_YEARS[expected]
        in_sched = _scalar(conn, "SELECT ARCHIVE.RETENTION_PKG.IN_CLOSED_SCHEDULE(:c) FROM DUAL", c=row.policy_code)
        assert int(in_sched) == (1 if expected in spec.SET_ACTIVE else 0)


def test_lineage_view_matches_resolve_class(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT POLICY_CODE, SOR_CODE, HOPS, IN_CLOSED_SCHEDULE FROM ARCHIVE.V_POLICY_LINEAGE")
        lineage = {p.strip(): (s.strip(), int(h), int(i)) for p, s, h, i in cur.fetchall()}
    assert len(lineage) == 40
    assert lineage["F07R"] == ("FIN7", 1, 1)
    assert lineage["L07R"] == ("LGL7", 1, 1)
    assert lineage["FIN7"] == ("FIN7", 0, 1)
    assert lineage["PERM"][2] == 0
    for code, (sor, _, sched) in lineage.items():
        assert _scalar(conn, "SELECT ARCHIVE.RETENTION_PKG.RESOLVE_CLASS(:c) FROM DUAL", c=code).strip() == sor
        assert int(_scalar(conn, "SELECT ARCHIVE.RETENTION_PKG.IN_CLOSED_SCHEDULE(:c) FROM DUAL", c=code)) == sched


def test_unknown_code_and_confirmation_guard_raise_application_errors(conn):
    with conn.cursor() as cur:
        with pytest.raises(oracledb.DatabaseError) as e:
            cur.execute("SELECT ARCHIVE.RETENTION_PKG.RESOLVE_CLASS('ZZZZ') FROM DUAL")
        assert e.value.args[0].code == 20002
        purged = cur.var(oracledb.NUMBER)
        with pytest.raises(oracledb.DatabaseError) as e:
            cur.callproc("ARCHIVE.RETENTION_PKG.PURGE_ELIGIBLE", ["test-run", 10, None, dt.date(2026, 1, 1), purged])
        assert e.value.args[0].code == 20001
        cur.execute("SELECT COUNT(*) FROM MIGAUDIT.PURGE_AUDIT WHERE RUN_ID = 'test-run'")
        assert cur.fetchone()[0] == 0


def test_cutoff_is_2019_01_01(conn):
    got = _scalar(conn, "SELECT ARCHIVE.RETENTION_PKG.CUTOFF_TS() FROM DUAL")
    assert got == CUTOFF
    assert _scalar(conn, "SELECT ARCHIVE.RETENTION_PKG.CUTOFF_TS(DATE '2027-06-15') FROM DUAL") == dt.datetime(
        2020, 1, 1
    )


def test_disposition_date_matches_stored_ebcdic_date(conn):
    """Package's leap-safe year arithmetic == the generator's add_years_yyyymmdd, on real rows and a leap day."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT ARCH_KEY, RETENTION_CLASS, LAST_ACCESS_TS, "
            "       ARCHIVE.RETENTION_PKG.DISPOSITION_DT_TEXT(DISPOSITION_DT), "
            "       TO_CHAR(ARCHIVE.RETENTION_PKG.DISPOSITION_DATE(LAST_ACCESS_TS, RETENTION_CLASS), 'YYYYMMDD') "
            "  FROM ARCHIVE.DOCARCH WHERE ARCH_KEY NOT LIKE 'MIG03-%' AND ROWNUM <= 500"
        )
        for key, _cls, _ts, stored, computed in cur.fetchall():
            assert stored == computed, key
        cur.execute("SELECT ARCHIVE.RETENTION_PKG.DISPOSITION_DATE(TIMESTAMP '2012-02-29 23:59:59', 'FIN7') FROM DUAL")
        assert cur.fetchone()[0] == dt.datetime(2019, 2, 28)
        cur.execute("SELECT ARCHIVE.RETENTION_PKG.DISPOSITION_DATE(TIMESTAMP '2013-02-28 00:00:00', 'F07R') FROM DUAL")
        assert cur.fetchone()[0] == dt.datetime(2020, 2, 28)
        # MIG-03: low-values decode to NULL rather than a date
        cur.execute(
            "SELECT COUNT(*) FROM ARCHIVE.DOCARCH WHERE ARCH_KEY LIKE 'MIG03-%'"
            "   AND ARCHIVE.RETENTION_PKG.DISPOSITION_DT_TEXT(DISPOSITION_DT) IS NULL"
        )
        assert cur.fetchone()[0] == 5


def test_is_eligible_agrees_with_seed_selection_for_planted_rows(conn):
    for tag, row in tables.planted_docarch():
        got = _scalar(
            conn,
            "SELECT ARCHIVE.RETENTION_PKG.IS_ELIGIBLE(RETENTION_CLASS, LAST_ACCESS_TS, LEGAL_HOLD_FLAG) "
            "  FROM ARCHIVE.DOCARCH WHERE ARCH_KEY = :k",
            k=row.arch_key.decode("ascii"),
        )
        expected = tables.is_selected_docarch(row)
        assert bool(got) == expected, (tag, row.arch_key)
        assert expected == (tag != "MIG-05-parent")


def test_eligible_view_count_equals_seed_selected_count(conn, sizes):
    n = _scalar(conn, "SELECT COUNT(*) FROM ARCHIVE.V_ELIGIBLE_DOCS")
    planted_selected = sum(1 for t, _ in tables.planted_docarch() if t != "MIG-05-parent")
    assert int(n) == sizes.docarch_s + planted_selected
    held = _scalar(conn, "SELECT COUNT(*) FROM ARCHIVE.V_ELIGIBLE_DOCS WHERE LEGAL_HOLD_FLAG = 'Y'")
    assert int(held) == 0
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT SOR_CLASS FROM ARCHIVE.V_ELIGIBLE_DOCS")
        assert {c.strip() for (c,) in cur.fetchall()} <= set(spec.SET_ACTIVE)


def test_class_totals_match_generator_sums(conn, sizes):
    """V_CLASS_TOTALS and the SYS_REFCURSOR agree with the generator, incl. MIG-07 rolled into FIN7/LGL7."""
    count: Counter[str] = Counter()
    charge: Counter[str] = Counter()
    for g in range(sizes.docarch_generated):
        row = tables.docarch_generated(sizes, g)
        if row.cohort == "S":
            count[row.retention_class] += 1
            charge[row.retention_class] += row.storage_charge
    for tag, row in tables.planted_docarch():
        if tag == "MIG-05-parent":
            continue
        sor = {"F07R": "FIN7", "L07R": "LGL7", "H07R": "HRS7"}.get(row.retention_class, row.retention_class)
        count[sor] += 1
        charge[sor] += row.storage_charge
    expected = {c: (count[c], Decimal(charge[c]).scaleb(-8)) for c in count}

    with conn.cursor() as cur:
        cur.execute("SELECT RETENTION_CLASS, DOC_COUNT, CHARGE_TOTAL FROM ARCHIVE.V_CLASS_TOTALS")
        view = {c.strip(): (int(n), Decimal(str(t))) for c, n, t in cur.fetchall()}
        ref = cur.callfunc("ARCHIVE.RETENTION_PKG.CLASS_TOTALS", oracledb.DB_TYPE_CURSOR, [dt.date(2026, 1, 1)])
        pkg = {c.strip(): (int(n), Decimal(str(t))) for c, n, t in ref.fetchall()}
    assert view == expected
    assert pkg == expected
    assert set(view) == set(spec.SET_ACTIVE)


def test_disposition_codes(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT ARCHIVE.RETENTION_PKG.DISPOSITION_CODE('FIN7', TIMESTAMP '2016-03-01 10:15:30', 'N'),"
            "       ARCHIVE.RETENTION_PKG.DISPOSITION_CODE('FIN7', TIMESTAMP '2016-03-01 10:15:30', 'Y'),"
            "       ARCHIVE.RETENTION_PKG.DISPOSITION_CODE('FIN7', TIMESTAMP '2025-02-01 12:00:00', 'N'),"
            "       ARCHIVE.RETENTION_PKG.DISPOSITION_CODE('PERM', TIMESTAMP '2001-01-01 00:00:00', 'N'),"
            "       ARCHIVE.RETENTION_PKG.DISPOSITION_CODE('F07R', TIMESTAMP '2017-01-01 00:00:00', 'N')"
            "  FROM DUAL"
        )
        assert cur.fetchone() == ("10", "40", "00", "90", "10")
        nine_year = next(
            r.policy_code for r in tables.retnplcy_rows() if r.retention_years == 9 and r.policy_code != "PERM"
        )
        cur.execute(
            "SELECT ARCHIVE.RETENTION_PKG.DISPOSITION_CODE(:c, TIMESTAMP '2010-05-05 00:00:00', 'N'),"
            "       ARCHIVE.RETENTION_PKG.NEXT_REVIEW_DATE(TIMESTAMP '2010-05-05 00:00:00', :c),"
            "       ARCHIVE.RETENTION_PKG.NEXT_REVIEW_DATE(TIMESTAMP '2010-05-05 00:00:00', 'FIN7')"
            "  FROM DUAL",
            c=nine_year,
        )
        assert cur.fetchone() == ("20", dt.datetime(2019, 11, 5), None)


def test_hold_trigger_writes_fileaud_event_then_rolls_back(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT ARCH_KEY FROM ARCHIVE.DOCARCH WHERE ARCH_KEY = 'MIG01-0000000001'")
        (key,) = cur.fetchone()
        cur.execute("SELECT COUNT(*) FROM ARCHIVE.FILEAUD WHERE ARCH_KEY = :k", k=key)
        before = cur.fetchone()[0]
        cur.execute("UPDATE ARCHIVE.DOCARCH SET LEGAL_HOLD_FLAG = 'Y' WHERE ARCH_KEY = :k", k=key)
        cur.execute(
            "SELECT EVENT_TYPE, DISPOSITION_CODE, DETAIL_TEXT FROM ARCHIVE.FILEAUD "
            " WHERE ARCH_KEY = :k AND AUDIT_KEY LIKE 'TRG%' ORDER BY EVENT_TS DESC",
            k=key,
        )
        events = cur.fetchall()
        assert events[0][0] == "HOLD" and events[0][1] == "40" and events[0][2].startswith("HOLD placed")
        cur.execute("SELECT COUNT(*) FROM ARCHIVE.V_LEGAL_HOLDS WHERE ARCH_KEY = :k", k=key)
        assert cur.fetchone()[0] == 1
        cur.execute(
            "SELECT ARCHIVE.RETENTION_PKG.IS_ELIGIBLE(RETENTION_CLASS, LAST_ACCESS_TS, LEGAL_HOLD_FLAG)"
            "  FROM ARCHIVE.DOCARCH WHERE ARCH_KEY = :k",
            k=key,
        )
        assert cur.fetchone()[0] == 0
        cur.execute("UPDATE ARCHIVE.DOCARCH SET LEGAL_HOLD_FLAG = 'N' WHERE ARCH_KEY = :k", k=key)
        cur.execute("SELECT COUNT(*) FROM ARCHIVE.FILEAUD WHERE ARCH_KEY = :k AND EVENT_TYPE = 'RLSE'", k=key)
        assert cur.fetchone()[0] == 1
        conn.rollback()
        cur.execute("SELECT COUNT(*) FROM ARCHIVE.FILEAUD WHERE ARCH_KEY = :k", k=key)
        assert cur.fetchone()[0] == before


def test_purge_eligible_audits_children_before_parent_then_rolls_back(conn):
    run_id = f"test-legacy-{dt.datetime.now(dt.UTC):%Y%m%d%H%M%S%f}"
    with conn.cursor() as cur:
        purged = cur.var(oracledb.NUMBER)
        cur.callproc(
            "ARCHIVE.RETENTION_PKG.PURGE_ELIGIBLE", [run_id, 3, "DESTROY ELIGIBLE RECORDS", dt.date(2026, 1, 1), purged]
        )
        assert int(purged.getvalue()) == 3
        cur.execute(
            "SELECT TABLE_NAME, COUNT(*) FROM MIGAUDIT.PURGE_AUDIT WHERE RUN_ID = :r GROUP BY TABLE_NAME", r=run_id
        )
        audit = dict(cur.fetchall())
        assert audit["DOCARCH"] == 3
        cur.execute(
            "SELECT COUNT(*) FROM ARCHIVE.DOCARCH d WHERE EXISTS "
            "(SELECT 1 FROM MIGAUDIT.PURGE_AUDIT a"
            "  WHERE a.RUN_ID = :r AND a.TABLE_NAME = 'DOCARCH' AND a.SOURCE_KEY = d.ARCH_KEY)",
            r=run_id,
        )
        assert cur.fetchone()[0] == 0
        cur.execute(
            "SELECT COUNT(*) FROM ARCHIVE.FILEAUD f WHERE EXISTS "
            "(SELECT 1 FROM MIGAUDIT.PURGE_AUDIT a"
            "  WHERE a.RUN_ID = :r AND a.TABLE_NAME = 'DOCARCH' AND a.SOURCE_KEY = f.ARCH_KEY)",
            r=run_id,
        )
        assert cur.fetchone()[0] == 0
        conn.rollback()
        cur.execute("SELECT COUNT(*) FROM MIGAUDIT.PURGE_AUDIT WHERE RUN_ID = :r", r=run_id)
        assert cur.fetchone()[0] == 0
        # the autonomous-transaction log survived the rollback
        cur.execute("SELECT SEVERITY, MESSAGE FROM MIGAUDIT.PURGE_LOG WHERE RUN_ID = :r ORDER BY LOG_ID", r=run_id)
        log = cur.fetchall()
        assert [s for s, _ in log] == ["INFO", "INFO"]
        assert log[1][1].endswith("purged=3")
