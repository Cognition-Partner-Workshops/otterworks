"""Live parity: ARCHIVE.RETENTION_PKG on the Oracle stand-in vs the Snowflake port (target/snowflake/2xx).

Skipped unless both sides are configured. Oracle (read-only: the session runs SET TRANSACTION READ ONLY):
LDM_TEST_ORACLE_DSN / LDM_TEST_ORACLE_USER / LDM_TEST_ORACLE_PASSWORD (python-oracledb thin, e.g. through
`kubectl port-forward svc/oracle-archive 1521:1521`). Snowflake: LDM_TEST_SNOWFLAKE_ACCOUNT, SNOWFLAKE_PAT (never
echoed), LDM_TEST_SNOWFLAKE_USER / _ROLE / _WAREHOUSE / _DATABASE as in test_snowflake.py - the scratch tenant
database, never a demo target (`*_AFTER` databases are refused).

What runs: `ldm init`'s archive DDL (every target/snowflake/*.sql in order, tracked in MIG.SCHEMA_VERSION); then
every RETENTION_PKG function evaluated on both sides over the same inputs - all RETNPLCY codes, code edge cases
(NULL, blanks, padding, case, over-length, unknown), every planted MIG row, a hashed sample of keys per
(RETENTION_CLASS, LEGAL_HOLD_FLAG) plus leap-day rows, synthetic leap-day timestamps and RAW(8) edge cases incl.
LOW-VALUES - errors compared as (code, message). The sampled rows are loaded into STG.* and promoted into ARCH.*
under a fresh namespace, and V_POLICY_LINEAGE / V_ELIGIBLE_DOCS / V_CLASS_TOTALS / V_LEGAL_HOLDS and PURGE_INTENT
are compared with the Oracle views (and PURGE_ELIGIBLE's selection, run as a plain SELECT) over the same keys.
A markdown + CSV report goes to $LDM_PARITY_REPORT_DIR (default <repo>/.demo). The namespace is removed afterwards.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import re
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field, replace
from decimal import Decimal
from pathlib import Path

import pytest

from ldm.stages.init import ddl_files

from .test_snowflake import SF_ENV

oracledb = pytest.importorskip("oracledb")
snowflake_connector = pytest.importorskip("snowflake.connector")

ORA_ENV = {
    "dsn": os.environ.get("LDM_TEST_ORACLE_DSN", ""),
    "user": os.environ.get("LDM_TEST_ORACLE_USER", ""),
    "password": os.environ.get("LDM_TEST_ORACLE_PASSWORD", ""),
}

pytestmark = pytest.mark.skipif(
    not (all(ORA_ENV.values()) and SF_ENV["SNOWFLAKE_ACCOUNT"] and SF_ENV["SNOWFLAKE_PAT"]),
    reason="LDM_TEST_ORACLE_* / LDM_TEST_SNOWFLAKE_ACCOUNT / SNOWFLAKE_PAT not set",
)

REPO = Path(__file__).resolve().parents[3]
DDL_DIR = REPO / "migration" / "target" / "snowflake"
REPORT_DIR = Path(os.environ.get("LDM_PARITY_REPORT_DIR", REPO / ".demo"))
RETENTION_DDL = ("200_retention_udfs.sql", "210_retention_views.sql", "220_purge_intent.sql")
SAMPLE_PER_CLASS = int(os.environ.get("LDM_PARITY_SAMPLE_PER_CLASS", "25"))
LEAP_PER_CLASS = int(os.environ.get("LDM_PARITY_LEAP_PER_CLASS", "3"))
PARALLEL = int(os.environ.get("LDM_PARITY_PARALLEL", "8"))
EXPECTED_POLICY_CODES = 40
EXPECTED_PLANTED_DOCARCH = 42
EXPECTED_PLANTED_FILEAUD = 5

TS9 = "YYYY-MM-DD HH24:MI:SS.FF9"
DAY = "YYYY-MM-DD"
DEFAULT = "DEFAULT"
ROW_AS_OF = (DEFAULT, "2019-01-01", "2030-06-30")
LEAP_AS_OF = (DEFAULT, "2024-02-29", "2030-06-30")
CUTOFF_AS_OF = (DEFAULT, "2026-01-01", "2026-12-31", "2019-06-15", "2020-02-29", "2000-01-01", "1999-12-31", None)
EDGE_CODES = (None, "", "    ", "FIN7 ", "FIN7  ", "FIN7X", " FIN7", "fin7", "F07R", "L07R ", "H07R", "ZZZZ", "PERM")
LEAP_TS = (
    "2000-02-29 00:00:00.000000000",
    "2011-02-28 12:00:00.000000000",
    "2012-02-29 08:00:00.000000001",
    "2016-02-29 23:59:59.999999999",
    "2018-12-31 23:59:59.999999499",
    "2018-12-31 23:59:59.999999500",
    "2018-12-31 23:59:59.999999999",
    "2019-01-01 00:00:00.000000000",
    "2019-02-28 12:00:00.000000000",
    "2020-02-29 00:00:00.000000000",
)
RAW_CASES = (
    None,
    "",
    "0000000000000000",
    "00000000000000",
    "0000000000000001",
    "F2F0F1F9F0F2F2F9",
    "F2F0F2F6F0F1F0F1",
    "F1F9F9F9F1F2F3F1",
    "F2F0F1F9F0F1F0",
    "F2F0F1F9F0F1F0F1F0",
    "F2F0F1F9F0F1F0C1",
    "4040404040404040",
    "C1C2C3C4C5C6C7C8",
    "3230313930313031",
)


# --- the two dialects ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Dialect:
    name: str
    pkg: str
    source: str
    ts: str
    raw: str
    fmt_ts: Callable[[str], str]
    fmt_day: Callable[[str], str]
    date_lit: Callable[[str | None], str]


ORACLE = Dialect(
    name="oracle",
    pkg="ARCHIVE.RETENTION_PKG.",
    source=(
        "JSON_TABLE(:j, '$[*]' COLUMNS (id NUMBER PATH '$.id', code VARCHAR2(32) PATH '$.code', "
        "ts VARCHAR2(40) PATH '$.ts', hold VARCHAR2(4) PATH '$.hold', rawhex VARCHAR2(64) PATH '$.raw')) i"
    ),
    ts=f"TO_TIMESTAMP(i.ts, '{TS9}')",
    raw="HEXTORAW(i.rawhex)",
    fmt_ts=lambda e: f"TO_CHAR({e}, '{TS9}')",
    fmt_day=lambda e: f"TO_CHAR({e}, '{DAY}')",
    date_lit=lambda d: "CAST(NULL AS DATE)" if d is None else f"DATE '{d}'",
)
SNOWFLAKE = Dialect(
    name="snowflake",
    pkg="ARCH.",
    source=(
        "(SELECT f.value:id::INT AS id, f.value:code::VARCHAR AS code, f.value:ts::VARCHAR AS ts, "
        "f.value:hold::VARCHAR AS hold, f.value:raw::VARCHAR AS raw "
        "FROM TABLE(FLATTEN(INPUT => PARSE_JSON(?))) f) i"
    ),
    ts=f"TO_TIMESTAMP_NTZ(i.ts, '{TS9}')::TIMESTAMP_NTZ(9)",
    raw="TO_BINARY(i.raw, 'HEX')",
    fmt_ts=lambda e: f"TO_CHAR({e}, '{TS9}')",
    fmt_day=lambda e: f"TO_CHAR({e}, '{DAY}')",
    date_lit=lambda d: "NULL::DATE" if d is None else f"'{d}'::DATE",
)


def _as_of_arg(d: Dialect, as_of: str | None) -> str:
    return "" if as_of == DEFAULT else ", " + d.date_lit(as_of)


# name -> (uses as_of, SQL builder)
FUNCS: dict[str, tuple[bool, Callable[[Dialect, str | None], str]]] = {
    "RESOLVE_CLASS": (False, lambda d, a: f"{d.pkg}RESOLVE_CLASS(i.code)"),
    "RETENTION_YEARS": (False, lambda d, a: f"{d.pkg}RETENTION_YEARS(i.code)"),
    "IN_CLOSED_SCHEDULE": (False, lambda d, a: f"{d.pkg}IN_CLOSED_SCHEDULE(i.code)"),
    "CUTOFF_TS": (
        True,
        lambda d, a: d.fmt_ts(f"{d.pkg}CUTOFF_TS({'' if a == DEFAULT else d.date_lit(a)})"),
    ),
    "IS_ELIGIBLE": (True, lambda d, a: f"{d.pkg}IS_ELIGIBLE(i.code, {d.ts}, i.hold{_as_of_arg(d, a)})"),
    "DISPOSITION_DATE": (False, lambda d, a: d.fmt_day(f"{d.pkg}DISPOSITION_DATE({d.ts}, i.code)")),
    "NEXT_REVIEW_DATE": (False, lambda d, a: d.fmt_day(f"{d.pkg}NEXT_REVIEW_DATE({d.ts}, i.code)")),
    "DISPOSITION_DT_TEXT": (False, lambda d, a: f"{d.pkg}DISPOSITION_DT_TEXT({d.raw})"),
    "DISPOSITION_CODE": (True, lambda d, a: f"{d.pkg}DISPOSITION_CODE(i.code, {d.ts}, i.hold{_as_of_arg(d, a)})"),
}
CODE_FUNCS = ("RESOLVE_CLASS", "RETENTION_YEARS", "IN_CLOSED_SCHEDULE")
ROW_FUNCS = (
    "RESOLVE_CLASS",
    "IS_ELIGIBLE",
    "DISPOSITION_DATE",
    "NEXT_REVIEW_DATE",
    "DISPOSITION_DT_TEXT",
    "DISPOSITION_CODE",
)
EDGE_FUNCS = (*CODE_FUNCS, "IS_ELIGIBLE", "DISPOSITION_DATE", "NEXT_REVIEW_DATE", "DISPOSITION_CODE")
LEAP_FUNCS = ("IS_ELIGIBLE", "DISPOSITION_DATE", "NEXT_REVIEW_DATE", "DISPOSITION_CODE")


@dataclass(frozen=True)
class Case:
    id: int
    label: str
    code: str | None = None
    ts: str | None = None
    hold: str | None = None
    raw: str | None = None

    def as_json(self) -> dict[str, object]:
        return {"id": self.id, "code": self.code, "ts": self.ts, "hold": self.hold, "raw": self.raw}


@dataclass(frozen=True)
class Group:
    name: str
    cases: tuple[Case, ...]
    funcs: tuple[str, ...]
    as_of: tuple[str | None, ...] = (DEFAULT,)


# --- value normalisation ----------------------------------------------------------------------------------


def norm(v: object) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return str(int(v))
    if isinstance(v, int | Decimal):
        d = Decimal(v)
        return str(int(d)) if d == d.to_integral_value() else format(d.normalize(), "f")
    if isinstance(v, float):
        return norm(Decimal(repr(v)))
    return str(v)


def ora_error(exc: Exception | str) -> str:
    line = str(exc).strip().splitlines()[0]
    m = re.match(r"ORA-(\d{5}): (.*)", line)
    return f"ERR -{int(m.group(1))}: {m.group(2).rstrip()}" if m else f"ERR ? {line}"


def sf_error(exc: Exception) -> str:
    m = re.search(r"(-\d{3,5}): (.+?)(?= in RAISE_APPLICATION_ERROR at |\n|$)", str(exc))
    return f"ERR {m.group(1)}: {m.group(2).rstrip()}" if m else f"ERR ? {str(exc).strip().splitlines()[0]}"


# --- connections --------------------------------------------------------------------------------------------


class Oracle:
    def __init__(self) -> None:
        oracledb.defaults.fetch_decimals = True
        self.conn = oracledb.connect(**ORA_ENV)
        with self.conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
        self.pool = oracledb.create_pool(**ORA_ENV, min=PARALLEL, max=PARALLEL, increment=0)

    def rows(self, sql: str, **binds: object) -> list[tuple]:
        with self.conn.cursor() as cur:
            cur.arraysize = 5000
            clobs = {k: oracledb.DB_TYPE_CLOB for k, v in binds.items() if isinstance(v, str) and len(v) > 2000}
            if clobs:
                cur.setinputsizes(**clobs)
            cur.execute(sql, binds)
            return list(cur.fetchall())

    def evaluate(self, sql: str, payload: str) -> list[tuple]:
        with self.pool.acquire() as conn, conn.cursor() as cur:
            try:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.arraysize = 5000
                cur.setinputsizes(j=oracledb.DB_TYPE_CLOB)
                cur.execute(sql, j=payload)
                return list(cur.fetchall())
            finally:
                conn.rollback()

    def screen(self, d: Dialect, funcs: Sequence[str], labels: Sequence[str], as_of: str | None, cases: list[Case]):
        """{(case id, label): error} for the inputs that raise, caught in PL/SQL so one statement covers them all."""
        if not funcs:
            return {}
        plsql = replace(d, raw="HEXTORAW(p_raw)")
        probes = [
            f"FUNCTION probe{n}(p_code VARCHAR2, p_ts VARCHAR2, p_hold VARCHAR2, p_raw VARCHAR2) RETURN VARCHAR2 IS\n"
            "  TYPE t IS RECORD (code VARCHAR2(32), ts VARCHAR2(40), hold VARCHAR2(4));\n"
            "  i t;\n  v VARCHAR2(4000);\n"
            "BEGIN\n  i.code := p_code; i.ts := p_ts; i.hold := p_hold;\n"
            f"  v := {FUNCS[f][1](plsql, as_of)};\n  RETURN NULL;\n"
            "EXCEPTION WHEN OTHERS THEN RETURN SQLERRM;\nEND;"
            for n, f in enumerate(funcs)
        ]
        cols = ", ".join(f"probe{n}(i.code, i.ts, i.hold, i.rawhex)" for n in range(len(funcs)))
        sql = "WITH\n" + "\n".join(probes) + f"\nSELECT i.id, {cols} FROM {d.source}"
        rows = self.evaluate(sql, json.dumps([c.as_json() for c in cases]))
        return {
            (int(r[0]), label): ora_error(err)
            for r in rows
            for label, err in zip(labels, r[1:], strict=True)
            if err is not None
        }

    def error(self, exc: Exception) -> str:
        return ora_error(exc)

    def close(self) -> None:
        self.pool.close(force=True)
        self.conn.rollback()
        self.conn.close()


class Snowflake:
    def __init__(self) -> None:
        self.database = SF_ENV["SNOWFLAKE_DATABASE"]
        if not self.database or self.database.upper().endswith("_AFTER"):
            pytest.fail(f"refusing to run the parity harness against {self.database!r}: use the scratch database")
        self.conn = snowflake_connector.connect(
            account=SF_ENV["SNOWFLAKE_ACCOUNT"],
            user=SF_ENV["SNOWFLAKE_USER"],
            authenticator="PROGRAMMATIC_ACCESS_TOKEN",
            token=SF_ENV["SNOWFLAKE_PAT"],
            role=SF_ENV["SNOWFLAKE_ROLE"],
            warehouse=SF_ENV["SNOWFLAKE_WAREHOUSE"],
            database=self.database,
            paramstyle="qmark",
            autocommit=True,
        )

    def rows(self, sql: str, params: Sequence[object] = ()) -> list[tuple]:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())

    def executemany(self, sql: str, rows: Sequence[Sequence[object]], chunk: int = 500) -> None:
        with self.conn.cursor() as cur:
            for i in range(0, len(rows), chunk):
                cur.executemany(sql, rows[i : i + chunk])

    def script(self, text: str) -> None:
        for _ in self.conn.execute_string(text):
            pass

    def evaluate(self, sql: str, payload: str) -> list[tuple]:
        return self.rows(sql, (payload,))

    def screen(self, d: Dialect, funcs: Sequence[str], labels: Sequence[str], as_of: str | None, cases: list[Case]):
        """Snowflake SQL cannot catch a UDF error, so raising inputs are isolated by `evaluate_group` instead."""
        return {}

    def error(self, exc: Exception) -> str:
        return sf_error(exc)

    def close(self) -> None:
        self.conn.close()


# --- function parity ----------------------------------------------------------------------------------------


def _select(d: Dialect, funcs: Sequence[str], as_of: str | None) -> str:
    cols = ", ".join(FUNCS[f][1](d, as_of) for f in funcs)
    return f"SELECT i.id, {cols} FROM {d.source}"


def evaluate_group(side: Oracle | Snowflake, d: Dialect, group: Group) -> dict[tuple[int, str], str]:
    """{(case id, function label): normalised result or 'ERR <code>: <message>'}.

    Each as-of is tried as one statement over every case and function, minus the inputs `side.screen` already
    found raising. A failing statement is split per function, then halved until each raising input stands alone,
    so one error never hides the results of its neighbours. Statements run `PARALLEL` at a time.
    """
    out: dict[tuple[int, str], str] = {}
    with ThreadPoolExecutor(PARALLEL) as pool:
        pending: dict[Future, tuple[tuple[str, ...], tuple[str, ...], str | None, list[Case]]] = {}

        def submit(funcs: tuple[str, ...], labels: tuple[str, ...], as_of: str | None, cases: list[Case]) -> None:
            payload = json.dumps([c.as_json() for c in cases])
            pending[pool.submit(side.evaluate, _select(d, funcs, as_of), payload)] = (funcs, labels, as_of, cases)

        for as_of in group.as_of:
            funcs = tuple(f for f in group.funcs if FUNCS[f][0] or as_of == group.as_of[0])
            labels = tuple(f if not FUNCS[f][0] or len(group.as_of) == 1 else f"{f}(as_of={as_of})" for f in funcs)
            errors = side.screen(d, funcs, labels, as_of, list(group.cases))
            if not errors:
                submit(funcs, labels, as_of, list(group.cases))
                continue
            out.update(errors)
            for f, label in zip(funcs, labels, strict=True):
                rest = [c for c in group.cases if (c.id, label) not in errors]
                if rest:
                    submit((f,), (label,), as_of, rest)
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for fut in done:
                funcs, labels, as_of, cases = pending.pop(fut)
                try:
                    rows = fut.result()
                except Exception as exc:  # noqa: BLE001 - one failing input fails the whole statement
                    if len(funcs) > 1:
                        for f, label in zip(funcs, labels, strict=True):
                            submit((f,), (label,), as_of, cases)
                    elif len(cases) == 1:
                        out[(cases[0].id, labels[0])] = side.error(exc)
                    else:
                        mid = len(cases) // 2
                        submit(funcs, labels, as_of, cases[:mid])
                        submit(funcs, labels, as_of, cases[mid:])
                    continue
                for row in rows:
                    for label, v in zip(labels, row[1:], strict=True):
                        out[(int(row[0]), label)] = norm(v)
    return out


# --- the run ------------------------------------------------------------------------------------------------


@dataclass
class Check:
    section: str
    item: str
    key: str
    inputs: str
    oracle: str
    snowflake: str

    @property
    def ok(self) -> bool:
        return self.oracle == self.snowflake


@dataclass
class Parity:
    namespace: str
    checks: list[Check] = field(default_factory=list)
    facts: dict[str, object] = field(default_factory=dict)
    class_totals: list[tuple[str, str, str, str, str]] = field(default_factory=list)
    oracle_full_totals: list[tuple] = field(default_factory=list)
    skipped_rows: dict[str, str] = field(default_factory=dict)
    schema_version: dict[str, tuple[str, str]] = field(default_factory=dict)

    def mismatches(self, section: str | None = None) -> list[Check]:
        return [c for c in self.checks if not c.ok and (section is None or c.section == section)]

    def add_rows(self, section: str, item: str, ora: dict[str, tuple], sf: dict[str, tuple]) -> None:
        for key in sorted(set(ora) | set(sf)):
            o = " | ".join(norm(v) for v in ora[key]) if key in ora else "<no row>"
            s = " | ".join(norm(v) for v in sf[key]) if key in sf else "<no row>"
            self.checks.append(Check(section, item, key, "", o, s))


def _keys_json(keys: Sequence[str]) -> str:
    return json.dumps(list(keys))


ORA_KEYS = "SELECT k FROM JSON_TABLE(:keys, '$[*]' COLUMNS (k VARCHAR2(16) PATH '$'))"
DOC_COLS = (
    "ARCH_KEY, DOC_ID, VERSION_NO, RETENTION_CLASS, TO_CHAR(LAST_ACCESS_TS, '" + TS9 + "'), STORAGE_CHARGE, "
    "UNIT_RATE, RAWTOHEX(OWNER_NAME), RAWTOHEX(DISPOSITION_DT), LEGAL_HOLD_FLAG, CHECKSUM_ALG, CONTENT_SHA256, "
    "BYTE_SIZE, SOURCE_SYS"
)


def _split_ts(ts9: str) -> tuple[str, int]:
    """'YYYY-MM-DD HH:MI:SS.fffffffff' -> (TIMESTAMP_NTZ(6) text, NANOS_TAIL holding fraction digits 7-12)."""
    return ts9[:26], int(ts9[26:29]) * 1000


def _landing_problem(row: tuple) -> str | None:
    """Why the promoted target types could not hold this source row (the engine rejects it before ARCH)."""
    _, _, _, _, _, _, unit_rate, _, disp_hex, *_ = row
    if abs(Decimal(unit_rate)) >= Decimal(10) ** 10:
        return "UNIT_RATE exceeds NUMBER(18,8)"
    try:
        dt.datetime.strptime(bytes.fromhex(disp_hex or "").decode("cp037"), "%Y%m%d")
    except ValueError:
        return f"DISPOSITION_DT x'{disp_hex}' is not an EBCDIC YYYYMMDD date"
    return None


def _sample_keys(ora: Oracle) -> tuple[list[str], list[str], Counter]:
    planted = [r[0] for r in ora.rows("SELECT ARCH_KEY FROM ARCHIVE.DOCARCH WHERE ARCH_KEY LIKE 'MIG%' ORDER BY 1")]
    sampled = ora.rows(
        """
        SELECT ARCH_KEY, RETENTION_CLASS, LEGAL_HOLD_FLAG, IS_LEAP FROM (
            SELECT ARCH_KEY, RETENTION_CLASS, LEGAL_HOLD_FLAG,
                   CASE WHEN TO_CHAR(LAST_ACCESS_TS, 'MMDD') = '0229' THEN 1 ELSE 0 END AS IS_LEAP,
                   ROW_NUMBER() OVER (PARTITION BY RETENTION_CLASS, LEGAL_HOLD_FLAG
                                      ORDER BY ORA_HASH(ARCH_KEY, 4294967295, 20260101), ARCH_KEY) AS RN,
                   ROW_NUMBER() OVER (PARTITION BY RETENTION_CLASS,
                                                   CASE WHEN TO_CHAR(LAST_ACCESS_TS, 'MMDD') = '0229' THEN 1 END
                                      ORDER BY ORA_HASH(ARCH_KEY, 4294967295, 20260101), ARCH_KEY) AS RN_LEAP
              FROM ARCHIVE.DOCARCH
             WHERE ARCH_KEY NOT LIKE 'MIG%')
         WHERE RN <= :n OR (IS_LEAP = 1 AND RN_LEAP <= :m)
         ORDER BY ARCH_KEY
        """,
        n=SAMPLE_PER_CLASS,
        m=LEAP_PER_CLASS,
    )
    per_class: Counter = Counter()
    for _, cls, hold, leap in sampled:
        per_class[f"{cls.rstrip()}/{hold}"] += 1
        if leap:
            per_class[f"{cls.rstrip()}/leap-day"] += 1
    return planted, [r[0] for r in sampled], per_class


def _load(sf: Snowflake, ns: str, run_id: str, policies: list[tuple], docs: list[tuple], auds: list[tuple]) -> None:
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None).isoformat(sep=" ")
    meta = "RUN_ID, NAMESPACE, SOURCE_KEY, RANGE_SEQ, BATCH_ID, RAW_BYTES, LOADED_AT"

    def stg(key: str, raw: bytes) -> list[object]:
        return [run_id, ns, key, 1, 1, raw, now]

    pol_cols = (
        "POLICY_CODE, POLICY_DESC, RETENTION_YEARS, SUCCESSOR_CODE, ACTIVE_FLAG, DISPOSITION_ACTION, "
        "EFFECTIVE_TS, EFFECTIVE_TS_NANOS_TAIL"
    )
    sf.executemany(
        f"INSERT INTO STG.RETNPLCY ({meta}, {pol_cols}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            [*stg(p[0].rstrip(), p[0].encode("cp037")), p[0], p[1], int(p[2]), p[3], p[4], p[5], *_split_ts(p[6])]
            for p in policies
        ],
    )
    doc_cols = (
        "ARCH_KEY, DOC_ID, VERSION_NO, RETENTION_CLASS, LAST_ACCESS_TS, LAST_ACCESS_TS_NANOS_TAIL, STORAGE_CHARGE, "
        "UNIT_RATE, OWNER_NAME, DISPOSITION_DT, LEGAL_HOLD_FLAG, CHECKSUM_ALG, CONTENT_SHA256, BYTE_SIZE, SOURCE_SYS"
    )
    doc_rows = []
    for r in docs:
        key, doc_id, ver, cls, ts9, charge, rate, owner_hex, disp_hex, hold, alg, sha, size, sys_ = r
        owner, disp = bytes.fromhex(owner_hex), bytes.fromhex(disp_hex)
        day = dt.datetime.strptime(disp.decode("cp037"), "%Y%m%d").date().isoformat()
        doc_rows.append(
            [
                *stg(key.rstrip(), owner + disp),
                key.rstrip(),
                doc_id,
                int(ver),
                cls,
                *_split_ts(ts9),
                str(charge),
                str(rate),
                owner.decode("cp037").rstrip(),
                day,
                hold,
                alg,
                sha,
                int(size),
                sys_,
            ]
        )
    sf.executemany(
        f"INSERT INTO STG.DOCARCH ({meta}, {doc_cols}) VALUES ({', '.join(['?'] * 22)})",
        doc_rows,
    )
    aud_cols = (
        "AUDIT_KEY, ARCH_KEY, EVENT_TYPE, EVENT_TS, EVENT_TS_NANOS_TAIL, ACTOR_ID, RETENTION_CLASS, "
        "DISPOSITION_CODE, CLIENT_IP, DETAIL_TEXT"
    )
    sf.executemany(
        f"INSERT INTO STG.FILEAUD ({meta}, {aud_cols}) VALUES ({', '.join(['?'] * 17)})",
        [
            [*stg(a[0].rstrip(), a[0].encode("cp037")), a[0], a[1].rstrip(), a[2], *_split_ts(a[3]), *a[4:9]]
            for a in auds
        ],
    )
    for table, cols in (("RETNPLCY", pol_cols), ("DOCARCH", doc_cols), ("FILEAUD", aud_cols)):
        sf.rows(
            f"INSERT INTO ARCH.{table} ({cols}, SOURCE_KEY, ROW_HASH, NAMESPACE, MIGRATED_RUN_ID) "
            f"SELECT {cols}, SOURCE_KEY, SHA2_BINARY(SOURCE_KEY || HEX_ENCODE(RAW_BYTES)), NAMESPACE, RUN_ID "
            f"FROM STG.{table} WHERE RUN_ID = ? AND NAMESPACE = ?",
            (run_id, ns),
        )


def _cleanup(sf: Snowflake, ns: str) -> None:
    sf.rows("DELETE FROM MIG.PURGE_INTENT WHERE NAMESPACE = ?", (ns,))
    for table in ("FILEAUD", "DOCARCH", "RETNPLCY"):
        for schema in ("ARCH", "STG"):
            sf.rows(f"DELETE FROM {schema}.{table} WHERE NAMESPACE = ?", (ns,))


def _apply_ddl(sf: Snowflake, parity: Parity) -> None:
    for path in ddl_files(DDL_DIR):
        text = path.read_text()
        sha = hashlib.sha256(text.encode()).hexdigest()
        sf.script(text)
        sf.rows(
            "MERGE INTO MIG.SCHEMA_VERSION t USING (SELECT ? AS FILE_NAME, ? AS FILE_SHA256) s "
            "ON t.FILE_NAME = s.FILE_NAME "
            "WHEN MATCHED THEN UPDATE SET FILE_SHA256 = s.FILE_SHA256, APPLIED_AT = SYSDATE()::TIMESTAMP_NTZ(3) "
            "WHEN NOT MATCHED THEN INSERT (FILE_NAME, FILE_SHA256) VALUES (s.FILE_NAME, s.FILE_SHA256)",
            (path.name, sha),
        )
    recorded = dict(sf.rows("SELECT FILE_NAME, FILE_SHA256 FROM MIG.SCHEMA_VERSION"))
    for name in RETENTION_DDL:
        text = (DDL_DIR / name).read_text()
        parity.schema_version[name] = (hashlib.sha256(text.encode()).hexdigest(), recorded.get(name, ""))


def _function_groups(policies: list[tuple], docs: dict[str, tuple], planted: list[str], sampled: list[str]):
    ids = iter(range(1, 1_000_000))
    groups: list[Group] = []
    codes = [p[0] for p in policies]
    groups.append(Group("RETNPLCY codes", tuple(Case(next(ids), repr(c), code=c) for c in codes), CODE_FUNCS))
    edge = [
        Case(next(ids), f"code={c!r} hold={h!r}", code=c, ts="2010-06-15 00:00:00.000000000", hold=h)
        for c in EDGE_CODES
        for h in ("N", "Y", None)
    ]
    groups.append(Group("code edge cases + hold precedence", tuple(edge), EDGE_FUNCS, ROW_AS_OF))
    groups.append(Group("CUTOFF_TS as-of dates", (Case(next(ids), "-"),), ("CUTOFF_TS",), CUTOFF_AS_OF))

    def row_case(key: str) -> Case:
        r = docs[key]
        return Case(next(ids), key.rstrip(), code=r[3], ts=r[4], hold=r[9], raw=r[8])

    groups.append(Group("planted MIG rows", tuple(row_case(k) for k in planted), ROW_FUNCS, ROW_AS_OF))
    groups.append(Group("sampled keys per class", tuple(row_case(k) for k in sampled), ROW_FUNCS, ROW_AS_OF))
    leap = [Case(next(ids), f"{c.rstrip()} @ {t}", code=c, ts=t, hold="N") for c in codes for t in LEAP_TS]
    groups.append(Group("leap-day timestamps x codes", tuple(leap), LEAP_FUNCS, LEAP_AS_OF))
    raws = [Case(next(ids), f"raw={r!r}", raw=r) for r in RAW_CASES]
    groups.append(Group("RAW(8) disposition dates", tuple(raws), ("DISPOSITION_DT_TEXT",)))
    return groups


def _view_checks(ora: Oracle, sf: Snowflake, parity: Parity, keys: list[str]) -> None:
    ns = parity.namespace
    kj = _keys_json(keys)

    ora_lineage = {
        r[0].rstrip(): r[1:]
        for r in ora.rows(
            "SELECT POLICY_CODE, SOR_CODE, HOPS, LINEAGE, IN_CLOSED_SCHEDULE FROM ARCHIVE.V_POLICY_LINEAGE"
        )
    }
    sf_lineage = {
        r[0].rstrip(): r[1:]
        for r in sf.rows(
            "SELECT POLICY_CODE, SOR_CODE, HOPS, LINEAGE, IN_CLOSED_SCHEDULE FROM ARCH.V_POLICY_LINEAGE "
            "WHERE NAMESPACE = ?",
            (ns,),
        )
    }
    parity.add_rows("views", "V_POLICY_LINEAGE", ora_lineage, sf_lineage)

    def trimmed(rows: list[tuple]) -> dict[str, tuple]:
        return {r[0].rstrip(): tuple(v.rstrip() if isinstance(v, str) else v for v in r[1:]) for r in rows}

    elig_cols = (
        f"ARCH_KEY, DOC_ID, VERSION_NO, RETENTION_CLASS, SOR_CLASS, TO_CHAR(LAST_ACCESS_TS, '{TS9}'), "
        f"STORAGE_CHARGE, BYTE_SIZE, LEGAL_HOLD_FLAG, TO_CHAR(DISPOSITION_DUE, '{DAY}'), DISPOSITION_DT_STORED, "
        "DISPOSITION_CODE"
    )
    parity.add_rows(
        "views",
        "V_ELIGIBLE_DOCS",
        trimmed(ora.rows(f"SELECT {elig_cols} FROM ARCHIVE.V_ELIGIBLE_DOCS WHERE ARCH_KEY IN ({ORA_KEYS})", keys=kj)),
        trimmed(sf.rows(f"SELECT {elig_cols} FROM ARCH.V_ELIGIBLE_DOCS WHERE NAMESPACE = ?", (ns,))),
    )

    hold_cols = (
        "ARCH_KEY, DOC_ID, RETENTION_CLASS, TO_CHAR(LAST_ACCESS_TS, '{ts}'), {owner}, "
        "TO_CHAR(LAST_HOLD_TS, '{ts}'), AUDIT_EVENTS"
    )
    ora_holds = [
        (r[0], r[1], r[2], r[3], bytes.fromhex(r[4] or "").decode("latin-1"), *r[5:])
        for r in ora.rows(
            f"SELECT {hold_cols.format(ts=TS9, owner='RAWTOHEX(UTL_RAW.CAST_TO_RAW(OWNER_NAME))')} "
            f"FROM ARCHIVE.V_LEGAL_HOLDS WHERE ARCH_KEY IN ({ORA_KEYS})",
            keys=kj,
        )
    ]
    sf_holds = sf.rows(
        f"SELECT {hold_cols.format(ts=TS9, owner='OWNER_NAME')} FROM ARCH.V_LEGAL_HOLDS WHERE NAMESPACE = ?", (ns,)
    )
    parity.add_rows("views", "V_LEGAL_HOLDS", trimmed(ora_holds), trimmed(sf_holds))

    view_text = ora.rows("SELECT TEXT FROM ALL_VIEWS WHERE OWNER = 'ARCHIVE' AND VIEW_NAME = 'V_CLASS_TOTALS'")[0][0]
    assert view_text.count("FROM ARCHIVE.DOCARCH d") == 1, "unexpected ARCHIVE.V_CLASS_TOTALS text"
    sampled_view = view_text.replace(
        "FROM ARCHIVE.DOCARCH d", f"FROM (SELECT * FROM ARCHIVE.DOCARCH WHERE ARCH_KEY IN ({ORA_KEYS})) d"
    )
    totals_cols = (
        f"RETENTION_CLASS, DOC_COUNT, CHARGE_TOTAL, TO_CHAR(OLDEST_ACCESS_TS, '{TS9}'), "
        f"TO_CHAR(NEWEST_ACCESS_TS, '{TS9}')"
    )
    ora_totals = trimmed(ora.rows(f"SELECT {totals_cols} FROM ({sampled_view})", keys=kj))
    sf_totals = trimmed(sf.rows(f"SELECT {totals_cols} FROM ARCH.V_CLASS_TOTALS WHERE NAMESPACE = ?", (ns,)))
    parity.add_rows("class totals", "V_CLASS_TOTALS", ora_totals, sf_totals)
    sf_udtf = trimmed(
        sf.rows(
            "SELECT RETENTION_CLASS, DOC_COUNT, CHARGE_TOTAL FROM TABLE(ARCH.CLASS_TOTALS('2026-01-01'::DATE)) "
            "WHERE NAMESPACE = ?",
            (ns,),
        )
    )
    parity.add_rows("class totals", "CLASS_TOTALS()", {k: v[:2] for k, v in ora_totals.items()}, sf_udtf)
    for cls in sorted(set(ora_totals) | set(sf_totals)):
        o, s = ora_totals.get(cls, ("-",) * 4), sf_totals.get(cls, ("-",) * 4)
        parity.class_totals.append((cls, norm(o[0]), norm(s[0]), norm(o[1]), norm(s[1])))
    parity.oracle_full_totals = ora.rows(
        "SELECT RETENTION_CLASS, DOC_COUNT, CHARGE_TOTAL FROM ARCHIVE.V_CLASS_TOTALS ORDER BY 1"
    )


def _purge_checks(ora: Oracle, sf: Snowflake, parity: Parity, keys: list[str]) -> None:
    ns = parity.namespace
    kj = _keys_json(keys)
    for as_of in ("2026-01-01", "2030-06-30"):
        run_id = f"{ns}-{as_of}"
        parents = ora.rows(
            f"""
            SELECT d.ARCH_KEY, l.SOR_CODE,
                   ARCHIVE.RETENTION_PKG.DISPOSITION_CODE(d.RETENTION_CLASS, d.LAST_ACCESS_TS, d.LEGAL_HOLD_FLAG,
                                                          DATE '{as_of}')
              FROM ARCHIVE.DOCARCH d
              JOIN ARCHIVE.V_POLICY_LINEAGE l ON l.POLICY_CODE = d.RETENTION_CLASS
             WHERE l.IN_CLOSED_SCHEDULE = 1
               AND d.LEGAL_HOLD_FLAG = 'N'
               AND d.LAST_ACCESS_TS < ARCHIVE.RETENTION_PKG.CUTOFF_TS(DATE '{as_of}')
               AND d.ARCH_KEY IN ({ORA_KEYS})
             ORDER BY d.ARCH_KEY
            """,
            keys=kj,
        )
        children = ora.rows(
            f"SELECT AUDIT_KEY, ARCH_KEY FROM ARCHIVE.FILEAUD WHERE ARCH_KEY IN ({ORA_KEYS})",
            keys=_keys_json([p[0] for p in parents]),
        )
        count = sf.rows("CALL MIG.PURGE_INTENT(?, ?::DATE, ?)", (run_id, as_of, ns))[0][0]
        again = sf.rows("CALL MIG.PURGE_INTENT(?, ?::DATE, ?)", (run_id, as_of, ns))[0][0]
        intents = sf.rows(
            "SELECT INTENT_SEQ, TABLE_NAME, SOURCE_KEY, ARCH_KEY, SOR_CLASS, REASON_CODE, SCHEDULE_CODE, "
            f"TO_CHAR(CUTOFF_TS, '{TS9}') FROM MIG.PURGE_INTENT WHERE RUN_ID = ? AND NAMESPACE = ? ORDER BY INTENT_SEQ",
            (run_id, ns),
        )
        item = f"PURGE_INTENT(as_of={as_of})"
        sf_parents = {r[3]: (r[4], r[5]) for r in intents if r[1] == "DOCARCH"}
        ora_parents = {p[0].rstrip(): (p[1].rstrip(), p[2]) for p in parents}
        parity.add_rows("purge intent", f"{item} parents", ora_parents, sf_parents)
        sf_children = {r[2]: (r[3],) for r in intents if r[1] == "FILEAUD"}
        ora_children = {c[0].rstrip(): (c[1].rstrip(),) for c in children}
        parity.add_rows("purge intent", f"{item} children", ora_children, sf_children)

        seq_of_parent = {r[3]: r[0] for r in intents if r[1] == "DOCARCH"}
        order_ok = all(r[1] != "FILEAUD" or r[0] < seq_of_parent.get(r[3], -1) for r in intents) and [
            r[3] for r in intents if r[1] == "DOCARCH"
        ] == sorted(seq_of_parent, key=lambda k: k.ljust(16))
        cutoff = ora.rows(f"SELECT TO_CHAR(ARCHIVE.RETENTION_PKG.CUTOFF_TS(DATE '{as_of}'), '{TS9}') FROM DUAL")[0][0]
        facts = [
            ("returned count = PURGE_ELIGIBLE parents", str(len(parents)), norm(count)),
            ("rerun is idempotent (same count)", str(len(parents)), norm(again)),
            ("rows recorded (children + parents)", str(len(parents) + len(children)), str(len(intents))),
            ("children precede their parent, parents in ARCH_KEY order", "true", str(order_ok).lower()),
            ("CUTOFF_TS recorded", cutoff, ",".join(sorted({r[7] for r in intents})) or cutoff),
            ("SCHEDULE_CODE", "CLSD7Y", ",".join(sorted({r[6] for r in intents})) or "CLSD7Y"),
        ]
        for name, o, s in facts:
            parity.checks.append(Check("purge intent", item, name, "", o, s))
        parity.facts[f"purge_intent_{as_of}"] = (len(parents), len(children))

    def sf_call(sql: str, params: Sequence[object]) -> str:
        try:
            return norm(sf.rows(sql, params)[0][0])
        except Exception as exc:  # noqa: BLE001
            return sf_error(exc)

    guard = [
        ("run_id NULL", "ERR -20001: RETENTION_PKG.PURGE_INTENT: run_id missing", "CALL MIG.PURGE_INTENT(NULL)", ()),
        (
            "run already recorded for another as-of",
            f"ERR -20001: RETENTION_PKG.PURGE_INTENT: run {ns}-2026-01-01 already recorded as_of=2026-01-01",
            "CALL MIG.PURGE_INTENT(?, '2027-01-01'::DATE, ?)",
            (f"{ns}-2026-01-01", ns),
        ),
    ]
    for name, expected, sql, params in guard:
        parity.checks.append(Check("purge intent", "PURGE_INTENT guards", name, "", expected, sf_call(sql, params)))


def _run(ora: Oracle, sf: Snowflake, parity: Parity) -> None:
    ns = parity.namespace
    _apply_ddl(sf, parity)
    others = sf.rows("SELECT COUNT(DISTINCT NAMESPACE) FROM ARCH.RETNPLCY WHERE NAMESPACE <> ?", (ns,))[0][0]
    parity.facts["other_namespaces"] = int(others)

    policies = ora.rows(
        "SELECT POLICY_CODE, POLICY_DESC, RETENTION_YEARS, SUCCESSOR_CODE, ACTIVE_FLAG, DISPOSITION_ACTION, "
        f"TO_CHAR(EFFECTIVE_TS, '{TS9}') FROM ARCHIVE.RETNPLCY ORDER BY POLICY_CODE"
    )
    planted, sampled, per_class = _sample_keys(ora)
    keys = planted + sampled
    doc_rows = ora.rows(f"SELECT {DOC_COLS} FROM ARCHIVE.DOCARCH WHERE ARCH_KEY IN ({ORA_KEYS})", keys=_keys_json(keys))
    docs = {r[0]: r for r in doc_rows}
    for key in keys:
        problem = _landing_problem(docs[key])
        if problem:
            parity.skipped_rows[key.rstrip()] = problem
    loaded = [k for k in keys if k.rstrip() not in parity.skipped_rows]
    auds = ora.rows(
        "SELECT AUDIT_KEY, ARCH_KEY, EVENT_TYPE, TO_CHAR(EVENT_TS, '" + TS9 + "'), ACTOR_ID, RETENTION_CLASS, "
        f"DISPOSITION_CODE, CLIENT_IP, DETAIL_TEXT FROM ARCHIVE.FILEAUD WHERE ARCH_KEY IN ({ORA_KEYS})",
        keys=_keys_json(loaded),
    )
    planted_aud = ora.rows("SELECT COUNT(*) FROM ARCHIVE.FILEAUD WHERE AUDIT_KEY LIKE 'MIG%'")[0][0]
    parity.facts.update(
        policy_codes=len(policies),
        planted_docarch=len(planted),
        planted_fileaud=int(planted_aud),
        planted_fileaud_loaded=sum(1 for a in auds if a[0].startswith("MIG")),
        sampled_keys=len(sampled),
        per_class=dict(sorted(per_class.items())),
        loaded_docarch=len(loaded),
        loaded_fileaud=len(auds),
        leap_rows=sum(1 for k in keys if docs[k][4][5:10] == "02-29"),
        low_values_rows=sum(1 for k in keys if docs[k][8] == "0" * 16),
    )

    _load(sf, ns, f"{ns}-load", policies, [docs[k] for k in loaded], auds)
    for group in _function_groups(policies, docs, planted, sampled):
        with ThreadPoolExecutor(2) as sides:
            o_fut = sides.submit(evaluate_group, ora, ORACLE, group)
            s_fut = sides.submit(evaluate_group, sf, SNOWFLAKE, group)
            o, s = o_fut.result(), s_fut.result()
        labels = {c.id: c for c in group.cases}
        for case_id, func in sorted(set(o) | set(s)):
            c = labels[case_id]
            inputs = json.dumps({k: v for k, v in c.as_json().items() if k != "id" and v is not None})
            parity.checks.append(
                Check(
                    "functions",
                    func,
                    f"{group.name}: {c.label}",
                    inputs,
                    o.get((case_id, func), "<missing>"),
                    s.get((case_id, func), "<missing>"),
                )
            )

    _view_checks(ora, sf, parity, loaded)
    _purge_checks(ora, sf, parity, loaded)


# --- report -------------------------------------------------------------------------------------------------


def write_report(parity: Parity) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path, md_path = REPORT_DIR / "retention-parity.csv", REPORT_DIR / "retention-parity.md"
    with csv_path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["section", "item", "case", "inputs", "oracle", "snowflake", "match"])
        for c in parity.checks:
            w.writerow([c.section, c.item, c.key, c.inputs, c.oracle, c.snowflake, "Y" if c.ok else "N"])

    f = parity.facts
    by_item: dict[tuple[str, str], list[Check]] = defaultdict(list)
    for c in parity.checks:
        by_item[(c.section, c.item)].append(c)
    lines = [
        "# RETENTION_PKG parity: Oracle stand-in vs Snowflake port",
        "",
        f"Generated {dt.datetime.now(dt.UTC):%Y-%m-%d %H:%M:%SZ} by `migration/job/tests/test_retention_parity.py`.",
        f"Oracle `ARCHIVE` (read-only session) vs Snowflake `{SF_ENV['SNOWFLAKE_DATABASE']}` "
        f"(role `{SF_ENV['SNOWFLAKE_ROLE']}`), namespace `{parity.namespace}`.",
        "",
        f"**{len(parity.checks)} comparisons, {len(parity.mismatches())} mismatches.**",
        "",
        "## Inputs",
        "",
        "| input set | rows |",
        "|---|---:|",
        f"| RETNPLCY policy codes | {f.get('policy_codes')} |",
        f"| code edge cases x hold (Y/N/NULL) | {len(EDGE_CODES) * 3} |",
        f"| planted MIG DOCARCH rows | {f.get('planted_docarch')} |",
        f"| planted MIG FILEAUD rows (loaded) | {f.get('planted_fileaud')} ({f.get('planted_fileaud_loaded')}) |",
        f"| sampled keys (<= {SAMPLE_PER_CLASS} per class x hold, + <= {LEAP_PER_CLASS} leap-day per class) "
        f"| {f.get('sampled_keys')} |",
        f"| leap-day (29 Feb) source rows among them | {f.get('leap_rows')} |",
        f"| LOW-VALUES DISPOSITION_DT source rows among them | {f.get('low_values_rows')} |",
        f"| synthetic leap-day timestamps x codes | {len(LEAP_TS) * (f.get('policy_codes') or 0)} |",
        f"| RAW(8) disposition-date cases | {len(RAW_CASES)} |",
        f"| loaded into STG -> ARCH: DOCARCH / FILEAUD | {f.get('loaded_docarch')} / {f.get('loaded_fileaud')} |",
        "",
        "## Results",
        "",
        "| section | object | comparisons | mismatches |",
        "|---|---|---:|---:|",
    ]
    for (section, item), checks in by_item.items():
        lines.append(f"| {section} | `{item}` | {len(checks)} | {sum(1 for c in checks if not c.ok)} |")
    lines += [
        "",
        "## V_CLASS_TOTALS over the loaded sample",
        "",
        "| class | Oracle docs | Snowflake docs | Oracle charge | Snowflake charge |",
        "|---|---:|---:|---:|---:|",
        *[f"| {c} | {od} | {sd} | {oc} | {sc} |" for c, od, sd, oc, sc in parity.class_totals],
        "",
        "Oracle `ARCHIVE.V_CLASS_TOTALS`, full population (context, not compared): "
        + ", ".join(f"{r[0].rstrip()} {norm(r[1])} / {norm(r[2])}" for r in parity.oracle_full_totals),
        "",
        "## PURGE_INTENT vs PURGE_ELIGIBLE's selection (sample)",
        "",
        "| as of | parents | children |",
        "|---|---:|---:|",
        *[
            f"| {k.removeprefix('purge_intent_')} | {v[0]} | {v[1]} |"
            for k, v in f.items()
            if k.startswith("purge_intent_")
        ],
        "",
        "## Rows evaluated but not loaded into ARCH (target types cannot hold them; the engine rejects them)",
        "",
        *([f"- `{k}`: {v}" for k, v in sorted(parity.skipped_rows.items())] or ["- none"]),
        "",
        "## Schema version",
        "",
        "| file | sha256 | recorded in MIG.SCHEMA_VERSION |",
        "|---|---|---|",
        *[f"| {n} | `{a[:12]}` | `{b[:12]}` |" for n, (a, b) in parity.schema_version.items()],
        "",
        f"Sample per class x hold: {', '.join(f'{k} {v}' for k, v in (f.get('per_class') or {}).items())}.",
        "",
    ]
    bad = parity.mismatches()
    if bad:
        lines += ["## Mismatches (first 50)", "", "| object | case | oracle | snowflake |", "|---|---|---|---|"]
        lines += [f"| {c.item} | {c.key} | `{c.oracle}` | `{c.snowflake}` |" for c in bad[:50]]
    md_path.write_text("\n".join(lines) + "\n")
    return md_path, csv_path


# --- tests --------------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def parity():
    ora, sf = Oracle(), Snowflake()
    result = Parity(namespace=f"rp-{uuid.uuid4().hex[:10]}")
    try:
        _run(ora, sf, result)
        write_report(result)
        yield result
    finally:
        try:
            _cleanup(sf, result.namespace)
        finally:
            sf.close()
            ora.close()


def _fail_text(checks: list[Check]) -> str:
    return "\n".join(f"{c.item} [{c.key}] oracle={c.oracle!r} snowflake={c.snowflake!r}" for c in checks[:20])


def test_inputs_cover_the_estate(parity: Parity) -> None:
    f = parity.facts
    assert f["policy_codes"] == EXPECTED_POLICY_CODES
    assert f["planted_docarch"] == EXPECTED_PLANTED_DOCARCH
    assert f["planted_fileaud"] == EXPECTED_PLANTED_FILEAUD
    assert f["leap_rows"] > 0 and f["low_values_rows"] > 0
    classes = {k.split("/")[0] for k in f["per_class"]}
    assert len(classes) >= 35


def test_retention_ddl_is_schema_versioned(parity: Parity) -> None:
    for name, (sha, recorded) in parity.schema_version.items():
        assert recorded == sha, name


def test_functions_match_oracle(parity: Parity) -> None:
    bad = parity.mismatches("functions")
    assert not bad, _fail_text(bad)


def test_views_match_oracle(parity: Parity) -> None:
    bad = parity.mismatches("views")
    assert not bad, _fail_text(bad)


def test_class_totals_match_oracle(parity: Parity) -> None:
    assert parity.class_totals
    bad = parity.mismatches("class totals")
    assert not bad, _fail_text(bad)


def test_purge_intent_matches_purge_eligible_selection(parity: Parity) -> None:
    bad = parity.mismatches("purge intent")
    assert not bad, _fail_text(bad)
