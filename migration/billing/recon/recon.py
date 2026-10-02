#!/usr/bin/env python3
"""OtterWorks billing recon: Oracle OW_BILLING vs MongoDB Atlas, driven by mapping_spec.json.

Plan step s3.4-recon-script. Replaces the mongo-migration plugin's recon harness with repo-only
tooling (python-oracledb + pymongo). For every collection in migration/billing/mapping_spec.json
it compares, per source table:

  * row counts (source rows vs target documents / embedded elements / quarantine documents),
  * keyed field-by-field values with the mapping applied (camelCase, compound _id, embedded
    arrays keyed by the identity the spec names), money as Decimal vs Decimal128 (a float on
    either side is a defect, never a rounding question),
  * tolerances read only from migration/billing/tolerances.json,
  * the known fixture anomalies (migration/billing/fixtures/demo.json#anomalies) as sets:
    orphaned INVOICE_LINE rows must land in invoice_feed_quarantine exactly, dirty dates and
    malformed CSV lists must keep the verbatim string and drop the derived field, and the EAV
    boolean spelling matrix must survive cell by cell,
  * the fixture's census delta (demo.json#census_delta) is accounted for explicitly, never
    reported as a dropped or unexpected row.

Oracle access is SELECT only under SET TRANSACTION READ ONLY at tolerances.json#concurrency.
Output is a JSON report conforming to docs/tech-partnerships/contracts/schema/recon-report.schema.json
(check: make tp-validate-recon FILE=<report>). run_mode is "live" only when the source is the
OW_TP_ORACLE_RO_DSN host and the target is the MONGODB_ATLAS_URI cluster; a fixture/local report
is never merge evidence and says so in merge_evidence=false.

Usage:
    recon.py selftest [--out DIR] [--mongo-uri mongodb://127.0.0.1:27117]
    recon.py run --mode live  --out FILE [--unit NAME] [--collections a,b]
    recon.py run --mode local --out FILE --oracle-dsn-env VAR --mongo-uri-env VAR --mongo-db DB
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
BILLING = HERE.parent
REPO = BILLING.parents[1]
SPEC_PATH = BILLING / "mapping_spec.json"
TOLERANCES_PATH = BILLING / "tolerances.json"
FIXTURE_PATH = BILLING / "fixtures" / "demo.json"
SCHEMA_PATH = REPO / "docs" / "tech-partnerships" / "contracts" / "schema" / "recon-report.schema.json"

SCHEMA_URL = "https://otterworks.dev/contracts/recon-report.schema.json"
SAMPLE_LIMIT = 25
UTC = dt.timezone.utc

MISSING = object()  # a field absent from a document / a NULL source column


# --------------------------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------------------------

def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def camel_to_snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).upper()


COLUMN_RE = re.compile(r"^([A-Z][A-Z0-9_]*)\.([A-Z][A-Z0-9_]*)$")
DERIVED_RE = re.compile(r"^(?:([A-Z][A-Z0-9_]*)\.([A-Z][A-Z0-9_]*) )?\(derived\)$")
IDENTITY_RE = re.compile(r"([A-Za-z_]+)\[\]\.([A-Za-z_]+) keeps ([A-Z][A-Z0-9_]*)\.([A-Z][A-Z0-9_]*)")
IDENTITY_SUBDOC_RE = re.compile(r"([A-Za-z_]+)\.([A-Za-z_]+) keeps ([A-Z][A-Z0-9_]*)\.([A-Z][A-Z0-9_]*)")
# Child-table column that holds the parent's _id (the spec says it "is the parent _id and is not
# repeated"); derived from the spec's `tables` section: the child's parent table is the collection's
# primary table, and the FK column is <PARENT_SINGULAR>_ID or ENTITY_ID.
PARENT_FK_RE = re.compile(r"([A-Z][A-Z0-9_]*)\.([A-Z][A-Z0-9_]*) is the parent _id")


@dataclass
class FieldMap:
    field: str          # document field name (camelCase)
    table: str          # source table (upper)
    column: str | None  # source column (upper) or None for purely derived fields
    bson: str
    nullable: bool
    derived: bool
    money: bool = False

    @property
    def comparable(self) -> bool:
        return self.column is not None and not self.derived


@dataclass
class EmbeddedMap:
    path: str
    table: str
    shape: str              # "array" | "subdoc"
    identity_field: str | None
    identity_column: str | None
    parent_fk: str
    fields: list[FieldMap]
    order_fields: list[str]
    fixed_filter: dict[str, str]   # column -> required constant (ENTITY_TYPE='CUSTOMER')
    quarantine_collection: str | None


@dataclass
class CollectionMap:
    name: str
    kind: str
    table: str                       # primary source table
    id_columns: list[str]            # source columns that form _id
    id_fields: list[str]             # document key names when compound ({codeType, codeVal})
    fields: list[FieldMap]
    embedded: list[EmbeddedMap]
    quarantine_of: EmbeddedMap | None = None   # set for invoice_feed_quarantine-style collections
    window_days: int | None = None            # billing_audit_log 90-day window


@dataclass
class Inputs:
    spec: dict
    tolerances: dict
    fixture: dict | None
    spec_sha: str
    tolerances_sha: str
    fixture_sha: str | None
    collections: list[CollectionMap] = field(default_factory=list)
    money_columns: dict[str, set[str]] = field(default_factory=dict)

    @property
    def unit(self) -> str:
        return self.spec.get("unit", "billing")


def _parse_source(source: str) -> tuple[str | None, str | None, bool]:
    m = COLUMN_RE.match(source)
    if m:
        return m.group(1), m.group(2), False
    m = DERIVED_RE.match(source)
    if m:
        return m.group(1), m.group(2), True
    raise ValueError(f"unrecognised field source {source!r}")


def _field_maps(fields: list[dict], default_table: str, money: dict[str, set[str]]) -> list[FieldMap]:
    out = []
    for f in fields:
        table, column, derived = _parse_source(f["source"])
        table = table or default_table
        is_money = f["bson"] == "decimal" and column is not None and column.lower() in money.get(table.lower(), set())
        out.append(FieldMap(f["field"], table, column, f["bson"], bool(f.get("nullable", False)), derived, is_money))
    return out


def _order_fields(text: str | None) -> list[str]:
    if not text:
        return []
    names = []
    for seg in re.sub(r"\([^)]*\)", "", text).split(","):
        seg = seg.strip()
        seg = re.sub(r"^then\s+", "", seg)
        m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", seg)
        if m and m.group(1) not in ("the", "ascending", "descending"):
            names.append(m.group(1))
    return names


def build_inputs(spec_path: Path = SPEC_PATH, tolerances_path: Path = TOLERANCES_PATH,
                 fixture_path: Path | None = FIXTURE_PATH) -> Inputs:
    spec = load_json(spec_path)
    tolerances = load_json(tolerances_path)
    fixture = load_json(fixture_path) if fixture_path and fixture_path.exists() else None
    money = {t.lower(): {c.lower() for c in cols}
             for t, cols in tolerances["numeric_tolerances"]["money"]["columns"].items()}
    inputs = Inputs(spec, tolerances, fixture, sha256_of(spec_path), sha256_of(tolerances_path),
                    sha256_of(fixture_path) if fixture else None, money_columns=money)
    tables = spec["tables"]
    by_name = {c["name"]: c for c in spec["collections"]}
    primary_for: dict[str, str] = {}
    for tname, t in tables.items():
        if t.get("mode") == "collection":
            primary_for[t["collection"]] = tname
    quarantine_target: dict[str, str] = {}
    for tname, t in tables.items():
        for q in t.get("quarantine", []) or []:
            quarantine_target[q] = tname

    for cname, c in by_name.items():
        if cname in quarantine_target:
            continue  # built after its parent collection below
        table = primary_for.get(cname)
        if table is None:
            raise ValueError(f"collection {cname} has no primary table in spec.tables")
        id_shape = c["_id"]["shape"]
        id_fields = list(id_shape.keys()) if isinstance(id_shape, dict) else []
        id_columns = [src.split(".")[-1] for src in c["_id"]["from"]]
        fields = _field_maps(c["fields"], table, money)
        embedded = []
        for e in c.get("embedded", []) or []:
            shape = "subdoc" if "one-to-one" in e.get("relationship", "") or e.get("shape") == "subdocument" else "array"
            ident = e.get("identity", "")
            m = IDENTITY_RE.search(ident) or IDENTITY_SUBDOC_RE.search(ident)
            ident_field = m.group(2) if m else None
            ident_col = m.group(4) if m else None
            m2 = PARENT_FK_RE.search(ident)
            if m2:
                parent_fk = m2.group(2)
            elif "ENTITY_ID" in ident:
                parent_fk = "ENTITY_ID"
            elif id_columns[0] != "ID":
                parent_fk = id_columns[0]          # INVOICE_HEADER.INVOICE_ID -> INVOICE_LINE.INVOICE_ID
            else:
                parent_fk = f"{table[:-1] if table.endswith('S') else table}_ID"
            fixed = {"ENTITY_TYPE": "CUSTOMER"} if "ENTITY_TYPE ('CUSTOMER')" in ident else {}
            qcoll = (tables.get(e["source_table"], {}).get("quarantine") or [None])[0]
            embedded.append(EmbeddedMap(e["path"], e["source_table"], shape, ident_field, ident_col, parent_fk,
                                        _field_maps(e["fields"], e["source_table"], money), _order_fields(e.get("order")),
                                        fixed, qcoll))
        window = None
        if "90" in json.dumps(tables.get(table, {}).get("retention", "")) and "day" in json.dumps(tables.get(table, {}).get("retention", "")):
            window = 90
        inputs.collections.append(CollectionMap(cname, c["kind"], table, id_columns, id_fields, fields, embedded, None, window))

    for qname, tname in quarantine_target.items():
        c = by_name[qname]
        parent = next(e for col in inputs.collections for e in col.embedded if e.table == tname)
        fields = _field_maps(c["fields"], tname, money)
        inputs.collections.append(CollectionMap(qname, c["kind"], tname, [src.split(".")[-1] for src in c["_id"]["from"]], [],
                                                fields, [], parent, None))
    return inputs


# --------------------------------------------------------------------------------------------
# Value canonicalisation and comparison
# --------------------------------------------------------------------------------------------

class TypeViolation(Exception):
    pass


def _as_decimal(v: Any, side: str) -> Decimal:
    if isinstance(v, bool):
        raise TypeViolation(f"{side} bool where decimal expected")
    if isinstance(v, float):
        raise TypeViolation(f"{side} binary float where decimal expected")
    if isinstance(v, Decimal):
        return v
    if isinstance(v, int):
        return Decimal(v)
    if type(v).__name__ == "Decimal128":
        return v.to_decimal()
    if isinstance(v, str):
        try:
            return Decimal(v)
        except InvalidOperation as exc:
            raise TypeViolation(f"{side} string {v!r} is not a decimal") from exc
    raise TypeViolation(f"{side} {type(v).__name__} where decimal expected")


def _as_int(v: Any, side: str) -> int:
    if isinstance(v, bool):
        raise TypeViolation(f"{side} bool where int expected")
    if isinstance(v, float):
        raise TypeViolation(f"{side} binary float where int expected")
    if isinstance(v, int):
        return int(v)
    if isinstance(v, Decimal):
        if v != v.to_integral_value():
            raise TypeViolation(f"{side} non-integral {v} where int expected")
        return int(v)
    if type(v).__name__ == "Decimal128":
        return _as_int(v.to_decimal(), side)
    raise TypeViolation(f"{side} {type(v).__name__} where int expected")


def _as_datetime(v: Any, side: str) -> dt.datetime:
    if isinstance(v, dt.datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=UTC)
        return v.astimezone(UTC)
    if isinstance(v, dt.date):
        return dt.datetime(v.year, v.month, v.day, tzinfo=UTC)
    raise TypeViolation(f"{side} {type(v).__name__} where date expected")


def canon_source(value: Any, bson: str) -> Any:
    """Oracle value -> comparable Python value (MISSING for NULL)."""
    if value is None:
        return MISSING
    if bson == "string":
        return value if isinstance(value, str) else str(value)
    if bson in ("int", "long"):
        return _as_int(value, "source")
    if bson == "decimal":
        return _as_decimal(value, "source")
    if bson == "date":
        return _as_datetime(value, "source")
    return value


def canon_target(doc: dict, name: str, bson: str) -> Any:
    """Document field -> comparable Python value (MISSING when absent; explicit null is a violation)."""
    if name not in doc:
        return MISSING
    value = doc[name]
    if value is None:
        raise TypeViolation("target stores an explicit null where the mapping says absent")
    if bson == "string":
        if not isinstance(value, str):
            raise TypeViolation(f"target {type(value).__name__} where string expected")
        return value
    if bson in ("int", "long"):
        return _as_int(value, "target")
    if bson == "decimal":
        if type(value).__name__ != "Decimal128":
            raise TypeViolation(f"target {type(value).__name__} where Decimal128 expected")
        return value.to_decimal()
    if bson == "date":
        return _as_datetime(value, "target")
    return value


def _json_safe(v: Any) -> Any:
    if v is MISSING:
        return None
    if isinstance(v, Decimal):
        return str(v)
    if type(v).__name__ == "Decimal128":
        return str(v.to_decimal())
    if isinstance(v, (dt.datetime, dt.date)):
        return v.isoformat()
    if isinstance(v, (list, tuple)):
        return [_json_safe(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _json_safe(x) for k, x in v.items()}
    if isinstance(v, bytes):
        return v.hex()
    return v


@dataclass
class Tolerance:
    money_abs: Decimal
    decimal_abs: Decimal
    date_seconds: int
    trim: bool
    case_insensitive: bool

    @classmethod
    def from_tolerances(cls, tol: dict) -> "Tolerance":
        num = tol["numeric_tolerances"]
        money = Decimal(str(num["money"].get("absolute", 0)))
        dec = Decimal(str(num.get("default", {}).get("absolute", 0)))
        date_tol = tol.get("date_tolerances", {}).get("absolute_seconds", 0)
        s = tol.get("string_tolerances", {})
        return cls(money, dec, int(date_tol), bool(s.get("trim", False)), bool(s.get("case_insensitive", False)))


def values_equal(expected: Any, actual: Any, fm: FieldMap, tol: Tolerance) -> bool:
    if expected is MISSING or actual is MISSING:
        return expected is MISSING and actual is MISSING
    if fm.bson == "decimal":
        limit = tol.money_abs if fm.money else tol.decimal_abs
        return abs(expected - actual) <= limit
    if fm.bson == "date":
        return abs((expected - actual).total_seconds()) <= tol.date_seconds
    if fm.bson == "string":
        a, b = expected, actual
        if tol.trim:
            a, b = a.strip(), b.strip()
        if tol.case_insensitive:
            a, b = a.lower(), b.lower()
        return a == b
    return expected == actual


# --------------------------------------------------------------------------------------------
# Derived-field rules (what the loader must have done; recon checks presence/absence, not value)
# --------------------------------------------------------------------------------------------

MONTHS = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
DDMONYY_RE = re.compile(r"^(\d{2})-([A-Z]{3})-(\d{2})$")
CLEAN_CSV_RE = re.compile(r"^\d+(,\d+)*$")
CLEAN_ID_CSV_RE = re.compile(r"^[A-Za-z0-9-]+(,[A-Za-z0-9-]+)*$")


def parse_ddmonyy(text: str | None) -> dt.date | None:
    """Oracle TO_DATE(x,'DD-MON-RR'): None when not a calendar date (fixture anomaly dirty_dates)."""
    if not text:
        return None
    m = DDMONYY_RE.match(text.strip().upper())
    if not m:
        return None
    day, mon, yy = int(m.group(1)), MONTHS.get(m.group(2)), int(m.group(3))
    if mon is None:
        return None
    year = 2000 + yy if yy < 50 else 1900 + yy
    try:
        return dt.date(year, mon, day)
    except ValueError:
        return None


def csv_is_clean(text: str | None, pattern: re.Pattern = CLEAN_ID_CSV_RE) -> bool:
    return bool(text) and bool(pattern.match(text))


# --------------------------------------------------------------------------------------------
# Adapters: source rows and target documents
# --------------------------------------------------------------------------------------------

TABLE_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,29}$")


class DictSource:
    """In-memory source (self-test): {TABLE: [row dict with UPPER column keys]}."""

    def __init__(self, tables: dict[str, list[dict]], describe: dict | None = None):
        self.tables = tables
        self._describe = describe or {"system": "oracle", "mode": "fixture", "schema": "OW_BILLING", "driver": "in-memory"}

    def rows(self, table: str) -> list[dict]:
        return list(self.tables.get(table, []))

    def describe(self) -> dict:
        return dict(self._describe)


class OracleSource:
    """SELECT-only reader over python-oracledb; every session is SET TRANSACTION READ ONLY."""

    def __init__(self, raw_secret: str, secret_name: str, schema: str, concurrency: int):
        import oracledb  # imported lazily so fixture mode needs no driver

        oracledb.defaults.fetch_decimals = True
        self.schema = schema
        self.secret_name = secret_name
        self.concurrency = max(1, concurrency)
        kw = _oracle_kwargs(raw_secret)
        self.dsn_host = _dsn_host(kw["dsn"])
        self._pool = oracledb.create_pool(min=1, max=self.concurrency, increment=1, **kw)
        self.principal = self._principal()

    def _principal(self) -> dict:
        with self._pool.acquire() as conn, conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SELECT USER FROM dual")
            user = cur.fetchone()[0]
            cur.execute("SELECT privilege FROM session_privs WHERE privilege IN "
                        "('INSERT ANY TABLE','UPDATE ANY TABLE','DELETE ANY TABLE','CREATE ANY TABLE','DROP ANY TABLE','ALTER ANY TABLE')")
            offending = sorted(r[0] for r in cur.fetchall())
        if offending:
            raise SystemExit(f"{self.secret_name} principal is not read-only: {offending}")
        return {"user": user, "offending_privileges": offending}

    def rows(self, table: str) -> list[dict]:
        if not TABLE_NAME_RE.match(table) or not TABLE_NAME_RE.match(self.schema):
            raise ValueError(f"refusing non-identifier table name {table!r}")
        with self._pool.acquire() as conn, conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.arraysize = 5000
            cur.execute(f"SELECT * FROM {self.schema}.{table}")
            cols = [d[0].upper() for d in cur.description]
            out = [dict(zip(cols, r)) for r in cur.fetchall()]
            conn.rollback()
        return out

    def describe(self) -> dict:
        return {"system": "oracle", "schema": self.schema, "dsn_secret": self.secret_name, "host": self.dsn_host,
                "transaction": "SET TRANSACTION READ ONLY", "concurrency": self.concurrency,
                "principal": self.principal["user"], "statements": "SELECT only"}


def _oracle_kwargs(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("{"):
        cfg = json.loads(raw)
        return {"user": cfg["user"], "password": cfg["password"], "dsn": cfg["dsn"]}
    if "@" in raw:
        creds, dsn = raw.rsplit("@", 1)
        user, _, password = creds.partition("/")
        return {"user": user, "password": password, "dsn": dsn}
    return {"dsn": raw}


def _dsn_host(dsn: str) -> str:
    m = re.search(r"HOST\s*=\s*([^)\s]+)", dsn, re.I)
    if m:
        return m.group(1)
    if "://" in dsn:
        return urlparse(dsn).hostname or dsn
    return dsn.split("/")[0].split(":")[0]


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", ""}


class DictTarget:
    """In-memory target (self-test): documents pass through a BSON round trip so types match a driver read."""

    def __init__(self, collections: dict[str, list[dict]], describe: dict | None = None):
        from bson import decode, encode
        from bson.codec_options import CodecOptions

        opts = CodecOptions(tz_aware=True)
        self.collections = {k: [decode(encode(d), codec_options=opts) for d in v] for k, v in collections.items()}
        self._describe = describe or {"system": "mongodb", "mode": "fixture", "driver": "in-memory"}

    def docs(self, collection: str) -> list[dict]:
        return list(self.collections.get(collection, []))

    def describe(self) -> dict:
        return dict(self._describe)


class MongoTarget:
    def __init__(self, uri: str, database: str, secret_name: str | None):
        from pymongo import MongoClient

        self.client = MongoClient(uri, tz_aware=True, serverSelectionTimeoutMS=15000, appname="ow-billing-recon")
        self.db = self.client[database]
        self.database = database
        self.secret_name = secret_name
        self.client.admin.command("ping")
        self.hosts = sorted({h for h, _port in self.client.nodes})

    def docs(self, collection: str) -> list[dict]:
        return list(self.db[collection].find({}, batch_size=5000))

    def describe(self) -> dict:
        return {"system": "mongodb", "database": self.database, "uri_secret": self.secret_name, "hosts": self.hosts,
                "statements": "find only"}


# --------------------------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------------------------

@dataclass
class Check:
    id: str
    expected: Any
    actual: Any
    source_of_truth: str
    result: str
    description: str = ""
    samples: list = field(default_factory=list)

    def to_json(self) -> dict:
        out = {"id": self.id, "description": self.description, "result": self.result,
               "expected": _json_safe(self.expected), "actual": _json_safe(self.actual),
               "source_of_truth": self.source_of_truth}
        if self.samples:
            out["samples"] = _json_safe(self.samples[:SAMPLE_LIMIT])
        return out


def canon_key(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else str(v)
    if type(v).__name__ == "Decimal128":
        return canon_key(v.to_decimal())
    if isinstance(v, float):
        return int(v) if v.is_integer() else str(v)
    if isinstance(v, int):
        return int(v)
    if isinstance(v, (dt.datetime, dt.date)):
        return _as_datetime(v, "key").isoformat()
    return v


def row_key(row: dict, columns: list[str]) -> tuple:
    return tuple(canon_key(row.get(c)) for c in columns)


def doc_key(doc: dict, cm: CollectionMap) -> tuple | None:
    _id = doc.get("_id")
    if cm.id_fields:
        if not isinstance(_id, dict) or list(_id.keys()) != cm.id_fields:
            return None
        return tuple(canon_key(_id[k]) for k in cm.id_fields)
    return (canon_key(_id),)


def _fmt_key(key: tuple) -> str:
    return ":".join(str(k) for k in key)


class ReconRun:
    def __init__(self, inputs: Inputs, source, target, run_mode: str, concurrency: int | None = None,
                 now: dt.datetime | None = None, collections: Iterable[str] | None = None):
        if run_mode not in ("fixture", "live"):
            raise ValueError("run_mode must be fixture or live")
        self.inputs = inputs
        self.source = source
        self.target = target
        self.run_mode = run_mode
        self.tol = Tolerance.from_tolerances(inputs.tolerances)
        self.concurrency = concurrency or int(inputs.tolerances.get("source", {}).get("concurrency", 1))
        self.now = now or dt.datetime.now(UTC)
        wanted = set(collections) if collections else None
        self.collections = [c for c in inputs.collections if wanted is None or c.name in wanted]
        self.checks: list[Check] = []
        self.unverified: list[str] = []
        self.anomaly_expected: list[str] = []
        self.anomaly_actual: list[str] = []
        self._rows: dict[str, list[dict]] = {}
        self._docs: dict[str, list[dict]] = {}
        self._derived_defects: list[dict] = []
        self.timings: dict[str, float] = {}

    # ---- fetch ---------------------------------------------------------------------------
    def fetch(self) -> None:
        tables = sorted({c.table for c in self.collections} | {e.table for c in self.collections for e in c.embedded})
        t0 = time.monotonic()
        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            for table, rows in zip(tables, pool.map(self.source.rows, tables)):
                self._rows[table] = rows
        self.timings["source_fetch_s"] = round(time.monotonic() - t0, 3)
        t0 = time.monotonic()
        for c in self.collections:
            self._docs[c.name] = self.target.docs(c.name)
        self.timings["target_fetch_s"] = round(time.monotonic() - t0, 3)

    def rows(self, table: str) -> list[dict]:
        return self._rows.get(table, [])

    # ---- checks --------------------------------------------------------------------------
    def check(self, cid: str, expected: Any, actual: Any, truth: str, ok: bool | None, description: str = "",
              samples: list | None = None) -> Check:
        result = "skipped" if ok is None else ("pass" if ok else "fail")
        c = Check(cid, expected, actual, truth, result, description, samples or [])
        self.checks.append(c)
        return c

    def compare(self) -> None:
        self.checks, self.unverified, self._derived_defects = [], [], []
        self.anomaly_expected, self.anomaly_actual = [], []
        self._check_tolerance_coverage()
        quarantine_sets: dict[str, dict[tuple, dict]] = {}
        for cm in self.collections:
            if cm.quarantine_of is not None:
                continue
            quarantine_sets.update(self._compare_collection(cm))
        for cm in self.collections:
            if cm.quarantine_of is not None:
                self._compare_quarantine(cm, quarantine_sets.get(cm.name, {}))
        self._check_census_delta()
        self._check_anomaly_sets(quarantine_sets)
        self._check_derived_defects()

    def _check_tolerance_coverage(self) -> None:
        missing = []
        for cm in self.collections:
            for fm in cm.fields + [f for e in cm.embedded for f in e.fields]:
                if fm.bson == "decimal" and not fm.derived and not fm.money and fm.column:
                    missing.append(f"{fm.table}.{fm.column}")
        self.check("tolerances.money_columns_cover_spec", [], sorted(set(missing)), "migration/billing/tolerances.json",
                   not missing, "every decimal column in the mapping spec is listed under numeric_tolerances.money.columns")
        self.check("tolerances.money_rule", {"absolute": "0", "float_is_defect": True},
                   {"absolute": str(self.tol.money_abs), "float_is_defect": True}, "migration/billing/tolerances.json",
                   self.tol.money_abs == 0, "money compares Decimal vs Decimal128 exactly; a binary float on either side is a defect")

    # -- primary table -> collection
    def _compare_collection(self, cm: CollectionMap) -> dict[str, dict[tuple, dict]]:
        truth = f"oracle.OW_BILLING.{cm.table}"
        rows = self.rows(cm.table)
        docs = self._docs.get(cm.name, [])
        if cm.window_days:
            cutoff = self.now - dt.timedelta(days=cm.window_days)
            col = next((f for f in cm.fields if f.bson == "date" and f.column), None)
            if col:
                before = len(rows)
                rows = [r for r in rows if r.get(col.column) is None or _as_datetime(r[col.column], "source") >= cutoff]
                docs = [d for d in docs if col.field not in d or _as_datetime(d[col.field], "target") >= cutoff]
                if before != len(rows):
                    self.unverified.append(f"{cm.name}: {before - len(rows)} source rows older than the {cm.window_days}-day retention window were not compared")
        src: dict[tuple, dict] = {}
        dup_src = []
        for r in rows:
            k = row_key(r, cm.id_columns)
            if k in src:
                dup_src.append(_fmt_key(k))
            src[k] = r
        tgt: dict[tuple, dict] = {}
        bad_id, dup_tgt = [], []
        for d in docs:
            k = doc_key(d, cm)
            if k is None:
                bad_id.append(_json_safe(d.get("_id")))
                continue
            if k in tgt:
                dup_tgt.append(_fmt_key(k))
            tgt[k] = d
        self.check(f"{cm.name}.row_count", len(rows), len(docs), truth, len(rows) == len(docs),
                   f"{cm.table} rows vs {cm.name} documents")
        if dup_src or bad_id or dup_tgt:
            self.check(f"{cm.name}.key_shape", {"duplicate_source_keys": 0, "malformed_ids": 0, "duplicate_target_keys": 0},
                       {"duplicate_source_keys": len(dup_src), "malformed_ids": len(bad_id), "duplicate_target_keys": len(dup_tgt)},
                       truth, False, "_id shape per mapping_spec.json", (dup_src + bad_id + dup_tgt))
        missing = sorted(src.keys() - tgt.keys(), key=_fmt_key)
        unexpected = sorted(tgt.keys() - src.keys(), key=_fmt_key)
        self.check(f"{cm.name}.keyed_presence", {"missing": 0, "unexpected": 0},
                   {"missing": len(missing), "unexpected": len(unexpected)}, truth, not missing and not unexpected,
                   "every source PK has exactly one document and no document lacks a source row",
                   [{"missing": _fmt_key(k)} for k in missing] + [{"unexpected": _fmt_key(k)} for k in unexpected])
        mismatches, money_violations = self._compare_fields(cm.name, cm.fields, src, tgt, cm.id_fields)
        self._emit_value_checks(cm.name, cm.table, truth, mismatches, money_violations)
        known = {"_id"} | {f.field for f in cm.fields} | {e.path for e in cm.embedded}
        extra = Counter(k for d in docs for k in d.keys() if k not in known)
        self.check(f"{cm.name}.fields_outside_mapping", {}, dict(extra), truth, not extra,
                   "document fields that the mapping spec does not define")
        quarantine: dict[str, dict[tuple, dict]] = {}
        for e in cm.embedded:
            q = self._compare_embedded(cm, e, src, tgt)
            if e.quarantine_collection:
                quarantine[e.quarantine_collection] = q
        return quarantine

    def _compare_fields(self, cname: str, fields: list[FieldMap], src: dict[tuple, dict], tgt: dict[tuple, dict],
                        skip_fields: list[str] | None = None) -> tuple[list[dict], list[dict]]:
        mismatches, money_violations = [], []
        skip = set(skip_fields or [])
        for k, row in src.items():
            doc = tgt.get(k)
            if doc is None:
                continue
            for fm in fields:
                if fm.field in skip:
                    continue
                if fm.derived:
                    self._check_derived(cname, k, fm, row, doc)
                    continue
                if fm.column is None:
                    continue
                try:
                    exp = canon_source(row.get(fm.column), fm.bson)
                    act = canon_target(doc, fm.field, fm.bson)
                except TypeViolation as exc:
                    entry = {"key": _fmt_key(k), "field": fm.field, "column": f"{fm.table}.{fm.column}", "reason": str(exc),
                             "expected": _json_safe(row.get(fm.column)), "actual": _json_safe(doc.get(fm.field, MISSING))}
                    mismatches.append(entry)
                    if fm.bson == "decimal":
                        money_violations.append(entry)
                    continue
                if not values_equal(exp, act, fm, self.tol):
                    mismatches.append({"key": _fmt_key(k), "field": fm.field, "column": f"{fm.table}.{fm.column}",
                                       "reason": "value differs", "expected": _json_safe(exp), "actual": _json_safe(act)})
        return mismatches, money_violations

    def _emit_value_checks(self, cname: str, table: str, truth: str, mismatches: list[dict], money_violations: list[dict]) -> None:
        self.check(f"{cname}.keyed_values", 0, len(mismatches), truth, not mismatches,
                   f"field-by-field values of {table} with the mapping applied (tolerances.json)", mismatches)
        self.check(f"{cname}.money_decimal128", 0, len(money_violations), truth, not money_violations,
                   "money fields are Decimal128 and equal the Oracle NUMBER as Decimal; no binary floats", money_violations)

    def _check_derived(self, cname: str, key: tuple, fm: FieldMap, row: dict, doc: dict) -> None:
        verbatim = row.get(fm.column) if fm.column else None
        present = fm.field in doc and doc[fm.field] is not None
        if fm.bson == "date" and fm.column:
            parsed = parse_ddmonyy(verbatim) if isinstance(verbatim, str) else None
            if parsed is None:
                if present:
                    self._derived_defects.append({"collection": cname, "key": _fmt_key(key), "field": fm.field,
                                                  "reason": "derived date present for a dirty/NULL verbatim string", "verbatim": verbatim})
            else:
                try:
                    act = canon_target(doc, fm.field, "date")
                except TypeViolation as exc:
                    act = str(exc)
                exp = dt.datetime(parsed.year, parsed.month, parsed.day, tzinfo=UTC)
                if act is MISSING or not isinstance(act, dt.datetime) or abs((act - exp).total_seconds()) > self.tol.date_seconds:
                    self._derived_defects.append({"collection": cname, "key": _fmt_key(key), "field": fm.field,
                                                  "reason": "derived date absent or differs", "verbatim": verbatim,
                                                  "expected": _json_safe(exp), "actual": _json_safe(act)})
        elif fm.bson == "array<string>" and fm.column:
            pattern = CLEAN_CSV_RE if fm.column == "GL_ACCT_CSV" else CLEAN_ID_CSV_RE
            clean = isinstance(verbatim, str) and csv_is_clean(verbatim, pattern)
            if clean:
                exp_list = verbatim.split(",")
                if not present or doc[fm.field] != exp_list:
                    self._derived_defects.append({"collection": cname, "key": _fmt_key(key), "field": fm.field,
                                                  "reason": "derived list absent or differs", "verbatim": verbatim,
                                                  "expected": exp_list, "actual": _json_safe(doc.get(fm.field, MISSING))})
            elif present:
                self._derived_defects.append({"collection": cname, "key": _fmt_key(key), "field": fm.field,
                                              "reason": "derived list present for a malformed verbatim CSV", "verbatim": verbatim})
        else:
            path = f"{cname}.{fm.field}"
            if path not in self.unverified:
                self.unverified.append(f"{path}: derived '{fm.bson}' value is loader-defined; recon checks only the verbatim source field")

    def _check_derived_defects(self) -> None:
        self.check("derived_fields.rules", 0, len(self._derived_defects), "migration/billing/mapping_spec.json",
                   not self._derived_defects,
                   "DD-MON-YY dates parse under the RR rule and CSV lists split only when clean; otherwise the derived field is absent",
                   self._derived_defects)

    # -- embedded child table
    def _compare_embedded(self, cm: CollectionMap, e: EmbeddedMap, src: dict[tuple, dict], tgt: dict[tuple, dict]) -> dict[tuple, dict]:
        truth = f"oracle.OW_BILLING.{e.table}"
        prefix = f"{cm.name}.{e.path}"
        children = self.rows(e.table)
        nonconforming = []
        if e.fixed_filter:
            keep = []
            for r in children:
                if all(r.get(col) == val for col, val in e.fixed_filter.items()):
                    keep.append(r)
                else:
                    nonconforming.append({col: r.get(col) for col in e.fixed_filter} | {"key": _fmt_key(row_key(r, [e.identity_column]))})
            children = keep
            self.check(f"{prefix}.row_class", {col: val for col, val in e.fixed_filter.items()} | {"other_rows": 0},
                       {"other_rows": len(nonconforming)}, truth, not nonconforming,
                       "rows of another entity type would fail the load; none expected", nonconforming)
        by_parent: dict[tuple, list[dict]] = defaultdict(list)
        orphans: dict[tuple, dict] = {}
        ident_cols = [e.identity_column] if e.identity_column else cm.id_columns
        for r in children:
            pk = (canon_key(r.get(e.parent_fk)),)
            if pk in src:
                by_parent[pk].append(r)
            else:
                orphans[row_key(r, ident_cols)] = r
        total_elems = 0
        missing, unexpected, mismatches, money_violations, order_defects, shape_defects = [], [], [], [], [], []
        for pk, doc in tgt.items():
            if pk not in src:
                continue
            exp_rows = {row_key(r, ident_cols): r for r in by_parent.get(pk, [])}
            raw = doc.get(e.path, MISSING)
            if e.shape == "subdoc":
                elems = [] if raw is MISSING else [raw]
                if raw is not MISSING and not isinstance(raw, dict):
                    shape_defects.append({"key": _fmt_key(pk), "reason": f"{e.path} is not a sub-document"})
                    continue
            else:
                if raw is MISSING:
                    elems = []
                elif not isinstance(raw, list):
                    shape_defects.append({"key": _fmt_key(pk), "reason": f"{e.path} is not an array"})
                    continue
                else:
                    elems = raw
            total_elems += len(elems)
            act_rows: dict[tuple, dict] = {}
            for el in elems:
                if not isinstance(el, dict):
                    shape_defects.append({"key": _fmt_key(pk), "reason": f"{e.path} element is not a document"})
                    continue
                k = (canon_key(el.get(e.identity_field)),) if e.identity_field else row_key(el, [])
                act_rows[k] = el
            if e.identity_field and len(act_rows) != len(elems):
                shape_defects.append({"key": _fmt_key(pk), "reason": f"duplicate {e.identity_field} inside {e.path}"})
            for k in exp_rows.keys() - act_rows.keys():
                missing.append({"parent": _fmt_key(pk), "missing": _fmt_key(k)})
            for k in act_rows.keys() - exp_rows.keys():
                unexpected.append({"parent": _fmt_key(pk), "unexpected": _fmt_key(k)})
            mm, mv = self._compare_fields(prefix, e.fields, exp_rows, act_rows)
            for m in mm:
                m["parent"] = _fmt_key(pk)
            mismatches.extend(mm)
            money_violations.extend(mv)
            if e.order_fields and len(elems) > 1:
                keys = [tuple(canon_key(el.get(f)) for f in e.order_fields) for el in elems if isinstance(el, dict)]
                if any(_order_lt(b, a) for a, b in zip(keys, keys[1:])):
                    order_defects.append({"key": _fmt_key(pk), "order": e.order_fields})
        quarantined = len(self._docs.get(e.quarantine_collection, [])) if e.quarantine_collection else 0
        self.check(f"{prefix}.row_count", len(children), total_elems + quarantined, truth,
                   len(children) == total_elems + quarantined,
                   f"{e.table} rows vs embedded {e.path} elements" + (f" + {e.quarantine_collection} documents" if e.quarantine_collection else ""))
        self.check(f"{prefix}.keyed_presence", {"missing": 0, "unexpected": 0}, {"missing": len(missing), "unexpected": len(unexpected)},
                   truth, not missing and not unexpected, f"each {e.table} row appears once under its parent, keyed by {e.identity_field}",
                   missing + unexpected)
        self._emit_value_checks(prefix, e.table, truth, mismatches, money_violations)
        self.check(f"{prefix}.shape_and_order", {"shape_defects": 0, "order_defects": 0},
                   {"shape_defects": len(shape_defects), "order_defects": len(order_defects)}, "migration/billing/mapping_spec.json",
                   not shape_defects and not order_defects, f"{e.path} is a {e.shape} ordered by {e.order_fields or 'n/a'}",
                   shape_defects + order_defects)
        if not e.quarantine_collection:
            self.check(f"{prefix}.orphans", 0, len(orphans), truth, not orphans,
                       f"{e.table} rows whose {e.parent_fk} has no parent row (no quarantine defined for this table)",
                       [_fmt_key(k) for k in orphans])
        return orphans

    # -- quarantine collection (orphan child rows)
    def _compare_quarantine(self, cm: CollectionMap, orphans: dict[tuple, dict]) -> None:
        truth = f"oracle.OW_BILLING.{cm.table}"
        docs = self._docs.get(cm.name, [])
        tgt = {k: d for d in docs if (k := doc_key(d, cm)) is not None}
        self.check(f"{cm.name}.row_count", len(orphans), len(docs), truth, len(orphans) == len(docs),
                   f"orphaned {cm.table} rows (parent missing) vs {cm.name} documents; quarantined rows must match exactly")
        missing = sorted(orphans.keys() - tgt.keys(), key=_fmt_key)
        unexpected = sorted(tgt.keys() - orphans.keys(), key=_fmt_key)
        self.check(f"{cm.name}.keyed_presence", {"missing": 0, "unexpected": 0}, {"missing": len(missing), "unexpected": len(unexpected)},
                   truth, not missing and not unexpected, "quarantine set equals the orphan set",
                   [{"missing": _fmt_key(k)} for k in missing] + [{"unexpected": _fmt_key(k)} for k in unexpected])
        mismatches, money_violations = self._compare_fields(cm.name, cm.fields, orphans, tgt)
        self._emit_value_checks(cm.name, cm.table, truth, mismatches, money_violations)
        bad_reason = [_fmt_key(k) for k, d in tgt.items()
                      if not isinstance(d.get("quarantine"), dict) or d["quarantine"].get("reason") != "orphaned_rows"]
        self.check(f"{cm.name}.quarantine_reason", 0, len(bad_reason), "migration/billing/mapping_spec.json", not bad_reason,
                   "every quarantined document carries quarantine.reason == 'orphaned_rows'", bad_reason)
        self.unverified.append(f"{cm.name}.quarantine.capturedAt: loader timestamp, not comparable to a source value")

    # -- census delta: fixture-only static_seed_version-2 rows are accounted for, never defects
    def _check_census_delta(self) -> None:
        fx = self.inputs.fixture
        if not fx or "census_delta" not in fx:
            self.check("census_delta.accounted", None, None, "migration/billing/fixtures/demo.json#census_delta", None,
                       "no fixture manifest supplied; census delta not evaluated")
            return
        delta = fx["census_delta"]["static_upgrade_rows"]
        tables_meta = fx.get("tables", {})
        table_to_cm = {c.table: c for c in self.collections if c.quarantine_of is None}
        table_to_emb = {e.table: (c, e) for c in self.collections for e in c.embedded}
        for table, pks in sorted(delta.items()):
            if table not in table_to_cm and table not in table_to_emb:
                if table != "FIXTURE_META":
                    self.unverified.append(f"census_delta.{table}: table is outside the mapping spec")
                continue
            rows = self.rows(table)
            if table in table_to_cm:
                cm = table_to_cm[table]
                present_src = {_fmt_key(row_key(r, cm.id_columns)) for r in rows} & set(pks)
                present_tgt = {_fmt_key(k) for d in self._docs.get(cm.name, []) if (k := doc_key(d, cm)) is not None} & set(pks)
            else:
                cm, e = table_to_emb[table]
                present_src = {_fmt_key(row_key(r, [e.identity_column])) for r in rows} & set(pks)
                present_tgt = set()
                for d in self._docs.get(cm.name, []):
                    raw = d.get(e.path)
                    for el in (raw if isinstance(raw, list) else [raw] if isinstance(raw, dict) else []):
                        if isinstance(el, dict):
                            present_tgt.add(_fmt_key((canon_key(el.get(e.identity_field)),)))
                present_tgt &= set(pks)
            census_rows = tables_meta.get(table, {}).get("census_rows")
            expected = {"census_rows": census_rows, "fixture_only_pks": sorted(pks), "rule": "source_rows == census_rows + fixture_only_present"}
            actual = {"source_rows": len(rows), "fixture_only_in_source": sorted(present_src), "fixture_only_in_target": sorted(present_tgt)}
            both_sides = present_src == present_tgt
            if self.run_mode == "fixture":
                ok = both_sides and (census_rows is None or len(rows) == census_rows + len(present_src))
            else:
                ok = both_sides
                if census_rows is not None and len(rows) != census_rows + len(present_src):
                    actual["note"] = "live row count drifted from the census capture; delta rows are still accounted for explicitly"
            self.check(f"census_delta.{table}", expected, actual, "migration/billing/fixtures/demo.json#census_delta", ok,
                       "fixture-only static_seed_version-2 rows are accounted for explicitly, never reported as dropped/unexpected")

    # -- planted anomaly sets
    def _check_anomaly_sets(self, quarantine_sets: dict[str, dict[tuple, dict]]) -> None:
        fx = self.inputs.fixture
        truth = "migration/billing/fixtures/demo.json#anomalies"
        if not fx or "anomalies" not in fx:
            self.check("anomalies.sets", None, None, truth, None, "no fixture manifest supplied; anomaly sets not evaluated")
            return
        for a in fx["anomalies"]:
            kind = a["kind"]
            handler = getattr(self, f"_anomaly_{kind}", None)
            if handler is None:
                self.unverified.append(f"anomalies.{kind}: no set comparison implemented")
                continue
            expected, in_source, in_target = handler(a, quarantine_sets)
            tagged_exp = [f"{kind}:{x}" for x in sorted(expected)]
            tagged_act = [f"{kind}:{x}" for x in sorted(in_target)]
            self.anomaly_expected.extend(tagged_exp)
            self.anomaly_actual.extend(tagged_act)
            missing_src, extra_src = sorted(expected - in_source), sorted(in_source - expected)
            missing_tgt, extra_tgt = sorted(expected - in_target), sorted(in_target - expected)
            self.check(f"anomalies.{kind}.source", {"size": len(expected)}, {"size": len(in_source), "missing": len(missing_src), "unexpected": len(extra_src)},
                       truth, not missing_src and not extra_src, f"{a.get('target')} planted set as seen in the source",
                       [{"missing": x} for x in missing_src] + [{"unexpected": x} for x in extra_src])
            self.check(f"anomalies.{kind}.target", {"size": len(expected)}, {"size": len(in_target), "missing": len(missing_tgt), "unexpected": len(extra_tgt)},
                       truth, not missing_tgt and not extra_tgt, f"{a.get('target')} planted set as it survived in the target (compare_as=set)",
                       [{"missing": x} for x in missing_tgt] + [{"unexpected": x} for x in extra_tgt])

    def _find(self, table: str):
        for c in self.collections:
            if c.table == table and c.quarantine_of is None:
                return c, None
            for e in c.embedded:
                if e.table == table:
                    return c, e
        return None, None

    def _anomaly_orphaned_rows(self, a: dict, quarantine_sets) -> tuple[set, set, set]:
        expected = set(a["line_ids"])
        cm, e = self._find("INVOICE_LINE")
        in_source = set()
        if e is not None:
            headers = {row_key(r, cm.id_columns) for r in self.rows(cm.table)}
            in_source = {r["LINE_ID"] for r in self.rows("INVOICE_LINE") if (canon_key(r.get(e.parent_fk)),) not in headers}
        in_target = set()
        for qname in quarantine_sets:
            qcm = next(c for c in self.collections if c.name == qname)
            in_target |= {_fmt_key(k) for d in self._docs.get(qname, []) if (k := doc_key(d, qcm)) is not None}
        return expected, in_source, in_target

    def _anomaly_dirty_dates(self, a: dict, _q) -> tuple[set, set, set]:
        table, column = a["target"].split(".")[-2:]
        expected = set(a["cust_ids"])
        cm, e = self._find(table)
        if cm is None:
            return expected, set(), set()
        in_source = {_fmt_key(row_key(r, cm.id_columns)) for r in self.rows(table)
                     if r.get(column) is not None and parse_ddmonyy(r[column]) is None}
        verbatim = next((f for f in cm.fields if f.column == column and not f.derived), None)
        derived = next((f for f in cm.fields if f.column == column and f.derived), None)
        in_target = set()
        if verbatim and derived:
            in_target = {_fmt_key(k) for d in self._docs.get(cm.name, [])
                         if (k := doc_key(d, cm)) is not None and verbatim.field in d and derived.field not in d}
        return expected, in_source, in_target

    def _anomaly_malformed_csv_lists(self, a: dict, _q) -> tuple[set, set, set]:
        table, column = a["target"].split(".")[-2:]
        expected = set(a["cust_ids"])
        cm, e = self._find(table)
        if cm is None:
            return expected, set(), set()
        pattern = re.compile(a["definition"].split("not matching ")[1].split(" ")[0]) if "not matching " in a.get("definition", "") else CLEAN_ID_CSV_RE
        in_source = {_fmt_key(row_key(r, cm.id_columns)) for r in self.rows(table)
                     if r.get(column) not in (None, "") and not pattern.match(r[column])}
        verbatim = next((f for f in cm.fields if f.column == column and not f.derived), None)
        derived = next((f for f in cm.fields if f.column == column and f.derived), None)
        in_target = set()
        if verbatim and derived:
            in_target = {_fmt_key(k) for d in self._docs.get(cm.name, [])
                         if (k := doc_key(d, cm)) is not None and d.get(verbatim.field) not in (None, "") and derived.field not in d}
        return expected, in_source, in_target

    def _anomaly_eav_boolean_spellings(self, a: dict, _q) -> tuple[set, set, set]:
        """(attr_name, attr_value) vocabulary with counts, cell by cell: 'NAME=VALUE#count'."""
        expected_counter: Counter = Counter()
        for name, cells in a["attr_value_matrix"].items():
            for value, n in cells.items():
                expected_counter[(name, value)] += n
        cm, e = self._find("ENTITY_ATTR_VALUE")
        if e is None:
            return set(), set(), set()
        rows = self.rows("ENTITY_ATTR_VALUE")
        static_ids = {str(r["eav_id"]) for r in a.get("static_baseline_rows", [])}
        present_static = {str(canon_key(r.get(e.identity_column))) for r in rows} & static_ids
        for r in a.get("static_baseline_rows", []):
            if str(r["eav_id"]) in present_static:
                expected_counter[(r["attr_name"], r["attr_value"])] += 1
        src_counter = Counter((r.get("ATTR_NAME"), r.get("ATTR_VALUE")) for r in rows if r.get(e.parent_fk) is not None)
        name_f = next(f for f in e.fields if f.column == "ATTR_NAME")
        value_f = next(f for f in e.fields if f.column == "ATTR_VALUE" and not f.derived)
        tgt_counter: Counter = Counter()
        for d in self._docs.get(cm.name, []):
            for el in d.get(e.path, []) or []:
                if isinstance(el, dict):
                    tgt_counter[(el.get(name_f.field), el.get(value_f.field))] += 1
        def fmt(c):
            return {f"{k[0]}={k[1]}#{n}" for k, n in c.items()}
        return fmt(expected_counter), fmt(src_counter), fmt(tgt_counter)

    # ---- verdict / report ----------------------------------------------------------------
    def verdict(self) -> str:
        return "pass" if all(c.result != "fail" for c in self.checks) else "fail"

    def signature(self) -> list[tuple]:
        return [(c.id, c.result, json.dumps(_json_safe(c.expected), sort_keys=True), json.dumps(_json_safe(c.actual), sort_keys=True))
                for c in self.checks]


def _order_lt(a: tuple, b: tuple) -> bool:
    try:
        return a < b
    except TypeError:
        return str(a) < str(b)


# --------------------------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------------------------

def build_report(run: ReconRun, namespace: str, idempotency: tuple[str, str], extra: dict | None = None) -> dict:
    inputs = run.inputs
    verdict = run.verdict()
    report = {
        "kind": "recon-report",
        "unit": inputs.unit,
        "namespace": namespace,
        "generated_at": run.now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_mode": run.run_mode,
        "verdict": verdict,
        "merge_evidence": run.run_mode == "live" and verdict == "pass",
        "merge_evidence_note": ("live recon report" if run.run_mode == "live"
                                else "fixture/local result: never merge evidence (tolerances.json#source.mode is live)"),
        "source": run.source.describe(),
        "target": run.target.describe(),
        "inputs": {
            "mapping_spec": {"path": "migration/billing/mapping_spec.json", "sha256": inputs.spec_sha},
            "tolerances": {"path": "migration/billing/tolerances.json", "sha256": inputs.tolerances_sha},
            "fixture": ({"path": "migration/billing/fixtures/demo.json", "sha256": inputs.fixture_sha} if inputs.fixture_sha else None),
        },
        "concurrency": {"oracle_sessions": run.concurrency},
        "timings": run.timings,
        "summary": {"checks": len(run.checks), "pass": sum(c.result == "pass" for c in run.checks),
                    "fail": sum(c.result == "fail" for c in run.checks), "skipped": sum(c.result == "skipped" for c in run.checks),
                    "failed_check_ids": [c.id for c in run.checks if c.result == "fail"]},
        "checks": [c.to_json() for c in run.checks],
        "values_recomputed_from_target": True,
        "idempotency_rerun": {"performed": True, "result": idempotency[0], "evidence": idempotency[1]},
        "planted_anomaly_detections": {
            "expected_set": sorted(run.anomaly_expected),
            "actual_set": sorted(run.anomaly_actual),
            "missing": sorted(set(run.anomaly_expected) - set(run.anomaly_actual)),
            "unexpected": sorted(set(run.anomaly_actual) - set(run.anomaly_expected)),
        },
        "unverified_paths": sorted(set(run.unverified)),
    }
    if extra:
        report.update(extra)
    return report


def execute(run: ReconRun) -> tuple[str, str]:
    """fetch once, compare twice; the second pass must reproduce the first (idempotency)."""
    run.fetch()
    run.compare()
    first = run.signature()
    run.compare()
    second = run.signature()
    if first == second:
        return "pass", f"compare() executed twice over the same fetched rows/documents; {len(first)} check signatures identical"
    diff = [a[0] for a, b in zip(first, second) if a != b]
    return "fail", f"second compare() pass differed on {diff[:10]}"


def validate_report(report: dict, schema_path: Path = SCHEMA_PATH) -> list[str]:
    from jsonschema import Draft202012Validator

    schema = load_json(schema_path)
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in validator.iter_errors(report)]


def write_report(report: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------------------------
# Self-test: a faithful synthetic copy built from the fixture manifest, loaded through the mapping
# --------------------------------------------------------------------------------------------

DEFAULT_SEED = 714559852
TRUE_SPELLINGS = {"Y", "1", "TRUE"}
FALSE_SPELLINGS = {"N", "0"}


def _uuid(rng) -> str:
    h = f"{rng.getrandbits(128):032x}"
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


def _ddmonyy(d: dt.date) -> str:
    return f"{d.day:02d}-{list(MONTHS)[d.month - 1]}-{d.year % 100:02d}"


def _rand_date(rng) -> dt.date:
    return dt.date(2024, 1, 1) + dt.timedelta(days=rng.randrange(0, 900))


def _rand_datetime(rng) -> dt.datetime:
    return dt.datetime(2024, 1, 1, tzinfo=UTC) + dt.timedelta(seconds=rng.randrange(0, 900 * 86400))


def _money(rng, lo: int = 0, hi: int = 50_000_00) -> Decimal:
    return Decimal(rng.randrange(lo, hi)).scaleb(-2)


def _rand_value(rng, fm: FieldMap, column: str, row_ix: int) -> Any:
    col = column.upper()
    if fm.bson == "string":
        if col.endswith("_DT") and len(col) <= 20 and col not in ("CREATED_DT", "UPDATED_DT") or col == "HIST_DT":
            return _ddmonyy(_rand_date(rng))
        if col.endswith("_YN"):
            return rng.choice(["Y", "N", "N", "N"])
        if col == "RELATED_ACCT_IDS":
            return ",".join(f"{rng.randrange(10000, 99999)}" for _ in range(rng.randrange(1, 4))) if rng.random() < 0.3 else None
        if col in ("CHILD_ACCT_IDS", "PROMO_CODES_CSV"):
            return ",".join(f"{rng.randrange(10000, 99999)}" for _ in range(rng.randrange(1, 3))) if rng.random() < 0.2 else None
        if col == "GL_ACCT_CSV":
            return ",".join(str(rng.randrange(1000, 9999)) for _ in range(rng.randrange(1, 4))) if rng.random() < 0.8 else None
        if col == "SERVICE_PERIOD":
            return f"{rng.randrange(1, 13):02d}2025-{rng.randrange(1, 13):02d}2025"
        if col == "ATTR_TYPE":
            return "STR"
        return f"{col.lower()}-{row_ix}"
    if fm.bson == "int":
        if col.endswith("_CD"):
            return rng.choice([10, 20, 30])
        return rng.randrange(0, 1000)
    if fm.bson == "long":
        return rng.randrange(0, 10_000_000)
    if fm.bson == "decimal":
        if col in ("QTY",):
            return Decimal(rng.randrange(1, 100_000)).scaleb(-3)
        if col in ("UNIT_PRICE", "OVERAGE_RATE"):
            return Decimal(rng.randrange(1, 1_000_000)).scaleb(-4)
        return _money(rng)
    if fm.bson == "date":
        return _rand_datetime(rng)
    return None


def build_faithful_copy(inputs: Inputs, seed: int = DEFAULT_SEED) -> dict[str, list[dict]]:
    """Synthesise OW_BILLING tables that satisfy demo.json: row counts, census-delta PKs and every anomaly set."""
    import random

    fx = inputs.fixture
    if fx is None:
        raise SystemExit("self-test needs migration/billing/fixtures/demo.json")
    rng = random.Random(seed)
    counts = {t: m["fixture_rows"] for t, m in fx["tables"].items()}
    delta = fx["census_delta"]["static_upgrade_rows"]
    anomalies = {a["kind"]: a for a in fx["anomalies"]}
    tables: dict[str, list[dict]] = {}

    def fill(row: dict, fms: list[FieldMap], ix: int) -> None:
        for fm in fms:
            if fm.derived or fm.column is None or fm.column in row:
                continue
            row[fm.column] = _rand_value(rng, fm, fm.column, ix)

    primaries = [c for c in inputs.collections if c.quarantine_of is None]
    # primary tables first so that children can point at real parents
    for cm in primaries:
        n = counts.get(cm.table, 0)
        pks = list(delta.get(cm.table, []))
        rows = []
        for i in range(n):
            row: dict[str, Any] = {}
            if cm.id_fields:
                row[cm.id_columns[0]] = f"TYPE_{i // 4}"
                row[cm.id_columns[1]] = (i % 4 + 1) * 10
            else:
                row[cm.id_columns[0]] = pks[i] if i < len(pks) else _uuid(rng)
            fill(row, cm.fields, i)
            rows.append(row)
        tables[cm.table] = rows

    # foreign keys between primary tables (names from the mapping: <table-singular>_ID)
    singular = {f"{t[:-1] if t.endswith('S') else t}_ID": t for t in tables}
    own_ids = {cm.table: set(cm.id_columns) for cm in primaries}
    for table, rows in tables.items():
        for row in rows:
            for col in list(row):
                if col in own_ids.get(table, set()):
                    continue
                if col in singular and singular[col] != table and tables[singular[col]]:
                    row[col] = rng.choice(tables[singular[col]])[next(iter(tables[singular[col]][0]))]

    # planted CUSTOMER_MASTER anomalies: dirty SIGNUP_DT and malformed RELATED_ACCT_IDS on the listed cust_ids
    customers = tables.get("CUSTOMER_MASTER", [])
    by_pk = {r["CUST_ID"]: r for r in customers}
    listed = []
    for kind in ("dirty_dates", "malformed_csv_lists"):
        for pk in anomalies.get(kind, {}).get("cust_ids", []):
            if pk not in listed:
                listed.append(pk)
    free = [r for r in customers if r["CUST_ID"] not in set(delta.get("CUSTOMER_MASTER", []))]
    for i, pk in enumerate(listed):
        free[i]["CUST_ID"] = pk
    by_pk = {r["CUST_ID"]: r for r in customers}
    for kind, column in (("dirty_dates", "SIGNUP_DT"), ("malformed_csv_lists", "RELATED_ACCT_IDS")):
        a = anomalies.get(kind)
        if not a:
            continue
        values = []
        for v, meta in a["values"].items():
            values.extend([v] * (meta["count"] if isinstance(meta, dict) else meta))
        rng.shuffle(values)
        for pk, v in zip(a["cust_ids"], values):
            by_pk[pk][column] = v

    # child tables
    for cm in primaries:
        parents = tables[cm.table]
        for e in cm.embedded:
            n = counts.get(e.table, 0)
            pks = list(delta.get(e.table, []))
            rows = []
            parent_ids = [p[cm.id_columns[0]] for p in parents]
            static_rows = anomalies.get("eav_boolean_spellings", {}).get("static_baseline_rows", []) if e.table == "ENTITY_ATTR_VALUE" else []
            if e.table == "ENTITY_ATTR_VALUE":
                admin = delta.get("CUSTOMER_MASTER", [parent_ids[0]])[0]
                seed_parents = [p for p in parent_ids if p != admin]
                cells = []
                for name, counts_by_value in anomalies["eav_boolean_spellings"]["attr_value_matrix"].items():
                    for value, k in counts_by_value.items():
                        cells.extend([(name, value)] * k)
                rng.shuffle(cells)
                for i, (name, value) in enumerate(cells):
                    row = {"EAV_ID": 1000 + i, "ENTITY_TYPE": "CUSTOMER", "ENTITY_ID": rng.choice(seed_parents),
                           "ATTR_NAME": name, "ATTR_VALUE": value}
                    fill(row, e.fields, i)
                    rows.append(row)
                for s in static_rows:
                    row = {"EAV_ID": int(s["eav_id"]), "ENTITY_TYPE": "CUSTOMER", "ENTITY_ID": admin,
                           "ATTR_NAME": s["attr_name"], "ATTR_VALUE": s["attr_value"]}
                    fill(row, e.fields, int(s["eav_id"]))
                    rows.append(row)
            else:
                orphan_ids = list(anomalies.get("orphaned_rows", {}).get("line_ids", [])) if e.table == "INVOICE_LINE" else []
                for i in range(n):
                    row = {}
                    ident = e.identity_column or "ID"
                    if i < len(pks):
                        row[ident] = pks[i]
                    elif i < len(pks) + len(orphan_ids):
                        row[ident] = orphan_ids[i - len(pks)]
                    else:
                        row[ident] = _uuid(rng)
                    if ident == "EAV_ID":
                        row[ident] = 1000 + i
                    if e.shape == "subdoc":
                        row[e.parent_fk] = parent_ids[i % len(parent_ids)] if parent_ids else _uuid(rng)
                    elif row[ident] in orphan_ids:
                        row[e.parent_fk] = _uuid(rng)
                        row["INVOICE_NO"] = f"{fx.get('namespace', 'demo').upper()}-GHOST-{i}"
                    else:
                        row[e.parent_fk] = rng.choice(parent_ids) if parent_ids else _uuid(rng)
                    for col, val in e.fixed_filter.items():
                        row[col] = val
                    fill(row, e.fields, i)
                    rows.append(row)
            tables[e.table] = rows
    return tables


def _to_bson(value: Any, bson: str) -> Any:
    from bson import Decimal128, Int64

    if value is None:
        return None
    if bson == "string":
        return str(value)
    if bson == "int":
        return int(value)
    if bson == "long":
        return Int64(int(value))
    if bson == "decimal":
        return Decimal128(value if isinstance(value, Decimal) else Decimal(str(value)))
    if bson == "date":
        return _as_datetime(value, "loader")
    return value


def _typed(value: str | None) -> Any:
    from bson import Decimal128

    if value is None:
        return None
    if value in TRUE_SPELLINGS:
        return True
    if value in FALSE_SPELLINGS:
        return False
    try:
        return Decimal128(Decimal(value))
    except (InvalidOperation, ValueError):
        return value


def _map_fields(row: dict, fields: list[FieldMap], now: dt.datetime) -> dict:
    doc: dict[str, Any] = {}
    for fm in fields:
        if fm.derived:
            verbatim = row.get(fm.column) if fm.column else None
            if fm.bson == "date":
                d = parse_ddmonyy(verbatim) if isinstance(verbatim, str) else None
                if d is not None:
                    doc[fm.field] = dt.datetime(d.year, d.month, d.day, tzinfo=UTC)
            elif fm.bson == "array<string>":
                pattern = CLEAN_CSV_RE if fm.column == "GL_ACCT_CSV" else CLEAN_ID_CSV_RE
                if isinstance(verbatim, str) and csv_is_clean(verbatim, pattern):
                    doc[fm.field] = verbatim.split(",")
            elif fm.bson == "object":
                doc[fm.field] = {"reason": "orphaned_rows", "rule": "INVOICE_ID not in invoice_feed._id", "capturedAt": now}
            else:
                t = _typed(verbatim)
                if t is not None:
                    doc[fm.field] = t
            continue
        if fm.column is None:
            continue
        v = _to_bson(row.get(fm.column), fm.bson)
        if v is not None:
            doc[fm.field] = v
    return doc


def map_source_row(cm: CollectionMap, row: dict, now: dt.datetime | None = None) -> dict:
    """Reference mapping of one primary-table row to its document (no embedded children)."""
    now = now or dt.datetime.now(UTC).replace(microsecond=0)
    if cm.id_fields:
        _id = {f: _to_bson(row.get(c), "int" if isinstance(row.get(c), (int, Decimal)) else "string") for f, c in zip(cm.id_fields, cm.id_columns)}
    else:
        v = row.get(cm.id_columns[0])
        _id = _to_bson(v, "long" if isinstance(v, (int, Decimal)) and not isinstance(v, bool) else "string")
    return {"_id": _id, **_map_fields(row, cm.fields, now)}


def load_documents(inputs: Inputs, tables: dict[str, list[dict]], now: dt.datetime | None = None) -> dict[str, list[dict]]:
    """Reference loader: apply mapping_spec.json to the synthetic tables (what the real loader must produce)."""
    now = now or dt.datetime.now(UTC).replace(microsecond=0)
    out: dict[str, list[dict]] = {}
    orphan_rows: dict[str, list[dict]] = {}
    for cm in inputs.collections:
        if cm.quarantine_of is not None:
            continue
        docs = {}
        for row in tables.get(cm.table, []):
            d = map_source_row(cm, row, now)
            docs[row_key(row, cm.id_columns)] = d
        for e in cm.embedded:
            groups: dict[tuple, list[dict]] = defaultdict(list)
            for r in tables.get(e.table, []):
                if any(r.get(c) != v for c, v in e.fixed_filter.items()):
                    continue
                pk = (canon_key(r.get(e.parent_fk)),)
                if pk in docs:
                    groups[pk].append(r)
                else:
                    orphan_rows.setdefault(e.quarantine_collection or "", []).append(r)
            for pk, rows in groups.items():
                elems = [_map_fields(r, e.fields, now) for r in rows]
                if e.shape == "subdoc":
                    docs[pk][e.path] = elems[0]
                else:
                    elems.sort(key=lambda el: tuple(canon_key(el.get(f)) for f in e.order_fields) if e.order_fields else ())
                    docs[pk][e.path] = elems
        out[cm.name] = list(docs.values())
    for cm in inputs.collections:
        if cm.quarantine_of is None:
            continue
        out[cm.name] = [{"_id": _to_bson(r.get(cm.id_columns[0]), "string"), **_map_fields(r, cm.fields, now)}
                        for r in orphan_rows.get(cm.name, [])]
    return out


# ---- planted defects -------------------------------------------------------------------------

@dataclass
class Defect:
    name: str
    collection: str
    doc_id: Any
    original: dict
    replacement: dict | None   # None = delete
    description: str


def plant_defects(docs: dict[str, list[dict]]) -> list[Defect]:
    """Three independent defects: a dropped row, a changed amount, a float-rounded amount."""
    from bson import Decimal128

    feed = sorted((d for d in docs["invoice_feed"] if d.get("lines")), key=lambda d: str(d["_id"]))
    customers = sorted((d for d in docs["customers"] if "curBalAmt" in d), key=lambda d: str(d["_id"]))
    dropped = feed[0]
    changed = dict(customers[0])
    changed["curBalAmt"] = Decimal128(changed["curBalAmt"].to_decimal() + Decimal("0.01"))
    rounded_src = feed[1]
    rounded = dict(rounded_src)
    rounded["lines"] = [dict(ln) for ln in rounded_src["lines"]]
    line = next(ln for ln in rounded["lines"] if "amount" in ln)
    line["amount"] = round(float(line["amount"].to_decimal()), 2)   # the amount went through a binary double
    return [
        Defect("dropped_row", "invoice_feed", dropped["_id"], dropped, None,
               "one invoice_feed document (header + lines) deleted from the target"),
        Defect("changed_amount", "customers", customers[0]["_id"], customers[0], changed,
               "customers.curBalAmt Decimal128 moved by 0.01"),
        Defect("float_rounded_amount", "invoice_feed", rounded_src["_id"], rounded_src, rounded,
               "invoice_feed.lines[].amount stored as a binary double rounded to 2 places instead of Decimal128"),
    ]


class MutableDictTarget(DictTarget):
    def apply(self, defect: Defect) -> None:
        coll = self.collections[defect.collection]
        idx = next(i for i, d in enumerate(coll) if d["_id"] == defect.doc_id)
        if defect.replacement is None:
            coll.pop(idx)
        else:
            coll[idx] = self._roundtrip(defect.replacement)

    def revert(self, defect: Defect) -> None:
        coll = self.collections[defect.collection]
        idx = next((i for i, d in enumerate(coll) if d["_id"] == defect.doc_id), None)
        if idx is None:
            coll.append(self._roundtrip(defect.original))
        else:
            coll[idx] = self._roundtrip(defect.original)

    @staticmethod
    def _roundtrip(doc: dict) -> dict:
        from bson import decode, encode
        from bson.codec_options import CodecOptions

        return decode(encode(doc), codec_options=CodecOptions(tz_aware=True))


class MutableMongoTarget(MongoTarget):
    def load(self, docs: dict[str, list[dict]]) -> None:
        self.client.drop_database(self.database)
        for name, items in docs.items():
            if items:
                self.db[name].insert_many(items, ordered=False)
            else:
                self.db.create_collection(name)

    def apply(self, defect: Defect) -> None:
        if defect.replacement is None:
            self.db[defect.collection].delete_one({"_id": defect.doc_id})
        else:
            self.db[defect.collection].replace_one({"_id": defect.doc_id}, defect.replacement)

    def revert(self, defect: Defect) -> None:
        self.db[defect.collection].replace_one({"_id": defect.doc_id}, defect.original, upsert=True)

    def drop(self) -> None:
        self.client.drop_database(self.database)


def run_selftest(inputs: Inputs, out_dir: Path, mongo_uri: str | None = None, seed: int = DEFAULT_SEED,
                 database: str = "ow_recon_selftest", log: Callable[[str], None] = print) -> dict:
    t0 = time.monotonic()
    tables = build_faithful_copy(inputs, seed)
    now = dt.datetime.now(UTC).replace(microsecond=0)
    docs = load_documents(inputs, tables, now)
    log(f"synthetic copy: {sum(len(v) for v in tables.values())} rows in {len(tables)} tables -> "
        f"{sum(len(v) for v in docs.values())} documents in {len(docs)} collections ({time.monotonic() - t0:.1f}s)")
    source = DictSource(tables, {"system": "oracle", "mode": "fixture", "schema": "OW_BILLING",
                                 "driver": "synthetic copy of migration/billing/fixtures/demo.json", "seed": seed})
    if mongo_uri:
        host = urlparse(mongo_uri if "://" in mongo_uri else f"mongodb://{mongo_uri}").hostname or ""
        if host not in LOCAL_HOSTS:
            raise SystemExit("self-test only loads into a loopback mongod; it never touches Atlas")
        target = MutableMongoTarget(mongo_uri, database, None)
        target.load(docs)
    else:
        target = MutableDictTarget(docs)
    namespace = inputs.fixture.get("namespace", "demo") if inputs.fixture else "demo"
    defects = plant_defects(docs)
    scenarios: list[tuple[str, Defect | None, str]] = [("faithful", None, "pass")] + [(d.name, d, "fail") for d in defects]
    results = []
    for name, defect, want in scenarios:
        if defect:
            target.apply(defect)
        run = ReconRun(inputs, source, target, "fixture", now=now)
        idem = execute(run)
        verdict = run.verdict()
        report = build_report(run, namespace, idem, {
            "selftest": {"scenario": name, "expected_verdict": want,
                         "planted_defect": ({"collection": defect.collection, "_id": _json_safe(defect.doc_id), "description": defect.description}
                                            if defect else None)}})
        path = write_report(report, out_dir / f"selftest-{name}.recon.json")
        schema_errors = validate_report(report)
        failed = [c.id for c in run.checks if c.result == "fail"]
        ok = verdict == want and not schema_errors
        results.append({"scenario": name, "expected": want, "verdict": verdict, "ok": ok, "report": str(path),
                        "failed_checks": failed, "schema_errors": schema_errors})
        log(f"[{'OK ' if ok else 'BAD'}] {name:<22} verdict={verdict:<4} expected={want:<4} failed_checks={failed[:6]} "
            f"schema_valid={not schema_errors} -> {path}")
        if defect:
            target.revert(defect)
    if isinstance(target, MutableMongoTarget):
        target.drop()
    summary = {"ok": all(r["ok"] for r in results), "scenarios": results, "seconds": round(time.monotonic() - t0, 1),
               "target": "mongod " + mongo_uri if mongo_uri else "in-memory (bson round-trip)"}
    write_report(summary, out_dir / "selftest-summary.json")
    log(f"self-test {'PASSED' if summary['ok'] else 'FAILED'} in {summary['seconds']}s; summary -> {out_dir / 'selftest-summary.json'}")
    return summary


# --------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------

def _require_env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise SystemExit(f"environment variable {name} is not set (secrets are referenced by name only)")
    return v


def cmd_run(args) -> int:
    inputs = build_inputs(Path(args.spec), Path(args.tolerances), Path(args.fixture) if args.fixture else None)
    tol = inputs.tolerances
    dsn_secret = tol.get("source", {}).get("dsn_secret", "OW_TP_ORACLE_RO_DSN")
    uri_secret = tol.get("target", {}).get("uri_secret", "MONGODB_ATLAS_URI")
    schema = tol.get("source", {}).get("schema", "OW_BILLING")
    database = args.mongo_db or inputs.spec.get("target", {}).get("database")
    concurrency = args.concurrency or int(tol.get("source", {}).get("concurrency", 1))
    if args.mode == "live":
        if args.oracle_dsn_env != dsn_secret or args.mongo_uri_env != uri_secret:
            raise SystemExit(f"--mode live requires the configured secrets {dsn_secret} and {uri_secret}")
    source = OracleSource(_require_env(args.oracle_dsn_env), args.oracle_dsn_env, schema, concurrency)
    target = MongoTarget(_require_env(args.mongo_uri_env), database, args.mongo_uri_env)
    local_src = source.dsn_host in LOCAL_HOSTS
    local_tgt = all(h in LOCAL_HOSTS for h in target.hosts)
    if args.mode == "live" and (local_src or local_tgt):
        raise SystemExit("--mode live refused: source or target resolves to loopback; use --mode local")
    if args.mode == "local" and not (local_src or local_tgt) and not args.allow_remote_local:
        raise SystemExit("--mode local against two remote hosts: pass --allow-remote-local if that is intended")
    run = ReconRun(inputs, source, target, "live" if args.mode == "live" else "fixture",
                   concurrency=concurrency, collections=args.collections.split(",") if args.collections else None)
    idem = execute(run)
    namespace = args.namespace or (inputs.fixture or {}).get("namespace", "demo")
    report = build_report(run, namespace, idem)
    path = write_report(report, Path(args.out))
    errors = validate_report(report)
    print(f"recon {run.run_mode}: verdict={run.verdict()} checks={len(run.checks)} failed={report['summary']['failed_check_ids'][:8]} -> {path}")
    if errors:
        print("report does not validate against recon-report.schema.json:\n  " + "\n  ".join(errors))
        return 2
    print(f"merge_evidence={report['merge_evidence']} ({report['merge_evidence_note']})")
    return 0 if run.verdict() == "pass" else 1


def cmd_selftest(args) -> int:
    inputs = build_inputs(Path(args.spec), Path(args.tolerances), Path(args.fixture))
    summary = run_selftest(inputs, Path(args.out), args.mongo_uri, args.seed)
    return 0 if summary["ok"] else 1


def cmd_validate(args) -> int:
    errors = validate_report(load_json(Path(args.report)))
    print("\n".join(errors) if errors else f"{args.report}: valid recon-report")
    return 1 if errors else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--spec", default=str(SPEC_PATH))
    p.add_argument("--tolerances", default=str(TOLERANCES_PATH))
    p.add_argument("--fixture", default=str(FIXTURE_PATH), help="fixture manifest (anomaly sets, census delta)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("selftest", help="faithful synthetic copy must pass; three planted defects must fail")
    s.add_argument("--out", default=str(HERE / "out" / "selftest"))
    s.add_argument("--mongo-uri", default=None, help="loopback mongod to load the copy into (default: in-memory)")
    s.add_argument("--seed", type=int, default=DEFAULT_SEED)
    s.set_defaults(func=cmd_selftest)
    r = sub.add_parser("run", help="recon a real source and target")
    r.add_argument("--mode", choices=["live", "local"], required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--oracle-dsn-env", default="OW_TP_ORACLE_RO_DSN", help="env var holding the Oracle DSN (name only)")
    r.add_argument("--mongo-uri-env", default="MONGODB_ATLAS_URI", help="env var holding the MongoDB URI (name only)")
    r.add_argument("--mongo-db", default=None)
    r.add_argument("--namespace", default=None)
    r.add_argument("--collections", default=None, help="comma-separated subset")
    r.add_argument("--concurrency", type=int, default=None, help="override tolerances.json#source.concurrency (1 = serial)")
    r.add_argument("--allow-remote-local", action="store_true")
    r.set_defaults(func=cmd_run)
    v = sub.add_parser("validate", help="validate a report against the repo schema")
    v.add_argument("report")
    v.set_defaults(func=cmd_validate)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
